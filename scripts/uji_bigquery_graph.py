"""Prove the production path: cross-plant precedent discovery on BigQuery Graph.

The prototype runs on PostgreSQL + Apache AGE. For a production estate whose
data already lives in BigQuery, the graph layer would move there — and the
question worth answering before promising that is whether it *works*, not
whether it sounds plausible.

What this script establishes, on on-demand pricing with no reservation:

1. `CREATE PROPERTY GRAPH` over the canonical tables
2. `GRAPH_EXPAND` traversal — equipment → failure → symptom / cause
3. The same cross-plant precedent question the local chain answers

Only the last step differs from the local implementation, and only in dialect.
`app/detection/repository.py` is the one file that touches storage; everything
above it works on dataclasses and never learns where the facts came from.

    uv run python scripts/uji_bigquery_graph.py            # export, build, query
    uv run python scripts/uji_bigquery_graph.py --hapus    # remove the dataset
"""

import argparse
import asyncio
import json

from google.cloud import bigquery

PROJECT = "ebco-aihack-amanda"
DATASET = "arka_graph"
LOCATION = "US"

TABEL = (
    "plants",
    "equipment",
    "components",
    "failure_events",
    "failure_symptoms",
    "failure_causes",
    "documents",
    "spare_parts",
    "work_orders",
)


async def ambil_dari_postgres() -> dict[str, list[dict]]:
    """Read the golden path out of the canonical tables."""
    from sqlalchemy import text

    from app.db.session import session_factory

    kueri = {
        "plants": "SELECT canonical_id AS id, name FROM plants",
        "equipment": """
            SELECT e.canonical_id AS id, e.tag_number AS tag, e.model,
                   p.canonical_id AS plant_id, p.name AS plant
            FROM equipment e
            JOIN production_lines l ON l.id = e.production_line_id
            JOIN plants p ON p.id = l.plant_id
        """,
        "failure_events": """
            SELECT f.canonical_id AS id, e.canonical_id AS equipment_id,
                   f.status, f.started_at::date::text AS started_on,
                   f.downtime_minutes, c.component_type
            FROM failure_events f
            JOIN equipment e ON e.id = f.equipment_id
            LEFT JOIN components c ON c.id = f.component_id
        """,
        "failure_symptoms": """
            SELECT f.canonical_id AS failure_id, s.code AS symptom_code
            FROM failure_event_symptoms fs
            JOIN failure_events f ON f.id = fs.failure_event_id
            JOIN symptoms s ON s.id = fs.symptom_id
        """,
        "failure_causes": """
            SELECT f.canonical_id AS failure_id, c.canonical_id AS cause_id, c.name AS cause_name
            FROM failure_event_causes fc
            JOIN failure_events f ON f.id = fc.failure_event_id
            JOIN causes c ON c.id = fc.cause_id
        """,
        "components": """
            SELECT c.canonical_id AS id, c.component_type, e.canonical_id AS equipment_id,
                   p.name AS plant
            FROM components c
            JOIN equipment e ON e.id = c.equipment_id
            JOIN production_lines l ON l.id = e.production_line_id
            JOIN plants p ON p.id = l.plant_id
        """,
        "documents": """
            SELECT d.canonical_id AS id, d.title, d.document_type,
                   ch.page_number, ch.content
            FROM documents d
            JOIN document_versions v ON v.document_id = d.id
            JOIN document_chunks ch ON ch.document_version_id = v.id
        """,
        "spare_parts": """
            SELECT part_number, name, component_type,
                   static_criticality::float8 AS static_criticality,
                   lead_time_weeks, vendor_count, primary_vendor
            FROM spare_parts
        """,
        "work_orders": """
            SELECT w.canonical_id AS id, e.tag_number AS equipment_tag,
                   w.work_order_type, w.status, w.description,
                   w.scheduled_start_at::date::text AS scheduled_on,
                   f.canonical_id AS failure_id
            FROM work_orders w
            JOIN equipment e ON e.id = w.equipment_id
            LEFT JOIN work_order_failure_events wf ON wf.work_order_id = w.id
            LEFT JOIN failure_events f ON f.id = wf.failure_event_id
        """,
    }

    hasil: dict[str, list[dict]] = {}
    async with session_factory() as session:
        for nama, sql in kueri.items():
            rows = (await session.execute(text(sql))).mappings().all()
            hasil[nama] = [dict(r) for r in rows]
    return hasil


def muat_ke_bigquery(data: dict[str, list[dict]]) -> bigquery.Client:
    client = bigquery.Client(project=PROJECT)
    client.create_dataset(
        bigquery.Dataset(f"{PROJECT}.{DATASET}"), exists_ok=True
    )
    for nama, baris in data.items():
        tabel = f"{PROJECT}.{DATASET}.{nama}"
        job = client.load_table_from_json(
            baris,
            tabel,
            job_config=bigquery.LoadJobConfig(
                write_disposition="WRITE_TRUNCATE", autodetect=True
            ),
        )
        job.result()
        print(f"  {nama:18} {len(baris):3} baris")
    return client


def bangun_graph(client: bigquery.Client) -> None:
    """Define the property graph. This runs on on-demand pricing."""
    ddl = f"""
    CREATE OR REPLACE PROPERTY GRAPH {DATASET}.arka_kg
      NODE TABLES (
        {DATASET}.equipment KEY (id)
          LABEL Equipment PROPERTIES (id, tag, model, plant),
        {DATASET}.failure_events KEY (id)
          LABEL FailureEvent PROPERTIES (id, status, started_on)
      )
      EDGE TABLES (
        {DATASET}.failure_events AS terjadi_pada
          KEY (id)
          SOURCE KEY (equipment_id) REFERENCES equipment (id)
          DESTINATION KEY (id) REFERENCES failure_events (id)
          LABEL TERJADI_PADA
      )
    """
    client.query(ddl).result()
    print("  property graph arka_kg dibuat")


def kueri_preseden(client: bigquery.Client) -> list[dict]:
    """Cross-plant precedent, traversed through the graph.

    `GRAPH_EXPAND` walks equipment → failure event; the surrounding SQL joins
    the symptom and cause facts and scores the symptom overlap. That split is
    the honest description: BigQuery's on-demand tier gives traversal, and the
    reasoning stays where it already lives.
    """
    sql = f"""
    WITH graf AS (
      SELECT * FROM GRAPH_EXPAND('{DATASET}.arka_kg')
    ),
    kasus_hidup AS (
      SELECT g.equipment_tag, g.equipment_plant, g.failure_events_id AS failure_id,
             ARRAY_AGG(s.symptom_code ORDER BY s.symptom_code) AS gejala
      FROM graf g
      JOIN {DATASET}.failure_symptoms s ON s.failure_id = g.failure_events_id
      WHERE g.failure_events_status = 'open' AND g.equipment_tag LIKE '%FIL-207%'
      GROUP BY 1, 2, 3
    ),
    preseden AS (
      SELECT g.equipment_plant AS pabrik, g.equipment_tag, g.failure_events_started_on AS tanggal,
             c.cause_name,
             ARRAY_AGG(s.symptom_code ORDER BY s.symptom_code) AS gejala
      FROM graf g
      JOIN {DATASET}.failure_symptoms s ON s.failure_id = g.failure_events_id
      JOIN {DATASET}.failure_causes c ON c.failure_id = g.failure_events_id
      WHERE g.failure_events_status = 'closed'
      GROUP BY 1, 2, 3, 4
    )
    SELECT p.pabrik, p.equipment_tag, p.cause_name,
           ROUND(
             (SELECT COUNT(*) FROM UNNEST(p.gejala) x
              WHERE x IN UNNEST(k.gejala)) / ARRAY_LENGTH(p.gejala), 4
           ) AS symptom_overlap
    FROM preseden p, kasus_hidup k
    WHERE p.pabrik != k.equipment_plant
    ORDER BY symptom_overlap DESC, p.pabrik
    """
    return [dict(r) for r in client.query(sql).result()]


def hapus() -> None:
    client = bigquery.Client(project=PROJECT)
    client.delete_dataset(
        f"{PROJECT}.{DATASET}", delete_contents=True, not_found_ok=True
    )
    print(f"Dataset {DATASET} dihapus.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hapus", action="store_true", help="Hapus dataset uji")
    if parser.parse_args().hapus:
        hapus()
        return

    print("Mengambil jalur emas dari PostgreSQL…")
    data = asyncio.run(ambil_dari_postgres())

    print("Memuat ke BigQuery…")
    client = muat_ke_bigquery(data)

    print("Membangun property graph…")
    bangun_graph(client)

    print("Menanyakan preseden lintas pabrik lewat GRAPH_EXPAND…\n")
    for baris in kueri_preseden(client):
        print(json.dumps(baris, ensure_ascii=False))


if __name__ == "__main__":
    main()
