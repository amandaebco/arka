"""Semantic search over document chunks, stored and searched in BigQuery.

Maintenance records are written by dozens of people over years with no shared
vocabulary. An engineer types "produk merembes waktu pengisian"; the record says
"kebocoran produk di kepala pengisi". Not one word matches, and keyword search
returns nothing — which is how the most valuable old records stay unreachable.

`VECTOR_SEARCH` compares stored vectors and needs no remote-model connection, so
this runs on plain BigQuery access. Embeddings are produced by
`app.retrieval.embedding` at load time.

Traceability: spec 003 FR-001, FR-004, FR-005 · tasks T011, T012.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google.cloud import bigquery

from app.bigquery import config
from app.retrieval.embedding import DIMENSION, embed, embed_one

logger = logging.getLogger(__name__)

# Project and dataset resolve through `app.bigquery.config` so the embedding
# index lands beside the canonical mirror rather than in a dataset of its own.
# Splitting them would mean a question could match a chunk whose case no longer
# exists — the copy-goes-stale failure in a new costume.
TABLE = "document_chunks_embedded"

# Below this similarity a hit is noise dressed as an answer. Returning nothing is
# a valid outcome; returning the least-bad match is how a system starts lying
# confidently.
#
# Measured on a 54-document, 104-chunk corpus, 11 August, `gemini-embedding-2`:
#
#     in-domain   0.7703  "apa penyebab torsi kepala pengisi menyimpang?"
#                 0.7542  "seal bocor di mesin filler"
#                 0.7483  "sabuk konveyor aus tidak merata"
#                 0.6418  "kenapa arus motor mixer naik?"
#                 0.6379  "kardus terlepas dari lengan robot"
#                 0.6359  "kenapa produk merembes saat pengisian?"
#                 0.5889  "label miring saat kecepatan tinggi"   ← below the floor
#     out-domain  0.5896  "harga saham minggu ini"               ← above that one
#                 0.5335  "jadwal kereta ke bandung"
#                 0.4834  "resep rendang padang"
#
# At 0.60 this admits six of seven in-domain questions and rejects all three
# nonsense ones — nine of ten correct. Usable, and honestly described as usable
# rather than as calibrated.
#
# ⚠️ The bands still **touch**: the weakest in-domain question sits 0.0007 below
# the strongest nonsense one. No threshold separates them perfectly, and one
# more sample either way would change which side each lands on. Do not present
# 0.60 as a boundary derived from the data; it is a precision-over-recall
# choice, and the trade is silence rather than a confident wrong citation.
#
# The gap closed in two measured steps, both worth knowing:
#   -0.0552  four documents, one chunk each
#   -0.0383  chunked (app/retrieval/chunking.py) — chunks match one idea
#   -0.0007  boilerplate varied per machine type — fifty near-identical opening
#            chunks had been flattening the corpus, so the measurement had been
#            measuring template repetition rather than retrieval
#
# Both steps improved the corpus, not the model. That is the lesson: a
# similarity floor reports the corpus it was measured on, and the fix for a bad
# floor is usually better documents, not a better number.
#
# The remaining fix is a relative test — margin between the top hit and the rest,
# or a rerank — because "is this the best match" and "is this a good match" are
# different questions and one cosine floor answers only the first.
#
# ---------------------------------------------------------------------------
#
# Measured again on the same corpus, 15 August, `text-embedding-3-large`, after
# the index moved to pgvector. Same ten questions, same documents, different
# model — and the bands that touched under Gemini now separate cleanly:
#
#     in-domain   0.6099  "seal bocor di mesin filler"
#                 0.5863  "apa penyebab torsi kepala pengisi menyimpang?"
#                 0.5689  "sabuk konveyor aus tidak merata"
#                 0.5533  "label miring saat kecepatan tinggi"
#                 0.5463  "kenapa arus motor mixer naik?"
#                 0.5175  "kardus terlepas dari lengan robot"
#                 0.4736  "kenapa produk merembes saat pengisian?"   ← weakest
#     out-domain  0.3366  "harga saham minggu ini"                   ← strongest
#                 0.2401  "jadwal kereta ke bandung"
#                 0.2238  "resep rendang padang"
#
# Gap: +0.1371, against -0.0007 under `gemini-embedding-2`. Every in-domain
# question now outranks every nonsense one, so 0.40 sits roughly midway with
# ~0.07 of room on each side and admits all seven while rejecting all three.
#
# The absolute numbers are lower than Gemini's and that means nothing on its
# own: cosine values are not comparable across models. Only the separation is.
#
# ⚠️ A threshold belongs to a (model, corpus) pair, never to the system. The map
# below exists so swapping `EMBED_PROVIDER` cannot silently keep a floor that was
# measured against different vectors — the failure that leaves search working,
# plausible, and wrong.
MIN_SIMILARITY_BY_MODEL = {
    "gemini-embedding-2": 0.60,
    "text-embedding-3-large": 0.40,
}


def min_similarity() -> float:
    """The floor measured for whichever model is producing vectors now."""
    from app.retrieval.embedding import active_model

    model = active_model()
    if model not in MIN_SIMILARITY_BY_MODEL:  # pragma: no cover — guards a model swap
        raise ValueError(
            f"No similarity floor measured for {model!r}. Measure it against the "
            "corpus before trusting retrieval; see the table above."
        )
    return MIN_SIMILARITY_BY_MODEL[model]


def min_similarity_candidate() -> float:
    """Relaxed floor for candidate retrieval, before reranking.

    Kept proportional to the measured floor rather than fixed: a constant 0.50
    sat *above* the 0.40 floor once the model changed, which silently discarded
    every candidate the reranker was supposed to judge.
    """
    return round(min_similarity() - 0.10, 4)


@dataclass(frozen=True)
class SemanticHit:
    """One chunk that matched, with the distance that earned its rank."""

    document_id: str
    title: str
    document_type: str
    content: str
    page_number: int | None
    similarity: float


def _client() -> bigquery.Client:
    return bigquery.Client(project=config.project())


def build_index(chunks: list[dict]) -> int:
    """Embed document chunks and store them for search.

    Args:
        chunks: Each with `document_id`, `title`, `document_type`, `content`,
            and optionally `page_number`.

    Returns:
        How many chunks were indexed.
    """
    if not chunks:
        return 0

    vectors = embed([c["content"] for c in chunks])
    rows = [
        {**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    client = _client()
    schema = [
        bigquery.SchemaField("document_id", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("document_type", "STRING"),
        bigquery.SchemaField("content", "STRING"),
        bigquery.SchemaField("page_number", "INTEGER"),
        bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
    ]
    job = client.load_table_from_json(
        rows,
        f"{config.dataset_ref()}.{TABLE}",
        job_config=bigquery.LoadJobConfig(
            schema=schema, write_disposition="WRITE_TRUNCATE"
        ),
    )
    job.result()
    logger.info("indexed %d chunks", len(rows))
    return len(rows)


def search(
    question: str, limit: int = 5, *, apply_rerank: bool = True
) -> list[SemanticHit]:
    """Find chunks whose meaning matches the question.

    Fetches candidate hits from VECTOR_SEARCH, then applies the reranker layer
    (composite similarity + keyword overlap + relative margin filtering) when
    `apply_rerank=True`.
    """
    from app.retrieval.reranker import rerank_hits

    vector = embed_one(question)
    if len(vector) != DIMENSION:  # pragma: no cover — guards a model swap
        raise ValueError(f"embedding dimension {len(vector)} != stored {DIMENSION}")

    candidate_k = max(limit * 2, 10)
    floor = min_similarity()
    floor_candidate = min_similarity_candidate()
    sql = f"""
    SELECT base.document_id, base.title, base.document_type, base.content,
           base.page_number, 1 - distance AS similarity
    FROM VECTOR_SEARCH(
      TABLE `{config.dataset_ref()}.{TABLE}`, 'embedding',
      (SELECT @q AS embedding),
      top_k => @k, distance_type => 'COSINE'
    )
    ORDER BY similarity DESC
    """
    job = _client().query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("q", "FLOAT64", vector),
                bigquery.ScalarQueryParameter("k", "INT64", candidate_k),
            ]
        ),
    )
    hits = [
        SemanticHit(
            document_id=r.document_id,
            title=r.title,
            document_type=r.document_type,
            content=r.content,
            page_number=r.page_number,
            similarity=round(float(r.similarity), 4),
        )
        for r in job.result()
        if float(r.similarity) >= floor_candidate
    ]

    if apply_rerank:
        kept = rerank_hits(question, hits)[:limit]
    else:
        kept = [h for h in hits if h.similarity >= floor][:limit]

    logger.info("semantic search kept %d of %d hits", len(kept), len(hits))
    return kept
