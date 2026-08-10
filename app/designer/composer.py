"""Prompt composer — compiles a presentation spec into drawing instructions.

This is not an agent. No model call, no reasoning, no optimisation. The same
inputs always produce the same prompt, so any difference between two runs traces
back to a difference in the specification rather than to model variance.

Card titles come from `Blok.judul` rather than from the design library, so the
infographic and the memo name the same thing the same way.
"""

from __future__ import annotations

from typing import Any

from app.designer import renderer
from app.designer.content import CanvasContent, CanvasItem
from app.designer.inspection import SEVERITY_WORDS
from app.designer.presentation import PresentationSpec

LANGUAGE_NAMES = {"id": "Indonesian", "en": "English"}

# The label the drawing model most often paraphrases. Naming it explicitly in
# the prompt is cheaper than catching the paraphrase after every run.
CONFIDENCE_LABEL = {"id": "Keyakinan", "en": "Confidence"}

EMPHASIS_INSTRUCTION = {
    "dominant": "the single largest and most prominent card on the canvas",
    "primary": "high emphasis, larger type and stronger contrast than surrounding cards",
    "secondary": "standard emphasis",
    "tertiary": "low emphasis, smallest type, visually recessive",
}

# Constraints that hold whatever the specification says.
BASE_CONSTRAINTS = [
    "no people or human figures",
    "no lorem ipsum, dummy text, or placeholder text",
    "no numbers, labels or values absent from the text above",
    "no confidence percentages — only the three levels given",
    "no cartoon, gaming or marketing-poster aesthetics",
    "no watermarks, logos or signatures",
    "no charts beyond those explicitly described",
    "never redraw, recompute, round or translate any quoted value",
    # A live run captioned an unlabelled 0..1 figure "Kritikalitas" and drew a
    # 0,25–1,00 axis with a threshold caption, none of it from the finding. Both
    # were the page answering a question the prompt left open.
    "never invent a caption, unit or category name for a number — print a number "
    "without a caption of your own if none is given",
    "no axis ticks, scale marks, gridline numbers or threshold captions",
]


def compose_prompt(
    spec: PresentationSpec,
    isi: CanvasContent,
    block_titles: dict[str, str],
    kb: Any,
) -> str:
    """Compile the specification into a finished prompt."""
    style = kb.resolve_style(spec.style)
    return renderer.render(
        _template(style), _template_blocks(spec, isi, block_titles, kb, style)
    )


def _template(style: dict[str, Any]) -> str:
    """Load the layout's prompt template, falling back to the primary grid."""
    from app.designer.knowledge.loader import DEFAULT_ROOT

    folder = DEFAULT_ROOT.parent / "templates"
    berkas = folder / f"{style['layout']['id']}.md"
    if not berkas.exists():
        berkas = folder / "technical_report_grid.md"
    return berkas.read_text(encoding="utf-8")


def _template_blocks(
    spec: PresentationSpec,
    isi: CanvasContent,
    block_titles: dict[str, str],
    kb: Any,
    style: dict[str, Any],
) -> dict[str, str]:
    layout = style["layout"]
    presentasi = style["style"]["presentation"]
    warna = style["color_system"]
    return {
        "orientation": layout["orientation"],
        "style_reference": presentasi["reference"],
        "style_mood": presentasi["mood"],
        "style_finish": presentasi["finish"],
        "background": f"{warna['background']['page']} background colour",
        "margin": layout["spacing"]["outer_margin"],
        "gutter": layout["spacing"]["card_gutter"],
        "visual_density": style["style"]["densities"][0],
        "columns": str(layout["columns"]),
        "card_style": layout["alignment"]["cards"],
        "card_chrome": _chrome(layout),
        "spatial_rhythm": _rhythm(style),
        "header_visual": _illustration(layout),
        "layout_structure": _structure(layout),
        "typography": _typography(style["typography"]),
        "color": _colour(spec, warna, isi),
        "icons": _icons(style["icon_system"]),
        "header": _header(isi),
        "identity_band": _identity_band(isi),
        "cards": _cards(spec, isi, block_titles, kb, int(layout["columns"])),
        "confidence_block": _confidence_block(isi, kb, warna),
        "language_name": LANGUAGE_NAMES.get(spec.language, spec.language),
        "subtitle": _subtitle(presentasi, spec.language),
        "confidence_label": CONFIDENCE_LABEL.get(spec.language, "Keyakinan"),
        "constraints": _constraints(spec, style),
    }


def _subtitle(presentation: dict[str, Any], language: str) -> str:
    """The line printed under the title.

    Deliberately separate from `reference`, which is a direction to the drawing
    model ("draw it like a consulting brief") and must never reach the canvas.
    Conflating the two put an English style note on an Indonesian page.
    """
    subtitle = presentation.get("subtitle") or {}
    if isinstance(subtitle, dict):
        return subtitle.get(language) or subtitle.get("id") or ""
    return str(subtitle)


def _structure(layout: dict[str, Any]) -> str:
    lewati = {"detail_grid", "assessment_row", "actions_band", "closing_row",
              "footnote", "body", "content_grid", "closing"}
    langkah = [b["content"] for b in layout.get("bands") or [] if b.get("id") not in lewati]
    langkah.append(
        f"then every card listed below on a {layout['columns']}-column grid, each "
        f"at the row and column its entry states — reading left to right, top to "
        f"bottom, with no card moved to balance the page"
    )
    baris = [f"{i}. {s}" for i, s in enumerate(langkah, 1)]
    baris.append(
        "Render each card exactly once. Do not add any card, band, footer or "
        "reference block that is not listed below."
    )
    return "\n".join(baris)


def _chrome(layout: dict[str, Any]) -> str:
    chrome = layout.get("card_chrome") or {}
    order = ["header", "header_accent", "body", "border", "chips", "dividers",
              "emphasis_treatment"]
    return "\n".join(f"- {str(chrome[k]).strip()}" for k in order if chrome.get(k))


def _rhythm(style: dict[str, Any]) -> str:
    baris: list[str] = []
    seen: set[str] = set()
    for aturan in style["design_rules"]:
        for grup in ("spatial_rhythm", "elevation"):
            for kunci, nilai in (aturan.get(grup) or {}).items():
                if kunci in seen:
                    continue
                seen.add(kunci)
                teks = (
                    f"{kunci.replace('_', ' ')}: {nilai}"
                    if isinstance(nilai, (int, float))
                    else str(nilai).strip()
                )
                baris.append(f"- {teks}")
    return "\n".join(baris)


def _illustration(layout: dict[str, Any]) -> str:
    visual = layout.get("header_visual") or {}
    if not visual.get("enabled"):
        return ""
    baris = ["HEADER ILLUSTRATION", str(visual["content"]).strip()]
    baris += [f"- {a}" for a in visual.get("rules") or []]
    return "\n".join(baris) + "\n"


def _typography(t: dict[str, Any]) -> str:
    skala = t["scale"]
    return (
        f"Title font: {t['family']['title']}. Body font: {t['family']['body']}. "
        f"Numbers: {t['family']['numeric']}. "
        f"Title {skala['title']}; section headers {skala['section_header']}; "
        f"body {skala['body']}. {t['hierarchy']['rule'].strip()}"
    )


def _colour(spec: PresentationSpec, c: dict[str, Any], isi: CanvasContent) -> str:
    latar = c["background"]
    baris = [
        f"Primary {c['primary']['base']} for {c['primary']['usage']}. "
        f"Secondary {c['secondary']['base']} for {c['secondary']['usage']}.",
        "Severity colours: " + ", ".join(f"{k} = {v}" for k, v in c["severity"].items()) + ".",
        f"Cards {latar['card']} with {latar['border']} borders.",
    ]

    # Warna struktural. Tanpa ini setiap kartu tampil sebagai kotak putih dengan
    # judul gelap, dan halaman terbaca sebagai deretan seragam — keluhan "terlalu
    # sepi" pada dasarnya adalah tidak adanya pengelompokan yang terlihat.
    if latar.get("card_header"):
        baris.append(
            f"Each card header sits on a filled {latar['card_header']} band running "
            f"the full width of the card, with its text and icon in "
            f"{latar.get('on_card_header', '#FFFFFF')}."
        )
    if latar.get("band_tint"):
        baris.append(
            f"Identity band and footer sit on {latar['band_tint']}; card bodies stay "
            f"{latar['card']} so the tint groups rather than competes."
        )

    for nilai, kunci in _accents(spec, isi).items():
        warna = c["severity"].get(kunci)
        if warna:
            baris.append(f'The value "{nilai}" is shown in {warna}.')
    return "\n".join(baris)


def _accents(spec: PresentationSpec, isi: CanvasContent) -> dict[str, str]:
    """Accents to apply, falling back to the levels the canvas actually holds.

    A live run sent `accents = {}` and drew a page with no semantic colour at all.
    Leaving the choice entirely to the designer means an empty answer is a valid
    one; deriving the fallback from the content means the page is never colourless
    by omission, and never coloured for a level the finding did not assign.
    """
    if spec.accents:
        return dict(spec.accents)

    dari_isi: dict[str, str] = {}
    for block in isi.sections:
        for item in isi.items(block):
            if item.level:
                for kata in SEVERITY_WORDS.get(item.level, ()):
                    dari_isi[kata] = item.level
    return dari_isi


def _icons(i: dict[str, Any]) -> str:
    policy = i["usage_policy"]
    baris = [f"Style: {i['style']}. Weight: {i['line_weight']}. Placement: {policy['placement']}."]
    if i.get("icon_grid"):
        baris.append(str(i["icon_grid"]).strip())
    baris.append(f"Never use: {', '.join(policy['forbidden'])}.")
    return "\n".join(baris)


def _header(isi: CanvasContent) -> str:
    return f'Main title, write exactly: "{isi.equipment_tag}"'


def _identity_band(isi: CanvasContent) -> str:
    chip = [("Pabrik", isi.pabrik)]
    if isi.model_equipment:
        chip.append(("Model", isi.model_equipment))
    isian = "; ".join(f'label "{k}", value "{v}"' for k, v in chip if v)
    if not isian:
        return ""
    return (
        "IDENTITY BAND\n"
        f"A row of {len(chip)} equal-width chips sharing one baseline: {isian}. "
        "Small label above, heavier value beneath.\n"
    )


def _grid_cells(spec: PresentationSpec, isi: CanvasContent, columns: int) -> list[str]:
    """Work out where each card sits, rather than leaving it to the drawing.

    Numbering the cards was not enough on its own: a live page printed them 2, 3,
    1 across a row, so the reading order the reporter settled was lost even though
    every header carried its number. The grid is ours to compute — the number of
    columns is known and the order is fixed — so the prompt states the cell instead
    of asking the page to infer it.

    A dominant card takes a row to itself; that is what "largest card on the
    canvas" means in a grid, and leaving it implicit is what let the rest shuffle.
    """
    cells: list[str] = []
    row, column = 1, 1

    for blok in spec.order:
        if not isi.items(blok):
            continue
        dominant = spec.emphasis.get(blok) == "dominant"
        if dominant:
            if column > 1:
                row, column = row + 1, 1
            cells.append(f"row {row}, spanning all {columns} columns")
            row, column = row + 1, 1
            continue

        cells.append(f"row {row}, column {column} of {columns}")
        column += 1
        if column > columns:
            row, column = row + 1, 1

    return cells


def _cards(
    spec: PresentationSpec,
    isi: CanvasContent,
    block_titles: dict[str, str],
    kb: Any,
    columns: int,
) -> str:
    kartu: list[str] = []
    cells = _grid_cells(spec, isi, columns)
    nomor = 0
    for blok in spec.order:
        item = isi.items(blok)
        if not item:
            continue
        kartu.append(
            _one_card(nomor + 1, blok, item, spec, block_titles, kb, cells[nomor])
        )
        nomor += 1
    return "\n\n".join(kartu)


def _one_card(
    nomor: int,
    blok: str,
    item: list[CanvasItem],
    spec: PresentationSpec,
    block_titles: dict[str, str],
    kb: Any,
    cell: str,
) -> str:
    judul = block_titles.get(blok, blok.replace("_", " ").title())
    emphasis = spec.emphasis.get(blok, "secondary")
    baris = [
        f'{nomor}. Card header, write exactly: "{nomor}. {judul}" '
        f"({emphasis} emphasis — {EMPHASIS_INSTRUCTION[emphasis]}).",
        f"   Place this card at {cell}.",
    ]

    form = spec.form.get(blok)
    if form:
        pola = kb.get_visualization(form)
        baris.append(f"   Render as {pola['name']}: {pola['preferred_placement']}.")
        for aturan in pola.get("rules") or []:
            baris.append(f"   - {aturan}")

    for satu in item:
        baris.append(f"   {_one_item(satu)}")
    return "\n".join(baris)


def _one_item(item: CanvasItem) -> str:
    sections: list[str] = []
    if item.label:
        sections.append(f'label "{item.label}"')
    if item.date:
        sections.append(f'date "{item.date}"')
    if item.horizon:
        sections.append(f'horizon "{item.horizon}"')
    if item.text:
        sections.append(f'text "{item.text}"')
    if item.value:
        nilai = f'value "{item.value}", printed as text beside any shape'
        if item.value_label:
            nilai += f', captioned exactly "{item.value_label}" and nothing else'
        if item.reference:
            nilai += (
                f', shown against "{item.reference}" captioned exactly '
                f'"{item.reference_label}" — the gap between the two is the point'
            )
        sections.append(nilai)
    if item.level:
        sections.append(f'level "{item.level}"')
    if item.owner:
        sections.append(f'owner "{item.owner}"')
    return "- " + ", ".join(sections)


def _confidence_block(isi: CanvasContent, kb: Any, warna: dict[str, Any]) -> str:
    if not isi.keyakinan and not isi.perlu_eskalasi:
        return ""
    pola = kb.get_visualization("confidence_encoding")
    baris = ["CONFIDENCE AND ESCALATION"]

    if isi.keyakinan:
        entri = pola["confidence_scale"][isi.keyakinan]
        arti = entri.get("meaning_id") or entri.get("meaning_en")
        baris.append(
            f'Confidence is shown with the token "{entri["token"]}" and the words '
            f'"{arti}". Never show a percentage.'
        )
    if isi.perlu_eskalasi:
        baris.append(
            "An escalation marker is shown: this finding awaits a human decision, "
            "and both leading candidates are presented rather than one."
        )
    return "\n".join(baris) + "\n"


def _constraints(spec: PresentationSpec, style: dict[str, Any]) -> str:
    forbidden: list[str] = list(BASE_CONSTRAINTS)
    for aturan in style["design_rules"]:
        forbidden += aturan.get("forbidden") or []
    forbidden += spec.constraints

    seen: list[str] = []
    for satu in forbidden:
        bersih = str(satu).strip().rstrip(".")
        if bersih and bersih.lower() not in [s.lower() for s in seen]:
            seen.append(bersih)
    return "\n".join(f"- {s}" for s in seen)
