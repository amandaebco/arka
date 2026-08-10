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

MODEL = "gemini-embedding-2"

# Vectors are stored in BigQuery and compared there; the dimension is fixed at
# load time and a mismatch fails the search rather than degrading it silently.
#
# Measured against `gemini-embedding-2` on 11 August, not assumed: the previous
# model (`gemini-embedding-001`) also returned 3072, so a changed dimension would
# not have announced itself here.
DIMENSION = 3072

# ⚠️ Vectors from two models are not comparable, and the dimension being equal
# hides that rather than excusing it. A query embedded by one model against an
# index built by another returns confident nonsense — the search succeeds, the
# distances are plausible, and every one of them is meaningless. Changing MODEL
# therefore obliges a full re-index (`scripts/migrasi_bigquery.py --index`) and
# a re-measurement of `MIN_SIMILARITY` in `app.retrieval.vector_store`.

# ⚠️ `gemini-embedding-2` embeds one text per request. Handed a list of three it
# returns a single vector rather than an error — measured on 11 August. The
# previous model accepted batches, so the batching loop that worked against it
# would, against this one, pair every chunk with the wrong vector and index all
# four documents as if they said the same thing. Search would still return
# results, ranked, and every rank would be meaningless.
#
# One text per request is therefore not a simplification, it is the contract.
# `_embed_one_request` is the only place that calls the model, and it asserts
# what came back.
BATCH = 1


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Order of the result matches the input."""
    from google import genai

    from app.core.config import terapkan_env_vertex

    if not texts:
        return []

    # `google-genai` reads the environment, not `Settings`. Without this bridge a
    # caller that never imports `app.agents` — a migration script, for one — falls
    # through to the public API-key path and fails on a project that only has
    # Vertex credentials.
    terapkan_env_vertex()
    client = genai.Client()
    vectors = [_embed_one_request(client, t) for t in texts]
    logger.info("embedded %d texts", len(vectors))
    return vectors


def _embed_one_request(client, text: str) -> list[float]:
    """One text, one request, one vector — checked rather than assumed.

    The model returns a single embedding whatever it is given, so the count is
    the only signal that the request meant what the caller thought. Silently
    taking `embeddings[0]` is exactly how a mismatched index gets built.
    """
    response = client.models.embed_content(model=MODEL, contents=[text])
    if len(response.embeddings) != 1:  # pragma: no cover — guards a model swap
        raise ValueError(
            f"{MODEL} returned {len(response.embeddings)} embeddings for one text"
        )
    return list(response.embeddings[0].values)


def embed_one(text: str) -> list[float]:
    """Embed a single query. Kept separate so callers read clearly."""
    return embed([text])[0]
