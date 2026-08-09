"""Penyaring narasi — penegakan "model tidak menyentuh angka".

Kebocoran nyata yang memicu berkas ini: reporter menulis "mengidentifikasi dua
kandidat penyebab utama". Digit tidak ada, aturan tetap dilanggar.
"""

from app.reporting.blocks import pilih_blok, susun_blok
from app.reporting.narasi import bersihkan_narasi, bersihkan_peta_narasi, memuat_angka
from app.synthetic.finding_contoh import finding_contoh


class TestMemuatAngka:
    def test_digit_terdeteksi(self):
        assert memuat_angka("skornya 0,82")
        assert memuat_angka("berulang di 5 pabrik")
        assert memuat_angka("sejak 15 September 2025")

    def test_kata_bilangan_terdeteksi(self):
        assert memuat_angka("dua kandidat bersaing ketat")
        assert memuat_angka("tiga pabrik terlibat")
        assert memuat_angka("belasan notifikasi")
        assert memuat_angka("puluhan jam henti")

    def test_narasi_kualitatif_lolos(self):
        assert not memuat_angka("Skornya jauh di atas kandidat lain.")
        assert not memuat_angka("Pola serupa berulang di beberapa pabrik.")
        assert not memuat_angka("Kegagalan ini menuntut keputusan segera.")

    def test_idiom_tidak_ikut_tersaring(self):
        # `satu` sengaja di luar daftar — nyaris selalu idiomatik.
        assert not memuat_angka("Ini salah satu penyebab yang paling mungkin.")
        assert not memuat_angka("Seal adalah satu-satunya komponen yang diganti.")

    def test_bilangan_tingkat_lolos(self):
        # "kedua kandidat" menyatakan urutan atau "keduanya", bukan mencacah.
        assert not memuat_angka("Kedua kandidat menuntut tindakan berbeda.")
        assert not memuat_angka("Langkah ketiga menutup penelusuran.")


class TestBersihkanNarasi:
    def test_hanya_kalimat_pelanggar_yang_dibuang(self):
        hasil = bersihkan_narasi(
            "Temuan ini menuntut keputusan segera. Ada dua kandidat penyebab. "
            "Keduanya menyangkut kepala pengisi."
        )
        assert hasil == (
            "Temuan ini menuntut keputusan segera. Keduanya menyangkut kepala pengisi."
        )

    def test_seluruhnya_melanggar_menjadi_none(self):
        assert bersihkan_narasi("Skornya 0,91 dan berulang di 5 pabrik.") is None

    def test_narasi_bersih_utuh(self):
        teks = "Pola serupa berulang di beberapa pabrik lain."
        assert bersihkan_narasi(teks) == teks

    def test_kosong_dan_none(self):
        assert bersihkan_narasi(None) is None
        assert bersihkan_narasi("   ") is None


class TestBersihkanPeta:
    def test_melaporkan_blok_yang_diubah(self):
        bersih, ditolak = bersihkan_peta_narasi(
            {
                "ringkasan": "Ada dua kandidat penyebab.",
                "rekomendasi": "Ganti seal pada kesempatan berhenti terdekat.",
            }
        )
        assert ditolak == ["ringkasan"]
        assert "ringkasan" not in bersih
        assert bersih["rekomendasi"].startswith("Ganti seal")

    def test_nilai_bukan_teks_diabaikan(self):
        bersih, _ = bersihkan_peta_narasi({"ringkasan": 42})  # type: ignore[dict-item]
        assert bersih == {}

    def test_peta_kosong(self):
        assert bersihkan_peta_narasi(None) == ({}, [])


class TestPenegakanDiPilihBlok:
    """Penyaringan harus terjadi di jalur rakit, bukan hanya di tool agent."""

    def test_angka_tidak_lolos_ke_blok(self):
        blok = pilih_blok(
            susun_blok(finding_contoh()),
            ["ringkasan", "kandidat_penyebab", "sitasi"],
            {"kandidat_penyebab": "Ada dua kandidat yang bersaing ketat."},
        )
        kandidat = next(b for b in blok if b.id == "kandidat_penyebab")
        assert kandidat.narasi is None

    def test_narasi_bersih_tetap_sampai(self):
        blok = pilih_blok(
            susun_blok(finding_contoh()),
            ["ringkasan", "kandidat_penyebab", "sitasi"],
            {"kandidat_penyebab": "Kandidat teratas menuntut penggantian seal."},
        )
        kandidat = next(b for b in blok if b.id == "kandidat_penyebab")
        assert kandidat.narasi == "Kandidat teratas menuntut penggantian seal."
