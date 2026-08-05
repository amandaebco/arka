import json
from dataclasses import asdict, dataclass
from typing import Any

import psycopg
from psycopg import sql

from app.core.config import get_settings
from app.graph.neighborhood import AGTYPE_SUFFIX, GRAPH_NAME_PATTERN
from app.db.connection import connection_string as _connection_string


@dataclass(frozen=True)
class CompetencyQuery:
    id: str
    question: str
    scope: str
    status: str
    required_parameters: tuple[str, ...]
    path: str
    cypher_template: str | None = None


CURRENT_QUERIES = (
    CompetencyQuery(
        id="maintenance-history",
        question="Work order dan notification apa yang terkait dengan equipment ini?",
        scope="reliability_graph",
        status="executable",
        required_parameters=("tag_number",),
        path="Equipment → WorkOrder → Notification",
        cypher_template="""
MATCH (e:Equipment {tag_number: __TAG__})-[:HAS_WORK_ORDER]->(w:WorkOrder)
OPTIONAL MATCH (w)-[:REFERENCES]->(n:Notification)
RETURN {tag_number: e.tag_number, work_order_number: w.work_order_number,
        work_order_status: w.status, notification_number: n.notification_number,
        notification_description: n.description} AS row
ORDER BY w.work_order_number
LIMIT __LIMIT__
""",
    ),
    CompetencyQuery(
        id="verified-causes",
        question="Cause terverifikasi apa yang terkait dengan histori equipment ini?",
        scope="reliability_graph",
        status="executable",
        required_parameters=("tag_number",),
        path="Equipment → WorkOrder → Notification → Cause",
        cypher_template="""
MATCH (e:Equipment {tag_number: __TAG__})-[:HAS_WORK_ORDER]->(w:WorkOrder)
      -[:REFERENCES]->(n:Notification)-[r:HAS_CAUSE]->(result:Cause)
RETURN {tag_number: e.tag_number, work_order_number: w.work_order_number,
        notification_number: n.notification_number, cause: result.name,
        review_status: r.review_status, confidence: r.confidence} AS row
LIMIT __LIMIT__
""",
    ),
    CompetencyQuery(
        id="reported-damages",
        question="Damage apa yang pernah dilaporkan pada equipment ini?",
        scope="reliability_graph",
        status="executable",
        required_parameters=("tag_number",),
        path="Equipment → WorkOrder → Notification → Damage",
        cypher_template="""
MATCH (e:Equipment {tag_number: __TAG__})-[:HAS_WORK_ORDER]->(w:WorkOrder)
      -[:REFERENCES]->(n:Notification)-[r:REPORTS_DAMAGE]->(result:Damage)
RETURN {tag_number: e.tag_number, work_order_number: w.work_order_number,
        notification_number: n.notification_number, damage: result.name,
        review_status: r.review_status, confidence: r.confidence} AS row
LIMIT __LIMIT__
""",
    ),
    CompetencyQuery(
        id="affected-parts",
        question="Object part apa yang pernah terdampak pada equipment ini?",
        scope="reliability_graph",
        status="executable",
        required_parameters=("tag_number",),
        path="Equipment → WorkOrder → Notification → ObjectPart",
        cypher_template="""
MATCH (e:Equipment {tag_number: __TAG__})-[:HAS_WORK_ORDER]->(w:WorkOrder)
      -[:REFERENCES]->(n:Notification)-[r:AFFECTS_PART]->(result:ObjectPart)
RETURN {tag_number: e.tag_number, work_order_number: w.work_order_number,
        notification_number: n.notification_number, object_part: result.name,
        review_status: r.review_status, confidence: r.confidence} AS row
LIMIT __LIMIT__
""",
    ),
    CompetencyQuery(
        id="top-equipment-by-work-orders",
        question="Equipment mana yang memiliki histori work order terbanyak?",
        scope="reliability_graph",
        status="executable",
        required_parameters=(),
        path="Equipment → WorkOrder",
        cypher_template="""
MATCH (e:Equipment)-[:HAS_WORK_ORDER]->(w:WorkOrder)
WITH e, count(w) AS work_order_count
RETURN {tag_number: e.tag_number, equipment_name: e.name,
        work_order_count: work_order_count} AS row
ORDER BY work_order_count DESC
LIMIT __LIMIT__
""",
    ),
    CompetencyQuery(
        id="maintenance-volume-by-plant",
        question="Berapa jumlah work order dan notification per plant?",
        scope="reliability_graph",
        status="executable",
        required_parameters=(),
        path="Plant ← Equipment → WorkOrder → Notification",
        cypher_template="""
MATCH (e:Equipment)-[:LOCATED_IN]->(p:Plant)
OPTIONAL MATCH (e)-[:HAS_WORK_ORDER]->(w:WorkOrder)
OPTIONAL MATCH (w)-[:REFERENCES]->(n:Notification)
WITH p, count(DISTINCT w) AS work_order_count,
     count(DISTINCT n) AS notification_count
RETURN {plant_code: p.code, plant_name: p.name,
        work_order_count: work_order_count,
        notification_count: notification_count} AS row
ORDER BY work_order_count DESC
LIMIT __LIMIT__
""",
    ),
)

TARGET_QUESTIONS = (
    "Symptom apa yang muncul pada failure event tertentu?",
    "Failure mode apa yang paling sering terjadi pada model pump yang sama?",
    "Probable cause apa yang didukung evidence untuk kombinasi symptom tertentu?",
    "Cause apa yang sudah diverifikasi dan mana yang masih berupa claim?",
    "Corrective action apa yang pernah berhasil untuk failure mode serupa?",
    "Apakah failure yang sama kembali terjadi dalam 30 hari setelah maintenance?",
    "Component dan spare part apa yang paling sering terkait dengan suatu failure mode?",
    "Technician mana yang pernah menangani failure serupa?",
    "Alarm dan observation apa yang terjadi sebelum failure?",
    "Dokumen dan potongan teks mana yang mendukung probable cause tertentu?",
)

QUERY_BY_ID = {query.id: query for query in CURRENT_QUERIES}


def competency_catalog() -> dict[str, Any]:
    executable = [
        {**asdict(query), "cypher_template": query.cypher_template.strip()}
        for query in CURRENT_QUERIES
    ]
    target = [
        {
            "id": f"target-{index:02d}",
            "question": question,
            "scope": "target_mvp",
            "status": "requires_future_projection",
        }
        for index, question in enumerate(TARGET_QUESTIONS, start=1)
    ]
    return {"executable": executable, "target": target}


def _parse_agtype_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool, dict, list)):
        return value
    raw = AGTYPE_SUFFIX.sub("", str(value))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def render_cypher(query: CompetencyQuery, tag_number: str | None, limit: int) -> str:
    if query.cypher_template is None:
        raise ValueError("Query is not executable")
    if "tag_number" in query.required_parameters and not tag_number:
        raise ValueError("tag_number is required")
    rendered = query.cypher_template.replace("__LIMIT__", str(limit))
    return rendered.replace("__TAG__", json.dumps(tag_number)).strip()


def execute_competency_query(
    query_id: str,
    tag_number: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    query = QUERY_BY_ID.get(query_id)
    if query is None:
        raise KeyError(query_id)
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    graph_name = get_settings().age_graph_name
    if not GRAPH_NAME_PATTERN.fullmatch(graph_name):
        raise ValueError("Invalid AGE graph name")
    cypher = render_cypher(query, tag_number, limit)

    with psycopg.connect(_connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("LOAD 'age'")
            cursor.execute('SET search_path = ag_catalog, "$user", public')
            cursor.execute(
                sql.SQL(
                    "SELECT * FROM cypher({}, $cypher${}$cypher$) AS (row agtype)"
                ).format(sql.Literal(graph_name), sql.SQL(cypher))
            )
            rows = [_parse_agtype_scalar(row[0]) for row in cursor.fetchall()]
    return {
        "query_id": query.id,
        "question": query.question,
        "parameters": {"tag_number": tag_number, "limit": limit},
        "cypher": cypher,
        "row_count": len(rows),
        "rows": rows,
    }
