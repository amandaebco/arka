"""Render ketiga jenis dokumen dari temuan contoh ke `out/`.

Alat waktu-pengembangan: melihat hasil lapisan pelaporan tanpa DB, tanpa
investigator, dan tanpa memanggil model. Jalankan:

    uv run python scripts/render_contoh.py            # HTML + PDF, nama tetap
    uv run python scripts/render_contoh.py --arsip    # + salinan bertimestamp
    uv run python scripts/render_contoh.py --tanpa-pdf

Nama berkas utama sengaja tetap (`out/memo.html`): tautan di IDE tidak basi dan
perintah di dokumentasi tidak berubah. Render bersifat deterministik, jadi
salinan bertimestamp hanya berguna ketika memang sedang membandingkan versi —
karena itu ia opsional, bukan bawaan.
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from app.reporting.dokumen import JENIS, KonteksDokumen
from app.reporting.lencana import lencana_data_uri
from app.reporting.memo import render_dokumen_html, render_dokumen_pdf
from app.synthetic.finding_contoh import finding_contoh

DIR_KELUARAN = Path(__file__).resolve().parent.parent / "out"

KONTEKS = KonteksDokumen(
    nomor="001/ARKA/VIII/2026",
    kepada="Manajer Keandalan — Pabrik Utara",
    dari="ARKA (Asset Reliability Knowledge Agent)",
    perihal="Preseden kegagalan berulang lintas pabrik",
    penanda_tangan="Kepala Unit Keandalan",
    jabatan_penanda_tangan="Reliability Lead",
    periode="Agustus 2026",
    # Unit fiktif. Tidak ada merek organisasi nyata yang tersimpan di repo —
    # lencananya dibangkitkan dari inisial saat render.
    unit_penerbit="Unit Keandalan Aset",
    logo=lencana_data_uri("UKA"),
)


async def render_semua(dengan_pdf: bool, dir_arsip: Path | None) -> None:
    temuan = finding_contoh()
    print(f"Temuan {temuan.finding_id} · {len(temuan.semua_sitasi())} sitasi")

    for id_jenis in JENIS:
        html = render_dokumen_html(temuan, jenis=id_jenis, konteks=KONTEKS)
        _simpan(f"{id_jenis}.html", html.encode("utf-8"), dir_arsip)

        if not dengan_pdf:
            continue
        try:
            pdf = await render_dokumen_pdf(temuan, jenis=id_jenis, konteks=KONTEKS)
        except Exception as exc:  # noqa: BLE001 — peramban belum terpasang bukan kegagalan
            print(f"  {id_jenis:12} PDF dilewati ({type(exc).__name__}) — jalankan "
                  "`playwright install chromium`")
            continue
        _simpan(f"{id_jenis}.pdf", pdf, dir_arsip)

    if dir_arsip:
        print(f"  arsip        ->  {dir_arsip}")


def _simpan(nama: str, isi: bytes, dir_arsip: Path | None) -> None:
    """Tulis berkas utama, lalu salin ke arsip bila diminta."""
    berkas = DIR_KELUARAN / nama
    berkas.write_bytes(isi)
    print(f"  {nama:20} {len(isi):8,} byte  ->  {berkas}")
    if dir_arsip:
        (dir_arsip / nama).write_bytes(isi)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render dokumen contoh ARKA")
    parser.add_argument(
        "--arsip",
        action="store_true",
        help="Simpan juga salinan lengkap (HTML dan PDF) di out/riwayat/<timestamp>/",
    )
    parser.add_argument(
        "--tanpa-pdf",
        action="store_true",
        help="Lewati render PDF — lebih cepat saat menyetel template",
    )
    argumen = parser.parse_args()

    DIR_KELUARAN.mkdir(exist_ok=True)
    dir_arsip = None
    if argumen.arsip:
        dir_arsip = DIR_KELUARAN / "riwayat" / datetime.now().strftime("%Y%m%d-%H%M%S")
        dir_arsip.mkdir(parents=True, exist_ok=True)

    asyncio.run(render_semua(dengan_pdf=not argumen.tanpa_pdf, dir_arsip=dir_arsip))


if __name__ == "__main__":
    main()
