"""Uji alur pembuatan Dashboard Report dengan skenario prompt contoh."""

from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path

from google.adk.tools.tool_context import ToolContext

from app.agents.reporter import (
    KUNCI_TEMUAN,
    terbitkan_dokumen,
)
from app.reporting.dokumen import KonteksDokumen
from app.reporting.lencana import lencana_data_uri
from app.synthetic.finding_contoh import finding_contoh


class ContextPalsu:
    """Context tiruan ADK untuk menguji pembuatan dashboard."""

    def __init__(self, finding_obj):
        self.state = {
            KUNCI_TEMUAN: finding_obj.model_dump(mode="json"),
        }
        self.artifacts = {}


    async def save_artifact(self, filename: str, artifact) -> None:
        self.artifacts[filename] = artifact
        out_dir = Path(__file__).resolve().parent.parent / "out"
        out_dir.mkdir(exist_ok=True)
        target = out_dir / filename
        if hasattr(artifact, "inline_data") and artifact.inline_data:
            target.write_bytes(artifact.inline_data.data)
        elif isinstance(artifact, bytes):
            target.write_bytes(artifact)


async def simulasikan_prompt(nomor_skenario: int, prompt_user: str, finding_obj, konteks_obj):
    print(f"\n==================================================")
    print(f"📌 SKENARIO PROMPT {nomor_skenario}:")
    print(f'   "{prompt_user}"')
    print(f"==================================================")

    ctx = ContextPalsu(finding_obj)

    # Memanggil terbitkan_dokumen dengan jenis "infografis"
    hasil = await terbitkan_dokumen(
        jenis_dokumen="dashboard",

        urutan_blok=[],
        narasi_json='{"ringkasan": "Terdeteksi indikasi degradasi komponen yang memerlukan tindakan."}',
        konteks_json=konteks_obj.model_dump_json(),
        tool_context=ctx,
    )

    print("\n💬 [RESPON REPORTER AGENT KE CHAT UI]:")
    print(hasil)

    print("\n📁 [ARTIKEL DIBANGKITKAN]:")
    for nama_file in ctx.artifacts:
        print(f"   -> out/{nama_file}")


async def main():
    # Skenario 1: Air Preheater PLT-U/FIL-207 Pabrik Utara (Perlu Eskalasi)
    finding_1 = finding_contoh()  # ARKA-2026-0042 (perlu eskalasi)
    konteks_1 = KonteksDokumen(
        nomor="001/ING/VIII/2026",
        unit_penerbit="INGOUDE COMPANY",
        logo=lencana_data_uri("ING"),
        penanda_tangan="Brigitte Schwartz",
        jabatan_penanda_tangan="Head of Reliability",
    )

    # Skenario 2: Centrifugal Pump P-102 Pabrik Selatan (Verified Otomatis)
    finding_2 = finding_contoh().model_copy(
        update={
            "finding_id": "ARKA-2026-0088",
            "equipment_tag": "PUMP-201",
            "pabrik": "Pabrik Selatan",
            "perlu_eskalasi": False,
        }
    )

    konteks_2 = KonteksDokumen(
        nomor="002/ING/VIII/2026",
        unit_penerbit="INGOUDE COMPANY",
        logo=lencana_data_uri("ING"),
        penanda_tangan="Brigitte Schwartz",
        jabatan_penanda_tangan="Head of Reliability",
    )

    await simulasikan_prompt(
        1,
        "Buatkan dashboard infografis keandalan eksekutif untuk Air Preheater PLT-U/FIL-207 di Pabrik Utara",
        finding_1,
        konteks_1,
    )

    await simulasikan_prompt(
        2,
        "Saya butuh dashboard tampilan visual interaktif untuk penanganan pompa sentrifugal PUMP-201 di Pabrik Selatan",
        finding_2,
        konteks_2,
    )


if __name__ == "__main__":
    asyncio.run(main())
