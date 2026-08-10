"""Volume latar — armada di sekitar jalur emas, bukan di dalamnya.

Jalur emas berisi 5 filler dan 8 kegagalan. Itu cukup untuk membuktikan
penalarannya benar, tapi tidak membuktikan apa pun tentang skala: penyaring
Scout yang menolak satu kasus dari tiga tidak sama meyakinkannya dengan
penyaring yang menolak puluhan dari ratusan.

Modul ini menambahkan ~500 equipment dan ~3.000 work order di sekitarnya.

## Kenapa ini tidak bisa menggeser angka demo

Bukan karena diperiksa sesudahnya, tapi karena **dibangun supaya tidak bisa**.
Ada tepat tiga jalur yang bisa membocorkan volume latar ke dalam skor, dan
ketiganya ditutup di sini:

1. `find_historical_cases` menyaring `equipment_model`. Volume latar memakai
   model di luar `MODEL_FILLER`, jadi tidak satu pun kasusnya bisa jadi
   preseden — corroboration dan symptom_overlap tidak tersentuh.
2. `find_spare_parts` menghitung `plants_served` lewat `component_type`. Volume
   latar memakai tipe komponen di luar `KOMPONEN_FILLER`, jadi jangkauan
   `SP-SEAL-8801` tetap 5 pabrik dan criticality tetap 0,8667.
3. `find_next_maintenance` menyaring `equipment_tag`. Work order latar hanya
   menempel pada equipment latar, jadi jadwal filler jalur emas tidak bergeser.

`TIPE_LATAR` dan `KOMPONEN_LATAR` karena itu **tidak boleh** beririsan dengan
konstanta jalur emas. `test_volume_latar.py` menjaga itu.

## Yang sengaja dibiarkan bocor

Kegagalan terbuka. `find_open_cases` tidak menyaring model — memang tidak boleh,
karena Scout harus memindai seluruh armada. Jadi kegagalan terbuka latar **akan**
muncul di pemindaian, dan itu diinginkan: kegagalan tanpa preseden semodel akan
skornya rendah dan ditolak. Penyaring yang tidak pernah menolak apa-apa bukan
penyaring.
"""

from __future__ import annotations

import logging
import random
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assets import Component, Equipment, ProductionLine
from app.models.maintenance import WorkOrder
from app.models.reliability import FailureEvent
from app.synthetic.jalur_emas import (
    PABRIK_ARMADA,
    SEKARANG,
    id_stabil,
)

logger = logging.getLogger(__name__)

# Berapa banyak, dan sebaran waktunya.
JUMLAH_EQUIPMENT = 500
JUMLAH_WORK_ORDER = 3_000
RENTANG_HARI = 365 * 3

# ~6 work order per unit selama tiga tahun. Rasio ini yang dipilih, bukan
# angka bulatnya: armada terawat menghasilkan sekitar itu, dan angka latar yang
# tidak masuk akal mengundang pertanyaan yang tidak ada hubungannya dengan ARKA.

# Tipe equipment latar. Tidak boleh memuat `TIPE_EQUIPMENT` maupun
# `MODEL_FILLER` — lihat jalur kebocoran 1 di docstring.
TIPE_LATAR: tuple[tuple[str, str, str], ...] = (
    ("mixer", "MIX", "Mixer Batch MB-300"),
    ("conveyor", "CNV", "Konveyor Modular KM-120"),
    ("labeller", "LBL", "Labeller Rotari LR-450"),
    ("capper", "CAP", "Capper Servo CS-220"),
    ("palletiser", "PAL", "Palletiser Robotik PR-900"),
)

# Tipe komponen latar. Tidak boleh beririsan dengan `KOMPONEN_FILLER`
# (seal, katup, brg, nozel) — lihat jalur kebocoran 2.
KOMPONEN_LATAR: tuple[tuple[str, str], ...] = (
    ("motor", "Motor penggerak"),
    ("belt", "Sabuk transmisi"),
    ("gearbox", "Kotak roda gigi"),
    ("panel", "Panel kendali"),
)

JENIS_WO = ("preventive", "corrective", "inspection")
STATUS_WO = ("created", "approved", "completed", "completed", "completed")

# Sebagian kecil kegagalan latar dibiarkan terbuka, supaya Scout punya sesuatu
# untuk ditolak. Selebihnya tertutup — armada yang separuhnya rusak tidak
# menggambarkan apa pun.
PELUANG_KEGAGALAN = 0.12
PELUANG_TERBUKA = 0.25

GEJALA_BEBAS = (
    "Suara tidak wajar saat operasi",
    "Getaran di luar kebiasaan",
    "Suhu bearing naik perlahan",
    "Konsumsi arus meningkat",
    "Kebocoran pelumas ringan",
)


async def tulis_volume_latar(
    sesi: AsyncSession,
    seed: int,
    *,
    jumlah_equipment: int = JUMLAH_EQUIPMENT,
    jumlah_work_order: int = JUMLAH_WORK_ORDER,
) -> dict[str, int]:
    """Tambahkan armada latar di sekitar jalur emas.

    Dipanggil setelah `tulis_armada`, karena memakai lini produksi yang sudah
    ada. Deterministik terhadap `seed`: dataset yang dibangun ulang menghasilkan
    armada latar yang sama, sehingga selisih apa pun pada angka demo pasti
    berasal dari perubahan kode, bukan dari undian yang berbeda.

    Returns:
        Cacah per kelompok yang ditulis.
    """
    acak = random.Random(seed ^ 0x5A7A)

    lini = {
        kode: (await sesi.execute(_lini_pabrik(kode))).scalar_one()
        for kode, _nama in PABRIK_ARMADA
    }

    mesin: list[Equipment] = []
    for nomor in range(jumlah_equipment):
        kode_pabrik = PABRIK_ARMADA[nomor % len(PABRIK_ARMADA)][0]
        tipe, sufiks, model = TIPE_LATAR[nomor % len(TIPE_LATAR)]
        tag = f"{kode_pabrik}/{sufiks}-{600 + nomor:04d}"
        unit = Equipment(
            id=id_stabil(seed, f"latar:equipment:{tag}"),
            production_line_id=lini[kode_pabrik].id,
            canonical_id=f"EQUIPMENT-{tag}",
            tag_number=tag,
            name=f"{tipe.capitalize()} {tag}",
            equipment_type=tipe,
            manufacturer="Pabrikan Mesin Fiktif",
            model=model,
            serial_number=f"SN-{sufiks}-{nomor:04d}",
            commissioned_at=None,
            status="active",
        )
        sesi.add(unit)
        mesin.append(unit)

        for jenis, nama in acak.sample(KOMPONEN_LATAR, k=2):
            tag_komponen = f"{tag}-{jenis.upper()}"
            sesi.add(
                Component(
                    id=id_stabil(seed, f"latar:komponen:{tag_komponen}"),
                    equipment_id=unit.id,
                    canonical_id=f"COMPONENT-{tag_komponen}",
                    tag_number=tag_komponen,
                    name=nama,
                    component_type=jenis,
                    status="active",
                )
            )

    await sesi.flush()

    kegagalan = _tulis_kegagalan(sesi, seed, acak, mesin)
    work_order = _tulis_work_order(sesi, seed, acak, mesin, jumlah_work_order)
    await sesi.flush()

    cacah = {
        "equipment_latar": len(mesin),
        "komponen_latar": len(mesin) * 2,
        "kegagalan_latar": kegagalan,
        "work_order_latar": work_order,
    }
    logger.info("volume latar: %s", cacah)
    return cacah


def _lini_pabrik(kode_pabrik: str):
    from sqlalchemy import select

    from app.models.assets import Plant

    return (
        select(ProductionLine)
        .join(Plant, Plant.id == ProductionLine.plant_id)
        .where(Plant.code == kode_pabrik)
        .limit(1)
    )


def _tulis_kegagalan(sesi: AsyncSession, seed: int, acak: random.Random, mesin) -> int:
    """Kegagalan pada equipment latar. Tanpa penyebab terverifikasi.

    Sengaja tidak diberi `FailureEventCause`: kasus tertutup tanpa penyebab
    terverifikasi memang dikecualikan `find_historical_cases`, dan itulah yang
    diinginkan — volume latar tidak boleh menyumbang bobot corroboration kepada
    penjelasan yang tidak pernah ditegakkan siapa pun.
    """
    jumlah = 0
    for unit in mesin:
        if acak.random() > PELUANG_KEGAGALAN:
            continue
        terbuka = acak.random() < PELUANG_TERBUKA
        mulai = SEKARANG - timedelta(days=acak.randint(1, RENTANG_HARI))
        jumlah += 1
        sesi.add(
            FailureEvent(
                id=id_stabil(seed, f"latar:kegagalan:{unit.tag_number}:{jumlah}"),
                equipment_id=unit.id,
                component_id=None,
                canonical_id=f"FAILURE-LATAR-{jumlah:05d}",
                event_number=f"FE-LATAR-{jumlah:05d}",
                title=f"Gangguan pada {unit.tag_number}",
                description=acak.choice(GEJALA_BEBAS),
                started_at=mulai,
                ended_at=None if terbuka else mulai + timedelta(hours=acak.randint(2, 48)),
                downtime_minutes=None if terbuka else acak.randint(30, 600),
                status="open" if terbuka else "closed",
                source_system="CMMS-FIKTIF",
                source_record_id=f"LATAR-{jumlah:05d}",
            )
        )
    return jumlah


def _tulis_work_order(
    sesi: AsyncSession, seed: int, acak: random.Random, mesin, jumlah: int
) -> int:
    """Work order pada equipment latar saja.

    Tidak satu pun menempel pada filler jalur emas — lihat jalur kebocoran 3.
    """
    for nomor in range(jumlah):
        unit = mesin[nomor % len(mesin)]
        dijadwalkan = SEKARANG - timedelta(days=acak.randint(-90, RENTANG_HARI))
        sesi.add(
            WorkOrder(
                id=id_stabil(seed, f"latar:wo:{nomor}"),
                equipment_id=unit.id,
                canonical_id=f"WORKORDER-LATAR-{nomor:05d}",
                work_order_number=f"WO-LATAR-{nomor:05d}",
                description=f"Perawatan {unit.tag_number} (data latar sintetis)",
                work_order_type=acak.choice(JENIS_WO),
                status=acak.choice(STATUS_WO),
                priority=acak.choice(("low", "medium", "high")),
                opened_at=dijadwalkan - timedelta(days=acak.randint(1, 14)),
                scheduled_start_at=dijadwalkan,
                completed_at=None,
                source_system="CMMS-FIKTIF",
                source_record_id=f"WO-LATAR-{nomor:05d}",
            )
        )
    return jumlah
