"""Tests for the infographic quality gate.

The heaviest check here is text fidelity. It is the second compensating control
behind the infographic exception in Constitution 1.2.0 — without it the exception
has no enforcement, only a promise.
"""

from __future__ import annotations

import pytest

from app.agents.designer import KUNCI_SPESIFIKASI
from app.agents.qa import _comes_from, _finding_text, periksa_infografis
from app.agents.reporter import KUNCI_TEMUAN
from app.designer.content import (
    CanvasContent,
    CanvasItem,
    build_content,
    is_composed_label,
)
from app.designer.inspection import authorised_strings, unauthorised_text
from app.reporting.blocks import susun_blok
from app.synthetic.finding_contoh import finding_contoh


class KonteksPalsu:
    """Minimal stand-in for ToolContext: the checker only touches `state`."""

    def __init__(self, state: dict):
        self.state = state


@pytest.fixture(scope="module")
def finding():
    return finding_contoh()


@pytest.fixture(scope="module")
def blocks(finding):
    return [b for b in susun_blok(finding).values() if b.tersedia]


@pytest.fixture(scope="module")
def content(blocks):
    return build_content(blocks)


@pytest.fixture(scope="module")
def selected(blocks, content):
    return [b.id for b in blocks if content.has(b.id)]


def konteks(finding, spec: dict) -> KonteksPalsu:
    return KonteksPalsu(
        {KUNCI_TEMUAN: finding.model_dump(mode="json"), KUNCI_SPESIFIKASI: spec}
    )


def spesifikasi(selected, **ubah) -> dict:
    dasar = {
        "style": "engineer_diagnosis",
        "order": list(selected),
        "emphasis": {s: "secondary" for s in selected},
    }
    dasar["emphasis"][selected[0]] = "dominant"
    dasar.update(ubah)
    return dasar


# --- Text provenance ------------------------------------------------------

def test_teks_kanvas_semuanya_berasal_dari_temuan(finding, content, selected):
    """Nothing on the canvas may be invented — this is the exception's guard."""
    source_text = _finding_text(finding)
    for block in selected:
        for item in content.items(block):
            checkable = [item.text]
            if item.label and not is_composed_label(item.label):
                checkable.append(item.label)
            for value in checkable:
                if value:
                    assert _comes_from(value, source_text), f"{block}: “{value}”"


def test_kalimat_karangan_tertangkap(finding):
    source_text = _finding_text(finding)
    assert not _comes_from("Kerusakan katastrofik akan segera terjadi", source_text)


def test_label_struktural_dikenali_sebagai_susunan(finding):
    """Composed labels name a role, not a value — they are exempt by declaration,
    not by a loophole in the fidelity check."""
    assert is_composed_label("Langkah 2")
    assert is_composed_label("Gejala")
    assert not is_composed_label("Degradasi seal kepala pengisi")


# --- Authorised page text -------------------------------------------------

def kanvas_dengan_level(level: str) -> CanvasContent:
    return CanvasContent(
        equipment_tag="APH-101",
        pabrik="Pabrik A",
        sections={"tindakan": [CanvasItem(text="Ganti seal", level=level)]},
    )


def test_kata_tingkat_ikut_disetujui_bersama_levelnya():
    """A severity chip is drawn as a word while the content carries the key. The
    word has to be authorised, or a faithful page is flagged for its own data."""
    allowed = authorised_strings(kanvas_dengan_level("high"), ["Tindakan"])
    assert not unauthorised_text(["TINGGI", "HIGH"], allowed)


def test_kata_tingkat_yang_tidak_dimiliki_tetap_ditolak():
    """Authorising every severity word globally would let a low finding print
    “TINGGI” unnoticed — the exemption follows the data, not the vocabulary."""
    allowed = authorised_strings(kanvas_dengan_level("low"), ["Tindakan"])
    assert unauthorised_text(["TINGGI"], allowed) == ["TINGGI"]


# --- Objective checks -----------------------------------------------------

@pytest.mark.asyncio
async def test_infografis_sehat_lulus(finding, selected):
    outcome = await periksa_infografis(konteks(finding, spesifikasi(selected)))
    assert outcome.startswith("LULUS")


@pytest.mark.asyncio
async def test_tanpa_spesifikasi_tidak_ada_yang_diperiksa(finding):
    konteks_kosong = KonteksPalsu({KUNCI_TEMUAN: finding.model_dump(mode="json")})
    outcome = await periksa_infografis(konteks_kosong)
    assert "Belum ada infografis" in outcome


@pytest.mark.asyncio
async def test_dua_blok_dominan_ditangkap(finding, selected):
    spec = spesifikasi(selected)
    spec["emphasis"][selected[1]] = "dominant"
    outcome = await periksa_infografis(konteks(finding, spec))
    assert "hanya boleh satu" in outcome


@pytest.mark.asyncio
async def test_tanpa_titik_fokus_ditangkap(finding, selected):
    spec = spesifikasi(selected)
    spec["emphasis"] = {s: "secondary" for s in selected}
    outcome = await periksa_infografis(konteks(finding, spec))
    assert "tidak punya titik fokus" in outcome


@pytest.mark.asyncio
async def test_blok_tanpa_isi_ditangkap(finding, selected):
    spec = spesifikasi(selected, order=selected + ["rantai_kausal_palsu"])
    outcome = await periksa_infografis(konteks(finding, spec))
    assert "tidak punya isi" in outcome


@pytest.mark.asyncio
async def test_eskalasi_wajib_terlihat_di_awal(finding, selected):
    if not finding.perlu_eskalasi:
        pytest.skip("temuan contoh tidak menuntut eskalasi")
    tanpa_kandidat = [s for s in selected if s != "kandidat_penyebab"]
    spec = spesifikasi(selected, order=tanpa_kandidat + ["kandidat_penyebab"])
    outcome = await periksa_infografis(konteks(finding, spec))
    assert "eskalasi" in outcome.lower()


def test_angka_bertelanjang_diberi_nama_di_kanvas(content):
    """A 0..1 figure with no caption is an open question, and the page answers it
    by inventing one — a live run captioned criticality “Kritikalitas”."""
    for block in ("kandidat_penyebab", "sparepart_kritis"):
        for item in content.items(block):
            if item.value:
                assert item.value_label, f"{block}: “{item.value}” tanpa nama"


def test_nama_angka_ikut_disetujui(content, selected):
    """The caption is composed, not quoted — so it has to be authorised, or the
    page gets flagged for printing exactly what we asked it to print."""
    allowed = authorised_strings(content, list(selected))
    assert not unauthorised_text(["Kekritisan (skala 0–1)"], allowed)
