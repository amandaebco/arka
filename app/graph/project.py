import argparse
import json
import re
from collections.abc import Iterator
from typing import Any

import psycopg
from psycopg import sql

from app.core.config import get_settings
from app.db.connection import connection_string as _connection_string

GRAPH_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

NODE_QUERIES = {
    "Plant": """
        SELECT canonical_id, code, name
        FROM plants
        ORDER BY canonical_id
    """,
    "Equipment": """
        SELECT canonical_id, tag_number, name, equipment_type, status
        FROM equipment
        ORDER BY canonical_id
    """,
    "Component": """
        SELECT canonical_id, tag_number, name, component_type, status
        FROM components
        ORDER BY canonical_id
    """,
    "WorkOrder": """
        SELECT canonical_id, work_order_number, work_order_type, priority, status
        FROM work_orders
        ORDER BY canonical_id
    """,
    "Notification": """
        SELECT canonical_id, notification_number, description
        FROM maintenance_notifications
        ORDER BY canonical_id
    """,
    "ObjectPart": """
        SELECT DISTINCT c.canonical_id, c.preferred_label AS name,
               c.normalized_label, c.description
        FROM semantic_concepts c
        JOIN notification_concept_links link ON link.semantic_concept_id=c.id
        WHERE c.concept_type='component_type' AND link.review_status<>'rejected'
        ORDER BY c.canonical_id
    """,
    "Damage": """
        SELECT DISTINCT c.canonical_id, c.preferred_label AS name,
               c.normalized_label, c.description
        FROM semantic_concepts c
        JOIN notification_concept_links link ON link.semantic_concept_id=c.id
        WHERE c.concept_type='damage' AND link.review_status<>'rejected'
        ORDER BY c.canonical_id
    """,
    "Cause": """
        SELECT DISTINCT c.canonical_id, c.preferred_label AS name,
               c.normalized_label, c.description
        FROM semantic_concepts c
        JOIN notification_concept_links link ON link.semantic_concept_id=c.id
        WHERE c.concept_type='cause' AND link.review_status<>'rejected'
        UNION
        SELECT c.canonical_id, c.name, lower(c.name) AS normalized_label, c.description
        FROM causes c
        ORDER BY canonical_id
    """,
    "FailureEvent": """
        SELECT canonical_id, event_number, title, status, started_at::text AS started_at
        FROM failure_events
        ORDER BY canonical_id
    """,
    "Symptom": """
        SELECT DISTINCT s.canonical_id, s.code, s.name, s.description
        FROM symptoms s
        JOIN failure_event_symptoms link ON link.symptom_id=s.id
        ORDER BY s.canonical_id
    """,
    "FailureMode": """
        SELECT DISTINCT f.canonical_id, f.code, f.name, f.description
        FROM failure_modes f
        JOIN failure_event_failure_modes link ON link.failure_mode_id=f.id
        ORDER BY f.canonical_id
    """,
    "DamageOccurrence": """
        SELECT d.id::text AS canonical_id, d.damage_type, d.description, d.severity,
               d.detected_at::text AS detected_at
        FROM damages d
        ORDER BY d.id
    """,
    "MaintenanceActivity": """
        SELECT a.id::text AS canonical_id, a.activity_code, a.activity_type,
               a.description, a.status
        FROM maintenance_activities a
        ORDER BY a.id
    """,
    "Document": """
        SELECT DISTINCT d.canonical_id, d.title, d.document_type, d.source_system
        FROM documents d
        JOIN document_versions v ON v.document_id=d.id
        JOIN document_chunks chunk ON chunk.document_version_id=v.id
        JOIN evidence e ON e.document_chunk_id=chunk.id
        JOIN claim_evidence ce ON ce.evidence_id=e.id
        JOIN claims c ON c.id=ce.claim_id
        WHERE c.review_status='accepted'
        ORDER BY d.canonical_id
    """,
    "Evidence": """
        SELECT DISTINCT e.id::text AS canonical_id, e.evidence_type, e.quote_text,
               e.evidence_format, e.confidence::float AS confidence,
               chunk.page_number
        FROM evidence e
        JOIN document_chunks chunk ON chunk.id=e.document_chunk_id
        JOIN claim_evidence ce ON ce.evidence_id=e.id
        JOIN claims c ON c.id=ce.claim_id
        WHERE c.review_status='accepted'
        ORDER BY canonical_id
    """,
    "Claim": """
        SELECT c.id::text AS canonical_id, c.claim_type, c.assertion_status,
               c.statement, c.predicate, c.confidence::float AS confidence,
               c.source_section
        FROM claims c
        WHERE c.review_status='accepted'
        ORDER BY c.id
    """,
}
NODE_PROPERTIES = {
    "Plant": ("canonical_id", "code", "name"),
    "Equipment": ("canonical_id", "tag_number", "name", "equipment_type", "status"),
    "Component": ("canonical_id", "tag_number", "name", "component_type", "status"),
    "WorkOrder": ("canonical_id", "work_order_number", "work_order_type", "priority", "status"),
    "Notification": ("canonical_id", "notification_number", "description"),
    "ObjectPart": ("canonical_id", "name", "normalized_label", "description"),
    "Damage": ("canonical_id", "name", "normalized_label", "description"),
    "Cause": ("canonical_id", "name", "normalized_label", "description"),
    "FailureEvent": ("canonical_id", "event_number", "title", "status", "started_at"),
    "Symptom": ("canonical_id", "code", "name", "description"),
    "FailureMode": ("canonical_id", "code", "name", "description"),
    "DamageOccurrence": (
        "canonical_id",
        "damage_type",
        "description",
        "severity",
        "detected_at",
    ),
    "MaintenanceActivity": (
        "canonical_id",
        "activity_code",
        "activity_type",
        "description",
        "status",
    ),
    "Document": ("canonical_id", "title", "document_type", "source_system"),
    "Evidence": (
        "canonical_id",
        "evidence_type",
        "quote_text",
        "evidence_format",
        "confidence",
        "page_number",
    ),
    "Claim": (
        "canonical_id",
        "claim_type",
        "assertion_status",
        "statement",
        "predicate",
        "confidence",
        "source_section",
    ),
}

EDGE_QUERIES = {
    ("Equipment", "LOCATED_IN", "Plant"): """
        SELECT e.canonical_id AS start_id, p.canonical_id AS end_id
        FROM equipment e
        JOIN production_lines line ON line.id=e.production_line_id
        JOIN plants p ON p.id=line.plant_id
        ORDER BY e.canonical_id
    """,
    ("Equipment", "HAS_COMPONENT", "Component"): """
        SELECT e.canonical_id AS start_id, c.canonical_id AS end_id
        FROM components c
        JOIN equipment e ON e.id=c.equipment_id
        ORDER BY e.canonical_id,c.canonical_id
    """,
    ("Equipment", "HAS_WORK_ORDER", "WorkOrder"): """
        SELECT e.canonical_id AS start_id, w.canonical_id AS end_id
        FROM work_orders w JOIN equipment e ON e.id=w.equipment_id
        ORDER BY w.canonical_id
    """,
    ("WorkOrder", "REFERENCES", "Notification"): """
        SELECT w.canonical_id AS start_id, n.canonical_id AS end_id
        FROM work_order_notifications link
        JOIN work_orders w ON w.id=link.work_order_id
        JOIN maintenance_notifications n ON n.id=link.notification_id
        ORDER BY w.canonical_id
    """,
    ("Notification", "CANDIDATE_AFFECTS_PART", "ObjectPart"): """
        SELECT n.canonical_id AS start_id, c.canonical_id AS end_id,
               link.review_status, link.confidence::float AS confidence,
               link.source_item_id::text AS source_item_id
        FROM notification_concept_links link
        JOIN maintenance_notifications n ON n.id=link.notification_id
        JOIN semantic_concepts c ON c.id=link.semantic_concept_id
        WHERE link.relationship_type='affects_part' AND link.review_status='unreviewed'
        ORDER BY n.canonical_id,c.canonical_id
    """,
    ("Notification", "CANDIDATE_REPORTS_DAMAGE", "Damage"): """
        SELECT n.canonical_id AS start_id, c.canonical_id AS end_id,
               link.review_status, link.confidence::float AS confidence,
               link.source_item_id::text AS source_item_id
        FROM notification_concept_links link
        JOIN maintenance_notifications n ON n.id=link.notification_id
        JOIN semantic_concepts c ON c.id=link.semantic_concept_id
        WHERE link.relationship_type='reports_damage' AND link.review_status='unreviewed'
        ORDER BY n.canonical_id,c.canonical_id
    """,
    ("Notification", "CANDIDATE_HAS_CAUSE", "Cause"): """
        SELECT n.canonical_id AS start_id, c.canonical_id AS end_id,
               link.review_status, link.confidence::float AS confidence,
               link.source_item_id::text AS source_item_id
        FROM notification_concept_links link
        JOIN maintenance_notifications n ON n.id=link.notification_id
        JOIN semantic_concepts c ON c.id=link.semantic_concept_id
        WHERE link.relationship_type='has_cause' AND link.review_status='unreviewed'
        ORDER BY n.canonical_id,c.canonical_id
    """,
    ("Notification", "AFFECTS_PART", "ObjectPart"): """
        SELECT n.canonical_id AS start_id, c.canonical_id AS end_id,
               link.review_status, link.confidence::float AS confidence,
               link.source_item_id::text AS source_item_id
        FROM notification_concept_links link
        JOIN maintenance_notifications n ON n.id=link.notification_id
        JOIN semantic_concepts c ON c.id=link.semantic_concept_id
        WHERE link.relationship_type='affects_part' AND link.review_status='accepted'
        ORDER BY n.canonical_id,c.canonical_id
    """,
    ("Notification", "REPORTS_DAMAGE", "Damage"): """
        SELECT n.canonical_id AS start_id, c.canonical_id AS end_id,
               link.review_status, link.confidence::float AS confidence,
               link.source_item_id::text AS source_item_id
        FROM notification_concept_links link
        JOIN maintenance_notifications n ON n.id=link.notification_id
        JOIN semantic_concepts c ON c.id=link.semantic_concept_id
        WHERE link.relationship_type='reports_damage' AND link.review_status='accepted'
        ORDER BY n.canonical_id,c.canonical_id
    """,
    ("Notification", "HAS_CAUSE", "Cause"): """
        SELECT n.canonical_id AS start_id, c.canonical_id AS end_id,
               link.review_status, link.confidence::float AS confidence,
               link.source_item_id::text AS source_item_id
        FROM notification_concept_links link
        JOIN maintenance_notifications n ON n.id=link.notification_id
        JOIN semantic_concepts c ON c.id=link.semantic_concept_id
        WHERE link.relationship_type='has_cause' AND link.review_status='accepted'
        ORDER BY n.canonical_id,c.canonical_id
    """,
    ("Equipment", "HAS_FAILURE_EVENT", "FailureEvent"): """
        SELECT e.canonical_id AS start_id, f.canonical_id AS end_id
        FROM failure_events f
        JOIN equipment e ON e.id=f.equipment_id
        ORDER BY e.canonical_id,f.canonical_id
    """,
    ("FailureEvent", "AFFECTS_COMPONENT", "Component"): """
        SELECT f.canonical_id AS start_id, c.canonical_id AS end_id
        FROM failure_events f
        JOIN components c ON c.id=f.component_id
        ORDER BY f.canonical_id,c.canonical_id
    """,
    ("FailureEvent", "HAS_SYMPTOM", "Symptom"): """
        SELECT f.canonical_id AS start_id, s.canonical_id AS end_id
        FROM failure_event_symptoms link
        JOIN failure_events f ON f.id=link.failure_event_id
        JOIN symptoms s ON s.id=link.symptom_id
        ORDER BY f.canonical_id,s.canonical_id
    """,
    ("FailureEvent", "HAS_FAILURE_MODE", "FailureMode"): """
        SELECT f.canonical_id AS start_id, m.canonical_id AS end_id
        FROM failure_event_failure_modes link
        JOIN failure_events f ON f.id=link.failure_event_id
        JOIN failure_modes m ON m.id=link.failure_mode_id
        ORDER BY f.canonical_id,m.canonical_id
    """,
    ("FailureEvent", "HAS_VERIFIED_CAUSE", "Cause"): """
        SELECT f.canonical_id AS start_id, c.canonical_id AS end_id
        FROM failure_event_causes link
        JOIN failure_events f ON f.id=link.failure_event_id
        JOIN causes c ON c.id=link.cause_id
        ORDER BY f.canonical_id,c.canonical_id
    """,
    ("FailureEvent", "HAS_DAMAGE", "DamageOccurrence"): """
        SELECT f.canonical_id AS start_id, d.id::text AS end_id
        FROM damages d
        JOIN failure_events f ON f.id=d.failure_event_id
        ORDER BY f.canonical_id,d.id
    """,
    ("WorkOrder", "RESPONDS_TO", "FailureEvent"): """
        SELECT w.canonical_id AS start_id, f.canonical_id AS end_id
        FROM work_order_failure_events link
        JOIN work_orders w ON w.id=link.work_order_id
        JOIN failure_events f ON f.id=link.failure_event_id
        ORDER BY w.canonical_id,f.canonical_id
    """,
    ("WorkOrder", "HAS_ACTIVITY", "MaintenanceActivity"): """
        SELECT w.canonical_id AS start_id, a.id::text AS end_id
        FROM maintenance_activities a
        JOIN work_orders w ON w.id=a.work_order_id
        ORDER BY w.canonical_id,a.id
    """,
    ("Document", "HAS_EVIDENCE", "Evidence"): """
        SELECT DISTINCT d.canonical_id AS start_id, e.id::text AS end_id
        FROM documents d
        JOIN document_versions v ON v.document_id=d.id
        JOIN document_chunks chunk ON chunk.document_version_id=v.id
        JOIN evidence e ON e.document_chunk_id=chunk.id
        JOIN claim_evidence ce ON ce.evidence_id=e.id
        JOIN claims c ON c.id=ce.claim_id
        WHERE c.review_status='accepted'
        ORDER BY start_id,end_id
    """,
    ("Evidence", "SUPPORTS", "Claim"): """
        SELECT e.id::text AS start_id, c.id::text AS end_id
        FROM claim_evidence link
        JOIN evidence e ON e.id=link.evidence_id
        JOIN claims c ON c.id=link.claim_id
        WHERE c.review_status='accepted'
        ORDER BY e.id,c.id
    """,
    ("Claim", "ABOUT_EQUIPMENT", "Equipment"): """
        SELECT c.id::text AS start_id, e.canonical_id AS end_id
        FROM claims c
        JOIN equipment e ON e.id=c.equipment_id
        WHERE c.review_status='accepted'
        ORDER BY c.id,e.canonical_id
    """,
    ("Claim", "ABOUT_COMPONENT", "Component"): """
        SELECT c.id::text AS start_id, component.canonical_id AS end_id
        FROM claims c
        JOIN components component ON component.id=c.component_id
        WHERE c.review_status='accepted'
        ORDER BY c.id,component.canonical_id
    """,
    ("Claim", "ABOUT_FAILURE_EVENT", "FailureEvent"): """
        SELECT c.id::text AS start_id, f.canonical_id AS end_id
        FROM claims c
        JOIN failure_events f ON f.id=c.failure_event_id
        WHERE c.review_status='accepted'
        ORDER BY c.id,f.canonical_id
    """,
}

CANDIDATE_EDGE_PROPERTIES = (
    "review_status: row.review_status, confidence: row.confidence, "
    "source_item_id: row.source_item_id"
)
SEMANTIC_EDGE_LABELS = {
    "CANDIDATE_AFFECTS_PART",
    "CANDIDATE_REPORTS_DAMAGE",
    "CANDIDATE_HAS_CAUSE",
    "AFFECTS_PART",
    "REPORTS_DAMAGE",
    "HAS_CAUSE",
}


def _batches(cursor: psycopg.Cursor, query: str, size: int) -> Iterator[list[dict[str, Any]]]:
    cursor.execute(query)
    columns = [column.name for column in cursor.description or ()]
    while rows := cursor.fetchmany(size):
        yield [
            {key: value for key, value in zip(columns, row, strict=True) if value is not None}
            for row in rows
        ]


def _execute_batch(cursor: psycopg.Cursor, statement: str, rows: list[dict[str, Any]]) -> None:
    payload = json.dumps({"rows": rows})
    cursor.execute(
        sql.SQL("EXECUTE {} ({}::agtype)").format(
            sql.Identifier(statement),
            sql.Literal(payload),
        )
    )


def project_graph(graph_name: str, batch_size: int = 1000) -> dict[str, dict[str, int]]:
    if not GRAPH_NAME_PATTERN.fullmatch(graph_name):
        raise ValueError("Invalid AGE graph name")
    counts: dict[str, dict[str, int]] = {"nodes": {}, "edges": {}}
    with psycopg.connect(_connection_string(), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("LOAD 'age'")
            cursor.execute('SET search_path = ag_catalog, "$user", public')
            cursor.execute(
                "SELECT drop_graph(%s, true) WHERE EXISTS (SELECT 1 FROM ag_graph WHERE name=%s)",
                (graph_name, graph_name),
            )
            cursor.execute("SELECT create_graph(%s)", (graph_name,))

            for label, source_query in NODE_QUERIES.items():
                statement = f"project_{label.lower()}"
                properties = ", ".join(f"{name}: row.{name}" for name in NODE_PROPERTIES[label])
                cypher = f"UNWIND $rows AS row CREATE (n:{label} {{{properties}}})"
                cursor.execute(
                    sql.SQL(
                        "PREPARE {}(agtype) AS SELECT * FROM "
                        "cypher({}, $cypher${}$cypher$, $1) AS (v agtype)"
                    ).format(
                        sql.Identifier(statement),
                        sql.Literal(graph_name),
                        sql.SQL(cypher),
                    )
                )
                count = 0
                read_cursor = connection.cursor()
                for batch in _batches(read_cursor, source_query, batch_size):
                    _execute_batch(cursor, statement, batch)
                    count += len(batch)
                read_cursor.close()
                cursor.execute(sql.SQL("DEALLOCATE {}").format(sql.Identifier(statement)))
                counts["nodes"][label] = count
                cursor.execute(
                    sql.SQL("CREATE INDEX {} ON {}.{} USING gin (properties)").format(
                        sql.Identifier(f"ix_{label.lower()}_properties"),
                        sql.Identifier(graph_name),
                        sql.Identifier(label),
                    )
                )
                indexed_properties = ["canonical_id"]
                if label == "Equipment":
                    indexed_properties.append("tag_number")
                for property_name in indexed_properties:
                    cursor.execute(
                        sql.SQL(
                            "CREATE INDEX {} ON {}.{} "
                            "(agtype_access_operator(VARIADIC ARRAY[properties, {}::agtype]))"
                        ).format(
                            sql.Identifier(f"ix_{label.lower()}_{property_name}"),
                            sql.Identifier(graph_name),
                            sql.Identifier(label),
                            sql.Literal(json.dumps(property_name)),
                        )
                    )

            for (start_label, edge_label, end_label), source_query in EDGE_QUERIES.items():
                statement = f"project_{edge_label.lower()}"
                edge_properties = (
                    f" {{{CANDIDATE_EDGE_PROPERTIES}}}"
                    if edge_label in SEMANTIC_EDGE_LABELS
                    else ""
                )
                cypher = (
                    f"UNWIND $rows AS row MATCH (a:{start_label}), (b:{end_label}) "
                    "WHERE a.canonical_id = row.start_id AND b.canonical_id = row.end_id "
                    f"CREATE (a)-[:{edge_label}{edge_properties}]->(b)"
                )
                cursor.execute(
                    sql.SQL(
                        "PREPARE {}(agtype) AS SELECT * FROM "
                        "cypher({}, $cypher${}$cypher$, $1) AS (v agtype)"
                    ).format(sql.Identifier(statement), sql.Literal(graph_name), sql.SQL(cypher))
                )
                count = 0
                read_cursor = connection.cursor()
                for batch in _batches(read_cursor, source_query, batch_size):
                    _execute_batch(cursor, statement, batch)
                    count += len(batch)
                read_cursor.close()
                cursor.execute(sql.SQL("DEALLOCATE {}").format(sql.Identifier(statement)))
                counts["edges"][edge_label] = count
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Apache AGE graph from canonical tables")
    parser.add_argument("--graph", default=get_settings().age_graph_name)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(project_graph(args.graph, args.batch_size), indent=2))


if __name__ == "__main__":
    main()
