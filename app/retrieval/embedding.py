"""Text embeddings, produced outside BigQuery on purpose.

BigQuery can generate embeddings itself through `ML.GENERATE_EMBEDDING`, but
that route needs a remote-model connection whose service account must be granted
Vertex AI access — and granting it requires `setIamPolicy`, which this project's
account does not have.

Embedding here instead sidesteps that entirely: `VECTOR_SEARCH` operates on
stored vectors and needs no connection at all. The trade is explicit — one more
step at load time, one less permission to negotiate.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MODEL = "gemini-embedding-001"

# Vectors are stored in BigQuery and compared there; the dimension is fixed at
# load time and a mismatch fails the search rather than degrading it silently.
DIMENSION = 3072

# Requests are batched because embedding is the slowest step of ingestion and
# the corpus grows with the document estate, not with the question.
BATCH = 16


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Order of the result matches the input."""
    from google import genai

    if not texts:
        return []

    client = genai.Client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        chunk = texts[start : start + BATCH]
        response = client.models.embed_content(model=MODEL, contents=chunk)
        vectors.extend(list(e.values) for e in response.embeddings)
    logger.info("embedded %d texts", len(vectors))
    return vectors


def embed_one(text: str) -> list[float]:
    """Embed a single query. Kept separate so callers read clearly."""
    return embed([text])[0]
