"""Volume latar tidak boleh bisa menggeser angka demo.

Tes ini menjaga tiga jalur kebocoran yang didokumentasikan di
`app/synthetic/volume_latar.py`. Semuanya berupa irisan himpunan, dan itu
disengaja: kalau penjagaannya berupa "jalankan lalu bandingkan skornya",
kegagalannya baru ketahuan setelah dataset ditulis dan angka demo sudah
bergeser. Irisan himpunan gagal sebelum satu baris pun ditulis.
"""

from __future__ import annotations

from app.synthetic import volume_latar as latar
from app.synthetic.jalur_emas import (
    KOMPONEN_FILLER,
    MODEL_FILLER,
    PABRIK_ARMADA,
    TIPE_EQUIPMENT,
)


class TestTidakMenyentuhJalurEmas:
    def test_model_latar_tidak_ada_yang_sama_dengan_filler(self):
        """Jalur 1: find_historical_cases menyaring equipment_model.

        Satu saja model latar yang sama dengan MODEL_FILLER akan menyeret
        ratusan kasus latar masuk sebagai preseden, dan corroboration langsung
        menyentuh batas atasnya.
        """
        model = {m for _tipe, _sufiks, m in latar.TIPE_LATAR}
        assert MODEL_FILLER not in model

    def test_tipe_equipment_latar_berbeda(self):
        tipe = {t for t, _s, _m in latar.TIPE_LATAR}
        assert TIPE_EQUIPMENT not in tipe

    def test_komponen_latar_tidak_beririsan(self):
        """Jalur 2: find_spare_parts menghitung plants_served lewat component_type.

        Komponen latar bertipe `seal` akan menambah pabrik ke jangkauan
        SP-SEAL-8801, dan criticality 0,8667 bergeser tanpa ada yang mengubah
        bobot apa pun.
        """
        emas = {sufiks.lower() for sufiks, _nama in KOMPONEN_FILLER}
        latar_tipe = {jenis for jenis, _nama in latar.KOMPONEN_LATAR}
        assert not (emas & latar_tipe)

    def test_tag_latar_tidak_bentrok_dengan_jalur_emas(self):
        """Nomor latar mulai dari 600; jalur emas memakai 118–412."""
        assert all(sufiks not in ("FIL",) for _t, sufiks, _m in latar.TIPE_LATAR)


class TestPenolakanBerbasisBukti:
    """Kasus latar harus punya gejala, dan tetap tidak punya preseden."""

    def test_kosakata_gejala_latar_tidak_beririsan(self):
        """`symptom_overlap` membandingkan kode; satu kode sama sudah cukup bocor."""
        from app.synthetic.jalur_emas import GEJALA

        emas = {kode for kode, _nama in GEJALA}
        latar = {kode for kode, _nama in latar_gejala()}
        assert not (emas & latar)

    def test_ada_cukup_gejala_untuk_bervariasi(self):
        assert len(latar_gejala()) >= 5

    def test_tidak_ada_penyebab_terverifikasi_untuk_kasus_latar(self):
        """Diukur, bukan lalai — lihat catatan panjang di volume_latar.py.

        Dengan penyebab terverifikasi, armada latar punya preseden berlimpah di
        modelnya sendiri dan kasus palletiser menembus 0,79 — ikut dilaporkan,
        menenggelamkan kasus jalur emas. Sistemnya benar; datanya yang salah.
        """
        import inspect

        from app.synthetic import volume_latar as modul

        assert not hasattr(modul, "PENYEBAB_LATAR")
        sumber = inspect.getsource(modul)
        assert "FailureEventCause" not in sumber


def latar_gejala():
    return latar.GEJALA_LATAR


class TestBentukVolume:
    def test_rasio_work_order_per_equipment_masuk_akal(self):
        """~6 per unit selama tiga tahun. Rasio yang dipilih, bukan angka bulatnya."""
        rasio = latar.JUMLAH_WORK_ORDER / latar.JUMLAH_EQUIPMENT
        assert 4 <= rasio <= 8

    def test_volume_cukup_untuk_menguji_penyaring(self):
        assert latar.JUMLAH_EQUIPMENT >= 100

    def test_sebagian_besar_kegagalan_tertutup(self):
        """Armada yang separuhnya rusak tidak menggambarkan apa pun."""
        assert latar.PELUANG_TERBUKA < 0.5
        assert latar.PELUANG_KEGAGALAN < 0.5

    def test_semua_pabrik_kebagian(self):
        assert latar.JUMLAH_EQUIPMENT >= len(PABRIK_ARMADA)


class TestDeterminisme:
    def test_seed_yang_sama_memberi_undian_yang_sama(self):
        """Selisih angka demo harus selalu berasal dari kode, bukan dari undian."""
        import random

        a = random.Random(20260806 ^ 0x5A7A)
        b = random.Random(20260806 ^ 0x5A7A)
        assert [a.random() for _ in range(20)] == [b.random() for _ in range(20)]

    def test_generator_tidak_memakai_volume_latar_secara_bawaan(self):
        """Tes berjalan atas jalur emas; ribuan baris latar hanya jadi ongkos."""
        import inspect

        from app.synthetic.generator import bangun

        assert inspect.signature(bangun).parameters["volume_latar"].default is False


class TestTagKotor:
    """Katalog penamaan yang tidak seragam — kekotoran yang tidak boleh menular.

    Nilainya ada pada satu jaminan: tabel ini tidak dibaca jalur deteksi, jadi
    seburuk apa pun katalognya, skor tidak bergeser. Tes di sini menjaga
    bentuk kekotorannya; paritas angkanya dijaga tes deteksi.
    """

    def test_satu_huruf_saja_yang_tertukar(self):
        """Tag yang rusak dua tempat terbaca sebagai tag lain sama sekali."""
        import random

        from app.synthetic.dirty_data import _tag_salah_baca

        asli = "PLT-U/FIL-207"
        keliru = _tag_salah_baca(asli, random.Random(1))
        assert keliru is not None
        assert len(keliru) == len(asli)
        assert sum(a != b for a, b in zip(asli, keliru, strict=True)) == 1

    def test_tag_tanpa_huruf_tertukar_dibiarkan(self):
        """Tidak semua tag punya karakter yang bisa salah dibaca."""
        import random

        from app.synthetic.dirty_data import _tag_salah_baca

        assert _tag_salah_baca("PLT-X/FIL-347", random.Random(1)) is None

    def test_hasilnya_deterministik(self):
        import random

        from app.synthetic.dirty_data import _tag_salah_baca

        satu = _tag_salah_baca("PLT-U/FIL-207", random.Random(7))
        dua = _tag_salah_baca("PLT-U/FIL-207", random.Random(7))
        assert satu == dua
