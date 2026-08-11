"""Korpus latar tidak boleh mencemari sitasi jalur emas.

Penjagaannya berupa irisan himpunan atas kosakata, karena itulah mekanisme yang
sebenarnya dipakai `group_by_cause`: dokumen menempel pada kandidat kalau ada
istilah yang sama. Satu kata `seal` yang lolos ke korpus latar akan melampirkan
lima puluh laporan mixer ke memo tentang kepala pengisi — dan memo itu tetap
terbit, hanya tidak terbaca.
"""

from __future__ import annotations

import pytest

from app.detection.repository import DocumentRef, HistoricalCase, group_by_cause
from app.synthetic import dokumen_latar as latar


def _teks_semua() -> str:
    bagian = []
    for mesin, komponen, temuan, tindakan in latar.TEMUAN:
        bagian += [mesin, komponen, temuan, tindakan]
    return " ".join(bagian).lower()


class TestKosakataTerpisah:
    @pytest.mark.parametrize("kata", sorted(latar.KATA_TERLARANG))
    def test_kata_jalur_emas_tidak_muncul(self, kata):
        assert kata not in _teks_semua()

    def test_judul_tidak_memuat_kata_terlarang(self):
        for _mesin, komponen, _t, _a in latar.TEMUAN:
            assert not (latar.KATA_TERLARANG & set(komponen.lower().split()))

    def test_daftar_terlarang_memuat_istilah_penentu(self):
        """Kalau daftarnya menyusut, penjagaan ini kehilangan artinya."""
        assert {"seal", "torsi", "pengisi", "kepala"} <= latar.KATA_TERLARANG


class TestBentukKorpus:
    def test_jumlah_cukup_untuk_mengukur_ambang(self):
        assert latar.JUMLAH_DOKUMEN >= 40

    def test_ada_beberapa_jenis_mesin(self):
        """Korpus satu jenis mesin akan rata secara semantik."""
        mesin = {m for m, _k, _t, _a in latar.TEMUAN}
        assert len(mesin) >= 4

    def test_setiap_temuan_punya_tindakan(self):
        for _m, _k, temuan, tindakan in latar.TEMUAN:
            assert len(temuan) > 40
            assert len(tindakan) > 20


class TestPelampiranSitasi:
    """`group_by_cause` harus menyaring, bukan memborong."""

    def _kasus(self) -> list[HistoricalCase]:
        from datetime import date

        return [
            HistoricalCase(
                failure_event_id="fe-1",
                cause_canonical_id="CAUSE-SEAL",
                cause_name="Degradasi seal kepala pengisi akibat batch material",
                plant="Pabrik Barat",
                equipment_tag="PLT-B/FIL-204",
                occurred_on=date(2025, 6, 1),
                symptom_codes=(),
                component_code="seal",
                resolution=None,
                downtime_minutes=None,
            )
        ]

    def _dokumen(self, judul: str, kutipan: str) -> DocumentRef:
        return DocumentRef(
            canonical_id=judul, title=judul, document_type="inspection_report", excerpt=kutipan
        )

    def test_dokumen_relevan_dilampirkan(self):
        relevan = self._dokumen("Laporan Kepala Pengisi", "seal mengeras sebelum umur pakai")
        hasil = group_by_cause(self._kasus(), [relevan])
        assert len(hasil[0].documents) == 1

    def test_dokumen_latar_tidak_dilampirkan(self):
        """Laporan mixer tidak boleh jadi rujukan memo tentang kepala pengisi."""
        asing = self._dokumen(
            "Laporan Inspeksi Motor Penggerak — Pabrik Utara",
            "Arus motor penggerak naik bertahap tanpa perubahan beban batch.",
        )
        hasil = group_by_cause(self._kasus(), [asing])
        assert hasil[0].documents == ()

    def test_lima_puluh_dokumen_asing_tidak_menambah_satu_pun_sitasi(self):
        asing = [
            self._dokumen(f"Laporan Konveyor {n}", "Sabuk transmisi aus tidak merata.")
            for n in range(50)
        ]
        hasil = group_by_cause(self._kasus(), asing)
        assert hasil[0].documents == ()

    def test_kata_fungsi_tidak_membuat_semua_relevan(self):
        """"akibat" ada di nama penyebab; ia tidak boleh mencocokkan apa pun."""
        asing = self._dokumen("Catatan", "Kerusakan terjadi akibat beban berlebih.")
        hasil = group_by_cause(self._kasus(), [asing])
        assert hasil[0].documents == ()

    def test_kandidat_tanpa_dokumen_tetap_dikembalikan(self):
        """Sitasi yang hilang memperlemah temuan, bukan menggugurkannya (FR-009)."""
        hasil = group_by_cause(self._kasus(), [])
        assert len(hasil) == 1
        assert hasil[0].documents == ()
