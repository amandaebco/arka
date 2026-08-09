"""Presentation specification — the designer's one decision, written down.

The designer decides emphasis and visual form. It does not decide which blocks
appear: `reporter` already owns that, and this module refuses any spec that tries
to widen the set it was given. Two modules holding the same decision is the one
failure mode Principle V exists to prevent.

The spec carries identifiers only — never content. Every string on the canvas is
produced by `content.py` from the finding; anything the model names here must
already exist in the design knowledge base or the spec is rejected.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

EMPHASIS_LEVELS = ("dominant", "primary", "secondary", "tertiary")


@dataclass
class PresentationSpec:
    """How the selected blocks are presented. Identifiers only, no content."""

    style: str
    language: str = "id"
    order: list[str] = field(default_factory=list)          # from reporter
    emphasis: dict[str, str] = field(default_factory=dict)  # block -> level
    form: dict[str, str] = field(default_factory=dict)     # block -> pattern id
    accents: dict[str, str] = field(default_factory=dict)      # value -> severity key
    constraints: list[str] = field(default_factory=list)
    rationale: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PresentationSpec:
        if not data.get("style"):
            raise ValueError("spesifikasi penyajian wajib menyebut 'style'")
        return cls(
            style=str(data["style"]),
            language=str(data.get("language") or "id"),
            order=[str(s) for s in data.get("order") or []],
            emphasis={str(k): str(v) for k, v in (data.get("emphasis") or {}).items()},
            form={str(k): str(v) for k, v in (data.get("form") or {}).items()},
            accents={str(k): str(v) for k, v in (data.get("accents") or {}).items()},
            constraints=[str(c) for c in data.get("constraints") or []],
            rationale=str(data.get("rationale") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise(
    spec: PresentationSpec,
    selected_blocks: list[str],
    default_emphasis: dict[str, str],
) -> PresentationSpec:
    """Force the spec back inside its boundaries.

    The order always follows what the reporter decided. The designer may weight
    blocks differently; it may not add, drop, or reorder them.
    """
    spec.order = list(selected_blocks)
    spec.emphasis = {
        blok: spec.emphasis.get(blok, default_emphasis.get(blok, "secondary"))
        for blok in selected_blocks
    }
    spec.form = {k: v for k, v in spec.form.items() if k in selected_blocks}
    return spec


def validate(spec: PresentationSpec, kb: Any, selected_blocks: list[str]) -> list[str]:
    """Return every problem found. An empty list means the spec is safe to compile."""
    problems: list[str] = []

    if spec.style not in kb.list_styles():
        problems.append(
            f"style '{spec.style}' tidak ada di pustaka desain. "
            f"Tersedia: {', '.join(kb.list_styles())}"
        )
        return problems  # the rest depends on a valid style

    if spec.language not in kb.languages:
        problems.append(f"bahasa '{spec.language}' tidak didukung ({kb.languages})")

    allowed = set(selected_blocks)
    for block in spec.order:
        if block not in allowed:
            problems.append(
                f"blok '{block}' tidak dipilih reporter — designer tidak boleh menambah"
            )
    if not spec.order:
        problems.append("spesifikasi tidak memuat satu blok pun")

    allowed_forms = set(kb.get_style(spec.style)["visual"]["visualization_patterns"])
    for block, form in spec.form.items():
        if form not in allowed_forms:
            problems.append(
                f"bentuk '{form}' untuk blok '{block}' tidak diizinkan style "
                f"'{spec.style}' ({', '.join(sorted(allowed_forms))})"
            )

    for block, level in spec.emphasis.items():
        if level not in EMPHASIS_LEVELS:
            problems.append(
                f"penekanan blok '{block}' bernilai '{level}', harus salah satu dari "
                f"{list(EMPHASIS_LEVELS)}"
            )
    dominant = [b for b, t in spec.emphasis.items() if t == "dominant" and b in spec.order]
    if len(dominant) > 1:
        problems.append(
            f"ada {len(dominant)} blok dominant ({', '.join(sorted(dominant))}); hanya boleh satu"
        )

    capacity = kb.page_capacity(spec.style)
    if len(spec.order) > capacity:
        problems.append(f"{len(spec.order)} blok melebihi kapasitas halaman ({capacity})")

    return problems
