"""Lencana unit penerbit — dibangkitkan, bukan aset yang disimpan di repo.

ARKA tidak menyimpan logo siapa pun. Yang ada di sini hanyalah kemampuan
membangkitkan lencana sederhana dari inisial, supaya dokumen demo punya kop
yang wajar tanpa perlu menempelkan merek organisasi nyata — lihat Batasan
Mutlak di CLAUDE.md.

Keluarannya data URI, bukan berkas atau tautan. Alasannya teknis sekaligus
prinsipil: Chromium merender kop halaman PDF di konteks terpisah yang tidak
selalu memuat sumber luar, dan di Agent Engine nanti tidak ada jaminan akses
jaringan sama sekali. Dokumen harus berdiri sendiri.
"""

from __future__ import annotations

import base64
from html import escape

# Selaras dengan --aksen pada memo.css. Ditulis ulang di sini karena SVG
# tidak ikut mewarisi custom property dokumen induknya.
_AKSEN = "#003554"
_TEAL = "#028090"


def lencana_svg(inisial: str = "ING", warna: str = _TEAL) -> str:
    """Lencana logo vektor geometri modern fiktif untuk Ingoude Company / ARKA.

    Args:
        inisial: Inisial unit atau perusahaan.
        warna: Warna utama lencana.
    """
    mentah = inisial.strip()
    if not mentah:
        teks = "?"
    else:
        teks = escape(mentah.upper()[:3])

    if teks in ("ING", "IC", "UKA"):
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" '
            'viewBox="0 0 52 52" role="img">'
            f'<title>Logo {teks}</title>'
            '<defs>'
            '<linearGradient id="ingGrad1" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'<stop offset="0%" stop-color="{warna}"/>'
            '<stop offset="50%" stop-color="#003554"/>'
            '<stop offset="100%" stop-color="#00a896"/>'
            '</linearGradient>'
            '<linearGradient id="ingGrad2" x1="100%" y1="0%" x2="0%" y2="100%">'
            '<stop offset="0%" stop-color="#38bdf8"/>'
            '<stop offset="100%" stop-color="#028090"/>'
            '</linearGradient>'
            '</defs>'
            '<polygon points="26,3 46,14.5 46,37.5 26,49 6,37.5 6,14.5" '
            'fill="none" stroke="url(#ingGrad1)" stroke-width="3.5"/>'
            '<path d="M 18,19 L 26,14 L 34,19 L 34,31 L 26,36 L 18,31 Z" '
            'fill="none" stroke="url(#ingGrad2)" stroke-width="2.5"/>'
            '<circle cx="26" cy="25" r="5" fill="url(#ingGrad1)"/>'
            '<circle cx="26" cy="25" r="2" fill="#ffffff"/>'
            '</svg>'
        )






    ukuran_huruf = {1: 26, 2: 21, 3: 16}[len(teks)]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" '
        'viewBox="0 0 48 48" role="img">'
        f"<title>Lencana unit {teks}</title>"
        f'<rect width="48" height="48" rx="10" fill="{warna}"/>'
        f'<text x="24" y="24" fill="#ffffff" font-size="{ukuran_huruf}" '
        'font-family="Plus Jakarta Sans, sans-serif" '
        'font-weight="700" letter-spacing="1" text-anchor="middle" '
        f'dominant-baseline="central">{teks}</text></svg>'
    )


def lencana_data_uri(inisial: str = "ING", warna: str = _TEAL) -> str:
    """Lencana siap pakai untuk `KonteksDokumen.logo`."""
    svg = lencana_svg(inisial, warna)
    sandi = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{sandi}"

