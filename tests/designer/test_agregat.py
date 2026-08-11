"""Tests for counts and scales derived from the canvas.

Both patterns stayed closed because the canvas had no shape they could take.
Opening them by computing the shape is sound; opening them by relaxing the
filter would invite the page to invent parts and grades of its own.
"""

from __future__ import annotations

import pytest

from app.agents.designer import knowledge_base
from app.designer.aggregate import confidence_scale, distribution
from app.designer.content import CanvasItem
from app.designer.forms import applicable_forms


@pytest.fixture(scope="module")
def kb():
    return knowledge_base()


def rekomendasi(*horizon: str) -> list[CanvasItem]:
    return [CanvasItem(text=f"tindakan {n}", horizon=h) for n, h in enumerate(horizon)]


def test_potongan_berjumlah_utuh():
    bagian, total = distribution(rekomendasi("Segera", "Terjadwal", "Segera"))
    assert total == 3
    assert sum(jumlah for _, jumlah in bagian) == total


def test_butir_tanpa_kelompok_membatalkan_donut():
    """A split that silently drops what it could not classify would draw a whole
    that is not whole."""
    sebagian = [CanvasItem(text="a", horizon="Segera"), CanvasItem(text="b")]
    assert distribution(sebagian) is None


def test_terlalu_banyak_kelompok_bukan_donut():
    assert distribution(rekomendasi("A", "B", "C", "D")) is None


def test_donut_ditawarkan_hanya_bila_potongannya_ada(kb):
    dengan = rekomendasi("Segera", "Terjadwal", "Segera")
    tanpa = [CanvasItem(text="a"), CanvasItem(text="b"), CanvasItem(text="c")]
    assert "donut_status" in applicable_forms(dengan, kb)
    assert "donut_status" not in applicable_forms(tanpa, kb)


def test_skala_keyakinan_selalu_utuh():
    """A gauge draws every grade, not only the one in force.

    The vocabulary is the canvas's, not the finding's — reading the finding's
    Indonesian here made the first version return None for every finding, so the
    gauge never appeared and nothing failed to say so.
    """
    jenjang, sekarang = confidence_scale("medium")
    assert jenjang == ["low", "medium", "high"]
    assert sekarang == "medium"


def test_kosakata_temuan_bukan_kosakata_kanvas():
    assert confidence_scale("sedang") is None


def test_nilai_di_luar_kosakata_tidak_diberi_tempat_di_busur():
    assert confidence_scale("lumayan") is None
