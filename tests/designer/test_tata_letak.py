"""Tests for deterministic card placement.

Numbering the cards was not enough: a live page printed them 2, 3, 1 across a
row. The reporter's reading order is a decision, not a suggestion, so the cell
each card occupies is computed here rather than left to the drawing.
"""

from __future__ import annotations

from app.designer.composer import _grid_cells
from app.designer.content import CanvasContent, CanvasItem
from app.designer.presentation import PresentationSpec


def kanvas(*blok: str) -> CanvasContent:
    return CanvasContent(
        equipment_tag="APH-101",
        pabrik="Pabrik A",
        sections={b: [CanvasItem(text="isi")] for b in blok},
    )


def spec(order: list[str], **emphasis: str) -> PresentationSpec:
    return PresentationSpec(
        style="engineer_diagnosis",
        order=order,
        emphasis={b: emphasis.get(b, "secondary") for b in order},
    )


def test_kartu_mengalir_kiri_ke_kanan_lalu_turun():
    blok = ["a", "b", "c", "d", "e"]
    cells = _grid_cells(spec(blok), kanvas(*blok), columns=2)
    assert cells == [
        "row 1, column 1 of 2",
        "row 1, column 2 of 2",
        "row 2, column 1 of 2",
        "row 2, column 2 of 2",
        "row 3, column 1 of 2",
    ]


def test_blok_dominan_mengambil_satu_baris_penuh():
    """“The largest card on the canvas” has to mean something in a grid, or the
    cards around it get shuffled to make room."""
    blok = ["a", "b", "c"]
    cells = _grid_cells(spec(blok, b="dominant"), kanvas(*blok), columns=2)
    assert cells == [
        "row 1, column 1 of 2",
        "row 2, spanning all 2 columns",
        "row 3, column 1 of 2",
    ]


def test_blok_tanpa_isi_tidak_menyisakan_sel_kosong():
    """A block the reporter selected but the finding cannot fill is not drawn,
    so it must not consume a cell either."""
    cells = _grid_cells(spec(["a", "kosong", "b"]), kanvas("a", "b"), columns=2)
    assert cells == ["row 1, column 1 of 2", "row 1, column 2 of 2"]
