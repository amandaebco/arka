"""Reranking layer for semantic retrieval.

Cosine similarity against document embeddings provides a strong candidate pool,
but a static cutoff (e.g. 0.60) struggles at the boundary where in-domain and
out-of-domain similarity scores overlap.

The reranker combines:
1. Cosine similarity score from vector search
2. Lexical keyword overlap score (matching domain terms, equipment tags, components)
3. Relative margin evaluation against the top hit (keeping close matches, pruning noise)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.retrieval.vector_store import SemanticHit

logger = logging.getLogger(__name__)

# Weight for cosine similarity vs keyword overlap in composite rerank score
WEIGHT_COSINE = 0.65
WEIGHT_KEYWORD = 0.35

# Relative margin threshold: candidate must achieve at least 70% of the top hit's composite score
MIN_RELATIVE_MARGIN = 0.70

# Absolute floor for composite score to reject pure noise.
#
# Composite is 0.65·cosine + 0.35·keyword, so it inherits the cosine scale — and
# cosine scales differ per embedding model. Measured over the same ten questions
# used for `MIN_SIMILARITY`, 15 August:
#
#     `gemini-embedding-2`      floor 0.55, reachable on that model's scale
#     `text-embedding-3-large`  weakest in-domain 0.3779, strongest nonsense
#                               0.3063 ("harga saham minggu ini") -- gap +0.0716
#
# A floor of 0.55 is reachable on the first and unreachable on the second, which
# is how a model swap silently rejected every paraphrased question while the
# search itself still looked healthy. 0.34 sits midway in the measured gap:
# it admits "kenapa produk merembes saat pengisian?", the paraphrase the whole
# design exists to catch, and rejects all three nonsense questions.
MIN_COMPOSITE_BY_MODEL = {
    "gemini-embedding-2": 0.55,
    "text-embedding-3-large": 0.34,
}

# Kept for callers that pass an explicit value; the default is resolved per model.
MIN_COMPOSITE_SCORE = 0.55


def min_composite_score() -> float:
    """The composite floor measured for whichever model is producing vectors."""
    from app.retrieval.embedding import active_model

    model = active_model()
    if model not in MIN_COMPOSITE_BY_MODEL:  # pragma: no cover — guards a model swap
        raise ValueError(
            f"No composite floor measured for {model!r}. Measure it against the "
            "corpus before trusting retrieval; see the table above."
        )
    return MIN_COMPOSITE_BY_MODEL[model]

# Key domain terms that receive extra relevance weight during keyword matching
DOMAIN_TERMS = frozenset(
    {
        "seal",
        "katup",
        "nozel",
        "bearing",
        "torsi",
        "vibrasi",
        "bocor",
        "kebocoran",
        "pompa",
        "filler",
        "motor",
        "suhu",
        "tekanan",
        "preseden",
        "penyebab",
    }
)


@dataclass(frozen=True)
class RerankedHit:
    """A semantic hit enriched with its composite rerank score."""

    hit: SemanticHit
    composite_score: float
    keyword_score: float
    relative_margin: float


def _extract_keywords(text: str) -> set[str]:
    """Extract clean lower-case terms from text."""
    words = text.lower().replace(",", " ").replace(":", " ").replace(";", " ").split()
    keywords = set()
    for word in words:
        clean = word.strip(".?!:;()[]{}")
        if len(clean) >= 3:
            keywords.add(clean)
    return keywords


def calculate_keyword_overlap(question: str, content: str, title: str) -> float:
    """Calculate weighted keyword overlap between question and document chunk."""
    q_words = _extract_keywords(question)
    if not q_words:
        return 0.0

    doc_words = _extract_keywords(f"{title} {content}")
    matched = q_words & doc_words

    bonus = 0.0
    for word in matched:
        if word.startswith("plt-") or word.startswith("fil-") or word in DOMAIN_TERMS:
            bonus += 0.20

    overlap_ratio = len(matched) / len(q_words)
    return min(1.0, overlap_ratio + bonus)


def rerank_hits(
    question: str,
    hits: list[SemanticHit],
    *,
    min_composite: float | None = None,
    min_relative_margin: float = MIN_RELATIVE_MARGIN,
) -> list[SemanticHit]:
    """Rerank and filter candidate hits using composite scoring and relative margin testing."""
    if min_composite is None:
        min_composite = min_composite_score()
    if not hits:
        return []

    scored_hits: list[RerankedHit] = []
    for hit in hits:
        kw_score = calculate_keyword_overlap(question, hit.content, hit.title)
        composite = WEIGHT_COSINE * hit.similarity + WEIGHT_KEYWORD * kw_score
        scored_hits.append(
            RerankedHit(
                hit=hit,
                composite_score=round(composite, 4),
                keyword_score=round(kw_score, 4),
                relative_margin=1.0,
            )
        )

    # Sort by composite score descending
    scored_hits.sort(key=lambda x: x.composite_score, reverse=True)
    top_score = scored_hits[0].composite_score

    # Apply relative margin filter against top hit
    filtered: list[SemanticHit] = []
    for r in scored_hits:
        margin = r.composite_score / top_score if top_score > 0 else 0.0
        if r.composite_score >= min_composite and margin >= min_relative_margin:
            filtered.append(r.hit)

    logger.info("reranked %d candidates down to %d top hits", len(hits), len(filtered))
    return filtered
