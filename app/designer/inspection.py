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
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.designer.transient import with_retry

logger = logging.getLogger(__name__)

SYSTEM = (
    "You transcribe infographics. You do not interpret, summarise, or judge them. "
    "List every distinct text string visible on the page — headings, labels, "
    "values, chips, captions, footers. One per line, exactly as printed, with no "
    "numbering and no commentary. Include text inside badges and pills. If a "
    "string is repeated, list it once."
)


HEADER_SYSTEM = (
    "You read infographics. Look only at the numbered card headers on the page — "
    "the title bar at the top of each card. List them top to bottom, then left to "
    "right, exactly as printed, one per line. List a header once for every time it "
    "appears: if the same card is drawn twice, write it twice. Report nothing else."
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


def _read_via_openai(page: bytes, prompt: str, system: str) -> str:
    """Read a page through OpenAI, for when Vertex is not reachable.

    Same contract as the Gemini path: hand over the image, get transcribed text.
    The reader must not judge, so temperature stays at zero here too — a reader
    that paraphrases is a reader that invents, and the whole point of this
    module is catching strings that were never authorised.
    """
    import base64

    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise InspectionUnavailable(
            "VISION_PROVIDER=openai but the OpenAI key is empty "
            "(set OPENAI_API_KEY or IMAGE_API_KEY)"
        )

    b64 = base64.b64encode(page).decode("ascii")
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.vision_model_openai,
        temperature=0.0,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            },
        ],
    )
    return (response.choices[0].message.content or "").strip()


def _using_openai() -> bool:
    return get_settings().vision_provider.strip().lower() == "openai"


def read_page_text(page: bytes) -> list[str]:
    """Transcribe every visible string on the page.

    Raises `InspectionUnavailable` rather than returning an empty list: an empty
    result and an unreadable page must never look the same to the caller, or a
    broken reader would silently certify every page as clean.
    """
    if _using_openai():
        try:
            text = _read_via_openai(page, "Transcribe every visible string.", SYSTEM)
        except InspectionUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — one explicit failure type
            raise InspectionUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if not text:
            raise InspectionUnavailable("pembaca halaman tidak mengembalikan teks apa pun")
        return [b for b in (x.strip(" -•\t") for x in text.splitlines()) if b]

    from google.genai import types

    settings = get_settings()
    try:
        isi = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=page, mime_type="image/png"),
                    types.Part.from_text(text="Transcribe every visible string."),
                ],
            )
        ]
        response = with_retry(
            lambda: _client().models.generate_content(
                model=settings.vertex_ai_model,
                contents=isi,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM, temperature=0.0
                ),
            ),
            what="Page transcription",
        )
    except Exception as exc:  # noqa: BLE001 — turned into one explicit failure type
        raise InspectionUnavailable(f"{type(exc).__name__}: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        raise InspectionUnavailable("pembaca halaman tidak mengembalikan teks apa pun")

    lines = [b.strip(" -•\t") for b in text.splitlines()]
    return [b for b in lines if b]


def read_card_headers(page: bytes) -> list[str]:
    """Read the card headers, counting repeats.

    A separate read because the transcription deliberately lists each distinct
    string once, which makes a card drawn twice indistinguishable from a card
    drawn once. A live page repeated one card twice and another three times, and
    dropped a fourth entirely; every string on it was authorised, so the fidelity
    check called it clean.
    """
    if _using_openai():
        try:
            text = _read_via_openai(
            page, "List every card header, repeats included.", HEADER_SYSTEM
        )
        except InspectionUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — one explicit failure type
            raise InspectionUnavailable(f"{type(exc).__name__}: {exc}") from exc
        return [b for b in (x.strip(" -•\t0123456789.") for x in text.splitlines()) if b]

    from google.genai import types

    settings = get_settings()
    try:
        isi = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=page, mime_type="image/png"),
                    types.Part.from_text(text="List every card header, repeats included."),
                ],
            )
        ]
        response = with_retry(
            lambda: _client().models.generate_content(
                model=settings.vertex_ai_model,
                contents=isi,
                config=types.GenerateContentConfig(
                    system_instruction=HEADER_SYSTEM, temperature=0.0
                ),
            ),
            what="Card header transcription",
        )
    except Exception as exc:  # noqa: BLE001 — one explicit failure type
        raise InspectionUnavailable(f"{type(exc).__name__}: {exc}") from exc

    lines = [b.strip(" -•\t0123456789.") for b in (response.text or "").splitlines()]
    return [b for b in lines if b]


def card_defects(drawn_headers: list[str], expected: list[str]) -> list[str]:
    """Cards missing from the page, and cards drawn more than once.

    A card that is missing is worse than a fabricated string: the reader has no
    way of knowing something was left out. Neither shows up in a check that only
    asks whether the text on the page was authorised.
    """
    terbaca = [normalise(h) for h in drawn_headers]
    cacat: list[str] = []

    for judul in expected:
        bersih = normalise(judul)
        if not bersih:
            continue
        jumlah = sum(1 for h in terbaca if bersih in h or h in bersih)
        if jumlah == 0:
            cacat.append(f"kartu “{judul}” tidak tergambar")
        elif jumlah > 1:
            cacat.append(f"kartu “{judul}” tergambar {jumlah} kali")

    return cacat


# Text that legitimately appears on a page without coming from the finding:
# structural labels the content layer composes, and the standing wording of the
# confidence and escalation markers.
STANDING_TEXT = (
    "Keyakinan", "Eskalasi", "Gejala", "Penyebab teratas", "Perlu putusan manusia",
    "Langkah", "indikasi awal", "sudah cukup kuat", "masih perlu dipastikan",
    "Pabrik", "Model", "jam", "Menunggu putusan manusia",
    "dua kandidat teratas disajikan",
)


# A severity chip is drawn as a word, but the content carries the key. Only the
# wording for levels the content actually holds is authorised — allowing every
# severity word globally would let a page label a low finding "TINGGI" unnoticed.
SEVERITY_WORDS = {
    "high": ("HIGH", "TINGGI"),
    "medium": ("MEDIUM", "SEDANG"),
    "low": ("LOW", "RENDAH"),
    "critical": ("CRITICAL", "KRITIS"),
}


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
                item.horizon, item.date, item.level, item.owner, item.value_label,
                item.reference, item.reference_label,
            ]
            allowed += SEVERITY_WORDS.get(item.level, ())
    return [a for a in allowed if a]


def normalise(value: str) -> str:
    """Reduce a string to what matters for comparison.

    Case, punctuation, and whitespace vary between what is asked for and what is
    drawn without changing meaning; a difference in those is a rendering artefact,
    not a fabrication.
    """
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


# A drawn string that is one or two characters away from an authorised one is a
# misprint, not an invention. Two live runs spent their whole three-round budget
# on exactly that: "Catatan Teknis" for "Catatan Teknisi", "Kandiat Penyebab" for
# "Kandidat Penyebab". Redrawing does not reliably fix a slip of the pen, so the
# budget burns while the real defect — a word missing one letter — stays.
#
# The tolerance is narrow on purpose. It applies only to strings long enough that
# near-identity cannot happen by chance: "Sedang" and "Rendah" are six characters
# and stay fabrications, which is what caught a page assigning severities the
# finding never gave.
MISPRINT_RATIO = 0.9
MISPRINT_MIN_LENGTH = 12


def _closest(clean: str, allowed: list[tuple[str, str]]) -> tuple[float, str]:
    """The nearest authorised string, reported in its original spelling.

    Comparison runs on the normalised form; the message quotes the original, so
    whoever reads the verdict sees the text as it was meant to be printed.
    """
    best, match = 0.0, ""
    for flat, asli in allowed:
        ratio = SequenceMatcher(None, clean, flat).ratio()
        if ratio > best:
            best, match = ratio, asli
    return best, match


def review_text(
    drawn: list[str], authorised: list[str], min_length: int = 4
) -> tuple[list[str], list[str]]:
    """Split what the page shows into inventions and misprints.

    A drawn string is accounted for when it appears inside any authorised string,
    or any authorised string appears inside it — line wrapping and truncation
    split and join text in ways that are cosmetic. Very short fragments are
    ignored: they carry too little meaning to tell a fabrication from a stray
    glyph.

    Returns `(fabricated, misprinted)`. Only the first blocks publication. The
    second is reported, because a citation title printed wrong is still wrong —
    but it is a defect in the drawing of authorised text, not a claim the finding
    never made, and treating the two alike is what stopped good pages publishing.
    """
    allowed = [(normalise(a), a) for a in authorised if a]
    fabricated: list[str] = []
    misprinted: list[str] = []

    for one in drawn:
        clean = normalise(one)
        if len(clean) < min_length:
            continue
        if any(clean in flat or flat in clean for flat, _ in allowed if flat):
            continue

        ratio, match = _closest(clean, allowed)
        if len(clean) >= MISPRINT_MIN_LENGTH and ratio >= MISPRINT_RATIO:
            misprinted.append(f"“{one}” — seharusnya “{match}”")
            continue
        fabricated.append(one)

    return fabricated, misprinted
