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


def _isi(mesin: str, komponen: str, temuan: str, tindakan: str, pabrik: str, tag: str) -> str:
    return (
        f"Inspeksi {komponen} pada unit {mesin} {tag} di {pabrik}.\n\n"
        f"Temuan: {temuan}\n\n"
        f"Tindakan: {tindakan}\n\n"
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
    ditulis = 0

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

        sesi.add(
            DocumentChunk(
                id=id_stabil(seed, f"latar:potongan:{canonical}"),
                document_version_id=versi.id,
                chunk_index=0,
                content=isi,
                content_hash=sha256(isi.encode()).hexdigest(),
                start_offset=0,
                end_offset=len(isi),
                page_number=1,
            )
        )
        ditulis += 1

    await sesi.flush()
    logger.info("dokumen latar: %d", ditulis)
    return {"dokumen_latar": ditulis}
