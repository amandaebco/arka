"""Tests for data-driven form selection.

A card's form follows what its own items can fill, the same rule the section
model already follows one level up. The knowledge base had stated each pattern's
data requirements from the start; nothing read them, so the designer chose from
memory and sent `{}` when unsure.
"""

from __future__ import annotations

import pytest

from app.agents.designer import knowledge_base
from app.designer.content import CanvasItem
from app.designer.forms import applicable_forms


@pytest.fixture(scope="module")
def kb():
    return knowledge_base()


def test_tanpa_tanggal_tidak_ditawari_linimasa(kb):
    """A causal chain carries no dates, and a live page answered the timeline it
    was given with four invented timestamps."""
    tanpa = [CanvasItem(label=f"L{n}", text="langkah") for n in range(4)]
    assert "timeline" not in applicable_forms(tanpa, kb)


def test_dengan_tanggal_boleh_linimasa(kb):
    dengan = [CanvasItem(label=f"L{n}", text="kejadian", date="2025-09-15") for n in range(4)]
    assert "timeline" in applicable_forms(dengan, kb)


def test_penunjuk_sitasi_bukan_angka(kb):
    """“hlm. 3, §2.1” is text that happens to contain digits. Read as a number it
    offered the citations card a KPI treatment — a page number as headline."""
    sitasi = [CanvasItem(label="fmea", text="FMEA", value="hlm. 3, §2.1") for _ in range(3)]
    assert "kpi_cards" not in applicable_forms(sitasi, kb)


def test_angka_sungguhan_boleh_kpi(kb):
    skor = [CanvasItem(label=f"K{n}", text="kandidat", value="0,91") for n in range(3)]
    assert "kpi_cards" in applicable_forms(skor, kb)


def test_bentuk_yang_menuntut_bidang_tak_dimiliki_tidak_ditawarkan(kb):
    """The canvas has no baseline, no grade labels, no target. Offering those
    patterns is how a page ends up drawing a scale nobody supplied."""
    item = [CanvasItem(label=f"K{n}", text="isi", value="0,50") for n in range(3)]
    ditawarkan = applicable_forms(item, kb)
    assert not {"comparison", "gauge_rating", "kpi_target", "donut_status"} & set(ditawarkan)


def test_kartu_kosong_tidak_punya_bentuk(kb):
    assert applicable_forms([], kb) == []


def test_kekritisan_dibawa_sebagai_perbandingan(kb):
    """ARKA's headline is the gap between the master data's number and its own —
    0,30 against 0,87. A lone figure hides exactly the thing worth showing."""
    from app.designer.content import build_content
    from app.reporting.blocks import susun_blok
    from app.synthetic.finding_contoh import finding_contoh

    blok = [b for b in susun_blok(finding_contoh()).values() if b.tersedia]
    item = build_content(blok).items("sparepart_kritis")

    assert all(i.reference and i.reference_label for i in item)
    assert "comparison" in applicable_forms(item, kb)
