"""Tool agent `reporter` — jalur yang sebelumnya tidak tersentuh tes sama sekali.

Model bahasa tidak dipanggil di sini. Yang diuji adalah perilaku tool saat
menerima masukan model yang cacat: JSON rusak, temuan hilang, narasi
bermuatan angka, temuan tanpa sitasi.
"""

import json

import pytest

from app.agents import reporter as rep
from app.synthetic.finding_contoh import finding_contoh


class AksiPalsu:
    """`tool_context.actions` seperlunya: hanya bendera escalate."""

    def __init__(self):
        self.escalate = False


class ToolContextPalsu:
    """Pengganti `ToolContext` seperlunya: state, aksi, dan penyimpanan artifact."""

    def __init__(self):
        self.state: dict = {}
        self.actions = AksiPalsu()
        self.artifacts: dict = {}
        self.gagal_simpan = False

    async def save_artifact(self, filename, artifact):
        if self.gagal_simpan:
            raise RuntimeError("penyimpanan artifact ditolak")
        self.artifacts[filename] = artifact
        return 0


@pytest.fixture
def ctx():
    return ToolContextPalsu()


@pytest.fixture
def ctx_bertemuan(ctx):
    rep.muat_temuan(finding_contoh().model_dump_json(), ctx)
    return ctx


class TestMuatPeta:
    def test_json_rusak_tidak_menggagalkan(self):
        assert rep._muat_peta("{bukan json", "narasi") == {}

    def test_bukan_peta_diabaikan(self):
        assert rep._muat_peta('["a", "b"]', "narasi") == {}

    def test_kosong(self):
        assert rep._muat_peta(None, "narasi") == {}
        assert rep._muat_peta("", "narasi") == {}

    def test_peta_sah(self):
        assert rep._muat_peta('{"ringkasan": "halo"}', "narasi") == {"ringkasan": "halo"}


class TestMuatTemuan:
    def test_temuan_sah_tersimpan_di_state(self, ctx):
        hasil = rep.muat_temuan(finding_contoh().model_dump_json(), ctx)
        assert rep.KUNCI_TEMUAN in ctx.state
        assert "ARKA-2026-0042" in hasil
        assert "Blok tersedia" in hasil

    def test_json_rusak_dilaporkan_bukan_dilempar(self, ctx):
        hasil = rep.muat_temuan("{bukan json", ctx)
        assert "tidak valid" in hasil.lower()
        assert rep.KUNCI_TEMUAN not in ctx.state

    def test_state_menyimpan_bentuk_json(self, ctx):
        rep.muat_temuan(finding_contoh().model_dump_json(), ctx)
        json.dumps(ctx.state[rep.KUNCI_TEMUAN])  # tidak boleh melempar


class TestAmbilTemuan:
    def test_dari_objek_finding(self, ctx):
        ctx.state[rep.KUNCI_TEMUAN] = finding_contoh()
        assert rep._ambil_temuan(ctx).finding_id == "ARKA-2026-0042"

    def test_dari_string_json(self, ctx):
        ctx.state[rep.KUNCI_TEMUAN] = finding_contoh().model_dump_json()
        assert rep._ambil_temuan(ctx).finding_id == "ARKA-2026-0042"

    def test_state_kosong(self, ctx):
        assert rep._ambil_temuan(ctx) is None

    def test_isi_tak_terbaca_mengembalikan_none(self, ctx):
        ctx.state[rep.KUNCI_TEMUAN] = {"finding_id": "cacat"}
        assert rep._ambil_temuan(ctx) is None


class TestRingkasTemuan:
    def test_tanpa_temuan(self, ctx):
        assert "Belum ada temuan" in rep.ringkas_temuan(ctx)

    def test_menyebut_eskalasi_dan_sitasi(self, ctx_bertemuan):
        hasil = rep.ringkas_temuan(ctx_bertemuan)
        assert "Eskalasi: ya" in hasil
        assert "Sitasi: 3" in hasil


class TestTerbitkanDokumen:
    async def test_tanpa_temuan_ditolak(self, ctx):
        hasil = await rep.terbitkan_dokumen("memo", [], "{}", "{}", ctx)
        assert "Belum ada temuan" in hasil
        assert ctx.artifacts == {}

    async def test_tanpa_sitasi_ditolak(self, ctx):
        tanpa = finding_contoh().model_copy(update={"kandidat": [], "preseden": []})
        ctx.state[rep.KUNCI_TEMUAN] = tanpa.model_dump(mode="json")
        hasil = await rep.terbitkan_dokumen("memo", [], "{}", "{}", ctx)
        assert "tidak diterbitkan" in hasil
        assert ctx.artifacts == {}

    async def test_artifact_tersimpan(self, ctx_bertemuan):
        hasil = await rep.terbitkan_dokumen("memo", [], "{}", "{}", ctx_bertemuan)
        assert "tersimpan" in hasil
        (nama,) = ctx_bertemuan.artifacts
        assert nama.startswith("memo-ARKA-2026-0042.")

    async def test_jenis_asing_mundur_ke_memo(self, ctx_bertemuan):
        await rep.terbitkan_dokumen("surat_sakti", [], "{}", "{}", ctx_bertemuan)
        (nama,) = ctx_bertemuan.artifacts
        assert nama.startswith("memo-")

    async def test_narasi_berangka_dilaporkan_ke_model(self, ctx_bertemuan):
        hasil = await rep.terbitkan_dokumen(
            "memo",
            [],
            json.dumps({"ringkasan": "Ada dua kandidat penyebab."}),
            "{}",
            ctx_bertemuan,
        )
        assert "tersimpan" in hasil
        assert "ringkasan" in hasil
        assert "dibuang otomatis" in hasil
        assert "Jangan menerbitkan ulang" in hasil

    async def test_narasi_bersih_tanpa_catatan(self, ctx_bertemuan):
        hasil = await rep.terbitkan_dokumen(
            "memo",
            [],
            json.dumps({"ringkasan": "Temuan ini menuntut keputusan segera."}),
            "{}",
            ctx_bertemuan,
        )
        assert "dibuang otomatis" not in hasil

    async def test_konteks_cacat_tidak_menggagalkan_terbit(self, ctx_bertemuan):
        hasil = await rep.terbitkan_dokumen(
            "nota_dinas", [], "{}", '{"tembusan": "bukan daftar"}', ctx_bertemuan
        )
        assert "tersimpan" in hasil

    async def test_gagal_simpan_artifact_dilaporkan(self, ctx_bertemuan):
        ctx_bertemuan.gagal_simpan = True
        hasil = await rep.terbitkan_dokumen("memo", [], "{}", "{}", ctx_bertemuan)
        assert "gagal disimpan" in hasil

    async def test_pdf_gagal_tidak_mundur_ke_html(self, ctx_bertemuan, monkeypatch):
        # HTML adalah bentuk kerja internal. Menyerahkannya ke pengguna sebagai
        # pengganti diam-diam lebih berbahaya daripada gagal terang-terangan.
        async def pdf_meledak(*a, **k):
            raise RuntimeError("peramban belum terpasang")

        monkeypatch.setattr(rep, "render_dokumen_pdf", pdf_meledak)
        hasil = await rep.terbitkan_dokumen("memo", [], "{}", "{}", ctx_bertemuan)
        assert "gagal diterbitkan" in hasil
        assert ctx_bertemuan.artifacts == {}

    async def test_artifact_selalu_pdf(self, ctx_bertemuan):
        for jenis in ("memo", "nota_dinas", "laporan"):
            await rep.terbitkan_dokumen(jenis, [], "{}", "{}", ctx_bertemuan)
        assert all(n.endswith(".pdf") for n in ctx_bertemuan.artifacts)
