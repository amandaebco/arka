"""Demo Full Comprehensive Executive Dashboard Generator untuk ARKA.

Menghasilkan Dashboard Komprehensif MKS/Enterprise yang menampilkan SELURUH seksi,
SELURUH grafik (Donut Chart & Bar Chart), rantai kausalitas Knowledge Graph,
serta rekomendasi aksi secara utuh dan kaya informasi.
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


def buat_temuan_full_komprehensif() -> Finding:
    sitasi1 = Sitasi(
        canonical_id="DOC-INSP-2026-001",
        judul="Laporan Pemindaian Termografi Filler Rotary PLT-U/FIL-207",
        tipe_dokumen="laporan_inspeksi",
    )
    sitasi2 = Sitasi(
        canonical_id="DOC-HIST-2025-088",
        judul="Catatan Histori Turnaround & Refraktori PLT-U/FIL-207",
        tipe_dokumen="work_order_history",
    )
    sitasi3 = Sitasi(
        canonical_id="DOC-STD-API-560",
        judul="Standar Keandalan API 560 Filler Rotarys for General Refinery Service",
        tipe_dokumen="standar_teknis",
    )

    return Finding(
        finding_id="FINDING-PLT-U/FIL-207-FULL",
        dibuat_pada=date.today(),
        equipment_tag="PLT-U/FIL-207",
        pabrik="Pabrik Utara",
        model_equipment="Filler Rotary Heavy Duty Crude Distillation Unit",
        gejala=[
            "Kenaikan temperatur permukaan pelat atap heater menembus batas aman 280°C",
            "Sinyal kenaikan konstan pada sensor tube skin TS-207 dan TE-223",
            "Fluktuasi efisiensi termal pembakaran sebesar 4.2%",
        ],
        perlu_eskalasi=True,
        keyakinan="sedang",
        alasan_eskalasi="Dua kandidat penyebab berselisih skor sangat tipis (0.88 vs 0.82) — memerlukan keputusan manajemen keandalan.",
        kandidat=[
            KandidatPenyebab(
                cause_id="C1",
                nama="Degradasi Refraktori Atap Heater (Roof Hot Spot)",
                deskripsi="Penurunan ketebalan dan retakan mikro pada lapisan ceramic fiber insulation lining di zona atap.",
                skor=buat_skor("0.88"),
                sitasi=[sitasi1, sitasi3],
            ),
            KandidatPenyebab(
                cause_id="C2",
                nama="Kerusakan / Drifting Sensor Thermocouple Tube Skin 100-TS-207",
                deskripsi="Deviasi sensitivitas elemen termokopel akibat akumulasi kerak pemicu sinyal pembacaan palsu.",
                skor=buat_skor("0.82"),
                sitasi=[sitasi2],
            ),
            KandidatPenyebab(
                cause_id="C3",
                nama="Fouling / Coking pada Tube Radiant Pass 2",
                deskripsi="Penumpukan lapisan kokas kualitatif di dinding bagian dalam tabung radiasi.",
                skor=buat_skor("0.65"),
                sitasi=[sitasi3],
            ),
        ],
        preseden=[
            Preseden(
                failure_event_id="PE-DUM-01",
                pabrik="Pabrik Utara",
                equipment_tag="PLT-U/FIL-207",
                tanggal_kejadian=date(2025, 4, 12),
                penyelesaian="Perbaikan lokal isolasi refraktori & inspeksi paku jangkar (anchor bolt)",
                downtime_jam=Decimal("18.5"),
                sitasi=[sitasi1],
            ),
            Preseden(
                failure_event_id="PE-CIL-02",
                pabrik="Pabrik Selatan",
                equipment_tag="200-H-02",
                tanggal_kejadian=date(2024, 11, 5),
                penyelesaian="Ganti selimut ceramic fiber & penggantian 2 unit sensor TS-207",
                downtime_jam=Decimal("24.0"),
                sitasi=[sitasi2],
            ),
            Preseden(
                failure_event_id="PE-BAL-03",
                pabrik="Pabrik Timur",
                equipment_tag="300-H-101",
                tanggal_kejadian=date(2023, 8, 19),
                penyelesaian="Injeksi sealing compound khusus tahan panas pada casing outer plate",
                downtime_jam=Decimal("12.0"),
                sitasi=[sitasi3],
            ),
        ],
        rantai_kausal=[
            MataRantai(
                peran="symptom",
                label="Roof Hot Spot & Alarm TS-207",
                detail="Peningkatan temperatur permukaan pelat atap >280°C terdeteksi pemindaian infra-merah.",
            ),
            MataRantai(
                peran="cause",
                label="Refractory Wall Failure",
                detail="Erosi dan retakan mikro pada struktur lining isolasi ceramic fiber akibat siklus termal.",
            ),
            MataRantai(
                peran="damage",
                label="Thermal Overheating Casing Plate",
                detail="Risiko deformasi fisik pelat outer casing akibat pemaparan panas langsung.",
            ),
            MataRantai(
                peran="part",
                label="Anchor Bolt & Ceramic Fiber Blanket",
                detail="Erosi jangkar penahan selimut isolasi refraktori membutuhkan penggantian material.",
            ),
        ],
        rekomendasi=[
            Rekomendasi(
                tindakan="Pemeriksaan Thermography Infra-Merah Harian pada Atap Filler Rotary",
                prioritas="segera",
                dasar="Verifikasi penyebaran titik panas dan laju kenaikan suhu permukaan casing luar secara realtime.",
            ),
            Rekomendasi(
                tindakan="Validasi & Kalibrasi Loop Sensor Thermocouple 100-TS-207",
                prioritas="terjadwal",
                dasar="Akurasi pengukuran tube skin sangat penting untuk membedakan antara hot spot asli dan indikasi sensor drifting.",
            ),
            Rekomendasi(
                tindakan="Mobilisasi Material Suku Cadang Ceramic Fiber Kit & Persiapan Shutdown Turnaround",
                prioritas="pantau",
                dasar="Menjamin ketersediaan kit refraktori PART-992-HT di gudang sebelum tindakan perbaikan besar dieksekusi.",
            ),
        ],
        sparepart=[
            SparepartKritis(
                part_number="PART-992-HT",
                nama="Kit Ceramic Fiber Refractory & High-Temp Sealing Blanket",
                criticality=Decimal("0.95"),
                static_criticality=Decimal("0.50"),
                lead_time_minggu=4,
                jumlah_vendor=3,
                pabrik_terdampak=["Pabrik Utara", "Pabrik Selatan"],
            ),
            SparepartKritis(
                part_number="PART-TS-207-K",
                nama="Thermocouple Tube Skin Assembly Type-K High-Accuracy",
                criticality=Decimal("0.88"),
                static_criticality=Decimal("0.60"),
                lead_time_minggu=2,
                jumlah_vendor=4,
                pabrik_terdampak=["Pabrik Utara"],
            ),
        ],
    )


async def main():
    ctx = ToolContextPalsu()

    print("\n" + "=" * 80)
    print("🚀 GENERATING FULL COMPREHENSIVE ARKA EXECUTIVE DASHBOARD (ALL CHARTS & BLOCKS)")
    print("=" * 80)

    finding = buat_temuan_full_komprehensif()
    ctx.state["finding"] = finding.model_dump(mode="json")

    # Full comprehensive sequence including ALL available blocks
    urutan_lengkap = [
        "ringkasan_eksekutif",
        "tabel_fakta",
        "kandidat_penyebab",
        "preseden_lintas_pabrik",
        "rantai_kausal",
        "rekomendasi_tindakan",
        "sparepart_kritis",
    ]

    narasi_komprehensif = json.dumps({
        "ringkasan_eksekutif": (
            "Pemeriksaan termografi berkala pada Filler Rotary PLT-U/FIL-207 di Pabrik Pabrik Utara "
            "mengindikasikan pembentukan titik panas di struktur atap heater. "
            "Sinyal kenaikan suhu juga terkonfirmasi dari sensor tube skin TS-207 dan TE-223. "
            "Analisis Knowledge Graph ARKA mengidentifikasi dua kandidat utama dengan tingkat keyakinan seimbang "
            "sehingga membutuhkan eskalasi manajemen keandalan."
        ),
        "rekomendasi_tindakan": (
            "Langkah mitigasi diprioritaskan pada pemindaian termografi harian, kalibrasi loop instrumen TS-207, "
            "serta kesiapan material isolasi refraktori di gudang."
        ),
    })

    konteks_enterprise = json.dumps({
        "unit_penerbit": "INGOUDE COMPANY",
        "perihal": "Executive Reliability Dashboard — Filler Rotary PLT-U/FIL-207 Hot Spot Anomaly",
    })

    respon_chat = await terbitkan_dokumen("dashboard", urutan_lengkap, narasi_komprehensif, konteks_enterprise, ctx)

    print("\n💬 [RESPON REPORTER AGENT KE CHAT UI]:")
    print(respon_chat)
    print("\n" + "=" * 80)
    print("✅ FULL COMPREHENSIVE DASHBOARD GENERATED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
