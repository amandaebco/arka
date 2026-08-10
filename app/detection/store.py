"""Which store answers — chosen once, here, and nowhere else.

Callers import from this module rather than from a backend directly, so moving
between PostgreSQL and BigQuery is a configuration change instead of an edit
across the codebase. The claim that the reasoning layer is storage-agnostic only
holds if exactly one place knows the difference; this is that place.

Selected by `ARKA_STORE`:

    postgres  (default)  PostgreSQL + Apache AGE — the proven local path
    bigquery             BigQuery property graph — the production path

Both return identical dataclasses, and the identical scores were verified on
11 August against the same seeded data.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

BIGQUERY = "bigquery"
POSTGRES = "postgres"


def active_store() -> str:
    """Which backend is configured. Unknown values fall back to PostgreSQL.

    An unrecognised name should not silently reach for the cloud: a typo in an
    environment variable would otherwise change where production data is read
    from, which is not a failure mode worth having.
    """
    nama = (os.getenv("ARKA_STORE") or POSTGRES).strip().lower()
    if nama not in (BIGQUERY, POSTGRES):
        logger.warning("ARKA_STORE=%r not recognised — using %s", nama, POSTGRES)
        return POSTGRES
    return nama


def _backend():
    if active_store() == BIGQUERY:
        from app.detection import bigquery_repository as backend
    else:
        from app.detection import repository as backend
    return backend


@asynccontextmanager
async def session():
    """A session for the active store.

    BigQuery needs none, but yielding `None` keeps every caller written the same
    way regardless of which backend is answering.
    """
    if active_store() == BIGQUERY:
        yield None
        return

    from app.db.session import session_factory

    async with session_factory() as s:
        yield s


async def find_open_cases(s):
    return await _backend().find_open_cases(s)


async def find_historical_cases(s, **kwargs):
    return await _backend().find_historical_cases(s, **kwargs)


async def find_documents(s, **kwargs):
    return await _backend().find_documents(s, **kwargs)


async def find_spare_parts(s, **kwargs):
    return await _backend().find_spare_parts(s, **kwargs)


async def find_next_maintenance(s, equipment_tag: str):
    backend = _backend()
    if active_store() == BIGQUERY:
        return await backend.find_next_maintenance(s, equipment_tag=equipment_tag)
    return await backend.find_next_maintenance(s, equipment_tag)


def load_subsystem_map():
    return _backend().load_subsystem_map()


def group_by_cause(cases, documents=None):
    return _backend().group_by_cause(cases, documents)
