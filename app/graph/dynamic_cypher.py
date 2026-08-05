import json
import re
from typing import Any

import psycopg
from psycopg import sql

from app.core.config import get_settings
from app.graph.neighborhood import (
    AGTYPE_SUFFIX,
    GRAPH_NAME_PATTERN,
)
from app.db.connection import connection_string as _connection_string

GRAPH_SCHEMA = """
Nodes:
- Equipment(canonical_id, tag_number, name, equipment_type, status)
- Plant(canonical_id, code, name)
- WorkOrder(canonical_id, work_order_number, work_order_type, priority, status)
- Notification(canonical_id, notification_number, description)
- ObjectPart(canonical_id, name, normalized_label, description)
- Damage(canonical_id, name, normalized_label, description)
- Cause(canonical_id, name, normalized_label, description)

Directed relationships:
- (Equipment)-[:LOCATED_IN]->(Plant)
- (Equipment)-[:HAS_WORK_ORDER]->(WorkOrder)
- (WorkOrder)-[:REFERENCES]->(Notification)
- (Notification)-[:AFFECTS_PART]->(ObjectPart)
- (Notification)-[:REPORTS_DAMAGE]->(Damage)
- (Notification)-[:HAS_CAUSE]->(Cause)
"""

ALLOWED_LABELS = {
    "Equipment",
    "Plant",
    "WorkOrder",
    "Notification",
    "ObjectPart",
    "Damage",
    "Cause",
}
ALLOWED_RELATIONSHIPS = {
    "LOCATED_IN",
    "HAS_WORK_ORDER",
    "REFERENCES",
    "AFFECTS_PART",
    "REPORTS_DAMAGE",
    "HAS_CAUSE",
}
ALLOWED_PROPERTIES = {
    "canonical_id",
    "tag_number",
    "name",
    "equipment_type",
    "status",
    "code",
    "work_order_number",
    "work_order_type",
    "priority",
    "notification_number",
    "description",
    "normalized_label",
    "review_status",
    "confidence",
    "source_item_id",
}
BLOCKED_KEYWORDS = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD|FOREACH|UNION|"
    r"GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)
ALLOWED_PLACEHOLDERS = {"__TAG_NUMBER__"}


class DynamicCypherError(RuntimeError):
    pass


def validate_generated_cypher(cypher: str, max_limit: int = 100) -> str:
    query = (
        cypher.strip()
        .replace("'__TAG_NUMBER__'", "__TAG_NUMBER__")
        .replace('"__TAG_NUMBER__"', "__TAG_NUMBER__")
    )
    if not query or len(query) > 4000:
        raise DynamicCypherError("Generated Cypher is empty or too long")
    if ";" in query or "//" in query or "/*" in query or "`" in query:
        raise DynamicCypherError("Generated Cypher contains blocked syntax")
    if "'" in query or '"' in query or "$" in query:
        raise DynamicCypherError("String literals and raw parameters are not allowed")
    if BLOCKED_KEYWORDS.search(query):
        raise DynamicCypherError("Generated Cypher contains a write or unsafe clause")
    if re.search(r"\bcollect\s*\(\s*\{", query, re.IGNORECASE):
        raise DynamicCypherError("Nested map collection is not allowed")
    if not re.match(r"^(MATCH|OPTIONAL\s+MATCH)\b", query, re.IGNORECASE):
        raise DynamicCypherError("Generated Cypher must start with MATCH")
    if not re.search(
        r"\bRETURN\s*\{[\s\S]+\}\s+AS\s+row\b",
        query,
        re.IGNORECASE,
    ):
        raise DynamicCypherError("Generated Cypher must return one map AS row")
    return_map = re.search(
        r"\bRETURN\s*\{([\s\S]+)\}\s+AS\s+row\b",
        query,
        re.IGNORECASE,
    )
    if return_map and re.search(
        r"\b(count|collect|sum|avg|min|max)\s*\(",
        return_map.group(1),
        re.IGNORECASE,
    ):
        raise DynamicCypherError(
            "Aggregations must be computed in WITH and returned by alias"
        )

    limits = re.findall(r"\bLIMIT\s+(\d+)\b", query, re.IGNORECASE)
    if len(limits) != 1 or not 1 <= int(limits[0]) <= max_limit:
        raise DynamicCypherError(f"Generated Cypher must have one LIMIT <= {max_limit}")
    if re.search(r"\[[^\]]*\*", query):
        raise DynamicCypherError("Variable-length traversal is not allowed")

    relationships = re.findall(r"\[[^\]]*:\s*([A-Za-z_]\w*)", query)
    if len(relationships) > 3:
        raise DynamicCypherError("Generated Cypher exceeds the 3-hop limit")
    unknown_relationships = set(relationships) - ALLOWED_RELATIONSHIPS
    if unknown_relationships:
        raise DynamicCypherError(
            f"Unknown relationships: {sorted(unknown_relationships)}"
        )

    labels = re.findall(r"\(\s*\w+\s*:\s*([A-Za-z_]\w*)", query)
    unknown_labels = set(labels) - ALLOWED_LABELS
    if unknown_labels:
        raise DynamicCypherError(f"Unknown labels: {sorted(unknown_labels)}")

    properties = re.findall(r"\b\w+\.([A-Za-z_]\w*)", query)
    unknown_properties = set(properties) - ALLOWED_PROPERTIES
    if unknown_properties:
        raise DynamicCypherError(
            f"Unknown properties: {sorted(unknown_properties)}"
        )

    placeholders = set(re.findall(r"__[A-Z_]+__", query))
    unknown_placeholders = placeholders - ALLOWED_PLACEHOLDERS
    if unknown_placeholders:
        raise DynamicCypherError(
            f"Unknown placeholders: {sorted(unknown_placeholders)}"
        )
    return query


def render_generated_cypher(cypher: str, tag_number: str | None) -> str:
    rendered = cypher
    if "__TAG_NUMBER__" in rendered:
        if not tag_number:
            raise DynamicCypherError("Generated Cypher requires tag_number")
        rendered = rendered.replace("__TAG_NUMBER__", json.dumps(tag_number))
    if re.search(r"__[A-Z_]+__", rendered):
        raise DynamicCypherError("Generated Cypher contains unresolved placeholders")
    return rendered


def _parse_agtype_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool, dict, list)):
        return value
    raw = AGTYPE_SUFFIX.sub("", str(value))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def execute_dynamic_cypher(
    cypher_template: str,
    question: str,
    tag_number: str | None,
    max_limit: int = 100,
    timeout_seconds: float = 5,
) -> dict[str, Any]:
    validated = validate_generated_cypher(cypher_template, max_limit)
    cypher = render_generated_cypher(validated, tag_number)
    graph_name = get_settings().age_graph_name
    if not GRAPH_NAME_PATTERN.fullmatch(graph_name):
        raise DynamicCypherError("Invalid AGE graph name")

    try:
        with psycopg.connect(_connection_string()) as connection:
            with connection.cursor() as cursor:
                cursor.execute("LOAD 'age'")
                cursor.execute('SET search_path = ag_catalog, "$user", public')
                cursor.execute(
                    sql.SQL("SET LOCAL statement_timeout = {}").format(
                        sql.Literal(f"{int(timeout_seconds * 1000)}ms")
                    )
                )
                statement = sql.SQL(
                    "SELECT * FROM cypher({}, $cypher${}$cypher$) AS (row agtype)"
                ).format(sql.Literal(graph_name), sql.SQL(cypher))
                cursor.execute(sql.SQL("EXPLAIN ") + statement)
                cursor.fetchall()
                cursor.execute(statement)
                rows = [_parse_agtype_scalar(row[0]) for row in cursor.fetchall()]
    except psycopg.Error as exc:
        database_message = getattr(exc.diag, "message_primary", None)
        safe_detail = (
            re.sub(r"[\r\n]+", " ", database_message)[:300]
            if database_message
            else "unknown database error"
        )
        raise DynamicCypherError(
            "Generated Cypher failed database syntax or timeout validation: "
            f"{safe_detail}"
        ) from exc
    return {
        "query_id": "dynamic-cypher",
        "question": question,
        "parameters": {"tag_number": tag_number, "limit": max_limit},
        "cypher": cypher,
        "row_count": len(rows),
        "rows": rows,
    }
