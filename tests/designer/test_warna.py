"""Tests for colour that the page cannot end up without.

A live run sent `accents = {}` and drew a page with no semantic colour at all.
Leaving the choice wholly to the designer makes an empty answer a valid one.
"""

from __future__ import annotations

from app.designer.composer import _accents
from app.designer.content import CanvasContent, CanvasItem
from app.designer.presentation import PresentationSpec


def kanvas(*level: str) -> CanvasContent:
    return CanvasContent(
        equipment_tag="APH-101",
        pabrik="Pabrik A",
        sections={"a": [CanvasItem(text="isi", level=lv) for lv in level]},
    )


def spec(accents: dict[str, str]) -> PresentationSpec:
    return PresentationSpec(style="engineer_diagnosis", order=["a"], accents=accents)


def test_aksen_kosong_diisi_dari_tingkat_di_kanvas():
    hasil = _accents(spec({}), kanvas("high", "medium"))
    assert hasil == {"HIGH": "high", "TINGGI": "high", "MEDIUM": "medium", "SEDANG": "medium"}


def test_tingkat_yang_tidak_dimiliki_tidak_diberi_warna():
    """Colouring a level the finding never assigned would put a severity on the
    page that no item carries."""
    assert "RENDAH" not in _accents(spec({}), kanvas("high"))


def test_pilihan_designer_tetap_menang():
    pilihan = {"TINGGI": "critical"}
    assert _accents(spec(pilihan), kanvas("high")) == pilihan


def test_kanvas_tanpa_tingkat_tidak_memaksa_warna():
    assert _accents(spec({}), kanvas("", "")) == {}
