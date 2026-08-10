"""Scout tools — the admission decision, tested without a model.

The behaviours pinned here are the ones that make the filter trustworthy: that
an empty fleet is a success, that skipped cases are always counted, and that a
case scoring below the ignore threshold really is left out.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.agents.scout import KUNCI_KASUS, explain_skip, scan_fleet
from app.detection.investigation import rank_screened, screen_case
from app.detection.repository import CandidateEvidence, HistoricalCase, OpenCase
from app.detection.scoring import Decision

TODAY = date(2026, 8, 10)


class Ctx:
    """Minimal stand-in for ToolContext: scout only needs state."""

    def __init__(self):
        self.state: dict = {}


def _open_case(tag: str, plant: str, symptoms=("GJL-BOCOR-KEPALA",), started=None) -> OpenCase:
    return OpenCase(
        failure_event_id=f"fe-{tag}",
        canonical_id=f"FAILURE-{tag}",
        equipment_tag=tag,
        equipment_model="Filler Rotary RF-8000",
        plant=plant,
        started_on=started or date(2026, 7, 1),
        symptom_codes=tuple(symptoms),
        symptom_names=tuple(symptoms),
        component_code="seal",
        description=None,
    )


def _candidate(cause: str, symptoms=("GJL-BOCOR-KEPALA",), plants=("Pabrik Barat",)):
    return CandidateEvidence(
        cause_canonical_id=cause,
        cause_name=f"Penyebab {cause}",
        historical_cases=tuple(
            HistoricalCase(
                failure_event_id=f"fe-{plant}",
                cause_canonical_id=cause,
                cause_name=f"Penyebab {cause}",
                plant=plant,
                equipment_tag=f"{plant}/FIL-100",
                occurred_on=date(2026, 5, 1),
                symptom_codes=tuple(symptoms),
                component_code="seal",
                resolution="Penggantian seal.",
                downtime_minutes=200,
            )
            for plant in plants
        ),
    )


class TestScreening:
    def test_strong_case_is_worth_investigating(self):
        screened = screen_case(_open_case("A", "Pabrik Utara"), [_candidate("X")], today=TODAY)
        assert screened.worth_investigating

    def test_unrelated_case_is_set_aside(self):
        # Different symptoms entirely: the evidence simply is not there.
        screened = screen_case(
            _open_case("B", "Pabrik Selatan", symptoms=("GJL-SUARA-KASAR",)),
            [_candidate("X")],
            today=TODAY,
        )
        assert screened.verdict.decision is Decision.IGNORE
        assert not screened.worth_investigating

    def test_case_with_no_history_is_set_aside(self):
        screened = screen_case(_open_case("C", "Pabrik Timur"), [], today=TODAY)
        assert not screened.worth_investigating

    def test_ranking_puts_strongest_first(self):
        strong = screen_case(_open_case("A", "Pabrik Utara"), [_candidate("X")], today=TODAY)
        weak = screen_case(
            _open_case("B", "Pabrik Selatan", symptoms=("GJL-LAIN",)),
            [_candidate("X")],
            today=TODAY,
        )
        ranked = rank_screened([weak, strong])
        assert ranked[0].open_case.equipment_tag == "A"

    def test_older_case_wins_a_tie(self):
        """A stale open failure is the one more likely to have been forgotten."""
        older = screen_case(
            _open_case("OLD", "Pabrik Utara", started=date(2026, 1, 1)),
            [_candidate("X")],
            today=TODAY,
        )
        newer = screen_case(
            _open_case("NEW", "Pabrik Barat", started=date(2026, 7, 20)),
            [_candidate("X")],
            today=TODAY,
        )
        assert rank_screened([newer, older])[0].open_case.equipment_tag == "OLD"


class TestExplainSkip:
    async def test_reports_the_recorded_reason(self):
        ctx = Ctx()
        ctx.state["kasus_diabaikan"] = [
            {"equipment_tag": "PLT-S/FIL-118", "top_score": "0.28", "reason": "Bukti lemah."}
        ]
        assert "Bukti lemah" in await explain_skip("PLT-S/FIL-118", ctx)

    async def test_says_so_when_the_case_was_shortlisted(self):
        ctx = Ctx()
        ctx.state[KUNCI_KASUS] = [{"equipment_tag": "PLT-U/FIL-207"}]
        assert "layak diselidiki" in await explain_skip("PLT-U/FIL-207", ctx)

    async def test_unknown_case_asks_for_a_scan(self):
        assert "Jalankan pemindaian" in await explain_skip("PLT-X/FIL-999", Ctx())


class TestScanFleet:
    """Needs the seeded database; skips when one is absent."""

    @pytest.fixture
    async def scanned(self):
        from sqlalchemy import text

        from app.db.session import session_factory

        try:
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"database unavailable: {type(exc).__name__}")

        ctx = Ctx()
        summary = await scan_fleet(ctx)
        return ctx, summary

    async def test_shortlists_the_golden_path_case(self, scanned):
        ctx, _ = scanned
        tags = {c["equipment_tag"] for c in ctx.state[KUNCI_KASUS]}
        if not tags:
            pytest.skip("golden path not seeded")
        assert "PLT-U/FIL-207" in tags

    async def test_the_escalating_case_leads(self, scanned):
        ctx, _ = scanned
        shortlist = ctx.state[KUNCI_KASUS]
        if not shortlist:
            pytest.skip("golden path not seeded")
        assert shortlist[0]["decision"] == "escalate"

    async def test_something_is_actually_ignored(self, scanned):
        """The filter must be falsifiable.

        A scout that admits everything proves nothing about its judgement, so
        the seeded data carries a case that should not clear the bar.
        """
        ctx, summary = scanned
        skipped = ctx.state.get("kasus_diabaikan") or []
        if not ctx.state.get(KUNCI_KASUS):
            pytest.skip("golden path not seeded")
        assert skipped, "no case was ignored — the filter cannot be questioned"
        assert Decimal(skipped[0]["top_score"]) < Decimal("0.50")

    async def test_summary_reports_the_skipped_count(self, scanned):
        _, summary = scanned
        assert "diabaikan" in summary or "Tidak ada kegagalan terbuka" in summary
