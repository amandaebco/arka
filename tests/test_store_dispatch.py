"""Which store answers is a production decision, so it is pinned here.

`app/detection/store.py` is the only module that knows the difference between
the two backends. Everything above it works on dataclasses. That claim is worth
exactly as much as this file: if the dispatcher can be nudged into the wrong
store by an unset or misspelt variable, the layers above will keep working and
keep answering — from the wrong data.
"""

from __future__ import annotations

import pytest

from app.detection import store


@pytest.fixture(autouse=True)
def bersihkan(monkeypatch):
    monkeypatch.delenv("ARKA_STORE", raising=False)


class TestBawaan:
    def test_tanpa_variabel_memakai_bigquery(self):
        """BigQuery adalah sumbernya; tidak menyetel apa pun berarti sumber."""
        assert store.active_store() == store.BIGQUERY

    def test_variabel_kosong_dianggap_tidak_disetel(self, monkeypatch):
        monkeypatch.setenv("ARKA_STORE", "   ")
        assert store.active_store() == store.BIGQUERY


class TestPemilihanEksplisit:
    @pytest.mark.parametrize("nilai", ["postgres", "POSTGRES", "  Postgres  "])
    def test_postgres_bisa_dipilih(self, monkeypatch, nilai):
        monkeypatch.setenv("ARKA_STORE", nilai)
        assert store.active_store() == store.POSTGRES

    @pytest.mark.parametrize("nilai", ["bigquery", "BigQuery", " bigquery "])
    def test_bigquery_bisa_dipilih(self, monkeypatch, nilai):
        monkeypatch.setenv("ARKA_STORE", nilai)
        assert store.active_store() == store.BIGQUERY


class TestSalahKetik:
    @pytest.mark.parametrize("nilai", ["bigquerry", "bq", "postgress", "gcp", "biqguery"])
    def test_nama_asing_jatuh_ke_postgres(self, monkeypatch, nilai):
        """Salah ketik tidak boleh diam-diam memindahkan sumber data ke cloud.

        Asimetrinya disengaja: memilih cloud menuntut ejaan yang benar,
        sedangkan jatuh ke lokal tidak pernah menuntut apa pun. Jawaban yang
        salah dari penyimpanan yang salah terlihat persis seperti jawaban benar.
        """
        monkeypatch.setenv("ARKA_STORE", nilai)
        assert store.active_store() == store.POSTGRES

    def test_salah_ketik_dicatat_bukan_didiamkan(self, monkeypatch, caplog):
        monkeypatch.setenv("ARKA_STORE", "bigquerry")
        with caplog.at_level("WARNING"):
            store.active_store()
        assert "bigquerry" in caplog.text

    def test_nilai_asli_yang_dicatat_bukan_yang_sudah_dirapikan(self, monkeypatch, caplog):
        """Pesan yang menampilkan versi rapi menyembunyikan spasi penyebabnya."""
        monkeypatch.setenv("ARKA_STORE", " BigQuerry ")
        with caplog.at_level("WARNING"):
            store.active_store()
        assert " BigQuerry " in caplog.text


class TestSesi:
    async def test_bigquery_tidak_membuka_sesi(self, monkeypatch):
        """BigQuery tidak punya sesi; None dihasilkan agar pemanggil seragam."""
        monkeypatch.setenv("ARKA_STORE", store.BIGQUERY)
        async with store.session() as s:
            assert s is None
