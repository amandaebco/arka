"""Semantic search over document chunks, stored and searched in PostgreSQL.

The BigQuery twin of this module (`app.retrieval.vector_store`) is the original;
this one exists so the retrieval layer survives without GCP. Both answer the
same question with the same contract, and the thresholds live in one place —
imported from there rather than copied, because two copies of a calibrated
number drift apart in exactly the way that stays invisible until it matters.

pgvector's `<=>` operator returns cosine *distance*, so similarity is `1 -
distance`, matching what `VECTOR_SEARCH` reports as `1 - distance` too. The two
backends therefore rank identically on identical vectors.

⚠️ No ANN index backs this table. pgvector caps HNSW and IVFFlat at 2,000
dimensions while `gemini-embedding-2` returns 3,072, so every query is a
sequential scan. At 104 chunks that is microseconds. At tens of thousands it
would not be, and the answer then is a smaller embedding, not an index.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings
from app.retrieval.embedding import DIMENSION, active_model, embed, embed_one
from app.retrieval.vector_store import (
    SemanticHit,
    min_similarity,
    min_similarity_candidate,
)

logger = logging.getLogger(__name__)

TABLE = "document_chunks_embedded"


@lru_cache
def _engine() -> Engine:
    """A synchronous engine, because the caller is synchronous.

    `app.db.session` is async throughout, but `retrieve()` in
    `app.retrieval.graphrag` is not, and the BigQuery twin this module replaces
    is not either. Driving the async engine from here would mean an event loop
    inside a sync call — the deadlock that only shows up under load.
    """
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _literal(vector: list[float]) -> str:
    """Render a vector the way pgvector parses it.

    Passed as a bound parameter without the pgvector adapter registered, a
    Python list arrives as a Postgres array and the cast fails. The literal
    form is unambiguous.
    """
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def build_index(chunks: list[dict]) -> int:
    """Embed document chunks and store them for search.

    Replaces the whole table rather than appending: an index that mixes two
    models cannot be told apart from a healthy one, because the search still
    succeeds and every distance still looks plausible.

    Args:
        chunks: Each with `document_id`, `title`, `document_type`, `content`,
            and optionally `page_number`.

    Returns:
        How many chunks were indexed.
    """
    if not chunks:
        return 0

    vectors = embed([c["content"] for c in chunks])

    with _engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLE}"))
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != DIMENSION:  # pragma: no cover — guards a model swap
                raise ValueError(f"embedding dimension {len(vector)} != expected {DIMENSION}")
            conn.execute(
                text(
                    f"INSERT INTO {TABLE} "
                    "(document_id, title, document_type, content, page_number, embedding, model) "
                    "VALUES (:document_id, :title, :document_type, :content, :page_number, "
                    "CAST(:embedding AS vector), :model)"
                ),
                {
                    "document_id": chunk["document_id"],
                    "title": chunk["title"],
                    "document_type": chunk["document_type"],
                    "content": chunk["content"],
                    "page_number": chunk.get("page_number"),
                    "embedding": _literal(vector),
                    "model": active_model(),
                },
            )

    logger.info("indexed %d chunks in pgvector (%s)", len(chunks), active_model())
    return len(chunks)


def search(question: str, limit: int = 5, *, apply_rerank: bool = True) -> list[SemanticHit]:
    """Find chunks whose meaning matches the question.

    Mirrors `app.retrieval.vector_store.search`: candidates come back on a
    relaxed floor, then the reranker decides what survives.
    """
    from app.retrieval.reranker import rerank_hits

    vector = embed_one(question)
    if len(vector) != DIMENSION:  # pragma: no cover — guards a model swap
        raise ValueError(f"embedding dimension {len(vector)} != stored {DIMENSION}")

    candidate_k = max(limit * 2, 10)
    floor = min_similarity()
    floor_candidate = min_similarity_candidate()

    with _engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT document_id, title, document_type, content, page_number, "
                f"1 - (embedding <=> CAST(:q AS vector)) AS similarity FROM {TABLE} "
                "ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"
            ),
            {"q": _literal(vector), "k": candidate_k},
        ).all()

    hits = [
        SemanticHit(
            document_id=r.document_id,
            title=r.title,
            document_type=r.document_type,
            content=r.content,
            page_number=r.page_number,
            similarity=round(float(r.similarity), 4),
        )
        for r in rows
        if float(r.similarity) >= floor_candidate
    ]

    if apply_rerank:
        kept = rerank_hits(question, hits)[:limit]
    else:
        kept = [h for h in hits if h.similarity >= floor][:limit]

    logger.info("semantic search kept %d of %d hits", len(kept), len(hits))
    return kept
