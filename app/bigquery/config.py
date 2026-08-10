"""Where the BigQuery data lives — resolved once, here.

Hard-coded project and dataset names were fine while BigQuery held a test copy.
Once it becomes the source of record, the names have to be overridable: a
migration that can only ever write to one dataset cannot be rehearsed before it
is run for real.

    ARKA_BQ_PROJECT   defaults to the hackathon project
    ARKA_BQ_DATASET   defaults to `arka` — the canonical mirror

`arka_graph` is deliberately *not* the default. That dataset holds the flattened
nine-table copy built by `scripts/uji_bigquery_graph.py`, and the demo still
reads from it. Writing the canonical mirror somewhere else means the migration
can be built and verified without the running demo changing underneath it.
"""

from __future__ import annotations

import os

DEFAULT_PROJECT = "ebco-aihack-amanda"
DEFAULT_DATASET = "arka"


def project() -> str:
    return os.getenv("ARKA_BQ_PROJECT") or DEFAULT_PROJECT


def dataset() -> str:
    return os.getenv("ARKA_BQ_DATASET") or DEFAULT_DATASET


def dataset_ref() -> str:
    """`project.dataset`, for DDL that cannot take a client default."""
    return f"{project()}.{dataset()}"


def table_ref(name: str) -> str:
    """Fully qualified and backquoted, ready to drop into a query."""
    return f"`{project()}.{dataset()}.{name}`"
