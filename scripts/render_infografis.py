"""Render one infographic from the example finding, with a full audit trail.

Development tool: exercises the whole visual path without a database, without an
investigator, and without an agent session. Run it as:

    uv run python scripts/render_infografis.py                  # default reader
    uv run python scripts/render_infografis.py --persona engineer
    uv run python scripts/render_infografis.py --prompt-saja    # no drawing call
    uv run python scripts/render_infografis.py --tanpa-periksa  # skip page reading

Everything up to the prompt is deterministic, so `--prompt-saja` is the cheap way
to inspect what the drawing provider will be asked for. Only the last two steps
cost money and time.

Each run writes its own folder under `out/infografis/`, never overwriting an
earlier one. The drawing is not reproducible, so the record is what makes a
published page accountable (FR-018).
"""

from __future__ import annotations

import argparse

import app.agents  # noqa: F401 — memasang variabel lingkungan Vertex
from app.agents.designer import DEFAULT_PERSONA, PERSONA
from app.designer.composer import compose_prompt
from app.designer.content import build_content
from app.designer.image import DrawingUnavailable, draw_page
from app.designer.inspection import (
    InspectionUnavailable,
    authorised_strings,
    read_page_text,
    unauthorised_text,
)
from app.designer.knowledge import DesignKnowledgeBase
from app.designer.presentation import PresentationSpec, normalise, validate
from app.designer.trail import RunTrail
from app.reporting.blocks import susun_blok
from app.synthetic.finding_contoh import finding_contoh


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", default=DEFAULT_PERSONA, choices=sorted(PERSONA))
    parser.add_argument("--prompt-saja", action="store_true")
    parser.add_argument("--tanpa-periksa", action="store_true")
    args = parser.parse_args()

    kb = DesignKnowledgeBase.load()
    finding = finding_contoh()
    trail = RunTrail(finding.finding_id)

    blocks = [b for b in susun_blok(finding).values() if b.tersedia]
    content = build_content(blocks)
    titles = {b.id: b.judul for b in blocks}
    selected = [b.id for b in blocks if content.has(b.id)]

    style = PERSONA[args.persona]
    trail.record_input(finding, content, args.persona, style)

    # Emphasis a designer agent would otherwise propose. Kept explicit here so the
    # script exercises the same validation path the agent goes through.
    emphasis = {"kandidat_penyebab": "dominant", "rekomendasi": "primary"}
    if finding.perlu_eskalasi:
        emphasis["ringkasan"] = "primary"

    spec = PresentationSpec.from_dict(
        {
            "style": style,
            "language": "id",
            "emphasis": emphasis,
            "form": {"rekomendasi": "priority_actions"},
            "accents": {"tinggi": "high", "sedang": "medium"},
            "rationale": "Kandidat penyebab dominan karena temuan ini menunggu putusan.",
        }
    )
    default_emphasis = kb.resolve_style(style)["storytelling"].get("emphasis_order") or {}
    spec = normalise(spec, selected, default_emphasis)

    problems = validate(spec, kb, selected)
    if problems:
        trail.record_round(1, spec, "", review={"specification_problems": problems})
        trail.finish("SPEC_REJECTED")
        print("Spesifikasi ditolak:")
        for one in problems:
            print(f"  - {one}")
        return 1

    prompt = compose_prompt(spec, content, titles, kb)

    print(f"Temuan   : {finding.finding_id} — {finding.equipment_tag}")
    print(f"Persona  : {args.persona} → {style}")
    print(f"Kartu    : {len(selected)} — {', '.join(selected)}")
    print(f"Prompt   : {len(prompt):,} karakter")

    if args.prompt_saja:
        trail.record_round(1, spec, prompt)
        trail_path = trail.finish("PROMPT_ONLY")
        print(f"Jejak    : {trail_path.parent}")
        return 0

    try:
        page = draw_page(prompt)
    except DrawingUnavailable as exc:
        trail.record_round(1, spec, prompt, review={"drawing_error": str(exc)})
        trail.finish("DRAWING_FAILED", str(exc))
        print(f"Penggambaran gagal: {exc}")
        return 1

    review = None
    if not args.tanpa_periksa:
        review = _inspect(page, content, blocks, style, kb)
        for one in review["unauthorised"]:
            print(f"  ! teks tak disetujui: “{one}”")

    page_path = trail.record_round(1, spec, prompt, page=page, review=review)
    outcome = "PUBLISHED" if not (review and review["unauthorised"]) else "PUBLISHED_WITH_FINDINGS"
    trail_path = trail.finish(outcome)

    print(f"Halaman  : {page_path} ({len(page):,} bita)")
    if review:
        print(f"Terbaca  : {review['strings_read']} teks, "
              f"{len(review['unauthorised'])} tak disetujui")
    print(f"Jejak    : {trail_path.parent}")
    return 0


def _inspect(page: bytes, content, blocks, style: str, kb) -> dict:
    """Read the drawn page and flag text that no authorised string accounts for."""
    authorised = authorised_strings(
        content,
        [b.judul for b in blocks],
        (kb.get_style(style)["presentation"].get("subtitle") or {}).get("id", ""),
    )

    try:
        drawn = read_page_text(page)
    except InspectionUnavailable as exc:
        return {"strings_read": 0, "unauthorised": [], "error": str(exc)}

    return {
        "strings_read": len(drawn),
        "drawn": drawn,
        "unauthorised": unauthorised_text(drawn, authorised),
    }


if __name__ == "__main__":
    raise SystemExit(main())
