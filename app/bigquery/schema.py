"""The PostgreSQL schema, expressed as BigQuery schemas.

Derived from SQLAlchemy metadata rather than written out by hand. Thirty-eight
tables transcribed manually would be thirty-eight chances to mistype a column,
and the mistake would not surface as an error — it would surface as a column
that silently arrives empty. Generating from the same metadata the ORM uses
means the mirror cannot drift from the model without the generation failing.

Column names, nullability, and order are preserved exactly. This is a mirror,
not a projection: the flattening that `scripts/uji_bigquery_graph.py` does
belongs to a query, not to storage.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from google.cloud import bigquery
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import Column, Table

from app.models.base import Base

# SQLAlchemy type → BigQuery type. Checked most-specific first, because
# `Uuid` and `Date` both answer to broader base classes.
_TYPE_MAP: tuple[tuple[type, str], ...] = (
    (Uuid, "STRING"),
    (JSONB, "JSON"),
    (DateTime, "TIMESTAMP"),
    (Date, "DATE"),
    (Boolean, "BOOL"),
    (Integer, "INT64"),
    (Numeric, "NUMERIC"),
    (Text, "STRING"),
    (String, "STRING"),
)


class UnmappedColumnType(RuntimeError):
    """A column type with no BigQuery equivalent.

    Raised rather than defaulted to STRING: a column nobody planned for is a
    column nobody has checked the semantics of, and stringifying it would hide
    that behind data that looks fine.
    """


def bigquery_type(column: Column) -> str:
    for sa_type, bq_type in _TYPE_MAP:
        if isinstance(column.type, sa_type):
            return bq_type
    raise UnmappedColumnType(
        f"{column.table.name}.{column.name}: no BigQuery type for {column.type!r}"
    )


def schema_for(table: Table) -> list[bigquery.SchemaField]:
    """BigQuery schema for one table, in the column order of the model.

    Every field is NULLABLE regardless of what PostgreSQL enforces. BigQuery has
    no foreign keys and does not check constraints; declaring REQUIRED would only
    turn a data problem into a load failure partway through, leaving the dataset
    half-written. PostgreSQL remains the place integrity is enforced.
    """
    return [
        bigquery.SchemaField(c.name, bigquery_type(c), mode="NULLABLE") for c in table.columns
    ]


def all_tables() -> list[Table]:
    """Every mapped table, in dependency order.

    `sorted_tables` orders parents before children. BigQuery does not care, but
    a deterministic order makes a partial run reproducible and its log readable.
    """
    return list(Base.metadata.sorted_tables)


def serialise(value: Any) -> Any:
    """One Python value, as the JSON loader expects it.

    NUMERIC arrives as a string on purpose. Routing a `Decimal` through a float
    would round it, and `static_criticality` is a number ARKA publishes a
    difference against — the one place a silent rounding would be visible in an
    argument rather than in a log.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return value


def serialise_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: serialise(v) for k, v in row.items()}
