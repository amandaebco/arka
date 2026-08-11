"""Pemotong dokumen — fungsi murni, jadi diuji tuntas tanpa database.

Yang dijaga di sini bukan panjang potongannya, melainkan sifat yang membuat
pencarian dan sitasi bisa dipercaya: tidak ada teks yang hilang, offsetnya
menunjuk ke tempat yang benar, dan tidak ada potongan yang terbelah di tengah
kata.
"""

from __future__ import annotations

from app.retrieval.chunking import (
    MIN_KARAKTER,
    TARGET_KARAKTER,
    Potongan,
    potong,
)

PARAGRAF = (
    "Inspeksi motor penggerak pada unit mixer PLT-U/MIX-0600 di Pabrik Utara "
    "dilakukan setelah operator melaporkan gangguan berulang selama dua sif."
)


def _dokumen(jumlah_paragraf: int) -> str:
    return "\n\n".join(f"Bagian {n}. {PARAGRAF}" for n in range(jumlah_paragraf))


class TestDokumenPendek:
    def test_teks_kosong_tidak_menghasilkan_potongan(self):
        assert potong("") == []
        assert potong("   \n\n  ") == []

    def test_dokumen_pendek_tetap_utuh(self):
        """Memotong yang pendek hanya menghasilkan serpihan."""
        hasil = potong("Satu kalimat pendek saja.")
        assert len(hasil) == 1
        assert hasil[0].isi == "Satu kalimat pendek saja."

    def test_potongan_tunggal_berindeks_nol(self):
        assert potong(PARAGRAF)[0].indeks == 0


class TestPemotongan:
    def test_dokumen_panjang_terpotong_lebih_dari_satu(self):
        hasil = potong(_dokumen(12))
        assert len(hasil) > 1

    def test_indeks_berurutan_tanpa_lompatan(self):
        hasil = potong(_dokumen(12))
        assert [p.indeks for p in hasil] == list(range(len(hasil)))

    def test_tidak_ada_potongan_yang_kosong(self):
        for p in potong(_dokumen(12)):
            assert p.isi.strip()

    def test_tidak_terbelah_di_tengah_kata(self):
        """Potongan yang mulai di tengah kata merusak makna dan kutipan."""
        teks = _dokumen(12)
        for p in potong(teks):
            assert not p.isi.startswith(" ")
            # Kata pertama potongan harus kata utuh yang ada di teks asli.
            kata_pertama = p.isi.split()[0].strip(".,")
            assert kata_pertama in teks

    def test_tidak_ada_serpihan_di_bawah_ambang(self):
        """Serpihan pendek menang skor karena pendek, lalu tidak membawa konteks."""
        hasil = potong(_dokumen(11))
        if len(hasil) > 1:
            assert all(p.panjang >= MIN_KARAKTER for p in hasil)


class TestTidakAdaTeksHilang:
    def test_seluruh_paragraf_muncul_di_suatu_potongan(self):
        """Kalimat yang hilang saat pemotongan tidak akan pernah bisa dicari."""
        teks = _dokumen(10)
        gabungan = " ".join(p.isi for p in potong(teks))
        for n in range(10):
            assert f"Bagian {n}." in gabungan

    def test_kalimat_terakhir_tidak_terbuang(self):
        teks = _dokumen(9) + "\n\nTindakan: unit dikembalikan ke operasi."
        gabungan = " ".join(p.isi for p in potong(teks))
        assert "dikembalikan ke operasi" in gabungan


class TestOffset:
    def test_offset_menunjuk_ke_teks_asli(self):
        """Sitasi bergantung pada ini: offset yang salah menunjuk kalimat lain."""
        teks = _dokumen(10)
        for p in potong(teks):
            assert 0 <= p.start_offset < p.end_offset <= len(teks)

    def test_offset_naik_monoton(self):
        hasil = potong(_dokumen(10))
        for a, b in zip(hasil, hasil[1:], strict=False):
            assert b.start_offset >= a.start_offset

    def test_offset_potongan_tunggal_mencakup_isinya(self):
        teks = "  " + PARAGRAF + "  "
        p = potong(teks)[0]
        assert teks[p.start_offset : p.end_offset] == PARAGRAF


class TestTumpangTindih:
    def test_ada_tumpang_tindih_antar_potongan(self):
        """Tanpa ini, kalimat di batas memisahkan pertanyaan dari jawabannya."""
        hasil = potong(_dokumen(12), tumpang_tindih=100)
        assert len(hasil) > 1
        ekor_pertama = hasil[0].isi[-60:].split()
        assert any(k in hasil[1].isi for k in ekor_pertama if len(k) > 4)

    def test_tumpang_tindih_nol_menghasilkan_potongan_terpisah(self):
        hasil = potong(_dokumen(12), tumpang_tindih=0)
        assert len(hasil) > 1
        assert not hasil[1].isi.startswith(hasil[0].isi[-40:])


class TestParameterDihormati:
    def test_target_lebih_kecil_menghasilkan_lebih_banyak_potongan(self):
        teks = _dokumen(16)
        banyak = potong(teks, target=300, maksimum=500)
        sedikit = potong(teks, target=1200, maksimum=1600)
        assert len(banyak) > len(sedikit)

    def test_target_bawaan_masuk_akal_untuk_laporan_inspeksi(self):
        assert 400 <= TARGET_KARAKTER <= 1200

    def test_paragraf_sangat_panjang_dipecah_per_kalimat(self):
        panjang = " ".join(f"Kalimat nomor {n} pada laporan ini." for n in range(80))
        hasil = potong(panjang, target=300, maksimum=400)
        assert len(hasil) > 1


class TestBentukPotongan:
    def test_potongan_adalah_dataclass_beku(self):
        p = Potongan(0, "isi", 0, 3)
        assert p.panjang == 3
