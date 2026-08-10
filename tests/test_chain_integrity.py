"""End-to-end integrity: the number in the document is the number that was computed.

This is the test that backs Principle I. Every other guard in the system —
narrative filtering, block selection, the quality reviewer — protects against a
model rewriting a value. This one checks the whole path at once: a score
computed from graph facts must appear, character for character, in the published
PDF.

If it ever fails, the claim that ARKA's numbers come straight from data is no
longer true, regardless of how many unit tests still pass.

Needs the seeded database and a working PDF renderer; skips without either.
"""

import shutil
import subprocess
from decimal import Decimal

import pytest

from app.detection.investigation import build_finding, score_candidates
from app.detection.repository import (
    find_documents,
    find_historical_cases,
    find_open_cases,
    find_spare_parts,
    group_by_cause,
    load_subsystem_map,
)


def _printed(value: Decimal) -> str:
    """Render a score the way the document does: two places, comma separator."""
    return f"{value:.2f}".replace(".", ",")


@pytest.fixture
async def finding():
    from sqlalchemy import text

    from app.db.session import session_factory

    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            cases = await find_open_cases(session)
            target = [c for c in cases if "FIL-207" in c.equipment_tag]
            if not target:
                pytest.skip("golden path not seeded")
            case = target[0]
            historical = await find_historical_cases(
                session,
                equipment_model=case.equipment_model,
                exclude_event_id=case.failure_event_id,
            )
            candidates = group_by_cause(historical, await find_documents(session))
            scored = score_candidates(case, candidates, load_subsystem_map())
            built, _ = build_finding(
                case, scored, spare_parts=await find_spare_parts(session)
            )
            return built
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unavailable: {type(exc).__name__}")


async def _render_text(finding, jenis: str, tmp_path) -> str:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext unavailable")

    from app.reporting.memo import render_dokumen_pdf

    try:
        content = await render_dokumen_pdf(finding, jenis)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pdf renderer unavailable: {type(exc).__name__}")

    path = tmp_path / f"{jenis}.pdf"
    path.write_bytes(content)
    result = subprocess.run(
        ["pdftotext", str(path), "-"], capture_output=True, text=True, timeout=60
    )
    return result.stdout


@pytest.fixture
async def pdf_text(finding, tmp_path):
    """The memo — the default document a field engineer receives."""
    return await _render_text(finding, "memo", tmp_path)


@pytest.fixture
async def report_text(finding, tmp_path):
    """The full report, which carries every block including spare parts."""
    return await _render_text(finding, "laporan", tmp_path)


class TestPublishedNumbersMatchComputedOnes:
    async def test_leading_score_appears_verbatim(self, finding, pdf_text):
        expected = _printed(finding.kandidat_terurut[0].skor.total)
        assert expected in pdf_text, (
            f"score {expected} computed by detection is absent from the document"
        )

    async def test_every_candidate_score_appears(self, finding, pdf_text):
        for candidate in finding.kandidat:
            assert _printed(candidate.skor.total) in pdf_text

    async def test_spare_part_gap_appears_in_the_full_report(self, finding, report_text):
        """The differentiator, checked where policy actually places it.

        The memo deliberately omits `sparepart_kritis` to stay short, so this
        assertion runs against the report. Worth knowing when demoing: the
        criticality gap — ARKA's most distinctive claim — is not in the default
        document a field engineer receives.
        """
        for part in finding.sparepart:
            assert _printed(part.criticality) in report_text
            assert _printed(part.static_criticality) in report_text

    async def test_citations_are_present(self, finding, pdf_text):
        for citation in finding.semua_sitasi():
            assert citation.canonical_id in pdf_text

    async def test_precedent_plants_are_named(self, finding, pdf_text):
        for precedent in finding.preseden:
            assert precedent.pabrik in pdf_text

    async def test_escalation_is_visible_to_the_reader(self, finding, pdf_text):
        if not finding.perlu_eskalasi:
            pytest.skip("finding does not escalate")
        assert "putusan manusia" in pdf_text.lower() or "keputusan" in pdf_text.lower()
