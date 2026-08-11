"""Aktivitas dan pemakaian material memperkaya graph tanpa menyentuh angka.

Klaim itu yang diuji di sini, dan diuji sebagai irisan himpunan supaya gagal
sebelum satu baris ditulis — bukan sesudah dataset jadi dan skor demo terlanjur
bergeser.
"""

from __future__ import annotations

from app.bigquery import edges
from app.synthetic import aktivitas
from app.synthetic.jalur_emas import KOMPONEN_FILLER, SEMUA_KASUS


class TestTidakMenyentuhAngka:
    def test_tidak_ada_lapisan_penilaian_yang_membaca_tabel_ini(self):
        """Penjagaan sesungguhnya: tabel ini tidak punya jalur ke skor.

        Kalau suatu hari `app/detection/` mulai membaca salah satunya, tes ini
        merah dan pengaruhnya ke angka wajib diperiksa ulang sebelum dilanjutkan.
        """
        from pathlib import Path

        tabel = (
            "maintenance_activities",
            "activity_spare_parts",
            "activity_technicians",
            "technicians",
            "failure_event_failure_modes",
        )
        kelas = ("MaintenanceActivity", "ActivitySparePart", "ActivityTechnician", "Technician")

        akar = Path(__file__).resolve().parent.parent
        for paket in ("app/detection", "app/agents", "app/reporting"):
            for berkas in (akar / paket).rglob("*.py"):
                isi = berkas.read_text()
                for nama in (*tabel, *kelas):
                    assert nama not in isi, f"{berkas.name} menyebut {nama}"

    def test_sparepart_latar_tidak_beririsan_jenis_komponen(self):
        """Jalur kebocoran `plants_served`: satu `seal` di sini menggeser 0,8667."""
        emas = {s.lower() for s, _n in KOMPONEN_FILLER}
        latar = {jenis for _nomor, _nama, jenis in aktivitas.PART_LATAR}
        assert not (emas & latar)

    def test_part_jalur_emas_hanya_untuk_jenis_komponen_jalur_emas(self):
        emas = {s.lower() for s, _n in KOMPONEN_FILLER}
        assert set(aktivitas.PART_PER_KOMPONEN) <= emas


class TestPemakaianJalurEmas:
    def test_setiap_jenis_komponen_punya_mode_kegagalan(self):
        emas = {s.lower() for s, _n in KOMPONEN_FILLER}
        assert emas <= set(aktivitas.MODE_PER_KOMPONEN)

    def test_hanya_kasus_tuntas_yang_bisa_memakai_part(self):
        """Pekerjaan terbuka belum mengambil material apa pun.

        Mencatatnya seolah sudah membuat riwayat berbohong ke arah yang paling
        merugikan: part terlihat lebih sering dipakai daripada kenyataannya, dan
        justru pemakaian itu yang jadi dasar argumen rantai pasok.
        """
        bisa = [
            k
            for k in SEMUA_KASUS
            if k.tuntas and k.komponen.lower() in aktivitas.PART_PER_KOMPONEN
        ]
        assert bisa, "tidak ada kasus tuntas yang memakai sparepart"
        assert all(k.tuntas for k in bisa)

    def test_seal_dipakai_di_lebih_dari_satu_pabrik(self):
        """Inti cerita rantai pasok: part yang sama, pekerjaan di pabrik berbeda."""
        pabrik = {
            k.kode_pabrik for k in SEMUA_KASUS if k.tuntas and k.komponen.lower() == "seal"
        }
        assert len(pabrik) >= 2


class TestGraphTidakMengiklankanKekosongan:
    def test_setiap_label_node_punya_sumber(self):
        for label, (tabel, kolom) in edges.NODE_SOURCES.items():
            assert tabel and kolom, label

    def test_label_aktivitas_dan_teknisi_terdaftar(self):
        """Keduanya dulu dideklarasikan tanpa satu baris pun."""
        assert "MaintenanceActivity" in edges.NODE_SOURCES
        assert "Technician" in edges.NODE_SOURCES

    def test_edge_yang_dulu_kosong_terdaftar(self):
        label = {e[-1] for e in edges.EDGE_SOURCES}
        assert {"AKTIVITAS", "MEMAKAI", "DIKERJAKAN_OLEH", "BERMODE"} <= label

    def test_aktivitas_ditampilkan_dengan_kode_bukan_jenis(self):
        """Tiga langkah yang semuanya bernama "penggantian" tidak membedakan apa pun."""
        _tabel, kolom = edges.NODE_SOURCES["MaintenanceActivity"]
        assert kolom == "activity_code"
