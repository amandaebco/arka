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
_AKSEN = "#0f365b"


def lencana_svg(inisial: str, warna: str = _AKSEN) -> str:
    """Lencana persegi berisi inisial unit. Sengaja polos — ini bukan merek.

    Args:
        inisial: Satu sampai tiga huruf. Lebih dari itu dipangkas.
        warna: Warna dasar lencana.
    """
    teks = escape(inisial.strip().upper()[:3]) or "?"
    ukuran_huruf = {1: 26, 2: 21, 3: 16}[len(teks)]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" '
        'viewBox="0 0 48 48" role="img">'
        f"<title>Lencana unit {teks}</title>"
        f'<rect width="48" height="48" rx="8" fill="{warna}"/>'
        f'<text x="24" y="24" fill="#ffffff" font-size="{ukuran_huruf}" '
        'font-family="Helvetica Neue, Helvetica, Arial, sans-serif" '
        'font-weight="700" letter-spacing="1" text-anchor="middle" '
        f'dominant-baseline="central">{teks}</text></svg>'
    )


def lencana_data_uri(inisial: str, warna: str = _AKSEN) -> str:
    """Lencana siap pakai untuk `KonteksDokumen.logo`."""
    svg = lencana_svg(inisial, warna)
    sandi = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{sandi}"
