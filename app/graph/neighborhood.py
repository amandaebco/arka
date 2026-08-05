import json
import re
from typing import Any

import psycopg
from psycopg import sql

from app.core.config import get_settings
from app.db.connection import connection_string as _connection_string

GRAPH_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
AGTYPE_SUFFIX = re.compile(r"::(?:vertex|edge)$")
CONCEPT_RELATIONSHIPS = {
    "Damage": "REPORTS_DAMAGE",
    "Cause": "HAS_CAUSE",
    "ObjectPart": "AFFECTS_PART",
}


def _parse_graph_element(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(AGTYPE_SUFFIX.sub("", str(value)))


def get_equipment_neighborhood(
    tag_number: str,
    max_hops: int = 2,
    limit: int = 100,
) -> dict[str, Any]:
    if not 1 <= max_hops <= 3:
        raise ValueError("max_hops must be between 1 and 3")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    graph_name = get_settings().age_graph_name
    if not GRAPH_NAME_PATTERN.fullmatch(graph_name):
        raise ValueError("Invalid AGE graph name")

    patterns = [
        (1, "-[:LOCATED_IN]->(neighbor:Plant)"),
        (1, "-[:HAS_WORK_ORDER]->(neighbor:WorkOrder)"),
        (
            2,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)"
            "-[:REFERENCES]->(neighbor:Notification)",
        ),
        (
            3,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)-[:REFERENCES]->(:Notification)"
            "-[:CANDIDATE_AFFECTS_PART]->(neighbor:ObjectPart)",
        ),
        (
            3,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)-[:REFERENCES]->(:Notification)"
            "-[:AFFECTS_PART]->(neighbor:ObjectPart)",
        ),
        (
            3,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)-[:REFERENCES]->(:Notification)"
            "-[:REPORTS_DAMAGE]->(neighbor:Damage)",
        ),
        (
            3,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)-[:REFERENCES]->(:Notification)"
            "-[:HAS_CAUSE]->(neighbor:Cause)",
        ),
        (
            3,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)-[:REFERENCES]->(:Notification)"
            "-[:CANDIDATE_REPORTS_DAMAGE]->(neighbor:Damage)",
        ),
        (
            3,
            "-[:HAS_WORK_ORDER]->(:WorkOrder)-[:REFERENCES]->(:Notification)"
            "-[:CANDIDATE_HAS_CAUSE]->(neighbor:Cause)",
        ),
    ]

    nodes: dict[int, dict[str, Any]] = {}
    edges: dict[int, dict[str, Any]] = {}
    truncated = False
    with psycopg.connect(_connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("LOAD 'age'")
            cursor.execute('SET search_path = ag_catalog, "$user", public')
            for depth, pattern in patterns:
                if depth > max_hops:
                    continue
                cypher = (
                    f"MATCH p=(e:Equipment {{tag_number: {json.dumps(tag_number)}}})"
                    f"{pattern} WITH p LIMIT {limit} "
                    "WITH relationships(p) AS rels UNWIND rels AS r "
                    "RETURN startNode(r), r, endNode(r)"
                )
                query = sql.SQL(
                    "SELECT * FROM cypher({}, $cypher${}$cypher$) "
                    "AS (source agtype, relationship agtype, target agtype)"
                ).format(sql.Literal(graph_name), sql.SQL(cypher))
                cursor.execute(query)
                rows = cursor.fetchall()
                truncated = truncated or len(rows) >= limit * depth
                for source_value, edge_value, target_value in rows:
                    source = _parse_graph_element(source_value)
                    edge = _parse_graph_element(edge_value)
                    target = _parse_graph_element(target_value)
                    nodes[source["id"]] = source
                    nodes[target["id"]] = target
                    edges[edge["id"]] = edge

    return {
        "start": {"label": "Equipment", "tag_number": tag_number},
        "max_hops": max_hops,
        "limit": limit,
        "truncated": truncated,
        "available_hops": 3,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def get_concept_connections(
    concept_label: str,
    canonical_id: str,
    max_hops: int = 3,
    limit: int = 100,
) -> dict[str, Any]:
    relationship = CONCEPT_RELATIONSHIPS.get(concept_label)
    if relationship is None:
        raise ValueError("concept_label must be Damage, Cause, or ObjectPart")
    if not canonical_id:
        raise ValueError("canonical_id is required")
    if not 1 <= max_hops <= 3:
        raise ValueError("max_hops must be between 1 and 3")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    graph_name = get_settings().age_graph_name
    if not GRAPH_NAME_PATTERN.fullmatch(graph_name):
        raise ValueError("Invalid AGE graph name")

    patterns = [
        (1, f"<-[:{relationship}]-(neighbor:Notification)"),
        (
            2,
            f"<-[:{relationship}]-(:Notification)"
            "<-[:REFERENCES]-(neighbor:WorkOrder)",
        ),
        (
            3,
            f"<-[:{relationship}]-(:Notification)<-[:REFERENCES]-(:WorkOrder)"
            "<-[:HAS_WORK_ORDER]-(neighbor:Equipment)",
        ),
    ]
    nodes: dict[int, dict[str, Any]] = {}
    edges: dict[int, dict[str, Any]] = {}
    truncated = False
    with psycopg.connect(_connection_string()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("LOAD 'age'")
            cursor.execute('SET search_path = ag_catalog, "$user", public')
            for depth, pattern in patterns:
                if depth > max_hops:
                    continue
                cypher = (
                    f"MATCH p=(concept:{concept_label} "
                    f"{{canonical_id: {json.dumps(canonical_id)}}})"
                    f"{pattern} WITH p LIMIT {limit} "
                    "WITH relationships(p) AS rels UNWIND rels AS r "
                    "RETURN startNode(r), r, endNode(r)"
                )
                query = sql.SQL(
                    "SELECT * FROM cypher({}, $cypher${}$cypher$) "
                    "AS (source agtype, relationship agtype, target agtype)"
                ).format(sql.Literal(graph_name), sql.SQL(cypher))
                cursor.execute(query)
                rows = cursor.fetchall()
                truncated = truncated or len(rows) >= limit * depth
                for source_value, edge_value, target_value in rows:
                    source = _parse_graph_element(source_value)
                    edge = _parse_graph_element(edge_value)
                    target = _parse_graph_element(target_value)
                    nodes[source["id"]] = source
                    nodes[target["id"]] = target
                    edges[edge["id"]] = edge

    inspector_cypher = (
        f"MATCH (concept:{concept_label} "
        f"{{canonical_id: {json.dumps(canonical_id)}}})"
        f"<-[semantic:{relationship}]-(notification:Notification)"
        "<-[:REFERENCES]-(work_order:WorkOrder)"
        "<-[:HAS_WORK_ORDER]-(equipment:Equipment)\n"
        "RETURN concept, semantic, notification, work_order, equipment\n"
        f"LIMIT {limit}"
    )
    return {
        "start": {
            "label": concept_label,
            "canonical_id": canonical_id,
        },
        "max_hops": max_hops,
        "limit": limit,
        "truncated": truncated,
        "available_hops": 3,
        "cypher": inspector_cypher,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
