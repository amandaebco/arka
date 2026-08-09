"""Tests for the infographic quality gate.

The heaviest check here is text fidelity. It is the second compensating control
behind the infographic exception in Constitution 1.2.0 — without it the exception
has no enforcement, only a promise.
"""

from __future__ import annotations

import pytest

from app.agents.designer import KUNCI_SPESIFIKASI
from app.agents.qa import _berasal_dari, _kumpulan_teks_temuan, periksa_infografis
from app.agents.reporter import KUNCI_TEMUAN
from app.designer.content import build_content, is_composed_label
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
    sumber = _kumpulan_teks_temuan(finding)
    for blok in selected:
        for item in content.items(blok):
            kandidat = [item.text]
            if item.label and not is_composed_label(item.label):
                kandidat.append(item.label)
            for nilai in kandidat:
                if nilai:
                    assert _berasal_dari(nilai, sumber), f"{blok}: “{nilai}”"


def test_kalimat_karangan_tertangkap(finding):
    sumber = _kumpulan_teks_temuan(finding)
    assert not _berasal_dari("Kerusakan katastrofik akan segera terjadi", sumber)


def test_label_struktural_dikenali_sebagai_susunan(finding):
    """Composed labels name a role, not a value — they are exempt by declaration,
    not by a loophole in the fidelity check."""
    assert is_composed_label("Langkah 2")
    assert is_composed_label("Gejala")
    assert not is_composed_label("Degradasi seal kepala pengisi")


# --- Objective checks -----------------------------------------------------

@pytest.mark.asyncio
async def test_infografis_sehat_lulus(finding, selected):
    hasil = await periksa_infografis(konteks(finding, spesifikasi(selected)))
    assert hasil.startswith("LULUS")


@pytest.mark.asyncio
async def test_tanpa_spesifikasi_tidak_ada_yang_diperiksa(finding):
    konteks_kosong = KonteksPalsu({KUNCI_TEMUAN: finding.model_dump(mode="json")})
    hasil = await periksa_infografis(konteks_kosong)
    assert "Belum ada infografis" in hasil


@pytest.mark.asyncio
async def test_dua_blok_dominan_ditangkap(finding, selected):
    spec = spesifikasi(selected)
    spec["emphasis"][selected[1]] = "dominant"
    hasil = await periksa_infografis(konteks(finding, spec))
    assert "hanya boleh satu" in hasil


@pytest.mark.asyncio
async def test_tanpa_titik_fokus_ditangkap(finding, selected):
    spec = spesifikasi(selected)
    spec["emphasis"] = {s: "secondary" for s in selected}
    hasil = await periksa_infografis(konteks(finding, spec))
    assert "tidak punya titik fokus" in hasil


@pytest.mark.asyncio
async def test_blok_tanpa_isi_ditangkap(finding, selected):
    spec = spesifikasi(selected, order=selected + ["rantai_kausal_palsu"])
    hasil = await periksa_infografis(konteks(finding, spec))
    assert "tidak punya isi" in hasil


@pytest.mark.asyncio
async def test_eskalasi_wajib_terlihat_di_awal(finding, selected):
    if not finding.perlu_eskalasi:
        pytest.skip("temuan contoh tidak menuntut eskalasi")
    tanpa_kandidat = [s for s in selected if s != "kandidat_penyebab"]
    spec = spesifikasi(selected, order=tanpa_kandidat + ["kandidat_penyebab"])
    hasil = await periksa_infografis(konteks(finding, spec))
    assert "eskalasi" in hasil.lower()
