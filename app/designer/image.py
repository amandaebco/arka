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
from math import gcd
from typing import Any

from app.core.config import get_settings
from app.designer.transient import with_retry

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
        raise DrawingUnavailable(f"pustaka penggambar tidak terpasang: {exc}") from exc

    return OpenAI(api_key=settings.image_api_key, timeout=settings.image_timeout_seconds)


def _aspect_ratio(size: str) -> str:
    """Turn "1024x1536" into "2:3".

    Derived from the same setting the OpenAI path uses rather than written out
    twice: two providers drawing different shapes of the same page is the kind of
    drift nobody notices until the layouts stop matching.
    """
    lebar, _, tinggi = size.lower().partition("x")
    try:
        w, h = int(lebar), int(tinggi)
    except ValueError as exc:
        raise DrawingUnavailable(f"IMAGE_SIZE tidak terbaca: {size!r}") from exc

    pembagi = gcd(w, h) or 1
    return f"{w // pembagi}:{h // pembagi}"


def _draw_vertex(prompt: str) -> bytes:
    """Draw with a Gemini image model on Vertex, using the project already
    configured for page reading.

    Kept alongside the OpenAI path rather than replacing it: drawing outside
    Google is a deliberate part of the stack, and this exists so a run is not
    blocked when that account cannot be called.
    """
    import os

    from google import genai
    from google.genai import types

    settings = get_settings()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise DrawingUnavailable("GOOGLE_CLOUD_PROJECT belum disetel")

    client = genai.Client(
        vertexai=True,
        project=project,
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )
    response = with_retry(
        lambda: client.models.generate_content(
            model=settings.image_model_vertex,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=_aspect_ratio(settings.image_size)
                ),
            ),
        ),
        what="Penggambaran halaman (Vertex)",
    )

    for kandidat in response.candidates or []:
        for bagian in (kandidat.content.parts if kandidat.content else None) or []:
            data = getattr(bagian, "inline_data", None)
            if data and data.data:
                return data.data

    raise DrawingUnavailable("penggambar Vertex tidak mengembalikan gambar")


def draw_page(prompt: str) -> bytes:
    """Draw the page and return PNG bytes.

    Raises `DrawingUnavailable` on any provider failure. Callers report the
    failure to the user; they never fall back to a partial page, because a page
    that looks finished but is not is worse than a visible failure.
    """
    settings = get_settings()
    if settings.image_provider.strip().lower() == "vertex":
        try:
            return _draw_vertex(prompt)
        except DrawingUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — satu jenis kegagalan yang jelas
            raise DrawingUnavailable(f"{type(exc).__name__}: {exc}") from exc

    try:
        hasil = with_retry(
            lambda: _client().images.generate(
                model=settings.image_model,
                prompt=prompt,
                size=settings.image_size,
                quality=settings.image_quality,
            ),
            what="Penggambaran halaman",
        )
    except DrawingUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — turned into one explicit failure type
        raise DrawingUnavailable(f"{type(exc).__name__}: {exc}") from exc

    isi = base64.b64decode(hasil.data[0].b64_json)
    logger.info("Halaman digambar (%d bita, %s)", len(isi), settings.image_model)
    return isi
