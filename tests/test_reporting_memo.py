"""Pengujian lapisan pelaporan.

Fokusnya satu: memastikan model bahasa tidak bisa merusak angka, sitasi, atau
struktur memo — berapa pun anehnya pilihan yang ia kirimkan.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.reporting.blocks import BLOK_WAJIB, pilih_blok, susun_blok
from app.reporting.dokumen import KonteksDokumen, ambil_jenis
from app.reporting.lencana import lencana_data_uri, lencana_svg
from app.reporting.memo import (
    DokumenTanpaSitasi,
    _filter_angka,
    render_dokumen_html,
    render_memo_html,
)
from app.synthetic.finding_contoh import finding_contoh


@pytest.fixture
def finding():
    return finding_contoh()


class TestBlok:
    def test_blok_kosong_ditandai_tidak_tersedia(self, finding):
        tanpa_sparepart = finding.model_copy(update={"sparepart": []})
        blok = susun_blok(tanpa_sparepart)
        assert blok["sparepart_kritis"].tersedia is False
        assert blok["kandidat_penyebab"].tersedia is True

    def test_blok_kosong_tidak_pernah_ikut_dirender(self, finding):
        tanpa_jejak = finding.model_copy(update={"jejak_penalaran": []})
        terpilih = pilih_blok(susun_blok(tanpa_jejak), ["ringkasan", "jejak_penalaran"])
        assert "jejak_penalaran" not in [b.id for b in terpilih]

    def test_blok_wajib_disisipkan_walau_model_lupa(self, finding):
        terpilih = pilih_blok(susun_blok(finding), ["kandidat_penyebab"])
        ids = [b.id for b in terpilih]
        for wajib in BLOK_WAJIB:
            assert wajib in ids
        assert ids[0] == "ringkasan", "ringkasan harus membuka memo"
        assert ids[-1] == "sitasi", "sitasi harus menutup memo"

    def test_id_blok_asing_diabaikan(self, finding):
        terpilih = pilih_blok(susun_blok(finding), ["kandidat_penyebab", "blok_karangan"])
        assert "blok_karangan" not in [b.id for b in terpilih]

    def test_urutan_model_dihormati(self, finding):
        terpilih = pilih_blok(
            susun_blok(finding), ["preseden_lintas_pabrik", "kandidat_penyebab"]
        )
        ids = [b.id for b in terpilih]
        assert ids.index("preseden_lintas_pabrik") < ids.index("kandidat_penyebab")

    def test_duplikasi_pilihan_tidak_menggandakan_blok(self, finding):
        terpilih = pilih_blok(susun_blok(finding), ["kandidat_penyebab", "kandidat_penyebab"])
        ids = [b.id for b in terpilih]
        assert ids.count("kandidat_penyebab") == 1

    def test_tanpa_urutan_memakai_urutan_baku(self, finding):
        ids = [b.id for b in pilih_blok(susun_blok(finding))]
        assert ids[0] == "ringkasan"
        assert "preseden_lintas_pabrik" in ids

    def test_kandidat_terurut_skor_menurun(self, finding):
        skor = [k.skor.total for k in finding.kandidat_terurut]
        assert skor == sorted(skor, reverse=True)

    def test_sparepart_terurut_selisih_terbesar_dulu(self, finding):
        blok = susun_blok(finding)["sparepart_kritis"]
        assert blok.data["sparepart"][0].part_number == "SP-RF8-SEAL-02"

    def test_sitasi_unik_lintas_kandidat_dan_preseden(self, finding):
        ids = [s.canonical_id for s in finding.semua_sitasi()]
        assert len(ids) == len(set(ids))


class TestAngka:
    def test_format_desimal_indonesia(self):
        assert _filter_angka(Decimal("0.91")) == "0,91"

    def test_selisih_positif_diberi_tanda(self):
        assert _filter_angka(Decimal("0.54"), tanda=True) == "+0,54"

    def test_nilai_kosong_jadi_pisah(self):
        assert _filter_angka(None) == "—"

    def test_selisih_dihitung_bukan_disimpan(self, finding):
        seal = next(s for s in finding.sparepart if s.part_number == "SP-RF8-SEAL-02")
        assert seal.selisih == Decimal("0.54")


class TestRenderMemo:
    def test_angka_berasal_dari_data_bukan_narasi(self, finding):
        # Narasi model sengaja memuat angka palsu; angka benar tetap harus muncul.
        html = render_memo_html(
            finding,
            ["kandidat_penyebab"],
            {"kandidat_penyebab": "Skornya mencapai 0,11 menurut model."},
        )
        assert "0,91" in html, "skor sebenarnya harus dirender dari data"

    def test_sitasi_selalu_terbit(self, finding):
        html = render_memo_html(finding, ["kandidat_penyebab"])
        assert "DOC-INS-2024-0417" in html

    def test_eskalasi_ditandai(self, finding):
        assert "Perlu putusan manusia" in render_memo_html(finding)

    def test_narasi_model_ikut_terbit(self, finding):
        html = render_memo_html(finding, ["preseden_lintas_pabrik"], {
            "preseden_lintas_pabrik": "Pola yang sama sudah pernah tuntas di pabrik lain."
        })
        assert "sudah pernah tuntas di pabrik lain" in html

    def test_narasi_disanitasi(self, finding):
        html = render_memo_html(finding, ["ringkasan"], {"ringkasan": "<script>alert(1)</script>"})
        assert "<script>" not in html

    def test_html_berdiri_sendiri(self, finding):
        html = render_memo_html(finding)
        assert html.startswith("<!doctype html>")
        assert "<style>" in html, "gaya harus tersemat agar berkas mandiri"

    def test_semua_blok_terisi_muncul(self, finding):
        # Laporan adalah satu-satunya jenis yang memuat seluruh blok; memo
        # sengaja diringkas lewat kebijakan blok bawaannya.
        html = render_dokumen_html(finding, "laporan")
        for judul in ("Kandidat Penyebab", "Preseden Lintas Pabrik", "Kekritisan Sparepart",
                      "Rantai Kausal", "Jejak Penalaran", "Rekomendasi", "Dokumen Sumber"):
            assert judul in html

    def test_blok_dapat_dipaksa_masuk_memo(self, finding):
        # Kebijakan bawaan hanya bawaan — reporter tetap boleh menariknya masuk.
        html = render_memo_html(finding, ["kandidat_penyebab", "sparepart_kritis"])
        assert "Kekritisan Sparepart" in html


class TestJenisDokumen:
    """Isi ketiga jenis harus identik; hanya chrome dan kebijakan blok yang berbeda."""

    def test_jenis_asing_mundur_ke_memo(self):
        assert ambil_jenis("surat_kaleng").id == "memo"
        assert ambil_jenis(None).id == "memo"
        assert ambil_jenis("NOTA_DINAS").id == "nota_dinas"

    def test_nota_dinas_punya_chrome_surat(self, finding):
        html = render_dokumen_html(
            finding,
            "nota_dinas",
            konteks=KonteksDokumen(
                nomor="001/ARKA/VIII/2026",
                kepada="Manajer Keandalan Pabrik Utara",
                dari="Unit Keandalan Pusat",
                perihal="Kebocoran berulang pada filler",
                tembusan=["Manajer Rantai Pasok"],
                penanda_tangan="Kepala Unit Keandalan",
            ),
        )
        for jejak in ("Nota Dinas", "001/ARKA/VIII/2026", "Manajer Keandalan Pabrik Utara",
                      "Tembusan", "Demikian kami sampaikan"):
            assert jejak in html

    def test_memo_tidak_punya_chrome_surat(self, finding):
        html = render_dokumen_html(finding, "memo")
        assert "Tembusan" not in html
        assert "Demikian kami sampaikan" not in html

    def test_angka_identik_di_ketiga_jenis(self, finding):
        """Satu temuan, tiga bentuk — nilainya tidak boleh bergeser sedikit pun."""
        for jenis in ("memo", "nota_dinas", "laporan"):
            html = render_dokumen_html(finding, jenis)
            assert "0,91" in html, f"skor hilang di {jenis}"
            assert "DOC-INS-2024-0417" in html, f"sitasi hilang di {jenis}"

    def test_kebijakan_blok_bawaan_berbeda(self, finding):
        memo = render_dokumen_html(finding, "memo")
        laporan = render_dokumen_html(finding, "laporan")
        assert "Jejak Penalaran" not in memo, "memo harus ringkas"
        assert "Jejak Penalaran" in laporan, "laporan harus lengkap"

    def test_urutan_reporter_menang_atas_bawaan(self, finding):
        html = render_dokumen_html(finding, "memo", urutan_blok=["jejak_penalaran"])
        assert "Jejak Penalaran" in html

    def test_nota_dinas_tanpa_konteks_tetap_terbit(self, finding):
        html = render_dokumen_html(finding, "nota_dinas")
        assert "Nota Dinas" in html
        assert "(" in html, "ruang tanda tangan kosong tetap dirender"

    def test_konteks_disanitasi(self, finding):
        html = render_dokumen_html(
            finding, "nota_dinas", konteks=KonteksDokumen(kepada="<script>alert(1)</script>")
        )
        assert "<script>" not in html


class TestKeterlacakan:
    """FR-009 — dokumen tanpa sitasi tidak boleh terbit (Constitution, prinsip II)."""

    @staticmethod
    def _tanpa_sitasi(finding):
        return finding.model_copy(update={
            "kandidat": [k.model_copy(update={"sitasi": []}) for k in finding.kandidat],
            "preseden": [p.model_copy(update={"sitasi": []}) for p in finding.preseden],
        })

    def test_tanpa_sitasi_ditolak(self, finding):
        with pytest.raises(DokumenTanpaSitasi):
            render_dokumen_html(self._tanpa_sitasi(finding), "memo")

    def test_penolakan_berlaku_semua_jenis(self, finding):
        kosong = self._tanpa_sitasi(finding)
        for jenis in ("memo", "nota_dinas", "laporan"):
            with pytest.raises(DokumenTanpaSitasi):
                render_dokumen_html(kosong, jenis)

    def test_satu_sitasi_sudah_cukup(self, finding):
        sebagian = finding.model_copy(update={
            "preseden": [p.model_copy(update={"sitasi": []}) for p in finding.preseden],
        })
        assert sebagian.semua_sitasi(), "kandidat masih membawa sitasi"
        assert "Dokumen Sumber" in render_dokumen_html(sebagian, "memo")


class TestLencanaUnit:
    """Kop dokumen milik unit penerbit; ARKA tinggal di kaki dokumen."""

    def test_tanpa_konteks_tidak_ada_kop_unit(self, finding):
        assert 'class="penerbit"' not in render_dokumen_html(finding, "memo")

    def test_lencana_dan_unit_muncul(self, finding):
        konteks = KonteksDokumen(
            unit_penerbit="Unit Keandalan Aset", logo=lencana_data_uri("UKA")
        )
        html = render_dokumen_html(finding, "memo", konteks=konteks)
        assert "Unit Keandalan Aset" in html
        assert "data:image/svg+xml;base64," in html

    def test_tautan_luar_ditolak(self):
        # URL jarak jauh gagal diam-diam saat render PDF — lebih baik ditolak awal.
        with pytest.raises(ValidationError):
            KonteksDokumen(logo="https://contoh.invalid/logo.png")

    def test_lencana_dibangkitkan_bukan_disimpan(self):
        svg = lencana_svg("UKA")
        assert svg.startswith("<svg") and "UKA" in svg

    def test_inisial_dipangkas_dan_dibersihkan(self):
        assert ">ABC<" in lencana_svg("abcdef")
        assert ">?<" in lencana_svg("   ")
