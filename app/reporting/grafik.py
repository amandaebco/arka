"""Grafik dokumen — SVG inline yang dirakit deterministik dari `Finding`.

Grafik masuk wilayah yang sama dengan angka: **dirender dari data, tidak pernah
dari model**. Model boleh memutuskan blok mana yang tampil; ia tidak punya jalur
untuk menggeser satu batang pun.

SVG inline dipilih dengan sengaja:

* tidak ada pustaka grafik, tidak ada berkas gambar, tidak ada permintaan jaringan
* ikut tercetak rapi ke PDF lewat Playwright karena ia teks biasa, bukan raster
* skalanya mengikuti lebar halaman tanpa kehilangan ketajaman

Setiap grafik memuat `<title>` supaya pembaca layar tetap mendapat isinya, dan
setiap batang tetap didampingi angkanya — grafik melengkapi tabel, bukan
menggantikannya.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

from app.reporting.finding import Finding

# Ambang dari mekanisme deteksi (CLAUDE.md). Digambar sebagai garis acuan
# supaya pembaca melihat posisi kandidat terhadap keputusan, bukan cuma
# panjang batang relatif satu sama lain.
AMBANG_LAPOR = Decimal("0.65")
AMBANG_ABAIKAN = Decimal("0.50")

# Palet ditahan seminimal mungkin: satu warna aksen, sisanya netral. Dokumen ini
# dicetak hitam-putih di lapangan, jadi perbedaan harus tetap terbaca lewat
# posisi dan panjang, bukan semata warna.
_AKSEN = "#1f4e79"
_AKSEN_MUDA = "#9db8d2"
_NETRAL = "#c9ced6"
_GARIS = "#8a919b"
_TEKS = "#2b2f36"

_LEBAR = 640
_PAD_KIRI = 210
_PAD_KANAN = 56
_TINGGI_BARIS = 26


def _x(nilai: Decimal | float, lebar_plot: int) -> float:
    """Petakan skor 0..1 ke koordinat mendatar."""
    return _PAD_KIRI + float(nilai) * lebar_plot


def _potong(teks: str, batas: int = 34) -> str:
    return teks if len(teks) <= batas else teks[: batas - 1] + "…"


def _angka(nilai: Decimal | float, digit: int = 2) -> str:
    return f"{float(nilai):.{digit}f}".replace(".", ",")


def grafik_kandidat(finding: Finding) -> str | None:
    """Batang skor total tiap kandidat, dengan garis ambang lapor dan abaikan.

    Inilah grafik yang paling menjelaskan keputusan ARKA: pembaca langsung
    melihat kandidat mana yang melewati ambang dan seberapa ketat persaingannya.
    """
    kandidat = finding.kandidat_terurut
    if not kandidat:
        return None

    lebar_plot = _LEBAR - _PAD_KIRI - _PAD_KANAN
    tinggi = _TINGGI_BARIS * len(kandidat) + 46
    bagian: list[str] = []

    for garis, label in ((AMBANG_ABAIKAN, "abaikan"), (AMBANG_LAPOR, "lapor")):
        px = _x(garis, lebar_plot)
        bagian.append(
            f'<line x1="{px:.1f}" y1="14" x2="{px:.1f}" y2="{tinggi - 22}" '
            f'stroke="{_GARIS}" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{px:.1f}" y="{tinggi - 8}" fill="{_GARIS}" font-size="10" '
            f'text-anchor="middle">{label} {_angka(garis)}</text>'
        )

    for i, k in enumerate(kandidat):
        y = 20 + i * _TINGGI_BARIS
        panjang = float(k.skor.total) * lebar_plot
        warna = _AKSEN if i == 0 else _AKSEN_MUDA
        bagian.append(
            f'<text x="{_PAD_KIRI - 10}" y="{y + 11}" fill="{_TEKS}" font-size="11" '
            f'text-anchor="end">{escape(_potong(k.nama))}</text>'
            f'<rect x="{_PAD_KIRI}" y="{y}" width="{panjang:.1f}" height="15" '
            f'fill="{warna}" rx="2"/>'
            f'<text x="{_PAD_KIRI + panjang + 6:.1f}" y="{y + 11}" fill="{_TEKS}" '
            f'font-size="11">{_angka(k.skor.total)}</text>'
        )

    judul = "Skor kandidat penyebab terhadap ambang keputusan"
    return _bungkus(judul, tinggi, "".join(bagian))


def grafik_kekritisan(finding: Finding) -> str | None:
    """Kekritisan master data versus perhitungan ARKA, per sparepart.

    Dibaca sebagai jarak, bukan dua batang terpisah: yang bernilai memang
    selisihnya, bukan nilai mutlaknya.
    """
    sparepart = sorted(finding.sparepart, key=lambda s: s.selisih, reverse=True)
    if not sparepart:
        return None

    lebar_plot = _LEBAR - _PAD_KIRI - _PAD_KANAN
    tinggi = _TINGGI_BARIS * len(sparepart) + 46
    bagian: list[str] = []

    for i, s in enumerate(sparepart):
        y = 20 + i * _TINGGI_BARIS
        x_master = _x(s.static_criticality, lebar_plot)
        x_arka = _x(s.criticality, lebar_plot)
        bagian.append(
            f'<text x="{_PAD_KIRI - 10}" y="{y + 11}" fill="{_TEKS}" font-size="11" '
            f'text-anchor="end">{escape(_potong(s.nama))}</text>'
            f'<line x1="{x_master:.1f}" y1="{y + 7}" x2="{x_arka:.1f}" y2="{y + 7}" '
            f'stroke="{_NETRAL}" stroke-width="3"/>'
            f'<circle cx="{x_master:.1f}" cy="{y + 7}" r="4" fill="{_NETRAL}" '
            f'stroke="{_GARIS}"/>'
            f'<circle cx="{x_arka:.1f}" cy="{y + 7}" r="4.5" fill="{_AKSEN}"/>'
            f'<text x="{max(x_master, x_arka) + 8:.1f}" y="{y + 11}" fill="{_TEKS}" '
            f'font-size="11">{_angka(s.selisih)}</text>'
        )

    bagian.append(
        f'<circle cx="{_PAD_KIRI + 4}" cy="{tinggi - 12}" r="4" fill="{_NETRAL}" '
        f'stroke="{_GARIS}"/>'
        f'<text x="{_PAD_KIRI + 14}" y="{tinggi - 8}" fill="{_GARIS}" font-size="10">'
        f"master data</text>"
        f'<circle cx="{_PAD_KIRI + 100}" cy="{tinggi - 12}" r="4.5" fill="{_AKSEN}"/>'
        f'<text x="{_PAD_KIRI + 110}" y="{tinggi - 8}" fill="{_GARIS}" font-size="10">'
        f"perhitungan ARKA</text>"
    )

    judul = "Kekritisan sparepart: master data versus perhitungan ARKA"
    return _bungkus(judul, tinggi, "".join(bagian))


def grafik_preseden(finding: Finding) -> str | None:
    """Sebaran preseden pada sumbu waktu, ditandai pabriknya.

    Menjawab pertanyaan yang paling sering muncul di ruang rapat: apakah ini
    kejadian tunggal atau pola yang sudah berulang di tempat lain.
    """
    preseden = sorted(finding.preseden, key=lambda p: p.tanggal_kejadian)
    if len(preseden) < 2:
        return None

    awal = preseden[0].tanggal_kejadian
    akhir = finding.dibuat_pada
    rentang = max((akhir - awal).days, 1)

    lebar_plot = _LEBAR - _PAD_KIRI - _PAD_KANAN
    kiri = 100
    sumbu_y = 68
    bagian: list[str] = [
        f'<line x1="{kiri}" y1="{sumbu_y}" x2="{kiri + lebar_plot}" y2="{sumbu_y}" '
        f'stroke="{_GARIS}" stroke-width="1"/>'
    ]

    # Kejadian yang berdekatan tanggalnya membuat labelnya bertumpuk. Label
    # dinaikkan bergantian ke tingkat kedua, dengan garis penghubung ke titiknya
    # supaya tetap jelas label itu milik siapa. Mengecilkan huruf bukan jalan
    # keluar — dokumen ini dibaca di lapangan, sering hasil cetakan.
    titik = [
        (kiri + ((p.tanggal_kejadian - awal).days / rentang) * lebar_plot, p) for p in preseden
    ]
    tingkat: list[int] = []
    x_terpakai: list[float] = []
    for px, p in titik:
        lebar_label = len(_potong(p.pabrik, 16)) * 5.4
        naik = any(
            abs(px - x_lain) < (lebar_label + lebar_lain) / 2 + 4
            for x_lain, lebar_lain in x_terpakai
        )
        tingkat.append(1 if naik else 0)
        if not naik:
            x_terpakai.append((px, lebar_label))

    for (px, p), lapis in zip(titik, tingkat, strict=True):
        y_label = sumbu_y - 12 - lapis * 14
        penghubung = (
            f'<line x1="{px:.1f}" y1="{sumbu_y - 7}" x2="{px:.1f}" y2="{y_label + 3}" '
            f'stroke="{_NETRAL}" stroke-width="1"/>'
            if lapis
            else ""
        )
        bagian.append(
            f'{penghubung}'
            f'<circle cx="{px:.1f}" cy="{sumbu_y}" r="5" fill="{_AKSEN_MUDA}" '
            f'stroke="{_AKSEN}"/>'
            f'<text x="{px:.1f}" y="{y_label}" fill="{_TEKS}" font-size="10" '
            f'text-anchor="middle">{escape(_potong(p.pabrik, 16))}</text>'
            f'<text x="{px:.1f}" y="{sumbu_y + 20}" fill="{_GARIS}" font-size="9" '
            f'text-anchor="middle">{p.tanggal_kejadian.strftime("%m/%y")}</text>'
        )

    tinggi = sumbu_y + 42

    # Kasus yang sedang diselidiki ditaruh di ujung kanan sebagai pembanding.
    px = kiri + lebar_plot
    bagian.append(
        f'<circle cx="{px:.1f}" cy="{sumbu_y}" r="6" fill="{_AKSEN}"/>'
        f'<text x="{px:.1f}" y="{sumbu_y - 12}" fill="{_TEKS}" font-size="10" '
        f'text-anchor="end" font-weight="600">sekarang</text>'
    )

    judul = "Sebaran preseden lintas pabrik pada sumbu waktu"
    return _bungkus(judul, tinggi, "".join(bagian))


def _bungkus(judul: str, tinggi: int, isi: str) -> str:
    """Bungkus potongan SVG menjadi gambar utuh yang bisa dibaca pembaca layar."""
    return (
        f'<figure class="grafik">'
        f'<svg viewBox="0 0 {_LEBAR} {tinggi}" width="100%" '
        f'role="img" aria-label="{escape(judul)}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"<title>{escape(judul)}</title>{isi}</svg>"
        f"<figcaption>{escape(judul)}</figcaption>"
        f"</figure>"
    )


# Peta blok → pembuat grafiknya. Blok yang tidak tercantum memang tidak
# bergrafik; menambahkannya cukup satu baris di sini.
PEMBUAT_GRAFIK = {
    "kandidat_penyebab": grafik_kandidat,
    "sparepart_kritis": grafik_kekritisan,
    "preseden_lintas_pabrik": grafik_preseden,
}


def grafik_untuk(id_blok: str, finding: Finding) -> str | None:
    """Grafik untuk satu blok, atau None bila blok itu tidak bergrafik."""
    pembuat = PEMBUAT_GRAFIK.get(id_blok)
    return pembuat(finding) if pembuat else None
