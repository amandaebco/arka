"""One place that decides which model an agent talks to.

Every reasoning agent asks this module instead of naming a model itself, so
switching providers is an `.env` edit rather than a sweep across nine files.

The switch is deliberately one-directional in its failure mode: anything the
module does not recognise falls back to Gemini. A typo in `TEXT_PROVIDER` must
not silently reroute investigation prompts to a provider nobody chose.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

GEMINI = "gemini"
DEEPSEEK = "deepseek"

SUPPORTED = (GEMINI, DEEPSEEK)


def pilih_model(*, butuh_vision: bool = False) -> Any:
    """Return the model an agent should be built with.

    Args:
        butuh_vision: The agent reads rendered pages, not just text. Only
            Gemini can do that here, so the provider setting is ignored — a
            quality gate that cannot see is worse than no quality gate.

    Returns:
        A model name for ADK's native Gemini path, or a `LiteLlm` instance
        wrapping another provider.
    """
    settings = get_settings()

    if butuh_vision:
        return settings.vertex_ai_model

    provider = settings.text_provider.strip().lower()

    if provider == DEEPSEEK:
        if not settings.deepseek_api_key:
            # Failing loudly here beats an agent that starts fine and then
            # errors on its first turn, halfway through a demo.
            raise RuntimeError(
                "TEXT_PROVIDER=deepseek but DEEPSEEK_API_KEY is empty. "
                "Set it in .env, or set TEXT_PROVIDER=gemini."
            )

        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(
            model=f"deepseek/{settings.deepseek_model}",
            api_key=settings.deepseek_api_key,
        )

    if provider != GEMINI:
        logger.warning(
            "TEXT_PROVIDER=%r is not one of %s — falling back to Gemini.",
            settings.text_provider,
            ", ".join(SUPPORTED),
        )

    return settings.vertex_ai_model
