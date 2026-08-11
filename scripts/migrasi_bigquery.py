"""Migrate every canonical table from PostgreSQL to BigQuery.

    python scripts/migrasi_bigquery.py --full       # mirror, verify, index — one command
    python scripts/migrasi_bigquery.py              # mirror all tables, build graph
    python scripts/migrasi_bigquery.py --verify     # row counts, both sides
    python scripts/migrasi_bigquery.py --graph      # rebuild the graph only
    python scripts/migrasi_bigquery.py --index      # rebuild the embedding index
    python scripts/migrasi_bigquery.py --only plants,equipment

Prefer `--full`. Run as three separate commands, the mirror is only as current as
the operator's memory of the third one, and a half-finished sync fails the way we
least want: quietly, by answering from a stale copy. `--full` stops at the first
step that fails and refuses to index a mirror that did not verify.

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

    if args.full:
        return await jalankan_penuh(args)

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
    hasil = await jalankan_migrasi(only)
    if hasil != 0:
        return hasil

    print("\nJalankan --verify untuk membandingkan jumlah baris kedua sisi,")
    print("lalu --index untuk membangun ulang indeks embedding di dataset ini.")
    print("Atau jalankan --full sekali, yang melakukan ketiganya dan berhenti")
    print("pada langkah pertama yang gagal.")
    return 0


async def jalankan_migrasi(only: tuple[str, ...]) -> int:
    """Copy the canonical tables, and rebuild the graph unless the copy was partial."""
    hasil = await sync.migrate(only=only)

    dimigrasi = [r for r in hasil if not r.skipped]
    total = sum(r.rows for r in dimigrasi)
    for r in dimigrasi:
        print(f"  {r.name:<32} {r.rows:>8,}")
    print(f"\n{len(dimigrasi)} tabel, {total:,} baris.")

    if not only:
        nodes, edge_count = edges.build()
        print(f"\nGraph: {nodes} node, {edge_count} edge, {len(edges.NODE_SOURCES)} label.")

    return 0


async def jalankan_penuh(args: argparse.Namespace) -> int:
    """Mirror, verify, then index — stopping at the first step that fails.

    The order is not a preference. Verification has to sit between the other two
    because indexing reads chunks *from* the mirror: embedding an incomplete copy
    produces an index that describes documents the mirror does not have, and
    nothing downstream can tell that from a good one.

    Every step announces itself, so an operator who walks away knows which one
    stopped and why.
    """
    only = tuple(t.strip() for t in args.only.split(",") if t.strip()) if args.only else ()
    if only:
        print("⚠️ --full mengabaikan --only: sebagian tabel tidak pernah lolos verifikasi.\n")
        only = ()

    print("[1/3] Menyalin tabel kanonik dan membangun graph")
    if await jalankan_migrasi(only) != 0:
        return 1

    print("\n[2/3] Membandingkan jumlah baris kedua sisi")
    if await laporkan_verifikasi() != 0:
        print("\nBerhenti. Indeks TIDAK dibangun di atas mirror yang tidak cocok —")
        print("menjawab dari salinan yang tidak lengkap adalah mode gagal yang diam.")
        return 1

    print("\n[3/3] Membangun ulang indeks embedding")
    if bangun_indeks() != 0:
        return 1

    print("\n✅ Mirror lengkap, terverifikasi, dan terindeks. ARKA_STORE=bigquery siap dipakai.")
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
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--full", action="store_true",
                   help="salin, verifikasi, lalu indeks — berhenti pada kegagalan pertama")
    p.add_argument("--verify", action="store_true", help="bandingkan jumlah baris kedua sisi")
    p.add_argument("--graph", action="store_true", help="bangun ulang node + edge list")
    p.add_argument("--index", action="store_true", help="bangun ulang indeks embedding")
    p.add_argument("--only", default="", help="daftar tabel dipisah koma")
    args = p.parse_args()
    return asyncio.run(jalankan(args))


if __name__ == "__main__":
    sys.exit(main())
