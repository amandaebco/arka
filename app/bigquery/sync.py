"""Copy every canonical table from PostgreSQL into BigQuery.

This is the migration, not a steady-state pipeline. It runs while PostgreSQL is
still where the synthetic generator writes; when BigQuery becomes the only
source, the generator writes there and this module stops being needed.

`WRITE_TRUNCATE` per table makes the run idempotent: the dataset after a run
depends on the source, never on how many times it has been run. The failure mode
recorded in `session.md` — a stale copy that answers without error — is only
avoided by re-running this whenever the golden path changes, which is why
`verify()` reports counts on both sides rather than trusting a load job's
success.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from google.cloud import bigquery
from sqlalchemy import func, select
from sqlalchemy.schema import Table

from app.bigquery import config
from app.bigquery.schema import all_tables, schema_for, serialise_row

logger = logging.getLogger(__name__)

# Rows per load job. Large enough that 38 tables are a handful of jobs, small
# enough that a single request stays well inside BigQuery's limits.
BATCH = 5_000


@dataclass(frozen=True)
class TableResult:
    """What one table's migration did, for the report at the end."""

    name: str
    rows: int
    skipped: bool = False


def client() -> bigquery.Client:
    return bigquery.Client(project=config.project())


def ensure_dataset(bq: bigquery.Client) -> None:
    ds = bigquery.Dataset(config.dataset_ref())
    ds.location = "US"
    bq.create_dataset(ds, exists_ok=True)


async def read_table(session, table: Table) -> list[dict]:
    """Every row of one table, as JSON-ready dicts."""
    rows = (await session.execute(select(table))).mappings().all()
    return [serialise_row(dict(r)) for r in rows]


def load_table(bq: bigquery.Client, table: Table, rows: list[dict]) -> None:
    """Replace one BigQuery table with these rows.

    An empty source table is still created, with its schema. A missing table and
    an empty one produce very different errors downstream, and only one of them
    points at the real problem.
    """
    target = f"{config.dataset_ref()}.{table.name}"
    schema = schema_for(table)
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    if not rows:
        bq.create_table(bigquery.Table(target, schema=schema), exists_ok=True)
        bq.query(f"TRUNCATE TABLE `{target}`").result()
        return

    for start in range(0, len(rows), BATCH):
        chunk = rows[start : start + BATCH]
        config_for_chunk = job_config
        if start:
            # Only the first chunk truncates; the rest append to it.
            config_for_chunk = bigquery.LoadJobConfig(
                schema=schema,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            )
        bq.load_table_from_json(chunk, target, job_config=config_for_chunk).result()


async def migrate(only: tuple[str, ...] = ()) -> list[TableResult]:
    """Mirror the canonical tables into BigQuery.

    Args:
        only: Table names to migrate. Empty means all of them.

    Returns:
        One result per table, in dependency order.
    """
    from app.db.session import session_factory

    bq = client()
    ensure_dataset(bq)

    hasil: list[TableResult] = []
    async with session_factory() as session:
        for table in all_tables():
            if only and table.name not in only:
                hasil.append(TableResult(table.name, 0, skipped=True))
                continue
            rows = await read_table(session, table)
            await asyncio.to_thread(load_table, bq, table, rows)
            logger.info("%s: %d rows", table.name, len(rows))
            hasil.append(TableResult(table.name, len(rows)))
    return hasil


async def verify() -> list[tuple[str, int, int]]:
    """Row counts on both sides, table by table.

    A load job reporting success only says BigQuery accepted what it was given.
    It says nothing about whether it was given everything, which is the question
    that matters when the copy is about to become the source.

    Returns:
        `(table, postgres_rows, bigquery_rows)` for every table.
    """
    from app.db.session import session_factory

    bq = client()
    hasil: list[tuple[str, int, int]] = []
    async with session_factory() as session:
        for table in all_tables():
            pg_count = (await session.execute(select(func.count()).select_from(table))).scalar_one()
            sql = f"SELECT COUNT(*) AS n FROM `{config.dataset_ref()}.{table.name}`"
            rows = await asyncio.to_thread(lambda q=sql: list(bq.query(q).result()))
            hasil.append((table.name, int(pg_count), int(rows[0].n)))
    return hasil
