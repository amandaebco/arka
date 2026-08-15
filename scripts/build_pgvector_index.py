"""Embed the document chunks held in PostgreSQL into the pgvector index.

The BigQuery counterpart lives in `scripts/migrasi_bigquery.py --index`. This one
reads the same chunks from the canonical tables instead of from a mirror, which
removes the failure that mirror had: no copy means no copy going stale.

    uv run python scripts/build_pgvector_index.py

Costs one embedding call per chunk, so it is a separate step rather than part of
a migration. Re-running is safe: the table is replaced, never appended to.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.retrieval.embedding import active_model
from app.retrieval.pgvector_store import build_index

logging.basicConfig(level=logging.INFO, format="%(message)s")

SQL = """
SELECT d.canonical_id AS document_id, d.title, d.document_type,
       ch.content, ch.page_number
FROM documents d
JOIN document_versions v ON v.document_id = d.id
JOIN document_chunks ch ON ch.document_version_id = v.id
WHERE ch.content IS NOT NULL
ORDER BY d.canonical_id, ch.page_number
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count the chunks without calling the embedding model.",
    )
    args = parser.parse_args()

    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        chunks = [dict(r._mapping) for r in conn.execute(text(SQL))]

    if not chunks:
        print("No document chunks to index.", file=sys.stderr)
        raise SystemExit(1)

    documents = len({c["document_id"] for c in chunks})
    print(f"{len(chunks)} chunks across {documents} documents.")

    if args.dry_run:
        print(f"Dry run — {active_model()} was not called.")
        return

    indexed = build_index(chunks)
    print(f"Indexed {indexed} chunks with {active_model()}.")


if __name__ == "__main__":
    main()
