"""The same facts, read from BigQuery instead of PostgreSQL.

Every function here mirrors one in `app.detection.repository` and returns the
identical dataclass. That is the whole point: the layers above — scoring,
finding assembly, the agents, the renderers — work on those dataclasses and
never learn which store answered.

Traversal uses `GRAPH_EXPAND` over the property graph, which runs on on-demand
pricing. The Enterprise reservation is required for GQL syntax, not for walking
a graph — a distinction that was assumed to be a blocker until it was tested.

BigQuery's client is synchronous, so each query is handed to a worker thread.
The callers are async and must not be blocked while a query runs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from google.cloud import bigquery

from app.detection.repository import (
    SUBSYSTEM_BY_COMPONENT_TYPE,
    CandidateEvidence,
    DocumentRef,
    HistoricalCase,
    OpenCase,
    SparePartFacts,
)

logger = logging.getLogger(__name__)

PROJECT = "ebco-aihack-amanda"
DATASET = "arka_graph"

OPEN_STATUSES = ("open", "under_investigation")
RESOLVED_STATUS = "closed"


def _client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT)


async def _rows(sql: str, params: list | None = None) -> list:
    """Run a query off the event loop and return its rows."""

    def jalankan():
        config = bigquery.QueryJobConfig(query_parameters=params or [])
        return list(_client().query(sql, job_config=config).result())

    return await asyncio.to_thread(jalankan)


def _as_date(value) -> date | None:
    if value is None:
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


async def find_open_cases(_session=None) -> list[OpenCase]:
    """Unresolved failures, oldest first.

    The session argument exists only so the two backends are drop-in
    interchangeable; BigQuery has no session to pass.
    """
    sql = f"""
    WITH graf AS (SELECT * FROM GRAPH_EXPAND('{DATASET}.arka_kg'))
    SELECT g.failure_events_id AS id, g.equipment_tag, g.equipment_plant AS plant,
           g.equipment_model AS model, g.failure_events_started_on AS started_on,
           ANY_VALUE(f.component_type) AS component_type,
           ARRAY_AGG(DISTINCT s.symptom_code IGNORE NULLS ORDER BY s.symptom_code)
             AS symptom_codes
    FROM graf g
    JOIN `{PROJECT}.{DATASET}.failure_events` f ON f.id = g.failure_events_id
    LEFT JOIN `{PROJECT}.{DATASET}.failure_symptoms` s ON s.failure_id = g.failure_events_id
    WHERE g.failure_events_status IN UNNEST(@statuses)
    GROUP BY 1, 2, 3, 4, 5
    ORDER BY started_on
    """
    rows = await _rows(
        sql,
        [bigquery.ArrayQueryParameter("statuses", "STRING", list(OPEN_STATUSES))],
    )
    return [
        OpenCase(
            failure_event_id=r.id,
            canonical_id=r.id,
            equipment_tag=r.equipment_tag,
            equipment_model=r.model,
            plant=r.plant,
            started_on=_as_date(r.started_on),
            symptom_codes=tuple(r.symptom_codes or ()),
            # BigQuery carries codes, not display names; the codes are what the
            # scoring uses, and the document renders names from the finding.
            symptom_names=tuple(r.symptom_codes or ()),
            component_code=r.component_type,
            description=None,
        )
        for r in rows
    ]


async def find_historical_cases(
    _session=None, *, equipment_model: str | None = None, exclude_event_id: str | None = None
) -> list[HistoricalCase]:
    """Resolved failures carrying a verified cause."""
    sql = f"""
    WITH graf AS (SELECT * FROM GRAPH_EXPAND('{DATASET}.arka_kg'))
    SELECT g.failure_events_id AS id, c.cause_id, c.cause_name,
           g.equipment_plant AS plant, g.equipment_tag,
           g.failure_events_started_on AS occurred_on,
           ANY_VALUE(f.component_type) AS component_type,
           ANY_VALUE(f.downtime_minutes) AS downtime_minutes,
           ANY_VALUE(w.description) AS resolution,
           ARRAY_AGG(DISTINCT s.symptom_code IGNORE NULLS ORDER BY s.symptom_code)
             AS symptom_codes
    FROM graf g
    JOIN `{PROJECT}.{DATASET}.failure_events` f ON f.id = g.failure_events_id
    JOIN `{PROJECT}.{DATASET}.failure_causes` c ON c.failure_id = g.failure_events_id
    LEFT JOIN `{PROJECT}.{DATASET}.failure_symptoms` s ON s.failure_id = g.failure_events_id
    LEFT JOIN `{PROJECT}.{DATASET}.work_orders` w ON w.failure_id = g.failure_events_id
    WHERE g.failure_events_status = @resolved
      AND (@model IS NULL OR g.equipment_model = @model)
      AND (@exclude IS NULL OR g.failure_events_id != @exclude)
    GROUP BY 1, 2, 3, 4, 5, 6
    ORDER BY occurred_on DESC
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
            failure_event_id=r.id,
            cause_canonical_id=r.cause_id,
            cause_name=r.cause_name,
            plant=r.plant,
            equipment_tag=r.equipment_tag,
            occurred_on=_as_date(r.occurred_on),
            symptom_codes=tuple(r.symptom_codes or ()),
            component_code=r.component_type,
            resolution=r.resolution,
            downtime_minutes=r.downtime_minutes,
        )
        for r in rows
    ]


async def find_documents(_session=None, *, plant_names: tuple[str, ...] = ()) -> list[DocumentRef]:
    """Citable documents, deduplicated by canonical id."""
    sql = f"""
    SELECT id, ANY_VALUE(title) AS title, ANY_VALUE(document_type) AS document_type,
           ANY_VALUE(page_number) AS page_number, ANY_VALUE(content) AS content
    FROM `{PROJECT}.{DATASET}.documents`
    GROUP BY id ORDER BY id
    """
    rows = await _rows(sql)
    hasil = []
    for r in rows:
        excerpt = (r.content or "").strip()
        if len(excerpt) > 300:
            excerpt = excerpt[:297].rstrip() + "…"
        hasil.append(
            DocumentRef(
                canonical_id=r.id,
                title=r.title,
                document_type=r.document_type,
                published_on=None,
                excerpt=excerpt or None,
                page_number=r.page_number,
            )
        )
    return hasil


async def find_spare_parts(_session=None, *, component_type: str | None = None):
    """Spare parts with their fleet reach, traversed through component type."""
    # Written as a join rather than a correlated subquery: BigQuery rejects
    # subqueries that reference another table unless it can de-correlate them,
    # and an aggregate join says the same thing without relying on that.
    sql = f"""
    WITH jangkauan AS (
      SELECT component_type, ARRAY_AGG(DISTINCT plant ORDER BY plant) AS plants
      FROM `{PROJECT}.{DATASET}.components`
      GROUP BY component_type
    )
    SELECT p.part_number, p.name, p.component_type, p.static_criticality,
           p.lead_time_weeks, p.vendor_count, p.primary_vendor,
           IFNULL(j.plants, []) AS plants_served
    FROM `{PROJECT}.{DATASET}.spare_parts` p
    LEFT JOIN jangkauan j ON j.component_type = p.component_type
    WHERE (@ct IS NULL OR p.component_type = @ct)
    ORDER BY p.part_number
    """
    rows = await _rows(
        sql, [bigquery.ScalarQueryParameter("ct", "STRING", component_type)]
    )
    return [
        SparePartFacts(
            part_number=r.part_number,
            name=r.name,
            component_type=r.component_type,
            static_criticality=r.static_criticality,
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
    SELECT MIN(scheduled_on) AS scheduled_on
    FROM `{PROJECT}.{DATASET}.work_orders`
    WHERE equipment_tag = @tag AND work_order_type = 'preventive'
      AND scheduled_on IS NOT NULL AND status IN ('created', 'approved')
    """
    rows = await _rows(
        sql, [bigquery.ScalarQueryParameter("tag", "STRING", equipment_tag)]
    )
    return _as_date(rows[0].scheduled_on) if rows and rows[0].scheduled_on else None


def load_subsystem_map() -> dict[str, str]:
    """Reliability judgement, identical in both backends."""
    return dict(SUBSYSTEM_BY_COMPONENT_TYPE)


def group_by_cause(cases, documents=None) -> list[CandidateEvidence]:
    """Shared with the PostgreSQL backend — grouping is not storage-specific."""
    from app.detection.repository import group_by_cause as _group

    return _group(cases, documents)
