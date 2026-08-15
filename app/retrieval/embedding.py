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


GEMINI = "gemini"
OPENAI = "openai"


def active_model() -> str:
    """The model name that produced — or will produce — the stored vectors.

    Written into every indexed row. Two providers both returning 3,072
    dimensions is exactly why the name has to travel with the vector.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if settings.embed_provider.strip().lower() == OPENAI:
        return settings.embed_model_openai
    return MODEL


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Order of the result matches the input."""
    from app.core.config import get_settings

    if not texts:
        return []

    provider = get_settings().embed_provider.strip().lower()
    if provider == OPENAI:
        vectors = _embed_openai(texts)
    else:
        if provider != GEMINI:
            logger.warning(
                "EMBED_PROVIDER=%r is not recognised — using Gemini.", provider
            )
        vectors = _embed_gemini(texts)

    logger.info("embedded %d texts with %s", len(vectors), active_model())
    return vectors


def _embed_gemini(texts: list[str]) -> list[list[float]]:
    from google import genai

    from app.core.config import terapkan_env_vertex

    # `google-genai` reads the environment, not `Settings`. Without this bridge a
    # caller that never imports `app.agents` — a migration script, for one — falls
    # through to the public API-key path and fails on a project that only has
    # Vertex credentials.
    terapkan_env_vertex()
    client = genai.Client()
    return [_embed_one_request(client, t) for t in texts]


def _embed_openai(texts: list[str]) -> list[list[float]]:
    """Embed through OpenAI, one text per request.

    Batching is available here — unlike the Gemini path, which returns one
    vector however many texts it is handed — but the loop is kept so both
    providers fail the same way and the dimension check below applies per text.
    """
    from openai import OpenAI

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "EMBED_PROVIDER=openai but no OpenAI key is set. "
            "Set OPENAI_API_KEY (or IMAGE_API_KEY) in .env."
        )

    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.embed_model_openai
    vectors: list[list[float]] = []
    for text in texts:
        response = client.embeddings.create(model=model, input=text)
        if len(response.data) != 1:  # pragma: no cover — guards an API change
            raise ValueError(f"{model} returned {len(response.data)} embeddings for one text")
        vector = list(response.data[0].embedding)
        if len(vector) != DIMENSION:
            raise ValueError(
                f"{model} returned {len(vector)} dimensions, expected {DIMENSION}"
            )
        vectors.append(vector)
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
