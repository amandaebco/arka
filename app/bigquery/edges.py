"""The knowledge graph as an edge list, because `GRAPH_EXPAND` cannot walk one.

BigQuery offers two ways to traverse a property graph, and on-demand pricing
gets neither of the ones this system needs. Measured on 11 August:

* `GRAPH … MATCH …` — full GQL, arbitrary hops — demands an Enterprise
  reservation. That cost was declined, and declining it is still right.
* `GRAPH_EXPAND(...)` — available on-demand, and not a traversal function at
  all. It refuses more than ten node tables, requires the graph to funnel into a
  single sink, and rejects convergent paths outright:

      The subgraph reachable from start node 'failure_events' contains a
      convergent path involving node 'equipment'. This structure is not
      supported.

  Equipment is reachable both directly and through its components, so this
  graph converges by construction. No amount of trimming fixes that — it is
  what the domain looks like.

So the graph is stored as an edge list and walked with a recursive CTE, which
on-demand BigQuery supports without qualification. That buys arbitrary depth,
cycle protection, and the full path as data rather than as a widening row.

`graph_edges` is generated from the mirrored tables and holds nothing that is
not already a foreign key — except `DIPASOK_OLEH`, where components and spare
parts relate through `component_type` rather than an id. That relationship is
real and was previously a join; expressing it as an edge does not invent it.
"""

from __future__ import annotations

import logging

from google.cloud import bigquery

from app.bigquery import config

logger = logging.getLogger(__name__)

EDGE_TABLE = "graph_edges"
NODE_TABLE = "graph_nodes"

# Node label → (mirrored table, the column a human would read it by).
NODE_SOURCES: dict[str, tuple[str, str]] = {
    "Plant": ("plants", "name"),
    "ProductionLine": ("production_lines", "name"),
    "Equipment": ("equipment", "tag_number"),
    "Component": ("components", "component_type"),
    "FailureEvent": ("failure_events", "title"),
    "Symptom": ("symptoms", "name"),
    "Cause": ("causes", "name"),
    "FailureMode": ("failure_modes", "name"),
    "Damage": ("damages", "damage_type"),
    "SparePart": ("spare_parts", "part_number"),
    "WorkOrder": ("work_orders", "canonical_id"),
    # `activity_code`, bukan `activity_type`: jalur adalah keluaran yang dibaca
    # manusia, dan tiga langkah yang semuanya bernama "penggantian" tidak
    # memberi tahu pekerjaan mana yang dimaksud.
    "MaintenanceActivity": ("maintenance_activities", "activity_code"),
    "Technician": ("technicians", "name"),
}

# (table the relationship lives in, source column, source label,
#  target column, target label, edge label)
#
# Direction is the direction of explanation, not of the foreign key. A failure
# event carries `equipment_id`, but the sentence a reader wants is "this
# equipment suffered this failure", so the edge runs Equipment → FailureEvent.
EDGE_SOURCES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("production_lines", "plant_id", "Plant", "id", "ProductionLine", "MEMILIKI_LINE"),
    ("equipment", "production_line_id", "ProductionLine", "id", "Equipment",
     "MEMILIKI_EQUIPMENT"),
    ("components", "equipment_id", "Equipment", "id", "Component", "MEMILIKI_KOMPONEN"),
    ("failure_events", "equipment_id", "Equipment", "id", "FailureEvent", "MENGALAMI"),
    ("failure_events", "component_id", "Component", "id", "FailureEvent", "TERDAMPAK"),
    ("failure_event_symptoms", "failure_event_id", "FailureEvent", "symptom_id", "Symptom",
     "MENUNJUKKAN"),
    ("failure_event_causes", "failure_event_id", "FailureEvent", "cause_id", "Cause",
     "DISEBABKAN_OLEH"),
    ("failure_event_failure_modes", "failure_event_id", "FailureEvent", "failure_mode_id",
     "FailureMode", "BERMODE"),
    ("damages", "failure_event_id", "FailureEvent", "id", "Damage", "MENIMBULKAN"),
    ("damages", "component_id", "Component", "id", "Damage", "MERUSAK"),
    ("work_orders", "equipment_id", "Equipment", "id", "WorkOrder", "DIJADWALKAN_PADA"),
    ("work_order_failure_events", "work_order_id", "WorkOrder", "failure_event_id",
     "FailureEvent", "MENANGANI"),
    ("maintenance_activities", "work_order_id", "WorkOrder", "id", "MaintenanceActivity",
     "AKTIVITAS"),
    ("activity_spare_parts", "activity_id", "MaintenanceActivity", "spare_part_id", "SparePart",
     "MEMAKAI"),
    ("activity_technicians", "activity_id", "MaintenanceActivity", "technician_id", "Technician",
     "DIKERJAKAN_OLEH"),
    # component_type, expressed as edges. Built by `_derived_sql` below because
    # it is the one relationship with no id to follow.
    ("component_spare_parts", "component_id", "Component", "spare_part_id", "SparePart",
     "DIPASOK_OLEH"),
)

DERIVED_TABLE = "component_spare_parts"


def _derived_sql() -> str:
    """Components and the spare parts that fit them, paired by component type."""
    return f"""
    CREATE OR REPLACE TABLE {config.table_ref(DERIVED_TABLE)} AS
    SELECT c.id AS component_id, p.id AS spare_part_id, c.component_type
    FROM {config.table_ref("components")} c
    JOIN {config.table_ref("spare_parts")} p ON p.component_type = c.component_type
    """


def _nodes_sql() -> str:
    """Every node, with the label and the name a reader recognises it by."""
    bagian = [
        f"SELECT CAST(id AS STRING) AS id, '{label}' AS label, "
        f"CAST({column} AS STRING) AS name FROM {config.table_ref(table)}"
        for label, (table, column) in NODE_SOURCES.items()
    ]
    return (
        f"CREATE OR REPLACE TABLE {config.table_ref(NODE_TABLE)} AS\n"
        + "\nUNION ALL\n".join(bagian)
    )


def _edges_sql() -> str:
    """Every relationship, in one shape.

    Rows where either end is null are dropped: an optional foreign key that was
    never filled is an absent relationship, and carrying it as an edge to
    nowhere would make traversal depth meaningless.
    """
    bagian = [
        f"SELECT CAST({src_col} AS STRING) AS source_id, '{src_label}' AS source_label, "
        f"CAST({dst_col} AS STRING) AS target_id, '{dst_label}' AS target_label, "
        f"'{edge_label}' AS edge_label FROM {config.table_ref(table)} "
        f"WHERE {src_col} IS NOT NULL AND {dst_col} IS NOT NULL"
        for table, src_col, src_label, dst_col, dst_label, edge_label in EDGE_SOURCES
    ]
    return (
        f"CREATE OR REPLACE TABLE {config.table_ref(EDGE_TABLE)} AS\n"
        + "\nUNION ALL\n".join(bagian)
    )


def build(bq: bigquery.Client | None = None) -> tuple[int, int]:
    """Rebuild the derived pairs, the node table, and the edge list.

    Returns:
        `(nodes, edges)` — how many rows each table now holds.
    """
    bq = bq or bigquery.Client(project=config.project())
    bq.query(_derived_sql()).result()
    bq.query(_nodes_sql()).result()
    bq.query(_edges_sql()).result()

    def hitung(nama: str) -> int:
        sql = f"SELECT COUNT(*) AS n FROM {config.table_ref(nama)}"
        return int(list(bq.query(sql).result())[0].n)

    nodes, edges = hitung(NODE_TABLE), hitung(EDGE_TABLE)
    logger.info("graph: %d nodes, %d edges", nodes, edges)
    return nodes, edges
