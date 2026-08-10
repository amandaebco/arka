"""Penulis data sintetis — langsung ke tabel kanonik, tanpa ETL.

Menggantikan generator lama yang menulis CSV untuk dataset pabrik. Domain,
skala, bahasa, dan bentuk keluarannya semua berbeda; tidak ada yang bisa
diselamatkan selain gagasan id deterministik.

Urutan penulisan mengikuti ketergantungan kunci asing, bukan kerapian: kosakata
lebih dulu, lalu aset, lalu kegagalan, lalu pekerjaan, lalu dokumen.

Jalankan:

    uv run python -m app.synthetic.generator --reset
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_factory
from app.models import (
    Cause,
    Component,
    Damage,
    Document,
    DocumentChunk,
    DocumentVersion,
    Equipment,
    FailureEvent,
    FailureEventCause,
    FailureEventSymptom,
    FailureMode,
    MaintenanceNotification,
    Plant,
    ProductionLine,
    SparePart,
    Symptom,
    WorkOrder,
    WorkOrderFailureEvent,
    WorkOrderNotification,
)
from app.synthetic.jalur_emas import (
    DOKUMEN,
    GEJALA,
    KOMPONEN_FILLER,
    MODE_KEGAGALAN,
    MODEL_FILLER,
    PABRIK_ARMADA,
    PENYEBAB,
    SEAL_KRITIS,
    SEED_BAWAAN,
    SEMUA_KASUS,
    SPAREPART_LAIN,
    TIPE_EQUIPMENT,
    id_stabil,
    tag_equipment,
)

logger = logging.getLogger(__name__)

# Urutan penghapusan = kebalikan ketergantungan. Ditulis eksplisit supaya
# `--reset` tidak bergantung pada ON DELETE CASCADE yang mungkin berubah.
URUTAN_HAPUS = (
    DocumentChunk,
    DocumentVersion,
    Document,
    WorkOrderNotification,
    WorkOrderFailureEvent,
    MaintenanceNotification,
    WorkOrder,
    Damage,
    FailureEventCause,
    FailureEventSymptom,
    FailureEvent,
    Component,
    Equipment,
    ProductionLine,
    Plant,
    SparePart,
    Cause,
    FailureMode,
    Symptom,
)


def _hash(teks: str) -> str:
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


async def kosongkan(sesi: AsyncSession) -> None:
    """Hapus isi tabel yang disentuh generator ini.

    Hanya tabel milik jalur emas. Tabel lain dibiarkan supaya `--reset` tidak
    diam-diam membuang data yang ditulis bagian lain sistem.
    """
    for model in URUTAN_HAPUS:
        await sesi.execute(delete(model))
    logger.info("Tabel jalur emas dikosongkan")


async def tulis_kosakata(sesi: AsyncSession, seed: int) -> dict[str, dict[str, object]]:
    """Gejala, penyebab, dan mode kegagalan. Dirujuk seluruh kasus."""
    peta: dict[str, dict[str, object]] = {"gejala": {}, "penyebab": {}, "mode": {}}

    for kode, nama in GEJALA:
        obj = Symptom(
            id=id_stabil(seed, f"gejala:{kode}"),
            canonical_id=kode,
            code=kode,
            name=nama,
        )
        sesi.add(obj)
        peta["gejala"][kode] = obj

    for kode, nama, kategori in PENYEBAB:
        obj = Cause(
            id=id_stabil(seed, f"penyebab:{kode}"),
            canonical_id=kode,
            code=kode,
            name=nama,
            category=kategori,
        )
        sesi.add(obj)
        peta["penyebab"][kode] = obj

    for kode, nama in MODE_KEGAGALAN:
        obj = FailureMode(
            id=id_stabil(seed, f"mode:{kode}"),
            canonical_id=kode,
            code=kode,
            name=nama,
        )
        sesi.add(obj)
        peta["mode"][kode] = obj

    await sesi.flush()
    return peta


async def tulis_armada(sesi: AsyncSession, seed: int) -> dict[str, dict]:
    """Pabrik, lini, filler, dan komponennya.

    Setiap pabrik mendapat satu filler dari model yang sama — inilah armada
    seragam yang membuat preseden lintas pabrik masuk akal.
    """
    equipment_per_kasus = {k.kode_pabrik: k for k in SEMUA_KASUS}
    hasil: dict[str, dict] = {"equipment": {}, "komponen": {}}

    for kode_pabrik, nama_pabrik in PABRIK_ARMADA:
        pabrik = Plant(
            id=id_stabil(seed, f"pabrik:{kode_pabrik}"),
            canonical_id=f"PLANT-{kode_pabrik}",
            code=kode_pabrik,
            name=nama_pabrik,
            description="Pabrik minuman kemasan (fiktif)",
        )
        sesi.add(pabrik)

        lini = ProductionLine(
            id=id_stabil(seed, f"lini:{kode_pabrik}"),
            plant_id=pabrik.id,
            canonical_id=f"LINE-{kode_pabrik}-01",
            code="LN-01",
            name=f"Lini Pengisian 1 — {nama_pabrik}",
        )
        sesi.add(lini)

        kasus = equipment_per_kasus.get(kode_pabrik)
        nomor = kasus.nomor_equipment if kasus else 100
        tag = tag_equipment(kode_pabrik, nomor)
        mesin = Equipment(
            id=id_stabil(seed, f"equipment:{tag}"),
            production_line_id=lini.id,
            canonical_id=f"EQUIPMENT-{tag}",
            tag_number=tag,
            name=f"Filler {tag}",
            equipment_type=TIPE_EQUIPMENT,
            manufacturer="Pabrikan Mesin Fiktif",
            model=MODEL_FILLER,
            serial_number=f"SN-{kode_pabrik}-{nomor:03d}",
            commissioned_at=None,
            status="active",
        )
        sesi.add(mesin)
        hasil["equipment"][kode_pabrik] = mesin

        for sufiks, nama_komponen in KOMPONEN_FILLER:
            tag_komponen = f"{tag}-{sufiks}"
            komponen = Component(
                id=id_stabil(seed, f"komponen:{tag_komponen}"),
                equipment_id=mesin.id,
                canonical_id=f"COMPONENT-{tag_komponen}",
                tag_number=tag_komponen,
                name=nama_komponen,
                component_type=sufiks.lower(),
                status="active",
            )
            sesi.add(komponen)
            hasil["komponen"][(kode_pabrik, sufiks)] = komponen

    await sesi.flush()
    return hasil


async def tulis_sparepart(sesi: AsyncSession, seed: int) -> dict[str, SparePart]:
    """Master sparepart, lengkap dengan atribut rantai pasok."""
    peta: dict[str, SparePart] = {}
    for spek in (SEAL_KRITIS, *SPAREPART_LAIN):
        obj = SparePart(
            id=id_stabil(seed, f"sparepart:{spek.part_number}"),
            canonical_id=f"PART-{spek.part_number}",
            part_number=spek.part_number,
            name=spek.nama,
            manufacturer=spek.vendor,
            description=f"Dipakai pada {MODEL_FILLER}",
            static_criticality=spek.static_criticality,
            lead_time_weeks=spek.lead_time_minggu,
            vendor_count=spek.jumlah_vendor,
            primary_vendor=spek.vendor,
        )
        sesi.add(obj)
        peta[spek.part_number] = obj
    await sesi.flush()
    return peta


async def tulis_kasus(
    sesi: AsyncSession,
    seed: int,
    kosakata: dict[str, dict[str, object]],
    armada: dict[str, dict],
) -> None:
    """Kegagalan, gejala yang menyertainya, kerusakan, dan pekerjaannya.

    Kasus yang sudah tuntas mendapat penyebab terverifikasi; kasus hidup tidak.
    Perbedaan itu yang membuat investigator punya sesuatu untuk diselidiki.
    """
    for kasus in SEMUA_KASUS:
        mesin = armada["equipment"][kasus.kode_pabrik]
        komponen = armada["komponen"][(kasus.kode_pabrik, kasus.komponen)]
        selesai = kasus.mulai + timedelta(minutes=kasus.menit_henti) if kasus.tuntas else None

        kejadian = FailureEvent(
            id=id_stabil(seed, f"kejadian:{kasus.kunci}"),
            equipment_id=mesin.id,
            component_id=komponen.id,
            canonical_id=f"FAILURE-{kasus.kunci.upper()}",
            event_number=f"FE-{kasus.kunci.upper()}",
            title=f"Kegagalan kepala pengisi {mesin.tag_number}",
            description=kasus.catatan,
            started_at=kasus.mulai,
            ended_at=selesai,
            downtime_minutes=kasus.menit_henti or None,
            status="closed" if kasus.tuntas else "open",
            source_system="sintetis",
            source_record_id=kasus.kunci,
        )
        sesi.add(kejadian)

        for kode_gejala in kasus.gejala:
            sesi.add(
                FailureEventSymptom(
                    failure_event_id=kejadian.id,
                    symptom_id=kosakata["gejala"][kode_gejala].id,
                    observed_at=kasus.mulai,
                    severity="high" if kasus.tuntas else "medium",
                )
            )

        if kasus.penyebab:
            sesi.add(
                FailureEventCause(
                    id=id_stabil(seed, f"penyebab-kejadian:{kasus.kunci}"),
                    failure_event_id=kejadian.id,
                    cause_id=kosakata["penyebab"][kasus.penyebab].id,
                    verification_method="inspeksi lapangan",
                    verified_at=selesai or kasus.mulai,
                    verified_by="Tim Keandalan",
                    is_primary=True,
                )
            )
            sesi.add(
                Damage(
                    id=id_stabil(seed, f"kerusakan:{kasus.kunci}"),
                    failure_event_id=kejadian.id,
                    component_id=komponen.id,
                    damage_type="degradasi" if kasus.komponen == "SEAL" else "penyimpangan",
                    description=kasus.solusi or kasus.catatan,
                    severity="high",
                    detected_at=kasus.mulai,
                )
            )

        notifikasi = MaintenanceNotification(
            id=id_stabil(seed, f"notifikasi:{kasus.kunci}"),
            canonical_id=f"NOTIF-{kasus.kunci.upper()}",
            notification_number=f"NT-{kasus.kunci.upper()}",
            description=kasus.catatan,
            source_system="sintetis",
            source_record_id=kasus.kunci,
        )
        sesi.add(notifikasi)

        perintah = WorkOrder(
            id=id_stabil(seed, f"wo:{kasus.kunci}"),
            equipment_id=mesin.id,
            canonical_id=f"WO-{kasus.kunci.upper()}",
            work_order_number=f"WO-{kasus.kunci.upper()}",
            work_order_type="corrective",
            priority="high",
            status="completed" if kasus.tuntas else "created",
            description=kasus.solusi or kasus.catatan,
            opened_at=kasus.mulai,
            completed_at=selesai,
            source_system="sintetis",
            source_record_id=kasus.kunci,
        )
        sesi.add(perintah)
        await sesi.flush()

        sesi.add(
            WorkOrderNotification(work_order_id=perintah.id, notification_id=notifikasi.id)
        )
        sesi.add(
            WorkOrderFailureEvent(
                work_order_id=perintah.id,
                failure_event_id=kejadian.id,
                relationship_type="responds_to",
            )
        )

    await sesi.flush()


async def tulis_dokumen(sesi: AsyncSession, seed: int) -> None:
    """Laporan inspeksi yang bisa dikutip.

    Satu potongan per dokumen sudah cukup untuk sitasi; pemotongan halus baru
    perlu kalau pencarian semantik menuntutnya.
    """
    for berkas in DOKUMEN:
        dokumen = Document(
            id=id_stabil(seed, f"dokumen:{berkas.canonical_id}"),
            canonical_id=berkas.canonical_id,
            source_system="sintetis",
            source_document_id=berkas.canonical_id,
            document_type="inspection_report",
            title=berkas.judul,
            author="Tim Keandalan",
            source_created_at=None,
        )
        sesi.add(dokumen)

        versi = DocumentVersion(
            id=id_stabil(seed, f"versi:{berkas.canonical_id}"),
            document_id=dokumen.id,
            version_number=1,
            content_hash=_hash(berkas.isi),
            mime_type="text/plain",
            extracted_text=berkas.isi,
        )
        sesi.add(versi)

        sesi.add(
            DocumentChunk(
                id=id_stabil(seed, f"potongan:{berkas.canonical_id}"),
                document_version_id=versi.id,
                chunk_index=0,
                content=berkas.isi,
                content_hash=_hash(berkas.isi),
                start_offset=0,
                end_offset=len(berkas.isi),
            )
        )

    await sesi.flush()


async def bangun(seed: int = SEED_BAWAAN, reset: bool = False) -> dict[str, int]:
    """Bangun jalur emas di dalam database. Mengembalikan cacah per kelompok."""
    async with session_factory() as sesi:
        if reset:
            await kosongkan(sesi)

        kosakata = await tulis_kosakata(sesi, seed)
        armada = await tulis_armada(sesi, seed)
        await tulis_sparepart(sesi, seed)
        await tulis_kasus(sesi, seed, kosakata, armada)
        await tulis_dokumen(sesi, seed)
        await sesi.commit()

    return {
        "pabrik": len(PABRIK_ARMADA),
        "equipment": len(PABRIK_ARMADA),
        "kasus": len(SEMUA_KASUS),
        "dokumen": len(DOKUMEN),
        "sparepart": 1 + len(SPAREPART_LAIN),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Bangun data sintetis ARKA")
    parser.add_argument("--seed", type=int, default=SEED_BAWAAN)
    parser.add_argument(
        "--reset", action="store_true", help="Kosongkan tabel jalur emas lebih dulu"
    )
    argumen = parser.parse_args()

    cacah = asyncio.run(bangun(seed=argumen.seed, reset=argumen.reset))
    for nama, jumlah in cacah.items():
        print(f"  {nama:12} {jumlah}")


if __name__ == "__main__":
    main()
