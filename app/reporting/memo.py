"""Renderer dokumen — `Finding` menjadi HTML, lalu PDF.

HTML adalah bentuk utama: bisa dirender tanpa dependensi peramban, dipakai
pengujian, dan menjadi masukan bagi PDF. PDF memakai Playwright agar tata
letak cetak identik dengan yang tampil di layar.

Jenis dokumen (memo, nota dinas, laporan) hanya menukar template chrome.
Isi, angka, dan sitasi dirakit lewat jalur yang sama untuk ketiganya —
lihat `app.reporting.dokumen`.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reporting.blocks import Blok, pilih_blok, susun_blok
from app.reporting.dokumen import JenisDokumen, KonteksDokumen, ambil_jenis
from app.reporting.finding import Finding

_DIR_TEMPLATE = Path(__file__).parent / "templates"


class DokumenTanpaSitasi(ValueError):
    """Penerbitan ditolak karena temuan tidak memuat satu pun sitasi.

    Keterlacakan adalah prinsip non-negotiable: dokumen yang klaimnya tidak dapat
    dirunut ke sumber lebih berbahaya daripada tidak ada dokumen sama sekali.
    """

_BULAN = (
    "",
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)


def _filter_angka(nilai: Decimal | float | None, digit: int = 2, tanda: bool = False) -> str:
    """Format angka gaya Indonesia (koma desimal).

    Dipakai untuk semua nilai numerik di dokumen agar tidak ada satu pun angka
    yang melewati model bahasa.
    """
    if nilai is None:
        return "—"
    hasil = f"{Decimal(str(nilai)):.{digit}f}".replace(".", ",")
    if tanda and Decimal(str(nilai)) > 0:
        hasil = f"+{hasil}"
    return hasil


def _filter_tanggal(nilai) -> str:
    if nilai is None:
        return "—"
    return f"{nilai.day} {_BULAN[nilai.month]} {nilai.year}"


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_DIR_TEMPLATE),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["angka"] = _filter_angka
    env.filters["tanggal"] = _filter_tanggal
    return env


def render_dokumen_html(
    finding: Finding,
    jenis: str | JenisDokumen | None = None,
    urutan_blok: list[str] | None = None,
    narasi: dict[str, str] | None = None,
    konteks: KonteksDokumen | None = None,
    sematkan_gaya: bool = True,
) -> str:
    """Render satu jenis dokumen menjadi HTML utuh.

    Raises:
        DokumenTanpaSitasi: Bila temuan tidak memuat satu pun sitasi.

    Args:
        finding: Temuan dari investigator.
        jenis: Id jenis ("memo", "nota_dinas", "laporan") atau objeknya.
            Nilai asing mundur ke memo.
        urutan_blok: Usulan urutan blok dari reporter. Bila kosong, dipakai
            urutan bawaan jenis dokumen tersebut.
        narasi: Narasi per blok dari reporter, dipetakan dengan id blok.
        konteks: Kelengkapan surat (nomor, kepada, dari, tanda tangan).
        sematkan_gaya: Sisipkan CSS inline agar berkas berdiri sendiri.
    """
    if not finding.semua_sitasi():
        raise DokumenTanpaSitasi(
            f"Temuan {finding.finding_id} tidak memuat sitasi — dokumen tidak diterbitkan."
        )

    jenis_dok = jenis if isinstance(jenis, JenisDokumen) else ambil_jenis(jenis)
    urutan = urutan_blok or list(jenis_dok.urutan_bawaan)
    terpilih: list[Blok] = pilih_blok(susun_blok(finding), urutan, narasi)

    env = _environment()
    isi = env.get_template(jenis_dok.berkas_template).render(
        finding=finding,
        blok_terpilih=terpilih,
        konteks=konteks or KonteksDokumen(),
        jenis=jenis_dok,
        urutan_blok=urutan,
        narasi=narasi or {},
    )

    if jenis_dok.id == "dashboard" or not sematkan_gaya:
        return isi


    gaya = (_DIR_TEMPLATE / "memo.css").read_text(encoding="utf-8")
    return (
        "<!doctype html><html lang='id'><head><meta charset='utf-8'>"
        f"<title>{jenis_dok.label} ARKA — {finding.finding_id}</title>"
        f"<style>{gaya}</style></head><body>{isi}</body></html>"
    )


def render_memo_html(
    finding: Finding,
    urutan_blok: list[str] | None = None,
    narasi: dict[str, str] | None = None,
    sematkan_gaya: bool = True,
) -> str:
    """Render memo. Pintasan `render_dokumen_html` untuk jenis bawaan."""
    return render_dokumen_html(
        finding,
        jenis="memo",
        urutan_blok=urutan_blok,
        narasi=narasi,
        sematkan_gaya=sematkan_gaya,
    )


_GAYA_TEPI = (
    "font-size:7.5pt;font-family:Inter,-apple-system,BlinkMacSystemFont,"
    "'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#475569;width:100%;"
    "padding:0 14mm;display:flex;justify-content:space-between;align-items:center;"
    "font-weight:600;"
)


def _kepala_halaman(jenis: JenisDokumen, finding: Finding) -> str:
    """Kepala halaman kosong — header utama ada di HTML Kop."""
    return '<div style="font-size:0px;"></div>'


def _kaki_halaman(finding: Finding) -> str:
    """Kaki halaman berulang di margin bawah PDF: nomor halaman resmi."""
    fid = finding.finding_id
    return (
        f'<div style="{_GAYA_TEPI}border-top:1px solid #cbd5e1;'
        'padding-top:4px;width:100%;">'
        '<span style="font-size:7pt;color:#64748b;letter-spacing:0.04em;">'
        'CONFIDENTIAL · INTERNAL USE ONLY</span>'
        '<span style="font-size:7.5pt;color:#028090;font-weight:700;">'
        f'INGOUDE COMPANY · {fid}</span>'
        '<span style="font-size:7.5pt;color:#003554;font-weight:700;">'
        'Halaman <span class="pageNumber"></span> '
        'dari <span class="totalPages"></span></span></div>'
    )





async def render_dokumen_pdf(
    finding: Finding,
    jenis: str | JenisDokumen | None = None,
    urutan_blok: list[str] | None = None,
    narasi: dict[str, str] | None = None,
    konteks: KonteksDokumen | None = None,
) -> bytes:
    """Render dokumen menjadi PDF A4 lewat Playwright.

    Membutuhkan `playwright install chromium`. Bila peramban belum terpasang,
    galat dibiarkan naik — pemanggil yang memutuskan mundur ke HTML.
    """
    from playwright.async_api import async_playwright

    jenis_dok = jenis if isinstance(jenis, JenisDokumen) else ambil_jenis(jenis)
    html = render_dokumen_html(finding, jenis_dok, urutan_blok, narasi, konteks)
    async with async_playwright() as p:
        peramban = await p.chromium.launch()
        try:
            halaman = await peramban.new_page()
            await halaman.set_content(html, wait_until="load")
            return await halaman.pdf(
                format="A4",
                print_background=True,
                margin={"top": "12mm", "bottom": "18mm", "left": "12mm", "right": "12mm"},
                display_header_footer=True,
                header_template=_kepala_halaman(jenis_dok, finding),
                footer_template=_kaki_halaman(finding),
            )
        finally:
            await peramban.close()



async def render_memo_pdf(
    finding: Finding,
    urutan_blok: list[str] | None = None,
    narasi: dict[str, str] | None = None,
) -> bytes:
    """Render memo sebagai PDF. Pintasan `render_dokumen_pdf`."""
    return await render_dokumen_pdf(finding, "memo", urutan_blok, narasi)
