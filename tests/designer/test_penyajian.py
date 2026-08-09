"""Tests for the deterministic half of the designer: content, spec, and composition.

None of these call a model. That is the point — everything that decides whether a
value reaches the page intact is code, and code can be pinned down by tests.
"""

from __future__ import annotations

import pytest

from app.designer.composer import compose_prompt
from app.designer.content import as_number, build_content
from app.designer.knowledge import DesignKnowledgeBase
from app.designer.presentation import PresentationSpec, normalise, validate
from app.reporting.blocks import susun_blok
from app.synthetic.finding_contoh import finding_contoh

STYLE = "engineer_diagnosis"


@pytest.fixture(scope="module")
def kb() -> DesignKnowledgeBase:
    return DesignKnowledgeBase.load()


@pytest.fixture(scope="module")
def temuan():
    return finding_contoh()


@pytest.fixture(scope="module")
def blok(temuan):
    return [b for b in susun_blok(temuan).values() if b.tersedia]


@pytest.fixture(scope="module")
def isi(blok):
    return build_content(blok)


@pytest.fixture(scope="module")
def terpilih(blok, isi):
    return [b.id for b in blok if isi.has(b.id)]


def spesifikasi(kb, terpilih, **ubah) -> PresentationSpec:
    dasar = {"style": STYLE, "language": "id"}
    dasar.update(ubah)
    bawaan = kb.resolve_style(STYLE)["storytelling"].get("emphasis_order") or {}
    return normalise(PresentationSpec.from_dict(dasar), terpilih, bawaan)


# --- Number formatting ----------------------------------------------------

def test_angka_memakai_konvensi_indonesia():
    assert as_number(3093.8, 1) == "3.093,8"
    assert as_number(0.91) == "0,91"


def test_angka_kosong_untuk_nilai_tidak_ada():
    assert as_number(None) == ""


# --- Content fidelity -----------------------------------------------------

def test_nilai_terbawa_verbatim_dari_temuan(temuan, isi):
    """Every candidate score reaches the canvas exactly as the finding states it."""
    tampil = {i.value for i in isi.items("kandidat_penyebab")}
    for kandidat in temuan.kandidat:
        assert as_number(kandidat.skor.total) in tampil


def test_setiap_nilai_juga_membawa_kuantitasnya(isi):
    """No value is ever carried by shape alone (Constitution 1.2.0, imbangan 1)."""
    for blok in isi.sections:
        for item in isi.items(blok):
            if item.quantity:
                assert item.value, f"{blok}: kuantitas tanpa nilai tertulis"


def test_keyakinan_tiga_tingkat_bukan_persentase(isi):
    assert isi.keyakinan in {"high", "medium", "low"}


def test_eskalasi_terbawa_ke_kanvas(temuan, isi):
    assert isi.perlu_eskalasi == temuan.perlu_eskalasi
    if temuan.perlu_eskalasi:
        label = {i.label for i in isi.items("ringkasan")}
        assert "Perlu putusan manusia" in label


def test_blok_tanpa_data_tidak_pernah_muncul(temuan):
    """A block the reporter could not fill is absent, never an empty card."""
    semua = susun_blok(temuan)
    kosong = [b for b in semua.values() if not b.tersedia]
    isi_semua = build_content(list(semua.values()))
    for satu in kosong:
        assert not isi_semua.has(satu.id)


def test_label_horizon_diambil_dari_kosakata_sumber(isi):
    horizon = {i.horizon for i in isi.items("rekomendasi") if i.horizon}
    assert horizon <= {"Segera", "Terjadwal", "Pantau"}


# --- Specification boundaries ---------------------------------------------

def test_spesifikasi_sah_lolos_pemeriksaan(kb, terpilih):
    assert validate(spesifikasi(kb, terpilih), kb, terpilih) == []


def test_designer_tidak_boleh_menambah_blok(kb, terpilih):
    """Block selection belongs to the reporter; widening it must be rejected."""
    spec = PresentationSpec.from_dict({"style": STYLE, "order": terpilih + ["sitasi_palsu"]})
    assert any("tidak dipilih reporter" in m for m in validate(spec, kb, terpilih))


def test_urutan_selalu_mengikuti_reporter(kb, terpilih):
    spec = spesifikasi(kb, terpilih, order=list(reversed(terpilih)))
    assert spec.order == terpilih


def test_bentuk_di_luar_style_ditolak(kb, terpilih):
    spec = spesifikasi(kb, terpilih, form={terpilih[0]: "kpi_target"})
    assert any("tidak diizinkan style" in m for m in validate(spec, kb, terpilih))


def test_dua_blok_dominan_ditolak(kb, terpilih):
    spec = spesifikasi(
        kb, terpilih, emphasis={terpilih[0]: "dominant", terpilih[1]: "dominant"}
    )
    assert any("hanya boleh satu" in m for m in validate(spec, kb, terpilih))


def test_style_tak_dikenal_ditolak(kb, terpilih):
    spec = PresentationSpec.from_dict({"style": "ngawur"})
    assert any("tidak ada di pustaka desain" in m for m in validate(spec, kb, terpilih))


def test_spesifikasi_wajib_menyebut_style():
    with pytest.raises(ValueError):
        PresentationSpec.from_dict({"language": "id"})


# --- Composition ----------------------------------------------------------

def test_prompt_deterministik(kb, isi, blok, terpilih):
    judul = {b.id: b.judul for b in blok}
    spec = spesifikasi(kb, terpilih)
    assert compose_prompt(spec, isi, judul, kb) == compose_prompt(spec, isi, judul, kb)


def test_setiap_teks_kanvas_muncul_di_prompt(kb, isi, blok, terpilih):
    judul = {b.id: b.judul for b in blok}
    prompt = compose_prompt(spesifikasi(kb, terpilih), isi, judul, kb)
    for satu in terpilih:
        for item in isi.items(satu):
            for nilai in (item.text, item.label, item.value, item.horizon):
                if nilai:
                    assert nilai in prompt, f"hilang dari prompt: {nilai}"


def test_judul_kartu_memakai_judul_blok_arka(kb, isi, blok, terpilih):
    """The infographic names a thing exactly as the memo names it."""
    judul = {b.id: b.judul for b in blok}
    prompt = compose_prompt(spesifikasi(kb, terpilih), isi, judul, kb)
    for satu in terpilih:
        assert judul[satu] in prompt


def test_prompt_melarang_persentase_keyakinan(kb, isi, blok, terpilih):
    judul = {b.id: b.judul for b in blok}
    prompt = compose_prompt(spesifikasi(kb, terpilih), isi, judul, kb)
    assert "Never show a percentage" in prompt
    assert "no confidence percentages" in prompt


def test_prompt_melarang_penggambar_menghitung(kb, isi, blok, terpilih):
    judul = {b.id: b.judul for b in blok}
    prompt = compose_prompt(spesifikasi(kb, terpilih), isi, judul, kb)
    assert "never redraw, recompute, round or translate any quoted value" in prompt


def test_nilai_disertai_perintah_menuliskannya(kb, isi, blok, terpilih):
    judul = {b.id: b.judul for b in blok}
    prompt = compose_prompt(spesifikasi(kb, terpilih), isi, judul, kb)
    assert "printed as text beside any shape" in prompt


def test_perubahan_spesifikasi_mengubah_prompt(kb, isi, blok, terpilih):
    """Proof the specification is the source of truth, not the prompt."""
    judul = {b.id: b.judul for b in blok}
    satu = compose_prompt(spesifikasi(kb, terpilih, emphasis={terpilih[0]: "dominant"}),
                        isi, judul, kb)
    dua = compose_prompt(spesifikasi(kb, terpilih, emphasis={terpilih[0]: "tertiary"}),
                       isi, judul, kb)
    assert satu != dua
