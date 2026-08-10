"""Script Uji Variasi Layout Dashboard Dinamis (On-The-Fly) untuk ARKA dengan Data Kaya.

Menguji 3 variasi prompt dengan urutan_blok dan data lengkap terisi kaya.
"""

import asyncio
import json
import logging
from datetime import date
from decimal import Decimal
from google.genai import types

from app.agents.reporter import terbitkan_dokumen
from app.reporting.finding import (
    Finding,
    KandidatPenyebab,
    MataRantai,
    Preseden,
    Rekomendasi,
    RincianSkor,
    Sitasi,
    SparepartKritis,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolContextPalsu:
    def __init__(self):
        self.state = {}
        self.artifacts = []

    async def save_artifact(self, filename: str, artifact: types.Part) -> None:
        self.artifacts.append((filename, len(artifact.inline_data.data)))


def buat_skor(v_str: str) -> RincianSkor:
    v = Decimal(v_str)
    return RincianSkor(
        symptom_overlap=v, component_match=v, corroboration=v, recency=v, total=v
    )


def buat_temuan_kaya(tag: str, pabrik: str, eskalasi: bool) -> Finding:
    sitasi1 = Sitasi(
        canonical_id="DOC-INSP-2026-001",
        judul=f"Laporan Inspeksi Rutin {tag}",
        tipe_dokumen="laporan_inspeksi",
    )
    sitasi2 = Sitasi(
        canonical_id="DOC-HIST-2025-088",
        judul=f"Catatan Histori Pemeliharaan {tag}",
        tipe_dokumen="work_order_history",
    )

    return Finding(
        finding_id=f"FINDING-{tag}",
        dibuat_pada=date.today(),
        equipment_tag=tag,
        pabrik=pabrik,
        model_equipment="Heavy Duty Industrial Unit",
        gejala=["Kenaikan suhu berlebih", "Vibrasi tinggi pada bearing", "Fluktuasi tekanan"],
        perlu_eskalasi=eskalasi,
        keyakinan="tinggi" if not eskalasi else "sedang",
        kandidat=[
            KandidatPenyebab(
                cause_id="C1",
                nama=f"Degradasi Refraktori / Seal Utama {tag}",
                deskripsi="Indikasi titik panas berlebih pada struktur casing luar.",
                skor=buat_skor("0.88"),
                sitasi=[sitasi1],
            ),
            KandidatPenyebab(
                cause_id="C2",
                nama=f"Keausan Mechanical Seal / Shaft Bearing {tag}",
                deskripsi="Drift pelumasan dan clearance berlebih pada poros.",
                skor=buat_skor("0.82" if eskalasi else "0.45"),
                sitasi=[sitasi2],
            ),
        ],
        preseden=[
            Preseden(
                failure_event_id="PE-01",
                pabrik="Pabrik Utara",
                equipment_tag="PLT-U/FIL-207",
                tanggal_kejadian=date(2025, 4, 12),
                penyelesaian="Penggantian refraktori lokal & re-seal",
                sitasi=[sitasi1],
            ),
            Preseden(
                failure_event_id="PE-02",
                pabrik="Pabrik Selatan",
                equipment_tag="200-P-02",
                tanggal_kejadian=date(2024, 11, 5),
                penyelesaian="Overhaul bearing kit & flushing oli",
                sitasi=[sitasi2],
            ),
        ],
        rantai_kausal=[
            MataRantai(peran="symptom", label="Roof Hot Spot", detail="Peningkatan temperatur permukaan pelat atap >280°C"),
            MataRantai(peran="cause", label="Refractory Wall Failure", detail="Erosi dan retakan mikro pada struktur lining isolasi"),
            MataRantai(peran="damage", label="Thermal Overheating Casing", detail="Risiko deformasi pelat outer casing akibat ekspansi berlebih"),
            MataRantai(peran="part", label="Anchor Bolt & Ceramic Fiber", detail="Erosi jangkar penahan selimut isolasi ceramic fiber"),
        ],
        rekomendasi=[
            Rekomendasi(
                tindakan="Pemeriksaan Thermography Infra-Merah Berkala Harian",
                prioritas="segera" if eskalasi else "terjadwal",
                dasar="Verifikasi penyebaran titik panas pada permukaan casing luar.",
            ),
            Rekomendasi(
                tindakan="Pengujian Vibrasi & Sampling Pelumas Rutin",
                prioritas="terjadwal",
                dasar="Mencegah kegagalan sekunder pada bantalan dan poros.",
            ),
            Rekomendasi(
                tindakan="Persiapan Suku Cadang Refraktori & Overhaul Turnaround",
                prioritas="pantau",
                dasar="Menjamin kesiapan material saat jadwal pemeliharaan besar.",
            ),
        ],
        sparepart=[
            SparepartKritis(
                part_number="PART-992-HT",
                nama="Kit Ceramic Fiber Refractory & Seal",
                criticality=Decimal("0.95"),
                static_criticality=Decimal("0.50"),
                lead_time_minggu=4,
                jumlah_vendor=2,
            )
        ],
    )


async def main():
    ctx = ToolContextPalsu()

    print("\n" + "=" * 70)
    print("📊 MEMBANGKITKAN 3 VARIASI LAYOUT DASHBOARD DINAMIC (KAYA DATA)")
    print("=" * 70)

    # VARIATION 1: Action Plan First
    f1 = buat_temuan_kaya("HEATER-101", "Pabrik Utara", True)
    ctx.state["finding"] = f1.model_dump(mode="json")
    urutan_v1 = ["rekomendasi_tindakan", "kandidat_penyebab", "tabel_fakta", "rantai_kausal"]
    narasi_v1 = json.dumps({
        "ringkasan_eksekutif": "Pemeriksaan termografi Filler Rotary HEATER-101 mengindikasikan hot spot di atap heater.",
        "rekomendasi_tindakan": "Segera lakukan pemindaian infra-merah harian dan siapkan overhaul refraktori.",
    })
    konteks_v1 = json.dumps({"perihal": "Eskalasi Darurat Hot Spot"})

    res_v1 = await terbitkan_dokumen("dashboard", urutan_v1, narasi_v1, konteks_v1, ctx)

    # VARIATION 2: Metrics & Precedents First
    f2 = buat_temuan_kaya("PUMP-302", "Pabrik Selatan", False)
    ctx.state["finding"] = f2.model_dump(mode="json")
    urutan_v2 = ["tabel_fakta", "preseden_lintas_pabrik", "rekomendasi_tindakan", "sparepart_kritis"]
    narasi_v2 = json.dumps({
        "tabel_fakta": "Metrik kesehatan pompa PUMP-302 dalam kondisi stabil terverifikasi.",
        "rekomendasi_tindakan": "Jadwalkan pemeliharaan preventif berkala.",
    })
    konteks_v2 = json.dumps({"perihal": "Monitoring Rutin Pompa"})

    res_v2 = await terbitkan_dokumen("dashboard", urutan_v2, narasi_v2, konteks_v2, ctx)

    # VARIATION 3: Executive Summary First
    f3 = buat_temuan_kaya("COMPRESSOR-404", "Pabrik Timur", True)
    ctx.state["finding"] = f3.model_dump(mode="json")
    urutan_v3 = ["ringkasan_eksekutif", "kandidat_penyebab", "rantai_kausal", "sparepart_kritis"]
    narasi_v3 = json.dumps({
        "ringkasan_eksekutif": "Analisis keandalan Kompresor COMPRESSOR-404 mengidentifikasi fluktuasi clearance pelumas.",
    })
    konteks_v3 = json.dumps({"perihal": "Investasi Kompresor Strategis"})

    res_v3 = await terbitkan_dokumen("dashboard", urutan_v3, narasi_v3, konteks_v3, ctx)

    print("\n1️⃣ VARIASI 1 (Layout: Action Plan -> Donut Chart -> KPI Metrics -> Rantai Kausal):")
    print(res_v1)
    print("\n2️⃣ VARIASI 2 (Layout: KPI Metrics -> Bar Chart -> Action Plan -> Spareparts):")
    print(res_v2)
    print("\n3️⃣ VARIASI 3 (Layout: Executive Summary -> Donut Chart -> Rantai Kausal -> Spareparts):")
    print(res_v3)
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
