"""Direct BigQuery ingestion connector for canonical tables.

Provides batch load capabilities directly to BigQuery canonical tables,
bypassing local PostgreSQL when running in direct GCP production mode.
"""

from __future__ import annotations

import logging
from typing import Any

from google.cloud import bigquery

from app.bigquery import config, edges

logger = logging.getLogger(__name__)


def _client() -> bigquery.Client:
    return bigquery.Client(project=config.project())


def load_table_records(table_name: str, records: list[dict[str, Any]]) -> int:
    """Load a list of dictionary records into a BigQuery canonical table.

    Args:
        table_name: Canonical table name (e.g. 'work_orders', 'failure_events').
        records: List of dictionary records to insert.

    Returns:
        Number of records loaded.
    """
    if not records:
        return 0

    client = _client()
    table_id = f"{config.dataset_ref()}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=True,
    )

    job = client.load_table_from_json(records, table_id, job_config=job_config)
    job.result()
    logger.info("ingested %d records into %s", len(records), table_id)
    return len(records)


def ingest_canonical_dataset(
    dataset_records: dict[str, list[dict[str, Any]]],
    *,
    rebuild_graph: bool = True,
) -> dict[str, int]:
    """Ingest a complete dataset map into BigQuery and rebuild property graph.

    Args:
        dataset_records: Map of table_name -> list of records.
        rebuild_graph: Whether to rebuild graph_nodes and graph_edges afterwards.

    Returns:
        Summary map of table_name -> count of ingested records.
    """
    counts = {}
    for table_name, records in dataset_records.items():
        count = load_table_records(table_name, records)
        counts[table_name] = count

    if rebuild_graph:
        node_count, edge_count = edges.build()
        counts["_graph_nodes"] = node_count
        counts["_graph_edges"] = edge_count
        logger.info("rebuilt graph: %d nodes, %d edges", node_count, edge_count)

    return counts
