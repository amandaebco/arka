"""Canvas content — turns assembled blocks into the strings that reach the page.

This module is the boundary that Principle I rests on. Every string the drawing
provider ever sees is produced here, from `Blok.data`, verbatim. The model that
draws the page never computes, rounds, translates, or infers a value; it only
receives text that this module has already fixed.

Two consequences follow, and both are deliberate:

* Number formatting lives here and nowhere else, so a figure reads identically on
  the infographic and in the memo.
* An item carries its value both as text and, where a shape will be drawn, as the
  quantity behind that shape — satisfying the rule that no value is ever carried
  by shape alone.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from app.reporting.blocks import Blok, IdBlok

# Confidence in `Finding` has exactly three levels, and the design library encodes
# exactly three tokens. The mapping is direct — never a percentage.
CONFIDENCE_TOKENS = {"tinggi": "high", "sedang": "medium", "rendah": "low"}

# Recommendation priority doubles as the horizon label on the actions block.
# Labels are taken from the source vocabulary, never normalised into another scheme.
HORIZON_LABELS = {"segera": "Segera", "terjadwal": "Terjadwal", "pantau": "Pantau"}

# Labels this module composes rather than lifts from the finding. They name a
# structural role, not a value, so the fidelity check must not read them as
# fabricated content — and must still read everything else strictly.
COMPOSED_LABELS = frozenset({"Gejala", "Penyebab teratas", "Perlu putusan manusia"})
COMPOSED_PREFIXES = ("Langkah ",)


def is_composed_label(label: str) -> bool:
    """Whether a label was authored here rather than taken from the finding."""
    return label in COMPOSED_LABELS or label.startswith(COMPOSED_PREFIXES)


@dataclass
class CanvasItem:
    """One line of content. Optional fields stay empty unless the source has them."""

    text: str = ""
    label: str = ""
    value: str = ""
    level: str = ""
    horizon: str = ""
    owner: str = ""
    date: str = ""
    quantity: str = ""  # the number behind a drawn shape, always also shown as text

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class CanvasContent:
    """Everything the page may contain, keyed by block."""

    equipment_tag: str
    pabrik: str
    model_equipment: str = ""
    keyakinan: str = ""
    perlu_eskalasi: bool = False
    sections: dict[str, list[CanvasItem]] = field(default_factory=dict)

    def items(self, blok: str) -> list[CanvasItem]:
        return self.sections.get(blok, [])

    def has(self, blok: str) -> bool:
        return bool(self.sections.get(blok))

    def to_dict(self) -> dict[str, Any]:
        return {
            "equipment_tag": self.equipment_tag,
            "pabrik": self.pabrik,
            "model_equipment": self.model_equipment,
            "keyakinan": self.keyakinan,
            "perlu_eskalasi": self.perlu_eskalasi,
            "sections": {k: [i.to_dict() for i in v] for k, v in self.sections.items()},
        }


def as_number(nilai: Decimal | float | int | None, decimals: int = 2) -> str:
    """Format a number once, here, so every surface shows it identically.

    Indonesian convention: dot for thousands, comma for the decimal mark.
    """
    if nilai is None:
        return ""
    teks = f"{Decimal(str(nilai)):,.{decimals}f}"
    return teks.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def as_percent(nilai: Decimal | float | None) -> str:
    """A score in 0–1 shown as a percentage. Never used for confidence."""
    return "" if nilai is None else f"{as_number(Decimal(str(nilai)) * 100, 1)}%"


def build_content(selected_blocks: list[Blok]) -> CanvasContent:
    """Build canvas content from the blocks the reporter selected.

    Blocks marked unavailable are skipped here rather than rendered empty — the
    single place where that filtering happens for the visual surface.
    """
    peta = {b.id: b for b in selected_blocks}
    ringkasan = peta.get("ringkasan")
    summary_data = ringkasan.data if ringkasan else {}

    isi = CanvasContent(
        equipment_tag=str(summary_data.get("equipment_tag", "")),
        pabrik=str(summary_data.get("pabrik", "")),
        model_equipment=str(summary_data.get("model_equipment") or ""),
        keyakinan=CONFIDENCE_TOKENS.get(str(summary_data.get("keyakinan", "")), ""),
        perlu_eskalasi=bool(summary_data.get("perlu_eskalasi")),
    )

    for blok in selected_blocks:
        if not blok.tersedia:
            continue
        bangun = BUILDERS.get(blok.id)
        if not bangun:
            continue
        item = [i for i in bangun(blok.data) if i.text or i.value or i.label]
        if item:
            isi.sections[blok.id] = item

    return isi


def _summary(data: dict) -> list[CanvasItem]:
    item = [CanvasItem(label="Gejala", text=g) for g in data.get("gejala") or []]
    top = data.get("penyebab_teratas")
    if top is not None:
        item.append(
            CanvasItem(
                label="Penyebab teratas",
                text=top.nama,
                value=as_number(top.skor.total),
                quantity=as_number(top.skor.total),
            )
        )
    if data.get("perlu_eskalasi"):
        item.append(
            CanvasItem(
                label="Perlu putusan manusia",
                text=str(data.get("alasan_eskalasi") or "Dua kandidat top berdekatan"),
                level="high",
            )
        )
    return item


def _candidates(data: dict) -> list[CanvasItem]:
    return [
        CanvasItem(
            label=k.nama,
            text=k.deskripsi or "",
            value=as_number(k.skor.total),
            quantity=as_number(k.skor.total),
        )
        for k in data.get("kandidat") or []
    ]


def _precedents(data: dict) -> list[CanvasItem]:
    return [
        CanvasItem(
            label=f"{p.pabrik} · {p.equipment_tag}",
            text=p.penyelesaian or "Penyelesaian belum tercatat",
            date=p.tanggal_kejadian.isoformat(),
            value=f"{as_number(p.downtime_jam, 1)} jam" if p.downtime_jam is not None else "",
            quantity=as_number(p.downtime_jam, 1) if p.downtime_jam is not None else "",
        )
        for p in data.get("preseden") or []
    ]


def _causal_chain(data: dict) -> list[CanvasItem]:
    return [
        CanvasItem(label=m.peran, text=m.label, value=m.detail or "")
        for m in data.get("mata_rantai") or []
    ]


def _spare_parts(data: dict) -> list[CanvasItem]:
    item = []
    for s in data.get("sparepart") or []:
        details = [f"{s.part_number}"]
        if s.lead_time_minggu is not None:
            details.append(f"lead time {s.lead_time_minggu} minggu")
        if s.jumlah_vendor is not None:
            details.append(f"{s.jumlah_vendor} vendor")
        item.append(
            CanvasItem(
                label=s.nama,
                text=" · ".join(details),
                value=as_number(s.criticality),
                quantity=as_number(s.criticality),
                level="high" if s.selisih > 0 else "",
            )
        )
    return item


def _reasoning_trail(data: dict) -> list[CanvasItem]:
    return [
        CanvasItem(label=f"Langkah {langkah.urutan}", text=langkah.aksi, value=langkah.hasil)
        for langkah in data.get("langkah") or []
    ]


def _recommendations(data: dict) -> list[CanvasItem]:
    """The action leads; the reasoning follows.

    `label` is what the page renders as the heading of an item, so the action
    belongs there and its justification below. Putting the justification first
    reads as though the reasoning were the recommendation.
    """
    return [
        CanvasItem(
            label=r.tindakan,
            text=r.dasar or "",
            horizon=HORIZON_LABELS.get(r.prioritas, r.prioritas),
        )
        for r in data.get("rekomendasi") or []
    ]


def _citations(data: dict) -> list[CanvasItem]:
    return [
        CanvasItem(
            label=s.tipe_dokumen,
            text=s.judul,
            date=s.tanggal.isoformat() if s.tanggal else "",
            value=s.lokator or "",
        )
        for s in data.get("sitasi") or []
    ]


BUILDERS: dict[IdBlok, Any] = {
    "ringkasan": _summary,
    "kandidat_penyebab": _candidates,
    "preseden_lintas_pabrik": _precedents,
    "rantai_kausal": _causal_chain,
    "sparepart_kritis": _spare_parts,
    "jejak_penalaran": _reasoning_trail,
    "rekomendasi": _recommendations,
    "sitasi": _citations,
}
