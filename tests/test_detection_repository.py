"""Query layer, verified against the seeded golden path.

These tests need a database. They skip rather than fail when one is absent, so
the deterministic suite stays runnable anywhere — but when a database is present
they are the ones that catch the failure mode that matters most: seeded data
that quietly stops discriminating between candidates.

Seed with:
    docker compose up -d
    uv run alembic upgrade head
    uv run python -m app.synthetic.generator --reset
"""

import pytest

from app.detection.repository import (
    SUBSYSTEM_BY_COMPONENT_TYPE,
    find_documents,
    find_historical_cases,
    find_open_cases,
    group_by_cause,
    load_subsystem_map,
)
from app.detection.scoring import symptom_overlap

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    from sqlalchemy import text

    from app.db.session import session_factory

    try:
        async with session_factory() as s:
            await s.execute(text("SELECT 1"))
            yield s
    except Exception as exc:  # noqa: BLE001 — absence of a database is not a failure
        pytest.skip(f"database unavailable: {type(exc).__name__}")


@pytest.fixture
async def open_case(session):
    cases = await find_open_cases(session)
    if not cases:
        pytest.skip("golden path not seeded")
    target = [c for c in cases if "FIL-207" in c.equipment_tag]
    if not target:
        pytest.skip("golden-path open case missing")
    return target[0]


class TestOpenCases:
    async def test_finds_the_live_case(self, open_case):
        assert open_case.plant == "Pabrik Utara"
        assert open_case.component_code == "seal"

    async def test_carries_symptoms_for_scoring(self, open_case):
        # Without symptoms every score collapses to zero and detection is blind.
        assert len(open_case.symptom_codes) >= 2

    async def test_resolved_cases_are_not_open(self, session):
        cases = await find_open_cases(session)
        tags = {c.equipment_tag for c in cases}
        assert "PLT-B/FIL-204" not in tags


class TestHistoricalCases:
    async def test_restricted_to_the_same_fleet(self, session, open_case):
        cases = await find_historical_cases(
            session, equipment_model=open_case.equipment_model
        )
        assert cases
        assert all(c.plant for c in cases)

    async def test_case_cannot_corroborate_itself(self, session, open_case):
        cases = await find_historical_cases(
            session,
            equipment_model=open_case.equipment_model,
            exclude_event_id=open_case.failure_event_id,
        )
        assert open_case.failure_event_id not in {c.failure_event_id for c in cases}

    async def test_every_precedent_carries_a_verified_cause(self, session, open_case):
        cases = await find_historical_cases(session, equipment_model=open_case.equipment_model)
        assert all(c.cause_canonical_id for c in cases)

    async def test_resolution_text_is_available(self, session, open_case):
        # The proven fix is the payload of the whole cross-plant story.
        cases = await find_historical_cases(session, equipment_model=open_case.equipment_model)
        assert any(c.resolution for c in cases)


class TestCandidateGrouping:
    async def test_groups_into_competing_explanations(self, session, open_case):
        cases = await find_historical_cases(
            session,
            equipment_model=open_case.equipment_model,
            exclude_event_id=open_case.failure_event_id,
        )
        candidates = group_by_cause(cases)
        assert len(candidates) >= 2

    async def test_precedents_span_other_plants(self, session, open_case):
        cases = await find_historical_cases(
            session,
            equipment_model=open_case.equipment_model,
            exclude_event_id=open_case.failure_event_id,
        )
        for candidate in group_by_cause(cases):
            assert open_case.plant not in candidate.plants or len(candidate.plants) > 1

    async def test_ordering_is_stable(self, session, open_case):
        cases = await find_historical_cases(session, equipment_model=open_case.equipment_model)
        first = [c.cause_canonical_id for c in group_by_cause(cases)]
        second = [c.cause_canonical_id for c in group_by_cause(cases)]
        assert first == second

    async def test_seeded_data_still_discriminates(self, session, open_case):
        """The regression that matters most.

        On 6 August every candidate scored an identical symptom overlap of 1.00,
        which made the detection score decorative. If this assertion fails, the
        demo's central claim is hollow even though every other test passes.
        """
        cases = await find_historical_cases(
            session,
            equipment_model=open_case.equipment_model,
            exclude_event_id=open_case.failure_event_id,
        )
        overlaps = {
            symptom_overlap(open_case.symptom_codes, c.symptom_codes) for c in cases
        }
        assert len(overlaps) > 1, "symptom overlap no longer separates candidates"


class TestDocuments:
    async def test_citable_documents_exist(self, session):
        docs = await find_documents(session)
        assert docs
        assert all(d.canonical_id and d.title for d in docs)

    async def test_documents_are_deduplicated(self, session):
        docs = await find_documents(session)
        ids = [d.canonical_id for d in docs]
        assert len(ids) == len(set(ids))


class TestSubsystemMap:
    def test_filling_head_components_share_a_subsystem(self):
        peta = load_subsystem_map()
        assert peta["seal"] == peta["katup"] == "filling_head"

    def test_drive_is_separate(self):
        peta = load_subsystem_map()
        assert peta["brg"] != peta["seal"]

    def test_returns_a_copy(self):
        peta = load_subsystem_map()
        peta["seal"] = "tampered"
        assert SUBSYSTEM_BY_COMPONENT_TYPE["seal"] == "filling_head"
