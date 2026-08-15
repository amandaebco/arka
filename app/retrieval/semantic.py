"""Picks which vector store answers, from the same switch the rest of ARKA uses.

Retrieval used to be BigQuery-only, because that is where the embeddings lived.
It no longer is: `ARKA_STORE=postgres` now reaches a pgvector index instead, so
the whole reasoning chain — scout, investigator, reporter, and question
answering — can run with no cloud dependency at all.

The two backends are kept behind one signature deliberately. Callers ask a
question and get `SemanticHit`s; which engine computed the cosine is not their
business, and the day it becomes their business is the day the abstraction has
failed.
"""

from __future__ import annotations

from app.detection.store import POSTGRES, active_store
from app.retrieval.vector_store import SemanticHit


def search(question: str, limit: int = 5, *, apply_rerank: bool = True) -> list[SemanticHit]:
    """Find chunks whose meaning matches the question, on the active store."""
    if active_store() == POSTGRES:
        from app.retrieval import pgvector_store

        return pgvector_store.search(question, limit, apply_rerank=apply_rerank)

    from app.retrieval import vector_store

    return vector_store.search(question, limit, apply_rerank=apply_rerank)


def build_index(chunks: list[dict]) -> int:
    """Embed and store document chunks on the active store."""
    if active_store() == POSTGRES:
        from app.retrieval import pgvector_store

        return pgvector_store.build_index(chunks)

    from app.retrieval import vector_store

    return vector_store.build_index(chunks)
