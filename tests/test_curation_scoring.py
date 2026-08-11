"""Penilai kandidat fakta — nol model, jadi diuji tuntas.

Yang dijaga bukan angka pastinya melainkan sifat yang membuat kurasi bisa
dipercaya: pertentangan tidak pernah bisa ditutup oleh bukti yang banyak,
dokumen yang tidak pernah ditinjau tidak seberat dokumen yang ditinjau, dan
klaim tanpa bukti tidak pernah lolos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.curation.scoring import (
    AMAN_OTOMATIS,
    BOBOT,
    BUKTI_PENUH,
    TERLALU_LEMAH,
    Keputusan,
    Kutipan,
    nilai,
    putuskan,
    skor_klaim,
)


def _kutipan(n: int, jenis: str = "inspection_report", yakin: str = "0.90") -> list[Kutipan]:
    return [Kutipan(jenis, Decimal(yakin), f"kutipan {i}") for i in range(n)]


class TestBobot:
    def test_bobot_berjumlah_satu(self):
        """Total di luar 0..1 membuat ambang kehilangan arti."""
        assert sum(BOBOT.values()) == Decimal("1.00")

    def test_semua_komponen_positif(self):
        assert all(b > 0 for b in BOBOT.values())

    def test_ambang_berurutan(self):
        assert TERLALU_LEMAH < AMAN_OTOMATIS


class TestBukti:
    def test_tanpa_kutipan_skornya_nol(self):
        s = skor_klaim([])
        assert s.bukti == 0
        assert s.keyakinan == 0
        assert s.kewenangan == 0

    def test_bukti_penuh_pada_tiga_kutipan(self):
        assert skor_klaim(_kutipan(BUKTI_PENUH)).bukti == 1

    def test_bukti_tidak_melebihi_satu(self):
        """Sepuluh kutipan tidak boleh membeli lebih dari tiga."""
        assert skor_klaim(_kutipan(10)).bukti == 1

    def test_lebih_banyak_kutipan_menaikkan_skor(self):
        assert skor_klaim(_kutipan(1)).total < skor_klaim(_kutipan(3)).total


class TestKewenangan:
    def test_dokumen_tertinjau_lebih_berat(self):
        """Catatan teknisi tidak pernah ditinjau siapa pun; FMEA ditinjau."""
        fmea = skor_klaim(_kutipan(3, "fmea"))
        catatan = skor_klaim(_kutipan(3, "technician_note"))
        assert fmea.total > catatan.total

    def test_jenis_tak_dikenal_diperlakukan_paling_rendah(self):
        asing = skor_klaim(_kutipan(3, "entah_apa"))
        catatan = skor_klaim(_kutipan(3, "technician_note"))
        assert asing.kewenangan < catatan.kewenangan

    def test_kewenangan_dirata_ratakan_bukan_diambil_maksimum(self):
        """Satu FMEA tidak mengangkat dua catatan teknisi ke derajatnya."""
        campur = skor_klaim(
            [*_kutipan(1, "fmea"), *_kutipan(2, "technician_note")]
        )
        murni = skor_klaim(_kutipan(3, "fmea"))
        assert campur.kewenangan < murni.kewenangan


class TestPertentangan:
    def test_klaim_dibantah_selalu_dieskalasi(self):
        """Berapa pun skornya — pertentangan menuntut manusia."""
        v = nilai(_kutipan(10, "fmea", "1.00"), dibantah=True)
        assert v.keputusan is Keputusan.ESKALASI

    def test_bukti_banyak_tidak_menutup_pertentangan(self):
        kuat = nilai(_kutipan(10, "fmea", "1.00"), dibantah=True)
        assert kuat.keputusan is not Keputusan.SETUJUI

    def test_pertentangan_diperiksa_sebelum_ambang_tolak(self):
        """Yang dibantah dieskalasi, bukan ditolak — keduanya belum tentu salah."""
        v = nilai([], dibantah=True)
        assert v.keputusan is Keputusan.ESKALASI

    def test_kesepakatan_nol_ketika_dibantah(self):
        assert skor_klaim(_kutipan(3), dibantah=True).kesepakatan == 0

    def test_penanda_dibantah_ikut_dibawa(self):
        assert skor_klaim(_kutipan(3), dibantah=True).dibantah is True


class TestKeputusan:
    def test_bukti_kuat_disetujui_otomatis(self):
        v = nilai(_kutipan(3, "fmea", "0.95"))
        assert v.keputusan is Keputusan.SETUJUI

    def test_tanpa_bukti_ditolak(self):
        assert nilai([]).keputusan is Keputusan.TOLAK

    def test_bukti_tipis_dieskalasi_bukan_ditolak(self):
        """Di antara dua ambang, manusia yang memutuskan."""
        v = nilai(_kutipan(1, "technician_note", "0.70"))
        assert v.keputusan is Keputusan.ESKALASI

    def test_setiap_vonis_membawa_alasan(self):
        for v in (nilai([]), nilai(_kutipan(3, "fmea")), nilai(_kutipan(1), dibantah=True)):
            assert len(v.alasan) > 20

    def test_alasan_menyebut_angka_yang_dipakai(self):
        v = nilai(_kutipan(3, "fmea", "0.95"))
        assert str(v.skor.total) in v.alasan


class TestDeterminisme:
    def test_masukan_sama_memberi_hasil_sama(self):
        a = nilai(_kutipan(2, "manual", "0.80"))
        b = nilai(_kutipan(2, "manual", "0.80"))
        assert a.skor == b.skor
        assert a.keputusan == b.keputusan

    @pytest.mark.parametrize("n", [0, 1, 2, 3, 7])
    def test_skor_selalu_dalam_rentang(self, n):
        s = skor_klaim(_kutipan(n))
        assert Decimal(0) <= s.total <= Decimal(1)

    def test_komponen_dibuka_untuk_dibantah(self):
        s = skor_klaim(_kutipan(3))
        assert set(s.komponen) == set(BOBOT)

    def test_putuskan_tidak_menghitung_ulang(self):
        """Skor dan keputusan dipisah supaya keduanya bisa diperiksa terpisah."""
        s = skor_klaim(_kutipan(3, "fmea", "0.95"))
        assert putuskan(s).skor is s
