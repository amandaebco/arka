"""Semantic search over document chunks, stored and searched in BigQuery.

Maintenance records are written by dozens of people over years with no shared
vocabulary. An engineer types "produk merembes waktu pengisian"; the record says
"kebocoran produk di kepala pengisi". Not one word matches, and keyword search
returns nothing — which is how the most valuable old records stay unreachable.

`VECTOR_SEARCH` compares stored vectors and needs no remote-model connection, so
this runs on plain BigQuery access. Embeddings are produced by
`app.retrieval.embedding` at load time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google.cloud import bigquery

from app.retrieval.embedding import DIMENSION, embed, embed_one

logger = logging.getLogger(__name__)

PROJECT = "ebco-aihack-amanda"
DATASET = "arka_graph"
TABLE = "document_chunks_embedded"

# Below this similarity a hit is noise dressed as an answer. Returning nothing is
# a valid outcome; returning the least-bad match is how a system starts lying
# confidently.
#
# Calibrated by measurement on 11 August, not chosen by feel. In-domain questions
# phrased with entirely different words scored 0.61–0.72; an out-of-domain
# question ("harga saham minggu ini") still reached 0.56, because a 3072-dimension
# model over a four-document corpus leaves little room between everything.
#
# ⚠️ This number is a property of the corpus, not of the model. It must be
# re-measured when the document estate grows — a threshold tuned on four
# documents will not hold on four thousand.
MIN_SIMILARITY = 0.60


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
    return bigquery.Client(project=PROJECT)


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
        f"{PROJECT}.{DATASET}.{TABLE}",
        job_config=bigquery.LoadJobConfig(
            schema=schema, write_disposition="WRITE_TRUNCATE"
        ),
    )
    job.result()
    logger.info("indexed %d chunks", len(rows))
    return len(rows)


def search(question: str, limit: int = 5) -> list[SemanticHit]:
    """Find chunks whose meaning matches the question.

    Results below `MIN_SIMILARITY` are dropped rather than returned with a low
    score, because a ranked list invites the reader to trust its top entry.
    """
    vector = embed_one(question)
    if len(vector) != DIMENSION:  # pragma: no cover — guards a model swap
        raise ValueError(f"embedding dimension {len(vector)} != stored {DIMENSION}")

    sql = f"""
    SELECT base.document_id, base.title, base.document_type, base.content,
           base.page_number, 1 - distance AS similarity
    FROM VECTOR_SEARCH(
      TABLE `{PROJECT}.{DATASET}.{TABLE}`, 'embedding',
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
                bigquery.ScalarQueryParameter("k", "INT64", limit),
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
    ]
    kept = [h for h in hits if h.similarity >= MIN_SIMILARITY]
    logger.info("semantic search kept %d of %d hits", len(kept), len(hits))
    return kept
