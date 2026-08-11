"""Aktivitas perawatan, pemakaian sparepart, dan mode kegagalan.

Menutup dua lubang yang terlihat begitu graph ditelusuri: empat jenis edge yang
dideklarasikan tetapi nol baris (`AKTIVITAS`, `MEMAKAI`, `DIKERJAKAN_OLEH`,
`BERMODE`), dan dua label node tanpa isi. Graph yang mengiklankan lebih dari
yang dimilikinya akan ketahuan pada penelusuran pertama.

## Yang berubah secara nyata

Sebelum ini sparepart terhubung ke komponen **hanya lewat `component_type`** —
kecocokan string, bukan riwayat. Pertanyaan "apa lagi yang memakai part ini"
karena itu dijawab dengan "apa lagi yang **tipenya** sama", yang tidak sama
artinya dan lebih lemah.

`activity_spare_parts` mencatat pemakaian yang benar-benar terjadi: pekerjaan
mana, kapan, berapa banyak. Traversal lima hop sekarang bisa berjalan dari satu
kegagalan ke pekerjaan yang menanganinya, ke part yang dipakai, lalu keluar ke
pekerjaan lain yang memakai part yang sama di pabrik lain — seluruhnya lewat
kejadian tercatat, bukan lewat kecocokan tipe.

## Kenapa ini tidak menyentuh angka

Tidak ada satu pun modul di `app/detection/`, `app/agents/`, atau
`app/reporting/` yang membaca `maintenance_activities`, `activity_spare_parts`,
`activity_technicians`, `technicians`, maupun `failure_event_failure_modes`.
Diperiksa sebelum ditulis, dan dijaga `test_aktivitas.py`.

Jadi tabel-tabel ini memperkaya graph tanpa punya jalur ke skor — dan itulah
alasan keduanya aman dikerjakan di hari submission.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maintenance import (
    ActivitySparePart,
    ActivityTechnician,
    MaintenanceActivity,
    SparePart,
    Technician,
    WorkOrder,
)
from app.models.reliability import FailureEvent, FailureEventFailureMode, FailureMode
from app.synthetic.jalur_emas import SEMUA_KASUS, id_stabil

logger = logging.getLogger(__name__)

# (nomor pegawai, nama, keahlian)
TEKNISI: tuple[tuple[str, str, str], ...] = (
    ("EMP-1001", "Teknisi Mekanik 1", "mekanik"),
    ("EMP-1002", "Teknisi Mekanik 2", "mekanik"),
    ("EMP-1003", "Teknisi Elektrik 1", "elektrik"),
    ("EMP-1004", "Teknisi Instrumentasi 1", "instrumentasi"),
    ("EMP-1005", "Teknisi Mekanik 3", "mekanik"),
)

# Jenis komponen jalur emas → part number yang dipakai menggantinya.
PART_PER_KOMPONEN: dict[str, str] = {
    "seal": "SP-SEAL-8801",
    "nozel": "SP-NOZEL-2210",
    "brg": "SP-BRG-4470",
}

# Mode kegagalan per jenis komponen. Seal yang mengeras sebelum umurnya adalah
# keausan dini; sisanya bermuara pada kebocoran sambungan statis.
MODE_PER_KOMPONEN: dict[str, str] = {
    "seal": "MOD-AUS-DINI",
    "katup": "MOD-BOCOR-STATIS",
    "nozel": "MOD-BOCOR-STATIS",
    "brg": "MOD-AUS-DINI",
}


async def tulis_teknisi(sesi: AsyncSession, seed: int) -> dict[str, Technician]:
    peta: dict[str, Technician] = {}
    for nomor, nama, keahlian in TEKNISI:
        obj = Technician(
            id=id_stabil(seed, f"teknisi:{nomor}"),
            canonical_id=f"TECH-{nomor}",
            employee_number=nomor,
            name=nama,
            specialization=keahlian,
            status="active",
        )
        sesi.add(obj)
        peta[nomor] = obj
    await sesi.flush()
    return peta


async def tulis_aktivitas_jalur_emas(
    sesi: AsyncSession, seed: int, teknisi: dict[str, Technician]
) -> dict[str, int]:
    """Satu aktivitas per work order jalur emas, dengan pemakaian partnya.

    Hanya kasus yang **tuntas** mencatat pemakaian sparepart: pekerjaan yang
    masih terbuka belum mengambil material apa pun, dan mencatatnya seolah sudah
    akan membuat riwayat pemakaian berbohong ke arah yang paling merugikan —
    part terlihat lebih sering dipakai daripada kenyataannya.
    """
    parts = {
        p.part_number: p
        for p in (await sesi.execute(select(SparePart))).scalars()
    }
    aktivitas_dibuat = pemakaian = penugasan = 0

    for urutan, kasus in enumerate(SEMUA_KASUS):
        wo = (
            await sesi.execute(
                select(WorkOrder).where(WorkOrder.canonical_id == f"WO-{kasus.kunci.upper()}")
            )
        ).scalar_one_or_none()
        if wo is None:  # pragma: no cover — generator selalu menulisnya
            continue

        jenis = kasus.komponen.lower()
        selesai = kasus.mulai + timedelta(minutes=kasus.menit_henti or 60)
        aktivitas = MaintenanceActivity(
            id=id_stabil(seed, f"aktivitas:{kasus.kunci}"),
            work_order_id=wo.id,
            activity_code=f"ACT-{kasus.kunci.upper()}",
            activity_type="penggantian" if kasus.tuntas else "pemeriksaan",
            sequence_number=1,
            description=kasus.solusi or kasus.catatan,
            status="completed" if kasus.tuntas else "planned",
            started_at=kasus.mulai,
            completed_at=selesai if kasus.tuntas else None,
            result=kasus.solusi if kasus.tuntas else None,
            source_system="sintetis",
            source_record_id=kasus.kunci,
        )
        sesi.add(aktivitas)
        await sesi.flush()
        aktivitas_dibuat += 1

        nomor = TEKNISI[urutan % len(TEKNISI)][0]
        sesi.add(
            ActivityTechnician(
                activity_id=aktivitas.id,
                technician_id=teknisi[nomor].id,
                role="pelaksana",
            )
        )
        penugasan += 1

        part_number = PART_PER_KOMPONEN.get(jenis)
        if kasus.tuntas and part_number and part_number in parts:
            sesi.add(
                ActivitySparePart(
                    activity_id=aktivitas.id,
                    spare_part_id=parts[part_number].id,
                    quantity=Decimal("1.000"),
                    unit="pcs",
                    batch_number=f"LOT-202602-{part_number.replace('SP-', '')}",
                )
            )
            pemakaian += 1

    await sesi.flush()
    return {
        "aktivitas": aktivitas_dibuat,
        "pemakaian_sparepart": pemakaian,
        "penugasan_teknisi": penugasan,
    }


async def tulis_mode_kegagalan(sesi: AsyncSession, seed: int) -> dict[str, int]:
    """Tautkan kegagalan jalur emas ke mode kegagalannya.

    `failure_modes` sudah berisi dua baris sejak awal tetapi tidak ada yang
    merujuknya — kosakata yang terdaftar dan tidak pernah dipakai. Mode kegagalan
    adalah kosakata baku keandalan (FMEA); tabel yang kosong membuat klaim
    "taksonomi mengikuti pola standar industri" tidak punya bukti.
    """
    mode = {
        m.canonical_id: m for m in (await sesi.execute(select(FailureMode))).scalars()
    }
    ditulis = 0
    for kasus in SEMUA_KASUS:
        kode = MODE_PER_KOMPONEN.get(kasus.komponen.lower())
        if kode not in mode:
            continue
        kejadian = (
            await sesi.execute(
                select(FailureEvent).where(
                    FailureEvent.canonical_id == f"FAILURE-{kasus.kunci.upper()}"
                )
            )
        ).scalar_one_or_none()
        if kejadian is None:  # pragma: no cover
            continue
        sesi.add(
            FailureEventFailureMode(
                failure_event_id=kejadian.id,
                failure_mode_id=mode[kode].id,
                # Kasus tuntas sudah diperiksa; kasus hidup masih dugaan.
                confidence=Decimal("0.9000") if kasus.tuntas else Decimal("0.6000"),
                is_primary=True,
            )
        )
        ditulis += 1

    await sesi.flush()
    return {"mode_kegagalan_tertaut": ditulis}


# Sparepart untuk armada latar. Jenis komponennya **tidak beririsan** dengan
# jalur emas (seal, katup, nozel, brg), jadi `plants_served` SP-SEAL-8801 tidak
# tersentuh dan kekritisannya tetap 0,8667 — jalur kebocoran yang sama yang
# dijaga `volume_latar.py`, dan dijaga ulang di `test_aktivitas.py`.
PART_LATAR: tuple[tuple[str, str, str], ...] = (
    ("SP-MOTOR-3300", "Motor penggerak MB-300", "motor"),
    ("SP-BELT-1150", "Sabuk transmisi KM-120", "belt"),
    ("SP-GEAR-7720", "Set roda gigi MB-300", "gearbox"),
    ("SP-PANEL-4400", "Modul kendali LR-450", "panel"),
)

# Berapa bagian pekerjaan latar yang tuntas mencatat pemakaian material.
# Tidak semua pekerjaan memakai sparepart — pemeriksaan dan penyetelan tidak —
# dan mencatat seolah semuanya memakai akan membuat riwayat pemakaian tidak
# berguna justru pada pertanyaan yang paling dibutuhkan.
PELUANG_PAKAI_PART = 0.35


async def tulis_aktivitas_latar(
    sesi: AsyncSession, seed: int, teknisi: dict[str, Technician]
) -> dict[str, int]:
    """Aktivitas dan pemakaian material untuk pekerjaan latar.

    Tanpa ini, `AKTIVITAS`, `DIKERJAKAN_OLEH`, dan `MEMAKAI` hanya punya
    segelintir baris dari jalur emas — graph yang secara teknis lengkap tetapi
    kosong begitu ditelusuri di luar delapan kasus demo.
    """
    import random

    acak = random.Random(seed ^ 0xAC7)

    parts = []
    for nomor, nama, jenis in PART_LATAR:
        obj = SparePart(
            id=id_stabil(seed, f"latar:sparepart:{nomor}"),
            canonical_id=f"PART-{nomor}",
            part_number=nomor,
            name=nama,
            manufacturer="Vendor Umum",
            description="Sparepart armada latar (data sintetis)",
            component_type=jenis,
            static_criticality=None,
            lead_time_weeks=acak.randint(1, 4),
            vendor_count=acak.randint(2, 5),
            primary_vendor="Vendor Umum",
        )
        sesi.add(obj)
        parts.append(obj)
    await sesi.flush()

    selesai = (
        await sesi.execute(
            select(WorkOrder).where(
                WorkOrder.canonical_id.like("WORKORDER-LATAR-%"),
                WorkOrder.status == "completed",
            )
        )
    ).scalars().all()

    aktivitas_dibuat = pemakaian = 0
    for urutan, wo in enumerate(selesai):
        aktivitas = MaintenanceActivity(
            id=id_stabil(seed, f"latar:aktivitas:{wo.canonical_id}"),
            work_order_id=wo.id,
            activity_code=f"ACT-{wo.work_order_number}",
            activity_type=acak.choice(("pemeriksaan", "penyetelan", "penggantian")),
            sequence_number=1,
            description="Pekerjaan perawatan rutin (data latar sintetis)",
            status="completed",
            started_at=wo.scheduled_start_at,
            completed_at=wo.scheduled_start_at,
            result="selesai",
            source_system="CMMS-FIKTIF",
            source_record_id=wo.source_record_id,
        )
        sesi.add(aktivitas)
        await sesi.flush()
        aktivitas_dibuat += 1

        sesi.add(
            ActivityTechnician(
                activity_id=aktivitas.id,
                technician_id=teknisi[TEKNISI[urutan % len(TEKNISI)][0]].id,
                role="pelaksana",
            )
        )

        if acak.random() < PELUANG_PAKAI_PART:
            sesi.add(
                ActivitySparePart(
                    activity_id=aktivitas.id,
                    spare_part_id=acak.choice(parts).id,
                    quantity=Decimal(acak.randint(1, 4)),
                    unit="pcs",
                )
            )
            pemakaian += 1

    await sesi.flush()
    return {
        "sparepart_latar": len(parts),
        "aktivitas_latar": aktivitas_dibuat,
        "pemakaian_latar": pemakaian,
    }


async def tulis_semua(
    sesi: AsyncSession, seed: int, *, volume_latar: bool = False
) -> dict[str, int]:
    """Teknisi, aktivitas, pemakaian part, dan tautan mode kegagalan."""
    teknisi = await tulis_teknisi(sesi, seed)
    hasil = {"teknisi": len(teknisi)}
    hasil |= await tulis_aktivitas_jalur_emas(sesi, seed, teknisi)
    hasil |= await tulis_mode_kegagalan(sesi, seed)
    if volume_latar:
        hasil |= await tulis_aktivitas_latar(sesi, seed, teknisi)
    logger.info("aktivitas: %s", hasil)
    return hasil
