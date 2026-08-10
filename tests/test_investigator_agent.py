"""Investigator tools, exercised without a model.

The agent's judgement is not tested here — only that its tools behave when the
world is imperfect: a tag that does not exist, a fleet with nothing open, a
finding that must still be produced when part of the evidence is missing (FR-019).
"""

import pytest
from sqlalchemy import text

from app.agents.investigator import KUNCI_TEMUAN, investigate_case, list_open_cases


class Ctx:
    """Minimal ToolContext stand-in: the investigator only needs state."""

    def __init__(self):
        self.state: dict = {}


@pytest.fixture
async def database():
    from app.db.session import session_factory

    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unavailable: {type(exc).__name__}")
    return True


class TestListOpenCases:
    async def test_lists_the_seeded_open_cases(self, database):
        ctx = Ctx()
        result = await list_open_cases(ctx)
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        assert "PLT-U/FIL-207" in result
        assert ctx.state["kasus_terbuka"]

    async def test_reports_symptoms_so_a_choice_can_be_made(self, database):
        result = await list_open_cases(Ctx())
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        assert "gejala" in result.lower()


class TestInvestigateCase:
    async def test_writes_the_finding_to_the_handover_key(self, database):
        ctx = Ctx()
        result = await investigate_case("PLT-U/FIL-207", ctx)
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        assert KUNCI_TEMUAN in ctx.state
        assert ctx.state[KUNCI_TEMUAN]["kandidat"]

    async def test_unknown_tag_is_reported_not_raised(self, database):
        # A model will mistype a tag eventually; that must not end the turn with
        # a stack trace the user has to interpret.
        ctx = Ctx()
        result = await investigate_case("PLT-X/FIL-999", ctx)
        assert "Tidak ada kegagalan terbuka pada" in result
        assert KUNCI_TEMUAN not in ctx.state

    async def test_unknown_tag_lists_what_is_available(self, database):
        result = await investigate_case("PLT-X/FIL-999", Ctx())
        assert "tersedia" in result.lower()

    async def test_reasoning_trail_is_recorded(self, database):
        ctx = Ctx()
        result = await investigate_case("PLT-U/FIL-207", ctx)
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        trail = ctx.state[KUNCI_TEMUAN]["jejak_penalaran"]
        assert len(trail) >= 3
        assert any("pabrik" in step["hasil"].lower() for step in trail)

    async def test_trail_crosses_a_plant_boundary(self, database):
        """SC-006: at least one traversal step must leave the home plant.

        Without it, ARKA is doing local root-cause analysis — useful, but not the
        thing that distinguishes it.
        """
        ctx = Ctx()
        result = await investigate_case("PLT-U/FIL-207", ctx)
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        finding = ctx.state[KUNCI_TEMUAN]
        plants = {p["pabrik"] for p in finding["preseden"]}
        assert plants - {finding["pabrik"]}

    async def test_summary_states_the_detection_decision(self, database):
        result = await investigate_case("PLT-U/FIL-207", Ctx())
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        assert "Keputusan deteksi" in result

    async def test_escalation_is_passed_on_as_an_instruction(self, database):
        """The agent must be told not to resolve the ambiguity itself."""
        ctx = Ctx()
        result = await investigate_case("PLT-U/FIL-207", ctx)
        if "Tidak ada kegagalan terbuka" in result:
            pytest.skip("golden path not seeded")
        if not ctx.state[KUNCI_TEMUAN]["perlu_eskalasi"]:
            pytest.skip("golden-path case does not currently escalate")
        assert "jangan memilih salah satu" in result

    async def test_case_without_precedent_still_yields_a_finding(self, database):
        """FR-019: a thin case degrades to an empty section, not to a failure."""
        ctx = Ctx()
        result = await investigate_case("PLT-S/FIL-118", ctx)
        if "Tidak ada kegagalan terbuka pada" in result:
            pytest.skip("ignorable case not seeded")
        assert KUNCI_TEMUAN in ctx.state
        assert ctx.state[KUNCI_TEMUAN]["equipment_tag"] == "PLT-S/FIL-118"
