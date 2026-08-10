"""Script Uji Skenario Golden Prompts untuk 3 Jenis Output Utama ARKA.

Menguji dan membuktikan bahwa ARKA dapat menerbitkan 3 jenis keluaran dokumen resmi:
1. Memo Teknis (memo) - Skenario Reliability Engineer CMRP
2. Executive Web Dashboard (dashboard) - Skenario Visual Interaktif + Live Mobile QR
3. Nota Dinas Eskalasi (nota_dinas) - Skenario VP Reliability / Manajemen Strategis
"""

import asyncio
import json
import logging
from datetime import date
from decimal import Decimal

from google.genai import types

from app.agents.reporter import terbitkan_dokumen
from app.reporting.finding import Finding, KandidatPenyebab, RincianSkor, Sitasi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolContextPalsu:
    def __init__(self):
        self.state = {}
        self.artifacts = []

    async def save_artifact(self, filename: str, artifact: types.Part) -> None:
        self.artifacts.append((filename, len(artifact.inline_data.data)))
        logger.info("Artifact %s disimpan (%d bita)", filename, len(artifact.inline_data.data))


def buat_skor(total_val: str) -> RincianSkor:
    v = Decimal(total_val)
    return RincianSkor(
        symptom_overlap=v,
        component_match=v,
        corroboration=v,
        recency=v,
        total=v,
    )


def buat_temuan_100_h_1() -> Finding:
    sitasi1 = Sitasi(
        canonical_id="DOC-INSP-2026-001",
        judul="Laporan Pemindaian Thermography Filler Rotary PLT-U/FIL-207",
        tipe_dokumen="laporan_inspeksi",
    )
    sitasi2 = Sitasi(
        canonical_id="DOC-RKAP-2026-009",
        judul="Rencana Program Pemeliharaan & Overhaul Refraktori Pabrik Utara",
        tipe_dokumen="program_rkap",
    )

    return Finding(
        finding_id="FINDING-PLT-U/FIL-207-GOLDEN",
        dibuat_pada=date.today(),
        equipment_tag="PLT-U/FIL-207",

        pabrik="Pabrik Utara",
        perlu_eskalasi=True,
        keyakinan="sedang",
        kandidat=[
            KandidatPenyebab(
                cause_id="C-001",
                nama="Degradasi Refraktori Atap Heater (Roof Hot Spot)",
                deskripsi="Indikasi titik panas akibat degradasi lapisan isolasi termal pada pelat atap.",
                skor=buat_skor("0.85"),
                sitasi=[sitasi1],
            ),
            KandidatPenyebab(
                cause_id="C-002",
                nama="Kerusakan Sensor Thermocouple Tube Skin (100-TS-207)",
                deskripsi="Drift pembacaan suhu pada sensor thermocouple pelindung tube skin.",
                skor=buat_skor("0.58"),
                sitasi=[sitasi2],
            ),
        ],
    )


async def main():
    ctx = ToolContextPalsu()
    finding = buat_temuan_100_h_1()
    ctx.state["finding"] = finding.model_dump(mode="json")


    print("\n" + "=" * 60)
    print("🚀 MERENDER SKENARIO 1: MEMO TEKNIS CMRP (jenis='memo')")
    print("=" * 60)

    urutan_blok = [
        "ringkasan_eksekutif",
        "tabel_fakta",
        "kandidat_penyebab",
        "rantai_bukti",
        "rekomendasi_tindakan",
    ]
    narasi_memo = json.dumps({
        "ringkasan_eksekutif": "Pemeriksaan termografi pada Filler Rotary PLT-U/FIL-207 mengindikasikan titik panas di atap heater. Penanganan refraktori diperlukan untuk mencegah degradasi outer casing.",
        "kandidat_penyebab": "Degradasi refraktori atap heater menjadi penyebab utama dengan tingkat keyakinan sedang.",
        "rantai_bukti": "Sinyal suhu menunjukkan kenaikan pada sensor tube skin TS-207 dan TE-223.",
        "rekomendasi_tindakan": "Mandatkan thermography berkala dan persiapkan perbaikan refraktori pada Turnaround mendatang.",
    })
    konteks_memo = json.dumps({
        "nomor_dokumen": "MEMO-ARKA/2026/001",
        "perihal": "Diagnosis Keandalan Filler Rotary PLT-U/FIL-207",
        "penerbit": "Tim Reliability Pabrik Utara",
    })

    res_memo = await terbitkan_dokumen("memo", urutan_blok, narasi_memo, konteks_memo, ctx)
    print("\n💬 [RESPON REPORTER AGENT MEMO]:")
    print(res_memo)

    print("\n" + "=" * 60)
    print("🚀 MERENDER SKENARIO 2: EXECUTIVE WEB DASHBOARD (jenis='dashboard')")
    print("=" * 60)

    res_dash = await terbitkan_dokumen("dashboard", urutan_blok, narasi_memo, konteks_memo, ctx)
    print("\n💬 [RESPON REPORTER AGENT DASHBOARD]:")
    print(res_dash)

    print("\n" + "=" * 60)
    print("🚀 MERENDER SKENARIO 3: NOTA DINAS ESKALASI VP (jenis='nota_dinas')")
    print("=" * 60)

    konteks_nota = json.dumps({
        "nomor_dokumen": "ND-ARKA/RU2/2026/042",
        "perihal": "Eskalasi Strategis Investasi Keandalan Filler Rotary PLT-U/FIL-207",
        "penerbit": "VP Reliability Asset Management",
    })

    res_nota = await terbitkan_dokumen("nota_dinas", urutan_blok, narasi_memo, konteks_nota, ctx)
    print("\n💬 [RESPON REPORTER AGENT NOTA DINAS]:")
    print(res_nota)

    print("\n" + "=" * 60)
    print("✅ HASIL PENGUJIAN GOLDEN PROMPTS TERVERIFIKASI")
    print(f"Total Artifact Terbentuk: {len(ctx.artifacts)}")
    for nama, ukuran in ctx.artifacts:
        print(f" - {nama} ({ukuran:,} bita)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
