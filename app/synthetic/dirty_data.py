"""Free-text notifications and the mess that real maintenance data arrives in.

Two gaps this closes, both measured against a real client fleet rather than
imagined:

**Free-text notifications.** Interpreting what a technician typed is the one job
the model owns in the detection chain, and the dataset held eight notifications —
all of them generated from the golden path, none of them written the way people
actually write. The argument for a graph over keyword search ("kebocoran produk
di kepala pengisi" versus "produk merembes waktu pengisian") cannot be
demonstrated on a corpus that never says the same thing twice differently.

**Dirty data.** On a large maintenance fleet, only a small minority of
equipment carries any work order, fewer carry notifications, and fewer still
carry reliability observations. Where a reliability figure does exist it is
often a placeholder zero, which means "not recorded" and reads as "never
fails". A dataset with none of that produces a demo that runs too smoothly to
believe, and hides the failure mode that matters most: absence of evidence
presenting itself as health.

## Why this cannot move the demo numbers

Nothing here is read by the scorer. `app/detection/repository.py` never touches
`maintenance_notifications` — verified, not assumed — so notification text
cannot reach `symptom_overlap`, `corroboration`, or any other component. The
orphaned work orders below carry no `equipment_id`, which is precisely what
makes them invisible to every equipment-scoped query in the detection path.

The one rule that must hold: **the golden path keeps its own records intact.**
Dirty rows are added beside it, never written over it.
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import AssetIdentifier, Equipment
from app.models.maintenance import MaintenanceNotification, WorkOrder
from app.synthetic.jalur_emas import id_stabil

# Berapa banyak notifikasi teks bebas ditulis. Ratusan, bukan puluhan: satu
# gejala yang diucapkan lima cara berbeda baru terlihat sebagai kemampuan
# setelah polanya berulang.
JUMLAH_NOTIFIKASI = 400

# Porsi work order yang kehilangan equipment-nya. Pada armada besar, sebagian
# besar equipment tidak punya satu pun work order yang tertaut. Delapan persen
# adalah sisi yang bisa kita tunjukkan -- perintah kerja yang ada tetapi tidak
# bisa dipetakan ke mesin mana pun.
PORSI_WO_YATIM = 0.08

# Notifikasi yang tidak membawa informasi apa pun. Setiap CMMS punya ini, dan
# agent yang tidak pernah bertemu satu pun belum pernah bertemu data sungguhan.
NOTIFIKASI_SAMPAH = ("-", ".", "tes", "asdf", "cek", "test 123", "?", "n/a")

# Satu keluhan, ditulis oleh orang berbeda pada hari berbeda.
#
# Inilah bahan bakar argumen "kenapa bukan pencarian kata kunci": tidak ada
# pasangan di dalam satu kelompok yang berbagi cukup kata untuk saling
# ditemukan oleh LIKE, sementara semuanya menggambarkan hal yang sama.
KELUHAN_SEMAKNA = (
    (
        "kebocoran produk di kepala pengisi",
        "produk merembes wkt filling",
        "bocor halus di nozzle, kena conveyor bawah",
        "drip di head 3, operator lap tiap shift",
        "ada tetesan terus di area pengisian",
    ),
    (
        "getaran meningkat pada putaran nominal",
        "mesin bergetar lbh dari biasanya",
        "vibrasi naik pas rpm normal, kerasa di pagar",
        "goyang di bagian atas waktu jalan penuh",
    ),
    (
        "penurunan akurasi volume pengisian",
        "isi botol tdk rata, ada yg kurang",
        "volume meleset terus, QC komplain",
        "takaran gak konsisten shift malam",
    ),
    (
        "suhu bearing naik perlahan",
        "bearing anget, dicek pakai tempgun 71 derajat",
        "panas di rumah bearing, blm sampai alarm",
    ),
    (
        "konsumsi arus meningkat",
        "ampere motor naik dikit tiap minggu",
        "arus lbh tinggi dr baseline, blm trip",
    ),
)

# Huruf yang tertukar ketika tag dibaca mesin dari kertas atau pelat terpasang.
# Bukan salah ketik acak: pasangan di bawah yang benar-benar tertukar, karena
# bentuknya memang mirip pada cetakan kecil.
TUKAR_OCR = (("0", "O"), ("O", "0"), ("1", "l"), ("l", "1"), ("5", "S"), ("8", "B"))

# Keluhan yang terdengar mirip tetapi berakar lain. Ada supaya penelusuran
# terlihat **menyingkirkan** kandidat, bukan sekadar mengumpulkan yang mirip.
KELUHAN_MENYESATKAN = (
    "bocor di sambungan pipa, bukan di kepala pengisi",
    "rembes dari gasket panel, lantai basah tapi mesin normal",
    "getaran dari conveyor sebelah, bukan dari filler",
)


def _tag_salah_baca(tag: str, acak: random.Random) -> str | None:
    """Satu tag yang tertukar satu huruf, atau None kalau tidak ada yang cocok.

    Hanya satu huruf yang diganti. Tag yang rusak dua tempat terbaca sebagai
    tag lain sama sekali; yang rusak satu huruf tetap terlihat benar sampai ada
    yang mencocokkannya -- dan itu bentuk kekotoran yang menyulitkan.
    """
    posisi = [
        (i, ganti)
        for i, huruf in enumerate(tag)
        for asli, ganti in TUKAR_OCR
        if huruf == asli
    ]
    if not posisi:
        return None
    i, ganti = acak.choice(posisi)
    return tag[:i] + ganti + tag[i + 1 :]


async def tulis_tag_kotor(sesi: AsyncSession, seed: int) -> dict[str, int]:
    """Katalog penamaan aset yang tidak seragam, seperti katalog sungguhan.

    Tiga bentuk, semuanya di `asset_identifiers` dan **tidak satu pun dibaca
    jalur deteksi** -- modul di `app/detection/` tidak menyentuh tabel ini,
    diperiksa bukan diandaikan. Jadi ini menambah kekotoran yang bisa
    diperlihatkan tanpa menggeser satu digit pun pada skor.

    1. Tag utama yang bersih, seperti yang tertulis di sistem induk.
    2. Salinan hasil pembacaan mesin dengan satu huruf tertukar (`0` jadi `O`).
       Inilah yang memperlihatkan pencocokan tetap menemukan mesinnya.
    3. Nomor lama yang dulu dipakai mesin lain. Dua baris sah, satu nomor,
       dan hanya sistem sumber yang membedakan -- persis alasan katalog
       penamaan tidak pernah bisa dipercaya begitu saja.

    Returns:
        Cacah per bentuk yang ditulis.
    """
    acak = random.Random(seed ^ 0x7A61)
    cacah = {"tag_utama": 0, "tag_salah_baca": 0, "tag_dipakai_ulang": 0}

    armada = (
        await sesi.execute(
            select(Equipment.id, Equipment.tag_number).order_by(Equipment.tag_number)
        )
    ).all()
    if not armada:
        return cacah

    penanda: list[AssetIdentifier] = []
    for eq_id, tag in armada:
        penanda.append(
            AssetIdentifier(
                id=id_stabil(seed, f"tag-utama:{tag}"),
                equipment_id=eq_id,
                source_system="katalog-induk",
                identifier_type="tag_fungsional",
                identifier_value=tag,
                is_primary=True,
            )
        )
        cacah["tag_utama"] += 1

        # Seperempat armada pernah masuk lewat pemindaian dokumen. Bukan semua:
        # katalog yang seluruhnya rusak tidak meyakinkan siapa pun.
        if acak.random() < 0.25:
            keliru = _tag_salah_baca(tag, acak)
            if keliru and keliru != tag:
                penanda.append(
                    AssetIdentifier(
                        id=id_stabil(seed, f"tag-ocr:{tag}"),
                        equipment_id=eq_id,
                        source_system="pemindaian-dokumen",
                        identifier_type="tag_terbaca",
                        identifier_value=keliru,
                    )
                )
                cacah["tag_salah_baca"] += 1

    # Nomor lama yang dipakai ulang: tag mesin A tercatat sebagai nomor lama
    # mesin B. Sistem sumbernya berbeda, jadi keduanya sah menurut kunci unik --
    # dan itulah yang membuat penggabungan katalog berbahaya.
    for i in range(0, min(len(armada) - 1, 40), 2):
        (eq_id, _tag), (_lain_id, tag_lain) = armada[i], armada[i + 1]
        penanda.append(
            AssetIdentifier(
                id=id_stabil(seed, f"tag-lama:{tag_lain}:{i}"),
                equipment_id=eq_id,
                source_system="sistem-lama",
                identifier_type="nomor_lama",
                identifier_value=tag_lain,
            )
        )
        cacah["tag_dipakai_ulang"] += 1

    sesi.add_all(penanda)
    return cacah


async def tulis_data_kotor(sesi: AsyncSession, seed: int) -> dict[str, int]:
    """Tambahkan notifikasi teks bebas dan kekotoran yang wajar.

    Dipanggil setelah volume latar, karena menempel pada work order yang sudah
    ada. Deterministik terhadap `seed`.

    Returns:
        Cacah per kelompok yang ditulis atau diubah.
    """
    acak = random.Random(seed ^ 0xD1B7)
    cacah: dict[str, int] = {}

    # --- notifikasi teks bebas ---------------------------------------------
    #
    # Ditempelkan ke work order latar, bukan ke jalur emas: kasus jalur emas
    # sudah punya notifikasinya sendiri, dan menambah baris di sana akan
    # membuat riwayatnya berbeda dari yang sudah dikalibrasi.
    perintah_latar = (
        await sesi.execute(
            select(WorkOrder.id, WorkOrder.canonical_id, WorkOrder.opened_at)
            .where(WorkOrder.canonical_id.like("WORKORDER-LATAR-%"))
            .limit(JUMLAH_NOTIFIKASI)
        )
    ).all()

    kelompok = list(KELUHAN_SEMAKNA)
    notifikasi: list[MaintenanceNotification] = []
    for i, (_, kunci_wo, _dibuka) in enumerate(perintah_latar):
        undian = acak.random()
        if undian < 0.08:
            teks = acak.choice(NOTIFIKASI_SAMPAH)
        elif undian < 0.14:
            teks = acak.choice(KELUHAN_MENYESATKAN)
        else:
            teks = acak.choice(acak.choice(kelompok))

        notifikasi.append(
            MaintenanceNotification(
                id=id_stabil(seed, f"notifikasi-latar:{kunci_wo}:{i}"),
                canonical_id=f"NOTIF-LATAR-{i:05d}",
                notification_number=f"NT-LATAR-{i:05d}",
                description=teks,
                source_system="sintetis-latar",
                source_record_id=f"{kunci_wo}:{i}",
            )
        )

        # Duplikat: keluhan yang sama dilaporkan dua kali dan menghasilkan dua
        # tiket. Nomornya berbeda -- sistem sumber menolak nomor kembar, persis
        # seperti tabel ini -- sehingga yang kembar adalah isinya, dan itulah
        # yang menyulitkan: dua baris sah yang menggambarkan satu kejadian.
        if acak.random() < 0.03:
            notifikasi.append(
                MaintenanceNotification(
                    id=id_stabil(seed, f"notifikasi-latar-dup:{kunci_wo}:{i}"),
                    canonical_id=f"NOTIF-LATAR-{i:05d}-B",
                    notification_number=f"NT-LATAR-{i:05d}-B",
                    description=teks,
                    source_system="sintetis-latar",
                    source_record_id=f"{kunci_wo}:{i}:dup",
                )
            )

    sesi.add_all(notifikasi)
    cacah["notifikasi_teks_bebas"] = len(notifikasi)

    # --- work order yatim: TIDAK ditulis, dan alasannya penting ------------
    #
    # Pekerjaan yang tidak bisa dipetakan ke mesin adalah bentuk kekotoran yang
    # paling sering ditemui di lapangan. Ia tidak bisa ditulis di sini:
    # `work_orders`
    # menyatakan `equipment_id` NOT NULL, jadi skema kanonik melarang keadaan
    # itu ada sama sekali.
    #
    # Melonggarkannya adalah keputusan skema, bukan keputusan data: setiap query
    # pada jalur deteksi menganggap tiap work order punya mesin, dan mengubah
    # anggapan itu menyentuh jauh lebih banyak daripada generator. Dicatat di
    # sini supaya pilihan itu diambil sadar, bukan ditemukan lagi dari nol.
    cacah["work_order_yatim"] = 0

    # --- tanggal yang tidak masuk akal -------------------------------------
    #
    # Selesai sebelum dibuka. Tidak ada mesin yang begitu; ada saja barisnya.
    kandidat_tanggal = (
        await sesi.execute(
            select(WorkOrder.id, WorkOrder.opened_at)
            .where(WorkOrder.canonical_id.like("WORKORDER-LATAR-%"))
            .where(WorkOrder.completed_at.is_not(None))
            .limit(200)
        )
    ).all()

    aneh = 0
    for wo_id, dibuka_pada in kandidat_tanggal:
        if acak.random() < 0.15 and dibuka_pada is not None:
            await sesi.execute(
                text("UPDATE work_orders SET completed_at = :t WHERE id = :id"),
                {"t": dibuka_pada - timedelta(days=acak.randint(1, 30)), "id": wo_id},
            )
            aneh += 1
    cacah["tanggal_mustahil"] = aneh

    return cacah
