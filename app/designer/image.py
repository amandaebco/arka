"""Page drawing — the only path in ARKA that calls a provider outside Google.

Nothing here reasons. It receives a finished prompt, returns bytes, and reports
failure plainly rather than substituting something that looks like success.

Constitution 1.2.0 permits a model to draw the infographic page, and only the
page: every string in the prompt was fixed by `content.py` from the finding, and
the quality gate checks each of them against the source before publication.
"""

from __future__ import annotations

import base64
import logging
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DrawingUnavailable(RuntimeError):
    """Raised when the drawing provider is unreachable or unconfigured."""


@lru_cache
def _client() -> Any:
    settings = get_settings()
    if not settings.image_api_key:
        raise DrawingUnavailable(
            "IMAGE_API_KEY belum disetel — penggambar infografis tidak dapat dipanggil"
        )
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DrawingUnavailable(f"knowledge_base penggambar tidak terpasang: {exc}") from exc

    return OpenAI(api_key=settings.image_api_key, timeout=settings.image_timeout_seconds)


def draw_page(prompt: str) -> bytes:
    """Draw the page and return PNG bytes.

    Raises `DrawingUnavailable` on any provider failure. Callers report the
    failure to the user; they never fall back to a partial page, because a page
    that looks finished but is not is worse than a visible failure.
    """
    settings = get_settings()
    try:
        hasil = _client().images.generate(
            model=settings.image_model,
            prompt=prompt,
            size=settings.image_size,
            quality=settings.image_quality,
        )
    except DrawingUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — turned into one explicit failure type
        raise DrawingUnavailable(f"{type(exc).__name__}: {exc}") from exc

    isi = base64.b64decode(hasil.data[0].b64_json)
    logger.info("Halaman digambar (%d bita, %s)", len(isi), settings.image_model)
    return isi
