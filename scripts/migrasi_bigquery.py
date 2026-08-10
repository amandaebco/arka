"""Migrate every canonical table from PostgreSQL to BigQuery.

    python scripts/migrasi_bigquery.py              # mirror all tables, build graph
    python scripts/migrasi_bigquery.py --verify     # row counts, both sides
    python scripts/migrasi_bigquery.py --graph      # rebuild the graph only
    python scripts/migrasi_bigquery.py --index      # rebuild the embedding index
    python scripts/migrasi_bigquery.py --only plants,equipment

The target dataset is `arka` by default, not `arka_graph`: the demo still reads
the old flattened copy, and a migration that overwrites the thing it is meant to
replace cannot be rehearsed. Override with `ARKA_BQ_DATASET`.

Verification is not optional politeness. A load job reports success for what it
was handed, so the only way to know the mirror is complete is to count both
sides — the same reasoning that made canonical tables preferable to the AGE
projection in the first place.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.bigquery import config, edges, sync


async def jalankan(args: argparse.Namespace) -> int:
    print(f"Target: {config.dataset_ref()}\n")

    if args.graph:
        nodes, edge_count = edges.build()
        print(f"Graph dibangun: {nodes} node, {edge_count} edge, "
              f"{len(edges.NODE_SOURCES)} label.")
        print("Ditelusuri lewat recursive CTE (app/bigquery/traversal.py), bukan")
        print("GRAPH_EXPAND — fungsi itu menolak jalur konvergen.")
        return 0

    if args.index:
        return bangun_indeks()

    if args.verify:
        return await laporkan_verifikasi()

    only = tuple(t.strip() for t in args.only.split(",") if t.strip()) if args.only else ()
    hasil = await sync.migrate(only=only)

    dimigrasi = [r for r in hasil if not r.skipped]
    total = sum(r.rows for r in dimigrasi)
    for r in dimigrasi:
        print(f"  {r.name:<32} {r.rows:>8,}")
    print(f"\n{len(dimigrasi)} tabel, {total:,} baris.")

    if not only:
        nodes, edge_count = edges.build()
        print(f"\nGraph: {nodes} node, {edge_count} edge, {len(edges.NODE_SOURCES)} label.")

    print("\nJalankan --verify untuk membandingkan jumlah baris kedua sisi,")
    print("lalu --index untuk membangun ulang indeks embedding di dataset ini.")
    return 0


def bangun_indeks() -> int:
    """Re-embed the mirrored document chunks into this dataset.

    Separate from the migration because it is the one step that calls a model
    and costs money. It also has to run *after* the mirror: the chunks it embeds
    are read from BigQuery, so an index built first would embed the old dataset's
    text and then sit beside documents it does not describe.
    """
    from google.cloud import bigquery

    from app.retrieval.vector_store import build_index

    sql = f"""
    SELECT d.canonical_id AS document_id, d.title, d.document_type,
           ch.content, ch.page_number
    FROM {config.table_ref("documents")} d
    JOIN {config.table_ref("document_versions")} v ON v.document_id = d.id
    JOIN {config.table_ref("document_chunks")} ch ON ch.document_version_id = v.id
    WHERE ch.content IS NOT NULL
    ORDER BY d.canonical_id, ch.page_number
    """
    client = bigquery.Client(project=config.project())
    chunks = [dict(r) for r in client.query(sql).result()]
    if not chunks:
        print("Tidak ada potongan dokumen di mirror — jalankan migrasi lebih dulu.")
        return 1

    jumlah = build_index(chunks)
    print(f"{jumlah} potongan dokumen diindeks di {config.dataset_ref()}.")
    print("\n⚠️ Ambang MIN_SIMILARITY=0,60 diukur atas empat dokumen. Kalau korpus")
    print("   ini lebih besar, ukur ulang sebelum mempercayai hasil pencarian.")
    return 0


async def laporkan_verifikasi() -> int:
    baris = await sync.verify()
    beda = [(t, pg, bq) for t, pg, bq in baris if pg != bq]
    for t, pg, bq in baris:
        tanda = " " if pg == bq else "✗"
        print(f" {tanda} {t:<32} postgres {pg:>8,}   bigquery {bq:>8,}")
    if beda:
        print(f"\n{len(beda)} tabel tidak cocok. Mirror belum bisa dipakai sebagai sumber.")
        return 1
    print(f"\n{len(baris)} tabel cocok, {sum(pg for _, pg, _ in baris):,} baris.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify", action="store_true", help="bandingkan jumlah baris kedua sisi")
    p.add_argument("--graph", action="store_true", help="bangun ulang node + edge list")
    p.add_argument("--index", action="store_true", help="bangun ulang indeks embedding")
    p.add_argument("--only", default="", help="daftar tabel dipisah koma")
    args = p.parse_args()
    return asyncio.run(jalankan(args))


if __name__ == "__main__":
    sys.exit(main())
