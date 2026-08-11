"""Penjaga kesegaran diuji tanpa menyentuh kedua penyimpanan.

Yang perlu dipastikan bukan angkanya — itu dibandingkan saat dijalankan —
melainkan kapan penjaga berbunyi dan kapan ia diam. Penjaga yang berbunyi di
lingkungan yang tidak punya PostgreSQL akan menghalangi produksi; penjaga yang
diam saat salinannya basi tidak menjaga apa pun.
"""

from __future__ import annotations

import pytest

from app.bigquery import kesegaran
from app.bigquery.kesegaran import Laporan, SalinanBasi, Status


class TestKapanDiam:
    async def test_diam_ketika_store_postgres(self, monkeypatch):
        monkeypatch.setenv("ARKA_STORE", "postgres")
        laporan = await kesegaran.periksa()
        assert laporan.status is Status.DILEWATI_BUKAN_BIGQUERY
        assert laporan.aman

    async def test_diam_ketika_postgres_tak_terjangkau(self, monkeypatch):
        """Di produksi tidak ada PostgreSQL — itu bukan kegagalan."""
        monkeypatch.setenv("ARKA_STORE", "bigquery")

        async def tanpa_postgres():
            return None

        monkeypatch.setattr(kesegaran, "_baca_postgres", tanpa_postgres)
        laporan = await kesegaran.periksa()
        assert laporan.status is Status.DILEWATI_TANPA_POSTGRES
        assert laporan.aman

    async def test_tidak_menghubungi_bigquery_saat_dilewati(self, monkeypatch):
        """Melewatkan pemeriksaan harus benar-benar melewatkannya."""
        monkeypatch.setenv("ARKA_STORE", "postgres")

        def jangan_dipanggil():
            raise AssertionError("BigQuery dihubungi padahal seharusnya dilewati")

        monkeypatch.setattr(kesegaran, "_baca_bigquery", jangan_dipanggil)
        await kesegaran.periksa()


class TestKapanBerbunyi:
    def _pasang(self, monkeypatch, pg_cacah, pg_sidik, bq_cacah, bq_sidik):
        monkeypatch.setenv("ARKA_STORE", "bigquery")

        async def baca_pg():
            return pg_cacah, pg_sidik

        monkeypatch.setattr(kesegaran, "_baca_postgres", baca_pg)
        monkeypatch.setattr(kesegaran, "_baca_bigquery", lambda: (bq_cacah, bq_sidik))

    async def test_cocok(self, monkeypatch):
        self._pasang(monkeypatch, {"plants": 5}, {"symptoms": "abc"}, {"plants": 5},
                     {"symptoms": "abc"})
        assert (await kesegaran.periksa()).status is Status.COCOK

    async def test_selisih_cacah_terdeteksi(self, monkeypatch):
        self._pasang(monkeypatch, {"plants": 5}, {}, {"plants": 4}, {})
        laporan = await kesegaran.periksa()
        assert laporan.status is Status.BASI
        assert "plants" in laporan.beda[0]

    async def test_tabel_hilang_di_bigquery_terdeteksi(self, monkeypatch):
        self._pasang(monkeypatch, {"plants": 5}, {}, {}, {})
        laporan = await kesegaran.periksa()
        assert laporan.status is Status.BASI
        assert "tidak ada di BigQuery" in laporan.beda[0]

    async def test_isi_berubah_dengan_cacah_sama_terdeteksi(self, monkeypatch):
        """Skenario sesungguhnya: jalur emas diubah, migrasi lupa dijalankan."""
        self._pasang(monkeypatch, {"symptoms": 5}, {"symptoms": "lama"}, {"symptoms": 5},
                     {"symptoms": "baru"})
        laporan = await kesegaran.periksa()
        assert laporan.status is Status.BASI
        assert "isinya berbeda" in laporan.beda[0]

    async def test_tidak_melapor_dua_kali_untuk_tabel_yang_sama(self, monkeypatch):
        """Cacah yang sudah beda membuat sidik jari tidak menambah informasi."""
        self._pasang(monkeypatch, {"symptoms": 5}, {"symptoms": "lama"}, {"symptoms": 4},
                     {"symptoms": "baru"})
        laporan = await kesegaran.periksa()
        assert len(laporan.beda) == 1


class TestWajibSegar:
    async def test_melempar_ketika_basi(self, monkeypatch):
        async def basi():
            return Laporan(Status.BASI, ("symptoms: isinya berbeda",))

        monkeypatch.setattr(kesegaran, "periksa", basi)
        with pytest.raises(SalinanBasi, match="migrasi_bigquery"):
            await kesegaran.wajib_segar()

    async def test_lolos_ketika_cocok(self, monkeypatch):
        async def cocok():
            return Laporan(Status.COCOK)

        monkeypatch.setattr(kesegaran, "periksa", cocok)
        assert (await kesegaran.wajib_segar()).status is Status.COCOK


class TestSqlSidikJari:
    def test_postgres_mengurutkan_byte_wise(self):
        """Tanpa COLLATE "C" penjaga berbunyi palsu setiap kali — terjadi sekali."""
        assert 'COLLATE "C"' in kesegaran._sql_sidik_postgres()

    def test_kedua_dialek_memakai_kolom_yang_sama(self):
        pg, bq = kesegaran._sql_sidik_postgres(), kesegaran._sql_sidik_bigquery()
        for tabel, kolom in kesegaran.SIDIK_JARI.items():
            assert tabel in pg
            assert tabel in bq
            for k in kolom:
                assert k in pg
                assert k in bq

    def test_sidik_jari_hanya_kolom_teks(self):
        """Angka dan waktu diformat berbeda; ikut disidik = berbunyi palsu."""
        from app.bigquery.schema import bigquery_type
        from app.models.base import Base

        for tabel, kolom in kesegaran.SIDIK_JARI.items():
            for k in kolom:
                jenis = bigquery_type(Base.metadata.tables[tabel].columns[k])
                assert jenis == "STRING", f"{tabel}.{k} bertipe {jenis}"

    def test_tabel_penentu_angka_ikut_disidik(self):
        assert {"failure_events", "symptoms", "causes", "spare_parts"} <= set(
            kesegaran.SIDIK_JARI
        )
