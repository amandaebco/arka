"""Temuan contoh untuk menguji reporter tanpa investigator dan tanpa database.

Mengikuti jalur emas demo: satu model filler yang sama dipakai di beberapa
pabrik, kegagalan yang pernah terjadi dan sudah pernah diselesaikan, serta
sparepart yang master data menilainya tidak kritis padahal pasokannya rapuh.

Alat waktu-pengembangan — tidak ikut ter-deploy.
"""

from datetime import date
from decimal import Decimal

from app.reporting.finding import (
    Finding,
    KandidatPenyebab,
    LangkahPenalaran,
    MataRantai,
    Preseden,
    Rekomendasi,
    RincianSkor,
    Sitasi,
    SparepartKritis,
)

_DOK_INSPEKSI = Sitasi(
    canonical_id="DOC-INS-2024-0417",
    judul="Laporan Inspeksi Filler Line 3 — Pabrik Utara",
    tipe_dokumen="inspection_report",
    tanggal=date(2024, 4, 17),
    lokator="hlm. 3, §2.1",
    kutipan=(
        "Keausan tidak merata pada permukaan seal ditemukan setelah 900 jam operasi; "
        "penggantian seal disertai penyetelan ulang torsi kepala pengisi menghentikan "
        "kebocoran hingga akhir periode pemantauan."
    ),
)

_DOK_TEKNISI = Sitasi(
    canonical_id="DOC-WON-2025-1182",
    judul="Catatan Teknisi — Kebocoran Berulang Filler F-207",
    tipe_dokumen="technician_note",
    tanggal=date(2025, 11, 3),
    lokator="entri 4",
    kutipan="Kebocoran muncul lagi 6 minggu setelah penggantian seal batch baru.",
)

_DOK_FMEA = Sitasi(
    canonical_id="DOC-FME-2023-0091",
    judul="FMEA Subsistem Pengisian — Rev. C",
    tipe_dokumen="fmea",
    tanggal=date(2023, 9, 12),
    lokator="baris 27",
)


def finding_contoh() -> Finding:
    """Temuan lengkap dengan dua kandidat bersaing ketat sehingga memicu eskalasi."""
    return Finding(
        finding_id="ARKA-2026-0042",
        dibuat_pada=date(2026, 8, 6),
        equipment_tag="PLT-U/FIL-207",
        pabrik="Pabrik Utara",
        model_equipment="Filler Rotary RF-8000",
        gejala=[
            "kebocoran produk di kepala pengisi",
            "penurunan akurasi volume pengisian",
            "getaran meningkat pada putaran nominal",
        ],
        keyakinan="sedang",
        perlu_eskalasi=True,
        alasan_eskalasi=(
            "Dua kandidat teratas berselisih di bawah ambang keyakinan, dan keduanya "
            "menuntut tindakan berbeda: penggantian seal versus penyetelan ulang torsi."
        ),
        kandidat=[
            KandidatPenyebab(
                cause_id="CAU-0311",
                nama="Degradasi seal kepala pengisi akibat batch material di bawah spesifikasi",
                deskripsi=(
                    "Seal dari batch vendor tunggal menunjukkan keausan lebih cepat "
                    "dibanding populasi historis pada jam operasi setara."
                ),
                skor=RincianSkor(
                    symptom_overlap=Decimal("0.42"),
                    component_match=Decimal("0.20"),
                    corroboration=Decimal("0.20"),
                    recency=Decimal("0.09"),
                    total=Decimal("0.91"),
                ),
                sitasi=[_DOK_INSPEKSI, _DOK_TEKNISI],
            ),
            KandidatPenyebab(
                cause_id="CAU-0198",
                nama="Penyimpangan torsi kepala pengisi pasca perawatan terjadwal",
                deskripsi=(
                    "Pola kebocoran muncul kembali dalam jarak waktu tetap setelah "
                    "tindakan perawatan, menyerupai kesalahan penyetelan berulang."
                ),
                skor=RincianSkor(
                    symptom_overlap=Decimal("0.38"),
                    component_match=Decimal("0.20"),
                    corroboration=Decimal("0.20"),
                    recency=Decimal("0.09"),
                    total=Decimal("0.87"),
                ),
                sitasi=[_DOK_FMEA],
            ),
            KandidatPenyebab(
                cause_id="CAU-0455",
                nama="Ketidaksejajaran poros akibat pemasangan bearing",
                skor=RincianSkor(
                    symptom_overlap=Decimal("0.19"),
                    component_match=Decimal("0.10"),
                    corroboration=Decimal("0.07"),
                    recency=Decimal("0.04"),
                    total=Decimal("0.40"),
                ),
            ),
        ],
        preseden=[
            Preseden(
                failure_event_id="FE-2024-8871",
                pabrik="Pabrik Barat",
                equipment_tag="PLT-B/FIL-104",
                tanggal_kejadian=date(2024, 4, 12),
                gejala=["kebocoran produk di kepala pengisi", "penurunan akurasi volume"],
                penyelesaian=(
                    "Penggantian seluruh seal kepala pengisi dengan batch vendor alternatif, "
                    "disertai penyetelan ulang torsi. Tidak berulang selama pemantauan."
                ),
                downtime_jam=Decimal("14.5"),
                sitasi=[_DOK_INSPEKSI],
            ),
            Preseden(
                failure_event_id="FE-2025-2210",
                pabrik="Pabrik Timur",
                equipment_tag="PLT-T/FIL-311",
                tanggal_kejadian=date(2025, 6, 28),
                gejala=["kebocoran produk di kepala pengisi", "getaran meningkat"],
                penyelesaian="Penggantian seal batch sama; kebocoran berulang setelah enam minggu.",
                downtime_jam=Decimal("9.0"),
                sitasi=[_DOK_TEKNISI],
            ),
            Preseden(
                failure_event_id="FE-2025-6634",
                pabrik="Pabrik Selatan",
                equipment_tag="PLT-S/FIL-118",
                tanggal_kejadian=date(2025, 9, 15),
                gejala=["penurunan akurasi volume pengisian"],
                penyelesaian="Penyetelan ulang torsi tanpa penggantian seal; tuntas.",
                downtime_jam=Decimal("3.5"),
            ),
        ],
        rantai_kausal=[
            MataRantai(
                peran="symptom",
                label="Kebocoran produk di kepala pengisi",
                detail="Terdeteksi operator pada pemeriksaan visual antar shift",
            ),
            MataRantai(
                peran="cause",
                label="Degradasi seal lebih cepat dari umur rancangan",
                detail="Konsisten pada unit yang memakai seal dari batch yang sama",
            ),
            MataRantai(
                peran="damage",
                label="Keausan tidak merata pada permukaan dudukan seal",
            ),
            MataRantai(
                peran="part",
                label="Seal kepala pengisi RF-8000",
                detail="Vendor tunggal, dipakai lintas pabrik",
            ),
        ],
        sparepart=[
            SparepartKritis(
                part_number="SP-RF8-SEAL-02",
                nama="Seal kepala pengisi RF-8000",
                criticality=Decimal("0.84"),
                static_criticality=Decimal("0.30"),
                lead_time_minggu=6,
                jumlah_vendor=1,
                pabrik_terdampak=[
                    "Pabrik Utara",
                    "Pabrik Barat",
                    "Pabrik Timur",
                    "Pabrik Selatan",
                    "Pabrik Tengah",
                ],
            ),
            SparepartKritis(
                part_number="SP-RF8-BRG-11",
                nama="Bearing poros utama RF-8000",
                criticality=Decimal("0.46"),
                static_criticality=Decimal("0.50"),
                lead_time_minggu=2,
                jumlah_vendor=3,
                pabrik_terdampak=["Pabrik Utara"],
            ),
        ],
        jejak_penalaran=[
            LangkahPenalaran(
                urutan=1,
                aksi="Ambil gejala aktif pada equipment terlapor",
                hasil="Tiga gejala aktif, dua di antaranya khas subsistem pengisian",
                jumlah_simpul=3,
            ),
            LangkahPenalaran(
                urutan=2,
                aksi="Traversal Equipment → Component → FailureEvent historis",
                hasil="Ditemukan kejadian serupa pada model filler yang sama di pabrik lain",
                jumlah_simpul=27,
            ),
            LangkahPenalaran(
                urutan=3,
                aksi="Saring preseden berdasar irisan gejala dan kecocokan komponen",
                hasil="Tiga preseden lolos ambang, tersebar di tiga pabrik berbeda",
                jumlah_simpul=3,
            ),
            LangkahPenalaran(
                urutan=4,
                aksi="Telusuri Part → Vendor → riwayat pasokan",
                hasil="Seal berasal dari vendor tunggal dengan lead time panjang",
                jumlah_simpul=8,
            ),
            LangkahPenalaran(
                urutan=5,
                aksi="Ambil dokumen pendukung tiap kandidat",
                hasil="Tiga dokumen terkutip, satu memuat solusi yang terbukti berhasil",
                jumlah_simpul=3,
            ),
        ],
        rekomendasi=[
            Rekomendasi(
                tindakan=(
                    "Ganti seal kepala pengisi dengan batch vendor alternatif, "
                    "lalu setel ulang torsi mengikuti prosedur yang berhasil di Pabrik Barat."
                ),
                prioritas="segera",
                dasar="Menutup kedua kandidat teratas sekaligus tanpa menunggu putusan.",
            ),
            Rekomendasi(
                tindakan=(
                    "Naikkan klasifikasi kekritisan seal dan tambah stok penyangga lintas pabrik."
                ),
                prioritas="terjadwal",
                dasar="Vendor tunggal dengan lead time panjang, dipakai banyak pabrik.",
            ),
            Rekomendasi(
                tindakan="Pantau getaran pada putaran nominal selama dua siklus produksi.",
                prioritas="pantau",
                dasar="Memisahkan kandidat ketiga yang skornya di bawah ambang.",
            ),
        ],
    )
