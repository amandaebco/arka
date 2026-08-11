"""Render ketiga jenis dokumen ke `out/`, dari temuan contoh atau dari graph.

Alat waktu-pengembangan: melihat hasil lapisan pelaporan tanpa investigator dan
tanpa memanggil model. Jalankan:

    uv run python scripts/render_contoh.py            # HTML + PDF, nama tetap
    uv run python scripts/render_contoh.py --arsip    # + salinan bertimestamp
    uv run python scripts/render_contoh.py --tanpa-pdf
    uv run python scripts/render_contoh.py --dari-graph              # kasus hidup terkuat
    uv run python scripts/render_contoh.py --dari-graph PLT-U/FIL-207

`--dari-graph` membaca kegagalan yang benar-benar terbuka di penyimpanan aktif,
sehingga angka di dokumen adalah angka yang sama dengan yang dilaporkan rantai.
Tanpa itu, setiap dokumen yang pernah ditunjukkan ke orang lain membawa angka
temuan contoh — mirip, tetapi bukan angka yang sedang dibicarakan.

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
    nomor="001/ING/VIII/2026",
    kepada="Manajer Keandalan — Pabrik Utara",
    dari="ARKA (Asset Reliability Knowledge Agent)",
    perihal="Preseden kegagalan berulang lintas pabrik",
    penanda_tangan="Brigitte Schwartz",
    jabatan_penanda_tangan="Head of Reliability",
    periode="Agustus 2026",
    unit_penerbit="INGOUDE COMPANY",
    logo=lencana_data_uri("ING"),
)



async def render_semua(
    dengan_pdf: bool, dir_arsip: Path | None, dari_graph: str | None | bool = None
) -> None:
    if dari_graph is None:
        temuan = finding_contoh()
        asal = "contoh"
    else:
        from app.detection.temuan_langsung import temuan_untuk

        tag = dari_graph if isinstance(dari_graph, str) else None
        temuan = await temuan_untuk(tag)
        asal = "graph"

    print(f"Temuan {temuan.finding_id} ({asal}) · {len(temuan.semua_sitasi())} sitasi")

    for id_jenis in JENIS:
        html = render_dokumen_html(temuan, jenis=id_jenis, konteks=KONTEKS)
        _simpan(f"{id_jenis}.html", html.encode("utf-8"), dir_arsip)

        if not dengan_pdf or id_jenis == "dashboard":
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
    parser.add_argument(
        "--dari-graph",
        nargs="?",
        const=True,
        default=None,
        metavar="TAG",
        help="Rakit temuan dari kegagalan terbuka di penyimpanan aktif, bukan dari contoh. "
             "Tanpa TAG, dipakai kasus dengan kandidat terkuat",
    )
    argumen = parser.parse_args()

    DIR_KELUARAN.mkdir(exist_ok=True)
    dir_arsip = None
    if argumen.arsip:
        dir_arsip = DIR_KELUARAN / "riwayat" / datetime.now().strftime("%Y%m%d-%H%M%S")
        dir_arsip.mkdir(parents=True, exist_ok=True)

    asyncio.run(
        render_semua(
            dengan_pdf=not argumen.tanpa_pdf,
            dir_arsip=dir_arsip,
            dari_graph=argumen.dari_graph,
        )
    )


if __name__ == "__main__":
    main()
