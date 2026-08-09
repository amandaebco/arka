"""Rendered-page inspection — reads the drawn image, not the prompt.

This closes the gap that the rest of the quality gate cannot reach. Every other
check compares canvas content against the finding, one stage upstream of the
drawing. But the drawing stage is precisely the one Constitution 1.2.0 exempts
from Principle I, so checking upstream of it verifies the wrong thing.

The failure this exists to catch is real, not hypothetical: an early run invented
two identity chips — a functional location lifted from a document title, and a
criticality lifted from a spare part — and presented both as facts about the
asset. Every string existed somewhere in the finding, so an upstream check passed
it. Only reading the page catches that.

The model here reads; it does not judge. It reports what text it sees, and code
decides which of that text was authorised.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM = (
    "You transcribe infographics. You do not interpret, summarise, or judge them. "
    "List every distinct text string visible on the page — headings, labels, "
    "values, chips, captions, footers. One per line, exactly as printed, with no "
    "numbering and no commentary. Include text inside badges and pills. If a "
    "string is repeated, list it once."
)


class InspectionUnavailable(RuntimeError):
    """Raised when the page cannot be read — never silently treated as clean."""


@lru_cache
def _client():
    """Cached because the underlying HTTP client closes when its owner is
    released; a fresh client per call would be shut down before the request
    completes."""
    import os

    from google import genai
    from google.genai.types import HttpOptions

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    if not project:
        raise InspectionUnavailable("GOOGLE_CLOUD_PROJECT belum disetel")

    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=HttpOptions(
            api_version="v1", timeout=int(settings.vertex_ai_timeout_seconds * 4 * 1000)
        ),
    )


def read_page_text(page: bytes) -> list[str]:
    """Transcribe every visible string on the page.

    Raises `InspectionUnavailable` rather than returning an empty list: an empty
    result and an unreadable page must never look the same to the caller, or a
    broken reader would silently certify every page as clean.
    """
    from google.genai import types

    settings = get_settings()
    try:
        response = _client().models.generate_content(
            model=settings.vertex_ai_model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=page, mime_type="image/png"),
                        types.Part.from_text(text="Transcribe every visible string."),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM, temperature=0.0
            ),
        )
    except Exception as exc:  # noqa: BLE001 — turned into one explicit failure type
        raise InspectionUnavailable(f"{type(exc).__name__}: {exc}") from exc

    teks = (response.text or "").strip()
    if not teks:
        raise InspectionUnavailable("pembaca halaman tidak mengembalikan teks apa pun")

    baris = [b.strip(" -•\t") for b in teks.splitlines()]
    return [b for b in baris if b]


# Text that legitimately appears on a page without coming from the finding:
# structural labels the content layer composes, and the standing wording of the
# confidence and escalation markers.
STANDING_TEXT = (
    "Keyakinan", "Eskalasi", "Gejala", "Penyebab teratas", "Perlu putusan manusia",
    "Langkah", "indikasi awal", "sudah cukup kuat", "masih perlu dipastikan",
    "Pabrik", "Model", "jam", "Menunggu putusan manusia",
    "dua kandidat teratas disajikan",
)


def authorised_strings(content: Any, block_titles: list[str], subtitle: str = "") -> list[str]:
    """Every string a page is allowed to show.

    Built in one place because two callers checking against two different lists
    is how a real defect hides behind a false one — a page flagged for a string
    that one list authorises and the other forgot.
    """
    allowed: list[str] = [
        content.equipment_tag,
        content.pabrik,
        content.model_equipment,
        subtitle,
    ]
    allowed += list(block_titles)
    allowed += list(STANDING_TEXT)
    for block in content.sections:
        for item in content.items(block):
            allowed += [
                item.text, item.label, item.value,
                item.horizon, item.date, item.level, item.owner,
            ]
    return [a for a in allowed if a]


def normalise(value: str) -> str:
    """Reduce a string to what matters for comparison.

    Case, punctuation, and whitespace vary between what is asked for and what is
    drawn without changing meaning; a difference in those is a rendering artefact,
    not a fabrication.
    """
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


def unauthorised_text(
    drawn: list[str], authorised: list[str], min_length: int = 4
) -> list[str]:
    """Strings visible on the page that no authorised string accounts for.

    A drawn string is accepted when it appears inside any authorised string, or
    any authorised string appears inside it — line wrapping and truncation split
    and join text in ways that are cosmetic. Very short fragments are ignored:
    they carry too little meaning to distinguish a fabrication from a stray glyph.
    """
    disetujui = [normalise(a) for a in authorised if a]
    asing: list[str] = []

    for satu in drawn:
        bersih = normalise(satu)
        if len(bersih) < min_length:
            continue
        if any(bersih in a or a in bersih for a in disetujui if a):
            continue
        asing.append(satu)

    return asing
