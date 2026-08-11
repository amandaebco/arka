"""Laporan inspeksi latar — korpus yang cukup besar untuk mengukur ambang.

Empat dokumen tidak cukup untuk menyimpulkan apa pun tentang pencarian
semantik. `MIN_SIMILARITY` adalah properti korpus, dan ambang yang diukur atas
empat dokumen tidak memberi tahu apa-apa tentang perilakunya pada empat ribu.
Modul ini menaikkan korpus ke ~50 dokumen supaya angkanya punya arti.

## Kenapa ini tidak menggeser sitasi memo

`group_by_cause` melampirkan dokumen menurut irisan istilah dengan nama
penyebab. Nama penyebab jalur emas berkisar pada **kepala pengisi**, **seal**,
dan **torsi**. Dokumen latar menulis tentang mesin lain — mixer, konveyor,
labeller, capper, palletiser — dengan kosakata yang **sengaja tidak beririsan**:
tidak ada kata `seal`, `pengisi`, `kepala`, maupun `torsi` di seluruh korpus
latar. `test_dokumen_latar.py` menjaga itu sebagai irisan himpunan.

Jadi dokumen latar terlihat oleh pencarian semantik — yang memang tujuannya —
tetapi tidak pernah menempel sebagai sitasi pada kandidat jalur emas.

## Kenapa isinya tidak diacak dari potongan kalimat

Setiap dokumen dirakit dari templat per jenis mesin dengan temuan dan tindakan
yang cocok satu sama lain. Kalimat acak akan menghasilkan korpus yang secara
semantik rata — dan ambang yang diukur atas korpus rata akan terlihat bagus
justru karena tidak ada yang benar-benar mirip apa pun.
"""

from __future__ import annotations

import logging
import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, DocumentVersion
from app.retrieval.chunking import potong
from app.synthetic.jalur_emas import PABRIK_ARMADA, id_stabil

logger = logging.getLogger(__name__)

JUMLAH_DOKUMEN = 50

# Kosakata yang dipesan jalur emas. Tidak boleh muncul di korpus latar —
# lihat docstring, dan `test_dokumen_latar.py` yang menjaganya.
KATA_TERLARANG = frozenset({"seal", "pengisi", "kepala", "torsi", "filler"})

# (mesin, komponen yang diperiksa, temuan, tindakan)
TEMUAN: tuple[tuple[str, str, str, str], ...] = (
    (
        "mixer",
        "motor penggerak",
        "Arus motor penggerak naik bertahap selama enam minggu terakhir tanpa "
        "perubahan beban batch. Pemeriksaan termografi menunjukkan titik panas "
        "pada terminal fasa kedua.",
        "Terminal dikencangkan ulang dan dilapis pasta konduktif. Arus kembali "
        "ke rentang normal pada batch berikutnya.",
    ),
    (
        "mixer",
        "kotak roda gigi",
        "Analisis pelumas kotak roda gigi menemukan partikel logam di atas "
        "ambang peringatan. Getaran pada frekuensi gigi meningkat dibanding "
        "pengukuran dasar.",
        "Pelumas diganti dan interval pemantauan dipersingkat menjadi bulanan. "
        "Penggantian roda gigi dijadwalkan pada perawatan besar berikutnya.",
    ),
    (
        "conveyor",
        "sabuk transmisi",
        "Sabuk transmisi menunjukkan keausan tidak merata di sisi luar. "
        "Penelusuran menemukan puli penggerak tidak sebidang dengan puli "
        "penerima sebesar dua milimeter.",
        "Puli disejajarkan ulang dan sabuk diganti. Pemeriksaan kesebidangan "
        "ditambahkan ke daftar periksa mingguan.",
    ),
    (
        "conveyor",
        "bantalan rol",
        "Suara berdengung pada rol tengah terdengar sejak awal sif malam. "
        "Suhu bantalan terukur dua puluh derajat di atas rol tetangganya.",
        "Bantalan diganti dan pelumasan dijadwalkan ulang. Tidak ditemukan "
        "kerusakan pada poros.",
    ),
    (
        "labeller",
        "panel kendali",
        "Panel kendali labeller berhenti merespons tiga kali dalam satu sif. "
        "Log menunjukkan tegangan suplai turun di bawah ambang saat kompresor "
        "lini menyala.",
        "Sirkuit kendali dipisahkan dari sirkuit daya kompresor. Gangguan tidak "
        "berulang selama dua minggu pemantauan.",
    ),
    (
        "labeller",
        "sensor posisi",
        "Sensor posisi label salah baca pada kecepatan lini tertinggi, "
        "menyebabkan label miring pada sebagian botol. Pada kecepatan menengah "
        "tidak ada gangguan.",
        "Sensor dibersihkan dan jaraknya disetel ulang sesuai lembar data. "
        "Tingkat label miring turun ke nol.",
    ),
    (
        "capper",
        "kopling servo",
        "Kopling servo pada unit penutup selip pada beban puncak. Pemeriksaan "
        "menemukan permukaan gesek terkontaminasi pelumas dari bantalan di "
        "atasnya.",
        "Kopling dibersihkan dan bantalan yang bocor diganti. Sekat pelindung "
        "ditambahkan untuk mencegah kontaminasi berulang.",
    ),
    (
        "capper",
        "unit pemandu",
        "Unit pemandu tutup macet berkala ketika menangani tutup dari pemasok "
        "kedua. Pengukuran menunjukkan selisih diameter setengah milimeter "
        "dibanding tutup pemasok utama.",
        "Pemandu disetel untuk rentang diameter yang lebih lebar. Masalah tidak "
        "berulang pada kedua jenis tutup.",
    ),
    (
        "palletiser",
        "lengan robotik",
        "Lengan robotik meleset dari titik tumpuk sekitar lima milimeter pada "
        "lapisan teratas. Kalibrasi terakhir tercatat delapan bulan lalu.",
        "Robot dikalibrasi ulang dan interval kalibrasi ditetapkan enam bulan. "
        "Akurasi tumpuk kembali dalam toleransi.",
    ),
    (
        "palletiser",
        "sistem vakum",
        "Daya isap sistem vakum menurun sehingga kardus terlepas saat "
        "perpindahan cepat. Uji kebocoran menemukan selang retak di dekat "
        "sambungan putar.",
        "Selang diganti dengan tipe tahan tekuk. Daya isap kembali ke nilai "
        "acuan dan tidak ada kardus terjatuh sejak perbaikan.",
    ),
)

PENULIS = (
    "Tim Keandalan",
    "Inspeksi Mekanikal",
    "Inspeksi Elektrikal",
    "Tim Perawatan Lini",
)


# Laporan inspeksi nyata punya beberapa bagian, dan panjangnya itulah yang
# membuat pemotongan berarti. Laporan 400 karakter tidak akan pernah terpotong,
# sehingga korpus sependek itu tidak membuktikan apa pun tentang strategi
# pemotongan maupun tentang ambang kemiripan yang diukur di atasnya.
#
# ⚠️ Bagian pembuka **berbeda per jenis mesin**, bukan satu templat untuk semua.
# Percobaan pertama memakai satu konteks dan satu metode untuk kelima puluh
# laporan; hasilnya lima puluh potongan pembuka yang nyaris kembar, korpus yang
# rata secara semantik, dan pengukuran ambang yang mengukur pengulangan templat
# alih-alih kemampuan mencari. Korpus yang rata membuat angka apa pun terlihat
# baik justru karena tidak ada yang benar-benar mirip apa pun.
_KONTEKS: dict[str, str] = {
    "mixer": (
        "Pemeriksaan dilakukan setelah batch terakhir dikeluarkan dan bejana "
        "dibilas, dengan penggerak dalam keadaan terkunci. Catatan arus dan suhu "
        "delapan minggu terakhir ditarik dari sistem pemantauan lini sebagai "
        "pembanding terhadap nilai saat unit diserahterimakan."
    ),
    "conveyor": (
        "Pemeriksaan dilakukan pada jendela henti mingguan lini, dengan sabuk "
        "dikendurkan dan pengaman rantai dipasang. Riwayat penggantian sabuk dua "
        "tahun terakhir ditinjau bersama catatan penyetelan puli, karena keluhan "
        "yang sama pernah muncul dan ditutup tanpa penyebab yang ditegakkan."
    ),
    "labeller": (
        "Pemeriksaan dilakukan sambil lini berjalan pada kecepatan bertahap, "
        "karena gangguan yang dilaporkan hanya muncul di kecepatan tertentu dan "
        "tidak dapat direproduksi saat unit berhenti. Log kendali satu bulan "
        "terakhir diunduh untuk mencocokkan waktu kejadian dengan beban lini."
    ),
    "capper": (
        "Pemeriksaan dilakukan pada pergantian sif, saat pasokan tutup dari dua "
        "pemasok kebetulan tersedia bersamaan sehingga keduanya dapat diuji pada "
        "unit yang sama. Dimensi tutup diukur ulang alih-alih diambil dari "
        "lembar spesifikasi pemasok."
    ),
    "palletiser": (
        "Pemeriksaan dilakukan dengan sel robot dalam mode kecepatan rendah dan "
        "pagar tertutup, mengikuti prosedur akses sel. Titik acuan tumpukan "
        "diukur ulang terhadap penanda lantai, bukan terhadap koordinat yang "
        "tersimpan di kendali robot."
    ),
}

_METODE: dict[str, str] = {
    "mixer": (
        "Termografi diambil pada terminal dan rumah bantalan saat unit berbeban, "
        "dilengkapi pengukuran arus per fasa. Analisis pelumas dikirim ke "
        "laboratorium untuk hitung partikel, dan hasilnya dibandingkan dengan "
        "sampel dari siklus sebelumnya pada unit yang sama."
    ),
    "conveyor": (
        "Kesebidangan puli diukur dengan penggaris laser pada tiga titik, dan "
        "ketegangan sabuk diperiksa dengan pengukur frekuensi. Suhu tiap rol "
        "diambil berurutan supaya rol yang menyimpang terlihat dibanding "
        "tetangganya, bukan dibanding ambang mutlak."
    ),
    "labeller": (
        "Tegangan suplai direkam bersamaan dengan status kompresor lini untuk "
        "menguji dugaan bahwa keduanya berkaitan. Jarak dan kebersihan sensor "
        "diperiksa terhadap lembar data, lalu diuji ulang pada tiga tingkat "
        "kecepatan dengan botol contoh yang sama."
    ),
    "capper": (
        "Torsi penutupan diukur pada sepuluh botol berturut-turut untuk tiap "
        "jenis tutup, dan permukaan kopling diperiksa terhadap jejak pelumas. "
        "Diameter tutup diukur dengan mikrometer pada tiga posisi keliling."
    ),
    "palletiser": (
        "Akurasi penempatan diukur pada empat sudut palet dan pada lapisan "
        "teratas, tempat simpangan paling besar terlihat. Daya isap diuji dengan "
        "manometer pada tiap mangkuk hisap, dan sambungan selang diperiksa dengan "
        "uji kebocoran bertekanan."
    ),
}

_TINDAK_LANJUT: dict[str, str] = {
    "mixer": (
        "Unit dikembalikan ke operasi setelah satu batch percobaan diawasi penuh. "
        "Arus per fasa dipantau harian selama dua minggu, dan analisis pelumas "
        "berikutnya dimajukan agar tren partikel dapat dinilai lebih cepat."
    ),
    "conveyor": (
        "Lini dijalankan kosong selama tiga puluh menit sebelum produk "
        "dimasukkan. Kesebidangan puli ditambahkan ke daftar periksa mingguan, "
        "karena temuan ini pernah berulang dan sebelumnya hanya diperiksa saat "
        "sabuk sudah aus."
    ),
    "labeller": (
        "Unit diamati selama dua sif penuh pada kecepatan tertinggi, karena "
        "gangguan sebelumnya tidak muncul di kecepatan menengah. Tingkat label "
        "miring dicatat per jam dan dilaporkan pada tinjauan mutu mingguan."
    ),
    "capper": (
        "Pengujian diulang untuk kedua jenis tutup sebelum unit dilepas ke "
        "produksi. Perbedaan dimensi antar pemasok diteruskan ke bagian "
        "pengadaan agar toleransi penerimaan ditinjau ulang."
    ),
    "palletiser": (
        "Sel dijalankan dengan palet percobaan sebanyak lima tumpukan penuh "
        "sebelum produksi dimulai. Interval kalibrasi diperpendek dan dicatat di "
        "rencana perawatan, karena selang delapan bulan terbukti terlalu panjang."
    ),
}


def _isi(mesin: str, komponen: str, temuan: str, tindakan: str, pabrik: str, tag: str) -> str:
    return (
        f"Laporan inspeksi {komponen} — unit {mesin} {tag}, {pabrik}.\n\n"
        f"Konteks pemeriksaan\n{_KONTEKS[mesin]}\n\n"
        f"Metode\n{_METODE[mesin]}\n\n"
        f"Temuan\n{temuan}\n\n"
        f"Tindakan yang diambil\n{tindakan}\n\n"
        f"Tindak lanjut dan pemantauan\n{_TINDAK_LANJUT[mesin]}\n\n"
        f"Status: selesai, unit dikembalikan ke operasi."
    )


async def tulis_dokumen_latar(
    sesi: AsyncSession, seed: int, *, jumlah: int = JUMLAH_DOKUMEN
) -> dict[str, int]:
    """Tambahkan laporan inspeksi latar. Satu potongan per dokumen.

    Satu potongan sudah cukup: yang diuji korpus ini adalah apakah ambang
    kemiripan memisahkan pertanyaan dalam domain dari luar domain, dan
    pemotongan halus tidak mengubah pertanyaan itu.
    """
    from hashlib import sha256

    acak = random.Random(seed ^ 0xD0C)
    ditulis = potongan = 0

    for nomor in range(jumlah):
        mesin, komponen, temuan, tindakan = TEMUAN[nomor % len(TEMUAN)]
        kode_pabrik, nama_pabrik = PABRIK_ARMADA[nomor % len(PABRIK_ARMADA)]
        tag = f"{kode_pabrik}/{mesin[:3].upper()}-{600 + nomor:04d}"
        canonical = f"DOC-LATAR-{nomor:04d}"
        isi = _isi(mesin, komponen, temuan, tindakan, nama_pabrik, tag)

        dokumen = Document(
            id=id_stabil(seed, f"latar:dokumen:{canonical}"),
            canonical_id=canonical,
            source_system="sintetis",
            source_document_id=canonical,
            document_type="inspection_report",
            title=f"Laporan Inspeksi {komponen.title()} — {nama_pabrik}",
            author=acak.choice(PENULIS),
            source_created_at=None,
        )
        sesi.add(dokumen)

        versi = DocumentVersion(
            id=id_stabil(seed, f"latar:versi:{canonical}"),
            document_id=dokumen.id,
            version_number=1,
            content_hash=sha256(isi.encode()).hexdigest(),
            mime_type="text/plain",
            extracted_text=isi,
        )
        sesi.add(versi)

        for bagian in potong(isi):
            sesi.add(
                DocumentChunk(
                    id=id_stabil(seed, f"latar:potongan:{canonical}:{bagian.indeks}"),
                    document_version_id=versi.id,
                    chunk_index=bagian.indeks,
                    content=bagian.isi,
                    content_hash=sha256(bagian.isi.encode()).hexdigest(),
                    start_offset=bagian.start_offset,
                    end_offset=bagian.end_offset,
                    page_number=1,
                )
            )
            potongan += 1
        ditulis += 1

    await sesi.flush()
    logger.info("dokumen latar: %d dokumen, %d potongan", ditulis, potongan)
    return {"dokumen_latar": ditulis, "potongan_latar": potongan}
