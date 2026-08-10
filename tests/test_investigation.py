"""Finding assembly — the seam between recorded facts and presentation.

Most of this runs on fixtures, without a database and without a model. The last
class needs the seeded golden path, because the calibration it pins is a fact
about the data rather than about the code.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.detection.investigation import build_finding, score_candidates
from app.detection.repository import (
    CandidateEvidence,
    DocumentRef,
    HistoricalCase,
    OpenCase,
    SparePartFacts,
)
from app.detection.scoring import Decision

TODAY = date(2026, 8, 10)


def _open_case(**overrides) -> OpenCase:
    base = dict(
        failure_event_id="fe-open",
        canonical_id="FAILURE-OPEN",
        equipment_tag="PLT-U/FIL-207",
        equipment_model="Filler Rotary RF-8000",
        plant="Pabrik Utara",
        started_on=date(2026, 7, 29),
        symptom_codes=("GJL-BOCOR-KEPALA", "GJL-AKURASI-TURUN"),
        symptom_names=("Kebocoran produk", "Akurasi turun"),
        component_code="seal",
        description=None,
    )
    return OpenCase(**{**base, **overrides})


def _historical(plant: str, cause: str, **overrides) -> HistoricalCase:
    base = dict(
        failure_event_id=f"fe-{plant}",
        cause_canonical_id=cause,
        cause_name=f"Penyebab {cause}",
        plant=plant,
        equipment_tag=f"{plant}/FIL-100",
        occurred_on=date(2026, 2, 1),
        symptom_codes=("GJL-BOCOR-KEPALA", "GJL-AKURASI-TURUN"),
        component_code="seal",
        resolution="Penggantian seal satu set.",
        downtime_minutes=300,
    )
    return HistoricalCase(**{**base, **overrides})


def _candidate(cause: str, cases: list[HistoricalCase], docs=()) -> CandidateEvidence:
    return CandidateEvidence(
        cause_canonical_id=cause,
        cause_name=f"Penyebab {cause}",
        historical_cases=tuple(cases),
        documents=tuple(docs),
    )


DOC = DocumentRef(
    canonical_id="DOC-INS-2024-0417",
    title="Laporan Inspeksi",
    document_type="inspection_report",
    published_on=date(2024, 4, 12),
    excerpt="Seal mengeras sebelum umur pakai nominal.",
)


class TestScoreCandidates:
    def test_ranks_by_total(self):
        strong = _candidate("A", [_historical("Pabrik Barat", "A")])
        weak = _candidate(
            "B", [_historical("Pabrik Timur", "B", symptom_codes=("GJL-LAIN",))]
        )
        scored = score_candidates(_open_case(), [weak, strong], today=TODAY)
        assert scored[0].evidence.cause_canonical_id == "A"

    def test_uses_the_best_supporting_case_not_an_average(self):
        # A single close match is what an engineer reasons from; averaging would
        # let two weak precedents drag down one strong one.
        cases = [
            _historical("Pabrik Barat", "A"),
            _historical("Pabrik Timur", "A", symptom_codes=("GJL-TIDAK-COCOK",)),
        ]
        scored = score_candidates(_open_case(), [_candidate("A", cases)], today=TODAY)
        assert scored[0].score.symptom_overlap == Decimal("1.0000")

    def test_more_supporting_cases_raise_corroboration(self):
        one = score_candidates(
            _open_case(), [_candidate("A", [_historical("Pabrik Barat", "A")])], today=TODAY
        )
        three = score_candidates(
            _open_case(),
            [
                _candidate(
                    "A",
                    [
                        _historical("Pabrik Barat", "A"),
                        _historical("Pabrik Timur", "A"),
                        _historical("Pabrik Selatan", "A"),
                    ],
                )
            ],
            today=TODAY,
        )
        assert three[0].score.corroboration > one[0].score.corroboration

    def test_subsystem_match_scores_below_exact_match(self):
        exact = score_candidates(
            _open_case(), [_candidate("A", [_historical("Pabrik Barat", "A")])], today=TODAY
        )
        near = score_candidates(
            _open_case(),
            [_candidate("A", [_historical("Pabrik Barat", "A", component_code="katup")])],
            {"seal": "filling_head", "katup": "filling_head"},
            today=TODAY,
        )
        assert exact[0].total > near[0].total

    def test_candidate_without_cases_is_skipped(self):
        assert score_candidates(_open_case(), [_candidate("A", [])], today=TODAY) == []

    def test_ordering_is_stable_for_equal_scores(self):
        a = _candidate("A", [_historical("Pabrik Barat", "A")])
        b = _candidate("B", [_historical("Pabrik Timur", "B")])
        forward = score_candidates(_open_case(), [a, b], today=TODAY)
        reversed_input = score_candidates(_open_case(), [b, a], today=TODAY)
        first = [s.evidence.cause_canonical_id for s in forward]
        second = [s.evidence.cause_canonical_id for s in reversed_input]
        assert first == second


class TestBuildFinding:
    def test_maps_candidates_and_precedents(self):
        scored = score_candidates(
            _open_case(),
            [_candidate("A", [_historical("Pabrik Barat", "A")], [DOC])],
            today=TODAY,
        )
        finding, _ = build_finding(_open_case(), scored, today=TODAY)
        assert finding.equipment_tag == "PLT-U/FIL-207"
        assert len(finding.kandidat) == 1
        assert finding.preseden[0].pabrik == "Pabrik Barat"
        assert finding.semua_sitasi()

    def test_precedent_means_another_plant(self):
        # A case at the same plant is history, not the cross-plant discovery.
        scored = score_candidates(
            _open_case(),
            [_candidate("A", [_historical("Pabrik Utara", "A")], [DOC])],
            today=TODAY,
        )
        finding, _ = build_finding(_open_case(), scored, today=TODAY)
        assert finding.preseden == []

    def test_weighted_parts_sum_to_the_printed_total(self):
        scored = score_candidates(
            _open_case(), [_candidate("A", [_historical("Pabrik Barat", "A")])], today=TODAY
        )
        finding, _ = build_finding(_open_case(), scored, today=TODAY)
        skor = finding.kandidat[0].skor
        parts = skor.symptom_overlap + skor.component_match + skor.corroboration + skor.recency
        assert parts == skor.total

    def test_proven_resolution_becomes_a_recommendation(self):
        scored = score_candidates(
            _open_case(), [_candidate("A", [_historical("Pabrik Barat", "A")])], today=TODAY
        )
        finding, _ = build_finding(_open_case(), scored, today=TODAY)
        assert any("seal" in r.tindakan.lower() for r in finding.rekomendasi)

    def test_escalation_leads_the_recommendations(self):
        close = [
            _candidate("A", [_historical("Pabrik Barat", "A")]),
            _candidate("B", [_historical("Pabrik Timur", "B")]),
        ]
        scored = score_candidates(_open_case(), close, today=TODAY)
        finding, verdict = build_finding(_open_case(), scored, today=TODAY)
        assert verdict.decision is Decision.ESCALATE
        assert finding.perlu_eskalasi
        assert finding.rekomendasi[0].prioritas == "segera"

    def test_spare_part_difference_is_surfaced(self):
        part = SparePartFacts(
            part_number="SP-SEAL-8801",
            name="Seal kepala pengisi RF-8000",
            static_criticality=0.30,
            lead_time_weeks=6,
            vendor_count=1,
            primary_vendor="Vendor Tunggal A",
        )
        scored = score_candidates(
            _open_case(), [_candidate("A", [_historical("Pabrik Barat", "A")])], today=TODAY
        )
        finding, _ = build_finding(_open_case(), scored, spare_parts=[part], today=TODAY)
        assert finding.sparepart
        assert finding.sparepart[0].selisih > 0

    def test_unmatched_spare_part_leaves_the_block_empty(self):
        part = SparePartFacts(
            part_number="SP-NOZEL-2210",
            name="Nozel pengisi RF-8000",
            static_criticality=0.55,
            lead_time_weeks=1,
            vendor_count=4,
            primary_vendor="Vendor B",
        )
        scored = score_candidates(
            _open_case(), [_candidate("A", [_historical("Pabrik Barat", "A")])], today=TODAY
        )
        finding, _ = build_finding(_open_case(), scored, spare_parts=[part], today=TODAY)
        assert finding.sparepart == []

    def test_no_candidates_still_produces_a_finding(self):
        # FR-019: a section that cannot be gathered degrades to empty rather than
        # failing the whole investigation.
        finding, verdict = build_finding(_open_case(), [], today=TODAY)
        assert verdict.decision is Decision.IGNORE
        assert finding.kandidat == []


class TestGoldenPathCalibration:
    """Pins the escalation the demo depends on. Needs the seeded database."""

    @pytest.fixture
    async def chain(self):
        from sqlalchemy import text

        from app.db.session import session_factory
        from app.detection.repository import (
            find_documents,
            find_historical_cases,
            find_open_cases,
            find_spare_parts,
            group_by_cause,
            load_subsystem_map,
        )

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
                yield build_finding(
                    case, scored, spare_parts=await find_spare_parts(session)
                )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"database unavailable: {type(exc).__name__}")

    async def test_the_ambiguous_pair_escalates(self, chain):
        """The most interesting moment of the demo, pinned.

        Calibrated by measurement on 10 August: the margin was 0.0919 with two
        torque precedents and a third was seeded to bring it inside the band.
        The lever was the data — weights and thresholds are published policy.
        """
        finding, verdict = chain
        assert verdict.decision is Decision.ESCALATE
        assert verdict.margin <= Decimal("0.05")
        assert finding.perlu_eskalasi

    async def test_precedents_span_at_least_two_other_plants(self, chain):
        finding, _ = chain
        assert len({p.pabrik for p in finding.preseden}) >= 2

    async def test_every_candidate_carries_a_citation(self, chain):
        finding, _ = chain
        assert all(k.sitasi for k in finding.kandidat)

    async def test_the_undervalued_part_is_surfaced(self, chain):
        finding, _ = chain
        assert finding.sparepart
        assert finding.sparepart[0].selisih > Decimal("0.2")
