"""Pemeriksaan mutu dokumen — bagian yang deterministik, tanpa memanggil model."""

import pytest

from app.agents import qa
from app.agents.reporter import KUNCI_TEMUAN
from app.synthetic.finding_contoh import finding_contoh
from tests.test_reporter_agent import ToolContextPalsu


@pytest.fixture
def ctx():
    konteks = ToolContextPalsu()
    konteks.state[KUNCI_TEMUAN] = finding_contoh().model_dump(mode="json")
    konteks.state["jenis_terakhir"] = "memo"
    konteks.state["urutan_terakhir"] = ["kandidat_penyebab", "preseden_lintas_pabrik"]
    konteks.state["narasi_terakhir"] = {}
    konteks.state["konteks_terakhir"] = {}
    return konteks


class TestPeriksaDokumen:
    async def test_dokumen_bersih_lulus(self, ctx):
        assert "LULUS" in await qa.periksa_dokumen(ctx)

    async def test_tanpa_temuan(self):
        assert "Tidak ada temuan" in await qa.periksa_dokumen(ToolContextPalsu())

    async def test_narasi_berangka_terdeteksi(self, ctx):
        ctx.state["narasi_terakhir"] = {"ringkasan": "Ada dua kandidat penyebab."}
        hasil = await qa.periksa_dokumen(ctx)
        assert "ringkasan" in hasil
        assert "memuat angka" in hasil

    async def test_blok_kosong_terdeteksi(self, ctx):
        kosong = finding_contoh().model_copy(update={"sparepart": []})
        ctx.state[KUNCI_TEMUAN] = kosong.model_dump(mode="json")
        ctx.state["urutan_terakhir"] = ["kandidat_penyebab", "sparepart_kritis"]
        assert "tidak punya data" in await qa.periksa_dokumen(ctx)

    async def test_id_blok_asing_terdeteksi(self, ctx):
        ctx.state["urutan_terakhir"] = ["blok_karangan"]
        assert "tidak dikenal" in await qa.periksa_dokumen(ctx)

    async def test_blok_wajib_tak_disebut_bukan_cacat(self, ctx):
        # `pilih_blok` menyisipkannya paksa. Memeriksanya di sini dulu memicu
        # putaran perbaikan untuk cacat yang tidak pernah ada.
        ctx.state["urutan_terakhir"] = ["kandidat_penyebab"]
        assert "LULUS" in await qa.periksa_dokumen(ctx)

    async def test_eskalasi_harus_di_depan(self, ctx):
        ctx.state["urutan_terakhir"] = [
            "preseden_lintas_pabrik",
            "rantai_kausal",
            "kandidat_penyebab",
        ]
        assert "perlu eskalasi" in await qa.periksa_dokumen(ctx)

    async def test_nota_dinas_tanpa_kelengkapan(self, ctx):
        ctx.state["jenis_terakhir"] = "nota_dinas"
        hasil = await qa.periksa_dokumen(ctx)
        for medan in ("kepada", "dari", "perihal"):
            assert medan in hasil

    async def test_nota_dinas_lengkap_lulus(self, ctx):
        ctx.state["jenis_terakhir"] = "nota_dinas"
        ctx.state["konteks_terakhir"] = {
            "kepada": "Manajer Keandalan",
            "dari": "Unit Keandalan",
            "perihal": "Preseden lintas pabrik",
        }
        assert "LULUS" in await qa.periksa_dokumen(ctx)

    async def test_tanpa_sitasi_terdeteksi(self, ctx):
        tanpa = finding_contoh().model_copy(update={"kandidat": [], "preseden": []})
        ctx.state[KUNCI_TEMUAN] = tanpa.model_dump(mode="json")
        assert "tidak memuat sitasi" in await qa.periksa_dokumen(ctx)


class TestKeputusanPenilai:
    def test_selesai_menghentikan_putaran(self, ctx):
        qa.selesai("sudah layak", ctx)
        assert ctx.actions.escalate is True
        assert ctx.state[qa.KUNCI_MASUKAN] == ""

    def test_minta_perbaikan_menyimpan_masukan(self, ctx):
        qa.minta_perbaikan("Dahulukan kandidat penyebab.", ctx)
        assert "Dahulukan" in ctx.state[qa.KUNCI_MASUKAN]
        assert ctx.actions.escalate is False


class TestRantaiPenerbitan:
    def test_batas_putaran_mengikuti_setelan(self):
        """Batasnya setelan, tetapi lingkarnya harus benar-benar memakainya.

        Dulu tes ini mematok angka 3. Begitu batasnya jadi `QA_MAX_ROUNDS`,
        mematok angka berarti tes gagal setiap kali seseorang memilih hemat —
        menghukum konfigurasi yang sah. Yang perlu dijaga bukan nilainya,
        melainkan bahwa lingkar perbaikan tidak mengabaikannya.
        """
        assert qa.reporter_terjaga.max_iterations == qa.MAKS_PUTARAN
        assert 1 <= qa.MAKS_PUTARAN <= 5

    def test_urutan_sub_agent(self):
        # Reporter menerbitkan lebih dulu, penilai memeriksa sesudahnya.
        assert [a.name for a in qa.reporter_terjaga.sub_agents] == ["reporter", "penilai"]
