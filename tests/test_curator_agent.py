"""Batas keras Curator — yang ditegakkan kode, bukan prompt.

Prompt hanya berlaku selama model menurut. Yang diuji di sini adalah larangan
yang tetap berlaku ketika model **tidak** menurut: klaim yang dibantah dan klaim
di bawah ambang tolak tidak dapat diterima lewat jalur ini, apa pun yang diminta.
"""

from __future__ import annotations

from pathlib import Path

import app.agents.curator as kur
from app.curation.scoring import TERLALU_LEMAH, Keputusan


class Ctx:
    def __init__(self, kandidat=None):
        self.state: dict = {kur.KUNCI_KANDIDAT: kandidat} if kandidat is not None else {}


def _entri(**ubah):
    dasar = {
        "claim_id": "00000000-0000-0000-0000-000000000001",
        "skor": "0.9260",
        "usulan": Keputusan.SETUJUI.value,
        "dibantah": False,
        "alasan": "Bukti konsisten.",
    }
    return {**dasar, **ubah}


class TestBatasKeras:
    async def test_klaim_dibantah_tidak_bisa_disetujui(self):
        """Pertentangan menuntut manusia — dan prompt saja tidak menjaminnya."""
        ctx = Ctx({"K": _entri(dibantah=True, usulan=Keputusan.ESKALASI.value)})
        hasil = await kur.putuskan_kandidat("K", True, "kelihatan kuat", ctx)
        assert "Ditolak" in hasil
        assert "manusia" in hasil

    async def test_klaim_di_bawah_ambang_tolak_tidak_bisa_disetujui(self):
        ctx = Ctx({"K": _entri(usulan=Keputusan.TOLAK.value, skor="0.1500")})
        hasil = await kur.putuskan_kandidat("K", True, "saya yakin", ctx)
        assert "Ditolak" in hasil
        assert str(TERLALU_LEMAH) in hasil

    async def test_klaim_dibantah_tetap_boleh_ditolak(self):
        """Larangannya hanya pada menerima. Menolak selalu lebih aman."""
        dicatat = {}

        async def palsu(sesi, **kw):
            dicatat.update(kw)

        import app.agents.curator as modul

        asli = modul.catat_keputusan
        modul.catat_keputusan = palsu
        try:
            ctx = Ctx({"K": _entri(dibantah=True)})
            hasil = await kur.putuskan_kandidat("K", False, "bukti bertentangan", ctx)
        finally:
            modul.catat_keputusan = asli
        assert "ditolak" in hasil.lower()
        assert dicatat.get("diterima") is False


class TestKunciTidakDikenal:
    async def test_kunci_asing_ditolak_dengan_petunjuk(self):
        hasil = await kur.putuskan_kandidat("TIDAK-ADA", True, "apa saja", Ctx({}))
        assert "tidak ada di daftar" in hasil
        assert "daftar_kandidat" in hasil

    async def test_tanpa_daftar_dulu_tidak_bisa_memutuskan(self):
        """Keputusan harus dinilai atas angka yang sama dengan yang dilihat model."""
        hasil = await kur.putuskan_kandidat("K", True, "alasan", Ctx())
        assert "tidak ada di daftar" in hasil


class TestPeranTerpisah:
    def test_agent_tidak_menghitung_skor_sendiri(self):
        """Angka milik lapisan deterministik; model tidak boleh menyentuhnya."""
        sumber = Path(kur.__file__).read_text()
        assert "BOBOT" not in sumber
        assert "skor_klaim(" not in sumber

    def test_prompt_melarang_lebih_longgar_dari_ambang(self):
        instruksi = kur.curator_agent.instruction
        assert "more" in instruksi and "cautious" in instruksi
        assert "never be less" in instruksi

    def test_prompt_menuntut_alasan_yang_bisa_diperiksa(self):
        assert "Terlihat masuk akal" in kur.curator_agent.instruction

    def test_ketiga_tool_terpasang(self):
        nama = {getattr(t, "__name__", "") for t in kur.curator_agent.tools}
        assert {"daftar_kandidat", "putuskan_kandidat", "ringkas_kurasi"} <= nama

    def test_peninjau_ditandai_otomatis(self):
        """Catatan tinjauan harus menyebut bahwa yang memutuskan bukan manusia."""
        assert "otomatis" in kur.PERINGKAT.lower()


class TestAmbangDiterbitkan:
    def test_ambang_disebut_di_daftar_kandidat(self):
        """Model harus melihat kebijakan yang berlaku, bukan menebaknya."""
        sumber = Path(kur.__file__).read_text()
        assert "AMAN_OTOMATIS" in sumber
        assert "TERLALU_LEMAH" in sumber

    def test_ambang_berasal_dari_satu_tempat(self):
        from app.curation import scoring

        assert kur.AMAN_OTOMATIS is scoring.AMAN_OTOMATIS
        assert kur.TERLALU_LEMAH is scoring.TERLALU_LEMAH


class TestTidakMenyentuhAngkaDemo:
    def test_lapisan_deteksi_tidak_membaca_klaim(self):
        """Kurasi menulis; deteksi tidak boleh membacanya, atau angka bisa bergeser."""
        akar = Path(__file__).resolve().parent.parent
        for paket in ("app/detection", "app/reporting"):
            for berkas in (akar / paket).rglob("*.py"):
                isi = berkas.read_text()
                assert "review_status" not in isi
                assert "ClaimReview" not in isi
