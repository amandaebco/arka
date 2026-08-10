"""Read-only access to the facts detection reasons over.

This layer answers exactly four questions and nothing else:

* which failures are still open,
* which resolved failures could explain them,
* which components belong to the same subsystem,
* which documents can be cited for a case.

Everything here is a read. Nothing in `app/detection/` ever writes to the graph
(Principle III) — findings travel as session state and become artifacts, and the
knowledge graph only changes when a human approves a curator proposal.

The queries run against **canonical tables** rather than the AGE projection. The
reasoning is recorded in `specs/001-arka-knowledge-agent/research.md`: every
relationship the golden path needs is one or two joins away, and a stale
projection fails by returning quietly wrong answers rather than an error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import Component, Equipment, Plant, ProductionLine
from app.models.knowledge import Document, DocumentChunk, DocumentVersion
from app.models.maintenance import WorkOrder
from app.models.reliability import (
    Cause,
    FailureEvent,
    FailureEventCause,
    FailureEventSymptom,
    Symptom,
    WorkOrderFailureEvent,
)

logger = logging.getLogger(__name__)

# A failure is worth investigating while it is unresolved.
OPEN_STATUSES = ("open", "under_investigation")

# A resolved case only teaches something if somebody confirmed why it happened.
# Closed cases without a verified cause are excluded deliberately: they would
# add corroboration weight to explanations nobody ever established.
RESOLVED_STATUS = "closed"

# Which subsystem each component type belongs to. Kept here rather than in the
# database because it is reliability judgement, not a recorded fact — a seal and
# a valve share the filling head, so a failure in one is weak evidence about the
# other. Moving this into a table would imply an authority it does not have.
SUBSYSTEM_BY_COMPONENT_TYPE: dict[str, str] = {
    "seal": "filling_head",
    "katup": "filling_head",
    "nozel": "filling_head",
    "brg": "drive",
}


@dataclass(frozen=True)
class DocumentRef:
    """A citable source. Quotation is optional; identity is not."""

    canonical_id: str
    title: str
    document_type: str
    published_on: date | None = None
    excerpt: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class OpenCase:
    """An unresolved failure — the thing an investigation is about."""

    failure_event_id: str
    canonical_id: str
    equipment_tag: str
    equipment_model: str | None
    plant: str
    started_on: date
    symptom_codes: tuple[str, ...]
    symptom_names: tuple[str, ...]
    component_code: str | None
    description: str | None


@dataclass(frozen=True)
class HistoricalCase:
    """A resolved failure with a verified cause, usable as precedent."""

    failure_event_id: str
    cause_canonical_id: str
    cause_name: str
    plant: str
    equipment_tag: str
    occurred_on: date
    symptom_codes: tuple[str, ...]
    component_code: str | None
    resolution: str | None
    downtime_minutes: int | None


@dataclass(frozen=True)
class CandidateEvidence:
    """Every resolved case that points at one explanation.

    Grouping happens by verified cause, not by equipment: the claim ARKA makes
    is "this explanation has happened before", and the strength of that claim
    comes from how many independent cases support it.
    """

    cause_canonical_id: str
    cause_name: str
    historical_cases: tuple[HistoricalCase, ...]
    documents: tuple[DocumentRef, ...] = field(default_factory=tuple)

    @property
    def plants(self) -> tuple[str, ...]:
        """Distinct plants involved, ordered for stable rendering."""
        return tuple(sorted({c.plant for c in self.historical_cases}))


def _plant_join(stmt):
    """Attach the equipment → line → plant chain shared by every query here."""
    return (
        stmt.join(Equipment, Equipment.id == FailureEvent.equipment_id)
        .join(ProductionLine, ProductionLine.id == Equipment.production_line_id)
        .join(Plant, Plant.id == ProductionLine.plant_id)
    )


async def _symptom_codes(session: AsyncSession, event_ids: list[str]) -> dict[str, list[str]]:
    """Symptom codes per failure event, in a single round trip."""
    if not event_ids:
        return {}
    rows = await session.execute(
        select(FailureEventSymptom.failure_event_id, Symptom.code, Symptom.name)
        .join(Symptom, Symptom.id == FailureEventSymptom.symptom_id)
        .where(FailureEventSymptom.failure_event_id.in_(event_ids))
        .order_by(Symptom.code)
    )
    grouped: dict[str, list[str]] = {}
    for event_id, code, _name in rows:
        grouped.setdefault(str(event_id), []).append(code)
    return grouped


async def _symptom_names(session: AsyncSession, event_ids: list[str]) -> dict[str, list[str]]:
    if not event_ids:
        return {}
    rows = await session.execute(
        select(FailureEventSymptom.failure_event_id, Symptom.name)
        .join(Symptom, Symptom.id == FailureEventSymptom.symptom_id)
        .where(FailureEventSymptom.failure_event_id.in_(event_ids))
        .order_by(Symptom.name)
    )
    grouped: dict[str, list[str]] = {}
    for event_id, name in rows:
        grouped.setdefault(str(event_id), []).append(name)
    return grouped


async def find_open_cases(session: AsyncSession) -> list[OpenCase]:
    """Every unresolved failure, oldest first.

    Oldest first because an open failure that has been waiting longest is the
    one most likely to have been forgotten — which is the situation ARKA exists
    to catch.
    """
    rows = await session.execute(
        _plant_join(
            select(
                FailureEvent.id,
                FailureEvent.canonical_id,
                FailureEvent.started_at,
                FailureEvent.description,
                Equipment.tag_number,
                Equipment.model,
                Plant.name,
                Component.component_type,
            )
        )
        .outerjoin(Component, Component.id == FailureEvent.component_id)
        .where(FailureEvent.status.in_(OPEN_STATUSES))
        .order_by(FailureEvent.started_at)
    )
    records = rows.all()
    ids = [str(r[0]) for r in records]
    codes = await _symptom_codes(session, ids)
    names = await _symptom_names(session, ids)

    return [
        OpenCase(
            failure_event_id=str(r[0]),
            canonical_id=r[1],
            started_on=r[2].date(),
            description=r[3],
            equipment_tag=r[4],
            equipment_model=r[5],
            plant=r[6],
            component_code=r[7],
            symptom_codes=tuple(codes.get(str(r[0]), ())),
            symptom_names=tuple(names.get(str(r[0]), ())),
        )
        for r in records
    ]


async def find_historical_cases(
    session: AsyncSession,
    *,
    equipment_model: str | None = None,
    exclude_event_id: str | None = None,
) -> list[HistoricalCase]:
    """Resolved failures with a verified cause.

    Args:
        session: Read-only session.
        equipment_model: Restrict to one fleet. Precedent from a different
            machine model is usually noise, and the golden path's whole premise
            is a uniform fleet across plants.
        exclude_event_id: The case under investigation, so it cannot corroborate
            itself.
    """
    stmt = _plant_join(
        select(
            FailureEvent.id,
            Cause.canonical_id,
            Cause.name,
            Plant.name,
            Equipment.tag_number,
            FailureEvent.started_at,
            FailureEvent.downtime_minutes,
            Component.component_type,
            WorkOrder.description,
        )
    )
    stmt = (
        stmt.join(FailureEventCause, FailureEventCause.failure_event_id == FailureEvent.id)
        .join(Cause, Cause.id == FailureEventCause.cause_id)
        .outerjoin(Component, Component.id == FailureEvent.component_id)
        .outerjoin(
            WorkOrderFailureEvent,
            WorkOrderFailureEvent.failure_event_id == FailureEvent.id,
        )
        .outerjoin(WorkOrder, WorkOrder.id == WorkOrderFailureEvent.work_order_id)
        .where(FailureEvent.status == RESOLVED_STATUS)
    )
    if equipment_model:
        stmt = stmt.where(Equipment.model == equipment_model)
    if exclude_event_id:
        stmt = stmt.where(FailureEvent.id != exclude_event_id)

    rows = (await session.execute(stmt.order_by(FailureEvent.started_at.desc()))).all()
    ids = [str(r[0]) for r in rows]
    codes = await _symptom_codes(session, ids)

    return [
        HistoricalCase(
            failure_event_id=str(r[0]),
            cause_canonical_id=r[1],
            cause_name=r[2],
            plant=r[3],
            equipment_tag=r[4],
            occurred_on=r[5].date(),
            downtime_minutes=r[6],
            component_code=r[7],
            resolution=r[8],
            symptom_codes=tuple(codes.get(str(r[0]), ())),
        )
        for r in rows
    ]


def load_subsystem_map() -> dict[str, str]:
    """Component type → subsystem, for partial credit in `component_match`.

    A function rather than a bare constant so the source can move into the
    database later without changing a single caller.
    """
    return dict(SUBSYSTEM_BY_COMPONENT_TYPE)


async def find_documents(
    session: AsyncSession, *, plant_names: tuple[str, ...] = ()
) -> list[DocumentRef]:
    """Citable documents, optionally narrowed to plants involved in a case.

    Citation is the backbone of Principle II, so a failure to attach documents
    degrades the finding rather than the run: a candidate with no document is
    still reported, it simply carries no reference.
    """
    stmt = (
        select(
            Document.canonical_id,
            Document.title,
            Document.document_type,
            Document.source_created_at,
            DocumentChunk.content,
            DocumentChunk.page_number,
        )
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .outerjoin(DocumentChunk, DocumentChunk.document_version_id == DocumentVersion.id)
        .order_by(Document.canonical_id)
    )
    rows = (await session.execute(stmt)).all()

    seen: dict[str, DocumentRef] = {}
    for canonical_id, title, doc_type, created_at, content, page in rows:
        if canonical_id in seen:
            continue
        excerpt = None
        if content:
            excerpt = content.strip()
            if len(excerpt) > 300:
                excerpt = excerpt[:297].rstrip() + "…"
        seen[canonical_id] = DocumentRef(
            canonical_id=canonical_id,
            title=title,
            document_type=doc_type,
            published_on=created_at.date() if created_at else None,
            excerpt=excerpt,
            page_number=page,
        )

    if plant_names:
        # Plant association is not modelled on documents; the narrowing is left
        # to the caller rather than faked here.
        logger.debug("plant narrowing requested but not modelled: %s", plant_names)
    return list(seen.values())


def group_by_cause(
    cases: list[HistoricalCase], documents: list[DocumentRef] | None = None
) -> list[CandidateEvidence]:
    """Collapse historical cases into one candidate per verified cause.

    Ordered by cause id so that two runs over the same data produce the same
    document. Determinism here is not tidiness — it is what allows a reviewer to
    compare today's memo against last week's and trust the difference is real.
    """
    grouped: dict[str, list[HistoricalCase]] = {}
    names: dict[str, str] = {}
    for case in cases:
        grouped.setdefault(case.cause_canonical_id, []).append(case)
        names[case.cause_canonical_id] = case.cause_name

    refs = tuple(documents or ())
    return [
        CandidateEvidence(
            cause_canonical_id=cause_id,
            cause_name=names[cause_id],
            historical_cases=tuple(
                sorted(items, key=lambda c: (c.occurred_on, c.failure_event_id), reverse=True)
            ),
            documents=refs,
        )
        for cause_id, items in sorted(grouped.items())
    ]


@dataclass(frozen=True)
class SparePartFacts:
    """A spare part with the supply-chain attributes criticality is built from."""

    part_number: str
    name: str
    component_type: str | None
    static_criticality: float | None
    lead_time_weeks: int | None
    vendor_count: int | None
    primary_vendor: str | None
    plants_served: tuple[str, ...] = ()


async def find_spare_parts(
    session: AsyncSession, *, component_type: str | None = None
) -> list[SparePartFacts]:
    """Master data for spare parts, with the fleet reach of each one.

    `plants_served` is traversed, not assumed: part → component type →
    components → equipment → plant. That path is what turns a lead time into a
    business fact. A six-week wait on a part fitted in one plant is an
    inconvenience; the same wait on a part fitted in five is a fleet-wide
    exposure, and static criticality records neither.
    """
    from app.models.maintenance import SparePart

    stmt = select(
        SparePart.part_number,
        SparePart.name,
        SparePart.component_type,
        SparePart.static_criticality,
        SparePart.lead_time_weeks,
        SparePart.vendor_count,
        SparePart.primary_vendor,
    ).order_by(SparePart.part_number)
    if component_type:
        stmt = stmt.where(SparePart.component_type == component_type)
    rows = (await session.execute(stmt)).all()

    reach = await _plants_by_component_type(session)
    return [
        SparePartFacts(
            part_number=r[0],
            name=r[1],
            component_type=r[2],
            static_criticality=float(r[3]) if r[3] is not None else None,
            lead_time_weeks=r[4],
            vendor_count=r[5],
            primary_vendor=r[6],
            plants_served=tuple(reach.get(r[2] or "", ())),
        )
        for r in rows
    ]


async def _plants_by_component_type(session: AsyncSession) -> dict[str, list[str]]:
    """Which plants have equipment fitted with each component type."""
    rows = (
        await session.execute(
            select(Component.component_type, Plant.name)
            .join(Equipment, Equipment.id == Component.equipment_id)
            .join(ProductionLine, ProductionLine.id == Equipment.production_line_id)
            .join(Plant, Plant.id == ProductionLine.plant_id)
            .distinct()
            .order_by(Component.component_type, Plant.name)
        )
    ).all()
    reach: dict[str, list[str]] = {}
    for component_type, plant in rows:
        reach.setdefault(component_type, []).append(plant)
    return reach
