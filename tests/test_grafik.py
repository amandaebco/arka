"""Grafik dokumen — dirakit dari data, tidak pernah dari model."""

from decimal import Decimal

from app.reporting.blocks import susun_blok
from app.reporting.grafik import (
    grafik_kandidat,
    grafik_kekritisan,
    grafik_preseden,
    grafik_untuk,
)
from app.synthetic.finding_contoh import finding_contoh


class TestGrafikKandidat:
    def test_menggambar_satu_batang_per_kandidat(self):
        f = finding_contoh()
        svg = grafik_kandidat(f)
        assert svg.count("<rect") == len(f.kandidat)

    def test_memuat_garis_ambang_keputusan(self):
        svg = grafik_kandidat(finding_contoh())
        assert "lapor 0,65" in svg
        assert "abaikan 0,50" in svg

    def test_angka_tetap_didampingkan(self):
        # Grafik melengkapi tabel, bukan menggantikannya.
        svg = grafik_kandidat(finding_contoh())
        assert "0,91" in svg

    def test_tanpa_kandidat_tidak_menggambar(self):
        kosong = finding_contoh().model_copy(update={"kandidat": []})
        assert grafik_kandidat(kosong) is None


class TestGrafikKekritisan:
    def test_dua_titik_per_sparepart(self):
        f = finding_contoh()
        svg = grafik_kekritisan(f)
        # Master dan ARKA, plus dua penanda legenda.
        assert svg.count("<circle") == len(f.sparepart) * 2 + 2

    def test_menyebut_kedua_sisi(self):
        svg = grafik_kekritisan(finding_contoh())
        assert "master data" in svg
        assert "perhitungan ARKA" in svg

    def test_tanpa_sparepart_tidak_menggambar(self):
        kosong = finding_contoh().model_copy(update={"sparepart": []})
        assert grafik_kekritisan(kosong) is None


class TestGrafikPreseden:
    def test_menandai_kasus_sekarang(self):
        svg = grafik_preseden(finding_contoh())
        assert "sekarang" in svg

    def test_preseden_tunggal_tidak_menggambar(self):
        # Satu titik pada sumbu waktu tidak menunjukkan pola apa pun.
        f = finding_contoh()
        satu = f.model_copy(update={"preseden": f.preseden[:1]})
        assert grafik_preseden(satu) is None


class TestKeamananRender:
    def test_nama_kandidat_dilarikan(self):
        f = finding_contoh()
        jahat = f.kandidat[0].model_copy(update={"nama": "<script>alert(1)</script>"})
        svg = grafik_kandidat(f.model_copy(update={"kandidat": [jahat]}))
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg

    def test_deterministik(self):
        # Dokumen yang sama harus menghasilkan berkas yang sama persis.
        assert grafik_kandidat(finding_contoh()) == grafik_kandidat(finding_contoh())


class TestPemasanganDiBlok:
    def test_blok_bergrafik_mendapat_svg(self):
        blok = susun_blok(finding_contoh())
        for id_blok in ("kandidat_penyebab", "sparepart_kritis", "preseden_lintas_pabrik"):
            assert blok[id_blok].data["grafik"].startswith("<figure")

    def test_blok_lain_tidak_bergrafik(self):
        blok = susun_blok(finding_contoh())
        assert blok["rekomendasi"].data.get("grafik") is None
        assert blok["sitasi"].data.get("grafik") is None

    def test_id_blok_asing_aman(self):
        assert grafik_untuk("blok_karangan", finding_contoh()) is None


class TestAngkaDariData:
    def test_batang_mengikuti_skor_bukan_urutan(self):
        f = finding_contoh()
        turun = f.kandidat[0].model_copy(
            update={"skor": f.kandidat[0].skor.model_copy(update={"total": Decimal("0.10")})}
        )
        svg = grafik_kandidat(f.model_copy(update={"kandidat": [turun]}))
        assert "0,10" in svg
        assert "0,91" not in svg
