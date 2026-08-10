"""Turn graph facts into a `Finding` — the handover the reporter already reads.

This is the seam of the whole system. Below it, everything is arithmetic over
recorded facts; above it, a language model decides how to present what was
found. The seam holds because `Finding` is immutable and every number inside it
was computed here, never restated by an agent.

Nothing in this module talks to a model, and nothing writes to the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.detection.criticality import dynamic_criticality
from app.detection.repository import (
    CandidateEvidence,
    DocumentRef,
    HistoricalCase,
    OpenCase,
    SparePartFacts,
)
from app.detection.scoring import (
    THRESHOLD_IGNORE,
    THRESHOLD_REPORT,
    Decision,
    ScoreBreakdown,
    Verdict,
    component_match,
    corroboration,
    decide,
    recency,
    symptom_overlap,
)
from app.reporting.finding import (
    Finding,
    KandidatPenyebab,
    LangkahPenalaran,
    MataRantai,
    Preseden,
    Rekomendasi,
    RincianSkor,
    Sitasi,
    SparepartKritis,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredCandidate:
    """One explanation, with the arithmetic that earned its rank."""

    evidence: CandidateEvidence
    score: ScoreBreakdown

    @property
    def total(self) -> Decimal:
        return self.score.total


def score_candidates(
    open_case: OpenCase,
    candidates: list[CandidateEvidence],
    subsystem_map: dict[str, str] | None = None,
    today: date | None = None,
) -> list[ScoredCandidate]:
    """Score every candidate against the open case, strongest first.

    Each component is computed against the candidate's **best** supporting case
    rather than an average. A single close match is what a reliability engineer
    actually reasons from; averaging would let two weak precedents drag down one
    strong one, which is the opposite of how evidence works.

    Ties break on cause id so that two runs over identical data produce an
    identical document — a reviewer comparing this week's memo with last week's
    must be able to trust that any difference is real.
    """
    reference = today or date.today()
    scored: list[ScoredCandidate] = []

    for candidate in candidates:
        if not candidate.historical_cases:
            continue

        best_overlap = max(
            symptom_overlap(open_case.symptom_codes, case.symptom_codes)
            for case in candidate.historical_cases
        )
        best_component = max(
            component_match(open_case.component_code, case.component_code, subsystem_map)
            for case in candidate.historical_cases
        )
        newest = max(case.occurred_on for case in candidate.historical_cases)
        scored.append(
            ScoredCandidate(
                evidence=candidate,
                score=ScoreBreakdown(
                    symptom_overlap=best_overlap,
                    component_match=best_component,
                    corroboration=corroboration(len(candidate.historical_cases)),
                    recency=recency((reference - newest).days),
                ),
            )
        )

    return sorted(
        scored, key=lambda s: (-s.total, s.evidence.cause_canonical_id)
    )


def _confidence(verdict: Verdict) -> str:
    """Translate a score into the word the document prints."""
    if verdict.top_score >= THRESHOLD_REPORT and verdict.decision is Decision.REPORT:
        return "tinggi"
    if verdict.top_score >= THRESHOLD_IGNORE:
        return "sedang"
    return "rendah"


def _citations(documents: tuple[DocumentRef, ...]) -> list[Sitasi]:
    return [
        Sitasi(
            canonical_id=doc.canonical_id,
            judul=doc.title,
            tipe_dokumen=doc.document_type,
            tanggal=doc.published_on,
            kutipan=doc.excerpt,
        )
        for doc in documents
    ]


def _precedents(cases: list[HistoricalCase], documents: tuple[DocumentRef, ...]) -> list[Preseden]:
    """Precedents, newest first, carrying the proven fix.

    The resolution text is the payload of the whole cross-plant story: it is the
    part somebody already paid for and nobody outside that plant ever saw.
    """
    citations = _citations(documents)
    return [
        Preseden(
            failure_event_id=case.failure_event_id,
            pabrik=case.plant,
            equipment_tag=case.equipment_tag,
            tanggal_kejadian=case.occurred_on,
            gejala=list(case.symptom_codes),
            penyelesaian=case.resolution,
            downtime_jam=(
                (Decimal(case.downtime_minutes) / Decimal(60)).quantize(Decimal("0.01"))
                if case.downtime_minutes
                else None
            ),
            sitasi=citations,
        )
        for case in sorted(cases, key=lambda c: c.occurred_on, reverse=True)
    ]


def _causal_chain(open_case: OpenCase, leader: ScoredCandidate | None) -> list[MataRantai]:
    """Symptom → Cause → Damage → Part, only as far as the facts reach.

    A link is omitted rather than invented when the data stops. A chain that
    always looks complete would teach a reader to stop checking it.
    """
    chain: list[MataRantai] = [
        MataRantai(peran="symptom", label=name) for name in open_case.symptom_names
    ]
    if leader is None:
        return chain

    chain.append(MataRantai(peran="cause", label=leader.evidence.cause_name))

    damaged = next(
        (c.component_code for c in leader.evidence.historical_cases if c.component_code),
        open_case.component_code,
    )
    if damaged:
        chain.append(MataRantai(peran="damage", label=f"Komponen terdampak: {damaged}"))
    return chain


def _spare_parts(
    open_case: OpenCase,
    leader: ScoredCandidate | None,
    parts: list[SparePartFacts],
    plants_involved: tuple[str, ...],
) -> list[SparepartKritis]:
    """Criticality for parts implicated by the leading candidate.

    Part selection matches on the component name because the schema carries no
    link between a spare part and the component it serves — see
    `repository.find_spare_parts`. When nothing matches, the block is left empty
    rather than filled with every part in the catalogue.
    """
    if leader is None or not open_case.component_code:
        return []

    needle = open_case.component_code.lower()
    matched = [p for p in parts if needle in p.name.lower()]
    if not matched:
        logger.info("no spare part matched component %s", open_case.component_code)
        return []

    cases = leader.evidence.historical_cases
    downtime = sum(c.downtime_minutes or 0 for c in cases)

    return [
        SparepartKritis(
            part_number=part.part_number,
            nama=part.name,
            criticality=dynamic_criticality(
                implicated_case_count=len(cases),
                total_downtime_minutes=downtime,
                lead_time_weeks=part.lead_time_weeks,
                vendor_count=part.vendor_count,
            ),
            static_criticality=Decimal(str(part.static_criticality or 0)),
            lead_time_minggu=part.lead_time_weeks,
            jumlah_vendor=part.vendor_count,
            pabrik_terdampak=list(plants_involved),
        )
        for part in matched
    ]


def _recommendations(
    leader: ScoredCandidate | None, verdict: Verdict, spare_parts: list[SparepartKritis]
) -> list[Rekomendasi]:
    """Actions ordered by how soon they must happen.

    Written in Indonesian because these lines are printed verbatim in the memo.
    """
    actions: list[Rekomendasi] = []
    if leader is None:
        return actions

    proven = next(
        (c.resolution for c in leader.evidence.historical_cases if c.resolution), None
    )
    if verdict.needs_human:
        actions.append(
            Rekomendasi(
                tindakan=(
                    "Putuskan antara dua kandidat teratas sebelum tindakan korektif "
                    "dijalankan, karena keduanya menuntut perbaikan berbeda."
                ),
                prioritas="segera",
                dasar=verdict.reason,
            )
        )
    if proven:
        actions.append(
            Rekomendasi(
                tindakan=proven,
                prioritas="segera" if not verdict.needs_human else "terjadwal",
                dasar="Tindakan ini sudah terbukti menyelesaikan kasus serupa di pabrik lain.",
            )
        )
    for part in spare_parts:
        if part.selisih > 0:
            actions.append(
                Rekomendasi(
                    tindakan=(
                        f"Tinjau ulang penggolongan kekritisan {part.nama} dan "
                        "pertimbangkan stok penyangga lintas pabrik."
                    ),
                    prioritas="terjadwal",
                    dasar="Kekritisan hasil perhitungan melampaui nilai di master data.",
                )
            )
    return actions


def build_finding(
    open_case: OpenCase,
    scored: list[ScoredCandidate],
    *,
    spare_parts: list[SparePartFacts] | None = None,
    trail: list[LangkahPenalaran] | None = None,
    today: date | None = None,
) -> tuple[Finding, Verdict]:
    """Assemble the handover object, and the verdict that justifies it."""
    verdict = decide([s.total for s in scored])
    leader = scored[0] if scored else None

    candidates = [
        KandidatPenyebab(
            cause_id=s.evidence.cause_canonical_id,
            nama=s.evidence.cause_name,
            skor=RincianSkor(
                symptom_overlap=s.score.weighted_parts["symptom_overlap"],
                component_match=s.score.weighted_parts["component_match"],
                corroboration=s.score.weighted_parts["corroboration"],
                recency=s.score.weighted_parts["recency"],
                total=s.total,
            ),
            sitasi=_citations(s.evidence.documents),
        )
        for s in scored
    ]

    precedents: list[Preseden] = []
    plants: set[str] = set()
    for s in scored:
        # Precedent means "somewhere else" — a case at the same plant is history,
        # not the cross-plant discovery ARKA claims to make.
        elsewhere = [c for c in s.evidence.historical_cases if c.plant != open_case.plant]
        precedents.extend(_precedents(elsewhere, s.evidence.documents))
        plants.update(c.plant for c in elsewhere)

    parts = _spare_parts(open_case, leader, spare_parts or [], tuple(sorted(plants)))

    finding = Finding(
        finding_id=f"ARKA-{open_case.canonical_id}",
        dibuat_pada=today or date.today(),
        equipment_tag=open_case.equipment_tag,
        pabrik=open_case.plant,
        model_equipment=open_case.equipment_model,
        gejala=list(open_case.symptom_names),
        keyakinan=_confidence(verdict),
        perlu_eskalasi=verdict.needs_human,
        alasan_eskalasi=verdict.reason if verdict.needs_human else None,
        kandidat=candidates,
        preseden=precedents,
        rantai_kausal=_causal_chain(open_case, leader),
        sparepart=parts,
        jejak_penalaran=trail or [],
        rekomendasi=_recommendations(leader, verdict, parts),
    )
    return finding, verdict
