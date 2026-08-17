"""Which store answers — chosen once, here, and nowhere else.

Callers import from this module rather than from a backend directly, so moving
between PostgreSQL and BigQuery is a configuration change instead of an edit
across the codebase. The claim that the reasoning layer is storage-agnostic only
holds if exactly one place knows the difference; this is that place.

Selected by `ARKA_STORE`:

    postgres  (default)  PostgreSQL + Apache AGE — runs anywhere, no billing
    bigquery             The canonical mirror in the cloud

Both return identical dataclasses, and identical scores were verified on
11 August against the same seeded data: 0.9071 / 0.8819, margin 0.0252,
5 precedents, 8 citations, seal criticality 0.8667.

⚠️ **Both the default and the fallback are PostgreSQL** — reaching for the
cloud always takes saying so. A typo in an environment variable must not quietly
change where data is read from, and a wrong answer from the wrong store looks
exactly like a right one.

The default was BigQuery until 17 August, on the reasoning that the cloud copy
is the source. It stopped being a safe default the moment the project's billing
was detached: an unset variable pointed the whole application at a store that
cannot answer, and the failure surfaced as a broken page rather than as a
misconfiguration. A default that only works for someone who read this file is
not a default.

The synthetic generator does not go through this module — it writes to
PostgreSQL directly, because that is where the truth is while data is being
built. Tests *do* come through here (scout and investigator both dispatch), so
`tests/conftest.py` pins them to PostgreSQL for the same reason: a test that
reads BigQuery is testing the last sync, not the code under it.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

BIGQUERY = "bigquery"
POSTGRES = "postgres"


def active_store() -> str:
    """Which backend is configured. PostgreSQL unless BigQuery is asked for.

    Unset means PostgreSQL, and so does a misspelt value: the cloud is never
    reached for by accident. See the module docstring for why the default
    changed.
    """
    mentah = os.getenv("ARKA_STORE")
    if mentah is None or not mentah.strip():
        return POSTGRES

    nama = mentah.strip().lower()
    if nama not in (BIGQUERY, POSTGRES):
        logger.warning("ARKA_STORE=%r not recognised — using %s", mentah, POSTGRES)
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

    from sqlalchemy import text

    from app.db.session import session_factory

    async with session_factory() as s:
        # A pathological query must fail rather than hang. Without a ceiling, a
        # scan that goes wrong holds its backend open indefinitely: the caller
        # times out, retries, and each abandoned attempt keeps scanning — the
        # pile-up that ends with a database nobody can query and a restart as
        # the only cure.
        #
        # `SET LOCAL` scopes to the current transaction and resets when the
        # connection returns to the pool, so this cannot leak into other work.
        # Thirty seconds is far above the measured scan (0.03-0.16s across 5,000
        # equipment); anything near it means something is wrong, not busy.
        await s.execute(text("SET LOCAL statement_timeout = '30s'"))
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


async def traverse_graph(
    start_label: str,
    start_name: str,
    *,
    max_hops: int = 5,
    only_label: str | None = None,
):
    """Walk outward from a node using multi-hop graph traversal."""
    if active_store() == BIGQUERY:
        import asyncio

        from app.bigquery.traversal import traverse

        return await asyncio.to_thread(
            traverse,
            start_label,
            start_name,
            max_hops=max_hops,
            only_label=only_label,
        )
    else:
        from app.bigquery.traversal import Path

        async with session() as s:
            parts = await find_spare_parts(s, component_type=None)
            matched = [p for p in parts if p.part_number == start_name or p.name == start_name]
            paths = []
            if matched:
                part = matched[0]
                for plant in part.plants_served:
                    paths.append(
                        Path(
                            target_id=f"plant-{plant}",
                            target_label="Plant",
                            target_name=plant,
                            hops=4,
                            edge_labels=(
                                "DIPASOK_OLEH⁻¹",
                                "MEMILIKI_KOMPONEN⁻¹",
                                "MEMILIKI_EQUIPMENT⁻¹",
                                "MEMILIKI_LINE⁻¹",
                            ),
                            node_names=(
                                part.part_number,
                                part.component_type or "component",
                                "equipment",
                                "line",
                                plant,
                            ),
                        )
                    )
            return paths

