"""The same facts, read from BigQuery instead of PostgreSQL.

Every function here mirrors one in `app.detection.repository` and returns the
identical dataclass. That is the whole point: the layers above — scoring,
finding assembly, the agents, the renderers — work on those dataclasses and
never learn which store answered.

These queries read the **canonical mirror** (`app.bigquery.sync`), which carries
the same tables and columns as PostgreSQL. The earlier version read a flattened
nine-table copy, and paid for it: `symptom_names` could only be filled with
codes, so a document published from this path printed `GJL-BOCOR-KEPALA` where
the PostgreSQL path printed a sentence. Mirroring the schema rather than a
projection removes that whole class of difference instead of patching this one.

These four questions are joins, and are written as joins. Traversal that is
genuinely a traversal — four and five hops out to a shared spare part and back
down into another plant — lives in `app.bigquery.traversal`, which walks an edge
list with a recursive CTE because `GRAPH_EXPAND` rejects convergent graphs and
full GQL demands an Enterprise reservation.

BigQuery's client is synchronous, so each query is handed to a worker thread.
The callers are async and must not be blocked while a query runs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

from google.cloud import bigquery

from app.bigquery import config
from app.detection.repository import (
    OPEN_STATUSES,
    RESOLVED_STATUS,
    SUBSYSTEM_BY_COMPONENT_TYPE,
    CandidateEvidence,
    DocumentRef,
    HistoricalCase,
    OpenCase,
    SparePartFacts,
)

logger = logging.getLogger(__name__)

# Longest excerpt carried on a citation, matched to the PostgreSQL backend so
# the two produce byte-identical documents.
EXCERPT_CHARS = 300


def _client() -> bigquery.Client:
    return bigquery.Client(project=config.project())


async def _rows(sql: str, params: list | None = None) -> list:
    """Run a query off the event loop and return its rows."""

    def jalankan():
        job_config = bigquery.QueryJobConfig(query_parameters=params or [])
        return list(_client().query(sql, job_config=job_config).result())

    return await asyncio.to_thread(jalankan)


def _as_date(value) -> date | None:
    """A BigQuery timestamp or date, as a plain date.

    The PostgreSQL backend calls `.date()` on a timestamp; both paths must land
    on the same value or every rendered date differs by a timezone.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _excerpt(content: str | None) -> str | None:
    if not content:
        return None
    teks = content.strip()
    if len(teks) > EXCERPT_CHARS:
        teks = teks[: EXCERPT_CHARS - 3].rstrip() + "…"
    return teks or None


# The equipment → line → plant chain every case query needs.
_PLANT_JOIN = f"""
    JOIN {config.table_ref("equipment")} e ON e.id = f.equipment_id
    JOIN {config.table_ref("production_lines")} l ON l.id = e.production_line_id
    JOIN {config.table_ref("plants")} p ON p.id = l.plant_id
    LEFT JOIN {config.table_ref("components")} c ON c.id = f.component_id
    LEFT JOIN {config.table_ref("failure_event_symptoms")} fs ON fs.failure_event_id = f.id
    LEFT JOIN {config.table_ref("symptoms")} s ON s.id = fs.symptom_id
"""


async def find_open_cases(_session=None) -> list[OpenCase]:
    """Every unresolved failure, oldest first.

    The session argument exists only so the two backends are drop-in
    interchangeable; BigQuery has no session to pass.
    """
    sql = f"""
    SELECT f.id, f.canonical_id, f.started_at, f.description,
           e.tag_number, e.model, p.name AS plant, c.component_type,
           ARRAY_AGG(DISTINCT s.code IGNORE NULLS ORDER BY s.code) AS symptom_codes,
           ARRAY_AGG(DISTINCT s.name IGNORE NULLS ORDER BY s.name) AS symptom_names
    FROM {config.table_ref("failure_events")} f
    {_PLANT_JOIN}
    WHERE f.status IN UNNEST(@statuses)
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
    ORDER BY f.started_at
    """
    rows = await _rows(
        sql, [bigquery.ArrayQueryParameter("statuses", "STRING", list(OPEN_STATUSES))]
    )
    return [
        OpenCase(
            failure_event_id=str(r.id),
            canonical_id=r.canonical_id,
            equipment_tag=r.tag_number,
            equipment_model=r.model,
            plant=r.plant,
            started_on=_as_date(r.started_at),
            symptom_codes=tuple(r.symptom_codes or ()),
            symptom_names=tuple(r.symptom_names or ()),
            component_code=r.component_type,
            description=r.description,
        )
        for r in rows
    ]


async def find_historical_cases(
    _session=None, *, equipment_model: str | None = None, exclude_event_id: str | None = None
) -> list[HistoricalCase]:
    """Resolved failures carrying a verified cause.

    One row per (event, cause). A failure answered by more than one work order
    collapses to a single case here rather than repeating: `corroboration` counts
    cases, and letting a second work order add weight would score the paperwork
    instead of the evidence.
    """
    sql = f"""
    SELECT f.id, cs.canonical_id AS cause_id, cs.name AS cause_name,
           p.name AS plant, e.tag_number, f.started_at,
           ANY_VALUE(f.downtime_minutes) AS downtime_minutes,
           ANY_VALUE(c.component_type) AS component_type,
           ANY_VALUE(w.description) AS resolution,
           ARRAY_AGG(DISTINCT s.code IGNORE NULLS ORDER BY s.code) AS symptom_codes
    FROM {config.table_ref("failure_events")} f
    {_PLANT_JOIN}
    JOIN {config.table_ref("failure_event_causes")} fc ON fc.failure_event_id = f.id
    JOIN {config.table_ref("causes")} cs ON cs.id = fc.cause_id
    LEFT JOIN {config.table_ref("work_order_failure_events")} wf ON wf.failure_event_id = f.id
    LEFT JOIN {config.table_ref("work_orders")} w ON w.id = wf.work_order_id
    WHERE f.status = @resolved
      AND (@model IS NULL OR e.model = @model)
      AND (@exclude IS NULL OR f.id != @exclude)
    GROUP BY 1, 2, 3, 4, 5, 6
    ORDER BY f.started_at DESC
    """
    rows = await _rows(
        sql,
        [
            bigquery.ScalarQueryParameter("resolved", "STRING", RESOLVED_STATUS),
            bigquery.ScalarQueryParameter("model", "STRING", equipment_model),
            bigquery.ScalarQueryParameter("exclude", "STRING", exclude_event_id),
        ],
    )
    return [
        HistoricalCase(
            failure_event_id=str(r.id),
            cause_canonical_id=r.cause_id,
            cause_name=r.cause_name,
            plant=r.plant,
            equipment_tag=r.tag_number,
            occurred_on=_as_date(r.started_at),
            symptom_codes=tuple(r.symptom_codes or ()),
            component_code=r.component_type,
            resolution=r.resolution,
            downtime_minutes=r.downtime_minutes,
        )
        for r in rows
    ]


async def find_documents(_session=None, *, plant_names: tuple[str, ...] = ()) -> list[DocumentRef]:
    """Citable documents, one entry per canonical id.

    The excerpt comes from the first chunk of the first version, matching the
    PostgreSQL backend's "first row wins" deduplication.
    """
    sql = f"""
    SELECT d.canonical_id, d.title, d.document_type, d.source_created_at,
           ch.content, ch.page_number,
           ROW_NUMBER() OVER (
             PARTITION BY d.canonical_id
             ORDER BY v.id, ch.page_number, ch.id
           ) AS urutan
    FROM {config.table_ref("documents")} d
    JOIN {config.table_ref("document_versions")} v ON v.document_id = d.id
    LEFT JOIN {config.table_ref("document_chunks")} ch ON ch.document_version_id = v.id
    QUALIFY urutan = 1
    ORDER BY d.canonical_id
    """
    rows = await _rows(sql)
    if plant_names:
        # Plant association is not modelled on documents; the narrowing is left
        # to the caller rather than faked here.
        logger.debug("plant narrowing requested but not modelled: %s", plant_names)
    return [
        DocumentRef(
            canonical_id=r.canonical_id,
            title=r.title,
            document_type=r.document_type,
            published_on=_as_date(r.source_created_at),
            excerpt=_excerpt(r.content),
            page_number=r.page_number,
        )
        for r in rows
    ]


async def find_spare_parts(_session=None, *, component_type: str | None = None):
    """Spare parts with the fleet reach of each one.

    `plants_served` is traversed, not assumed: part → component type →
    components → equipment → plant. Written as an aggregate join because
    BigQuery rejects correlated subqueries across tables.
    """
    sql = f"""
    WITH jangkauan AS (
      SELECT c.component_type, ARRAY_AGG(DISTINCT p.name ORDER BY p.name) AS plants
      FROM {config.table_ref("components")} c
      JOIN {config.table_ref("equipment")} e ON e.id = c.equipment_id
      JOIN {config.table_ref("production_lines")} l ON l.id = e.production_line_id
      JOIN {config.table_ref("plants")} p ON p.id = l.plant_id
      GROUP BY c.component_type
    )
    SELECT sp.part_number, sp.name, sp.component_type, sp.static_criticality,
           sp.lead_time_weeks, sp.vendor_count, sp.primary_vendor,
           IFNULL(j.plants, []) AS plants_served
    FROM {config.table_ref("spare_parts")} sp
    LEFT JOIN jangkauan j ON j.component_type = sp.component_type
    WHERE (@ct IS NULL OR sp.component_type = @ct)
    ORDER BY sp.part_number
    """
    rows = await _rows(sql, [bigquery.ScalarQueryParameter("ct", "STRING", component_type)])
    return [
        SparePartFacts(
            part_number=r.part_number,
            name=r.name,
            component_type=r.component_type,
            static_criticality=float(r.static_criticality)
            if r.static_criticality is not None
            else None,
            lead_time_weeks=r.lead_time_weeks,
            vendor_count=r.vendor_count,
            primary_vendor=r.primary_vendor,
            plants_served=tuple(r.plants_served or ()),
        )
        for r in rows
    ]


async def find_next_maintenance(_session=None, equipment_tag: str = "") -> date | None:
    """The next planned maintenance window for this equipment, if any."""
    sql = f"""
    SELECT MIN(w.scheduled_start_at) AS scheduled_at
    FROM {config.table_ref("work_orders")} w
    JOIN {config.table_ref("equipment")} e ON e.id = w.equipment_id
    WHERE e.tag_number = @tag
      AND w.work_order_type = 'preventive'
      AND w.status IN ('created', 'approved')
      AND w.scheduled_start_at IS NOT NULL
    """
    rows = await _rows(sql, [bigquery.ScalarQueryParameter("tag", "STRING", equipment_tag)])
    return _as_date(rows[0].scheduled_at) if rows and rows[0].scheduled_at else None


def load_subsystem_map() -> dict[str, str]:
    """Reliability judgement, identical in both backends."""
    return dict(SUBSYSTEM_BY_COMPONENT_TYPE)


def group_by_cause(cases, documents=None) -> list[CandidateEvidence]:
    """Shared with the PostgreSQL backend — grouping is not storage-specific."""
    from app.detection.repository import group_by_cause as _group

    return _group(cases, documents)
