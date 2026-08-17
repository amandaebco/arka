"""Poster sebagai HTML — susunannya diputuskan designer, isinya dirakit kode.

Jalur ini menggantikan penggambaran oleh model untuk pemakaian sehari-hari, dan
perbedaannya bukan soal selera:

* **Teksnya persis.** Uji 17 Agustus pada jalur gambar menemukan nomor sparepart
  tertulis `SP-RFB-SEAL-02` alih-alih `SP-RF8-SEAL-02`, dan lead time berubah
  dari dua minggu jadi tiga. Halaman yang dirender tidak bisa salah mengeja apa
  yang diberikan kepadanya.
* **Prinsip I berlaku penuh.** Kelonggaran Constitution 1.2.0 ada semata-mata
  karena penggambaran diserahkan ke model. Di sini tidak ada yang perlu
  dikecualikan.
* **Dua detik, bukan dua setengah menit**, dan tanpa biaya per halaman.

Yang tetap milik model: `PresentationSpec` — urutan kartu, penekanannya, dan
bentuk visual tiap blok. Susunan halaman benar-benar berubah antar temuan dan
antar persona; yang tidak pernah berubah adalah dari mana angkanya datang.

Pola yang belum punya makro jatuh ke kartu daftar biasa. Itu disengaja: kartu
sederhana yang benar lebih baik daripada bentuk mengesankan yang memaksa data
mengisi medan yang tidak ada.
"""

from __future__ import annotations

from html import escape

from app.designer.content import CanvasItem

# Lebar kolom menurut penekanan, pada grid dua belas kolom.
RENTANG = {"dominant": 12, "primary": 6, "secondary": 4, "tertiary": 3}

# Warna menurut derajat, dipakai lencana dan garis tepi kartu.
DERAJAT = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "medium": "#d97706",
    "low": "#0284c7",
    "info": "#0284c7",
    "segera": "#dc2626",
    "terjadwal": "#d97706",
    "pantau": "#0284c7",
}


def _warna(level: str) -> str:
    return DERAJAT.get((level or "").strip().lower(), "#334155")


def _teks(item: CanvasItem) -> str:
    return escape(item.text or item.label or "")


def _kpi_cards(items: list[CanvasItem]) -> str:
    sel = []
    for i in items[:4]:
        nilai = escape(i.value or i.quantity or "")
        sel.append(
            f'<div class="kpi"><div class="kpi-nilai">{nilai}</div>'
            f'<div class="kpi-label">{escape(i.label or i.text)}</div>'
            + (f'<div class="kpi-sub">{escape(i.value_label)}</div>' if i.value_label else "")
            + "</div>"
        )
    return f'<div class="kpi-baris">{"".join(sel)}</div>'


def _comparison(items: list[CanvasItem]) -> str:
    """Nilai berdampingan dengan pembandingnya — selisihnya yang jadi isi."""
    baris = []
    for i in items[:5]:
        if not i.reference:
            continue
        baris.append(
            '<div class="banding">'
            f'<div class="banding-label">{escape(i.label or i.text)}</div>'
            f'<div class="banding-nilai">{escape(i.value)}'
            f'<span class="banding-satuan">{escape(i.value_label)}</span></div>'
            f'<div class="banding-acuan">{escape(i.reference)}'
            f'<span class="banding-satuan">{escape(i.reference_label)}</span></div>'
            "</div>"
        )
    return "".join(baris) or _daftar(items)


def _priority_actions(items: list[CanvasItem]) -> str:
    baris = []
    for n, i in enumerate(items[:6], start=1):
        warna = _warna(i.level)
        baris.append(
            f'<div class="aksi" style="border-left-color:{warna}">'
            '<div class="aksi-kepala">'
            f'<span class="aksi-nomor" style="background:{warna}">P{n}</span>'
            + (f'<span class="aksi-horizon">{escape(i.horizon)}</span>' if i.horizon else "")
            + "</div>"
            f'<div class="aksi-teks">{_teks(i)}</div>'
            + (f'<div class="aksi-owner">{escape(i.owner)}</div>' if i.owner else "")
            + "</div>"
        )
    return f'<div class="aksi-baris">{"".join(baris)}</div>'


def _labelled_findings(items: list[CanvasItem]) -> str:
    baris = []
    for i in items[:8]:
        baris.append(
            '<div class="temuan">'
            + (f'<span class="temuan-label">{escape(i.label)}</span>' if i.label else "")
            + f"<span>{escape(i.text)}</span>"
            + (f'<span class="temuan-tanggal">{escape(i.date)}</span>' if i.date else "")
            + "</div>"
        )
    return "".join(baris)


def _bucket_distribution(items: list[CanvasItem]) -> str:
    """Batang mendatar. Panjangnya sebanding nilainya, dan angkanya tetap tertulis."""
    angka = []
    for i in items:
        try:
            angka.append(float((i.quantity or i.value or "0").replace(",", ".")))
        except ValueError:
            angka.append(0.0)
    puncak = max(angka) if angka and max(angka) > 0 else 1.0

    baris = []
    for i, n in list(zip(items, angka, strict=True))[:6]:
        lebar = max(4, round(n / puncak * 100))
        baris.append(
            '<div class="bar-baris">'
            f'<div class="bar-label">{escape(i.label or i.text)}</div>'
            f'<div class="bar-jalur"><div class="bar-isi" style="width:{lebar}%"></div></div>'
            f'<div class="bar-nilai">{escape(i.quantity or i.value)}'
            f'<span class="banding-satuan">{escape(i.value_label)}</span></div>'
            "</div>"
        )
    return "".join(baris)


def _focus_statement(items: list[CanvasItem]) -> str:
    utama = items[0] if items else None
    if not utama:
        return ""
    sisa = "".join(f"<li>{_teks(i)}</li>" for i in items[1:4])
    return (
        f'<div class="fokus">{_teks(utama)}</div>'
        + (f'<ul class="fokus-sisa">{sisa}</ul>' if sisa else "")
    )


def _daftar(items: list[CanvasItem]) -> str:
    baris = []
    for i in items[:8]:
        nilai = f'<span class="daftar-nilai">{escape(i.value)}</span>' if i.value else ""
        baris.append(f"<li>{_teks(i)}{nilai}</li>")
    return f'<ul class="daftar">{"".join(baris)}</ul>'


MAKRO = {
    "kpi_cards": _kpi_cards,
    "comparison": _comparison,
    "priority_actions": _priority_actions,
    "labelled_findings": _labelled_findings,
    "bucket_distribution": _bucket_distribution,
    "focus_statement": _focus_statement,
}


def isi_kartu(pola: str, items: list[CanvasItem]) -> str:
    """Isi satu kartu menurut pola yang dipilih designer.

    Pola tak dikenal tidak menggagalkan halaman: ia jatuh ke daftar. Sebuah
    halaman yang kehilangan satu bentuk visual masih terbaca; halaman yang gagal
    terbit tidak.
    """
    return MAKRO.get(pola, _daftar)(items)


def _kepala(isi, judul_gaya: str) -> str:
    lencana = (
        '<span class="pita pita-eskalasi">Menunggu putusan manusia</span>'
        if isi.perlu_eskalasi
        else '<span class="pita">Dapat diteruskan</span>'
    )
    return (
        '<header class="kepala">'
        '<div>'
        f'<div class="kepala-kecil">{escape(judul_gaya)}</div>'
        f'<h1>{escape(isi.equipment_tag)}</h1>'
        f'<div class="kepala-sub">{escape(isi.pabrik)}'
        + (f' · {escape(isi.model_equipment)}' if isi.model_equipment else "")
        + '</div></div>'
        f'<div class="kepala-kanan">{lencana}'
        f'<div class="kepala-keyakinan">Keyakinan: {escape(isi.keyakinan or "-")}</div>'
        '</div></header>'
    )


def render_poster(
    isi, spec, judul_blok: dict[str, str], judul_gaya: str = "Ringkasan Temuan"
) -> str:
    """Rangkai poster: satu kartu per blok, lebar dan bentuknya dari `spec`.

    Blok yang tidak punya isi dilewati, bukan digambar kosong: kartu kosong
    mengajari pembaca bahwa kartu boleh tidak berarti apa-apa.
    """
    kartu = []
    for blok in spec.order:
        items = isi.items(blok)
        if not items:
            continue
        rentang = RENTANG.get(spec.emphasis.get(blok, "secondary"), 4)
        pola = spec.form.get(blok, "")
        kartu.append(
            f'<section class="kartu" style="grid-column: span {rentang}">'
            f'<h2>{escape(judul_blok.get(blok, blok))}</h2>'
            f'{isi_kartu(pola, items)}'
            + (f'<div class="kartu-pola">{escape(pola)}</div>' if pola else "")
            + "</section>"
        )

    return (
        "<!DOCTYPE html><html lang=\"id\"><head><meta charset=\"utf-8\">"
        f"<title>Poster {escape(isi.equipment_tag)}</title>"
        f"<style>{GAYA}</style></head><body>"
        f'<main class="halaman">{_kepala(isi, judul_gaya)}'
        f'<div class="grid">{"".join(kartu)}</div>'
        '<footer class="kaki">Disusun ARKA dari temuan yang sama yang dipakai memo. '
        'Seluruh angka dihitung kode; susunan kartu diputuskan designer.</footer>'
        "</main></body></html>"
    )


GAYA = """
* { box-sizing: border-box; }
body { margin: 0; background: #f1f5f9; font-family: Inter, system-ui, sans-serif; color: #0f172a; }
.halaman { width: 1240px; margin: 0 auto; padding: 32px; }
.kepala { display: flex; justify-content: space-between; align-items: flex-start;
  background: linear-gradient(135deg, #0f294a, #0b7285); color: #fff;
  border-radius: 14px; padding: 24px 28px; margin-bottom: 18px; }
.kepala-kecil { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; opacity: .75; }
.kepala h1 { margin: 4px 0 2px; font-size: 34px; letter-spacing: -.02em; }
.kepala-sub { font-size: 14px; opacity: .85; }
.kepala-kanan { text-align: right; }
.pita { display: inline-block; padding: 5px 12px; border-radius: 999px;
  background: rgba(255,255,255,.16); font-size: 12px; font-weight: 700; }
.pita-eskalasi { background: #dc2626; }
.kepala-keyakinan { font-size: 12px; opacity: .8; margin-top: 6px; }
.grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
.kartu { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.kartu-pola { margin-top: 10px; font-size: 10px; color: #94a3b8; letter-spacing: .04em; }
.kartu h2 { margin: 0 0 10px; font-size: 13px; letter-spacing: .06em; text-transform: uppercase;
  color: #0b7285; }
.daftar { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.6; }
.daftar-nilai { float: right; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-baris { display: flex; gap: 12px; flex-wrap: wrap; }
.kpi { flex: 1 1 120px; background: #f8fafc; border-radius: 10px; padding: 12px; }
.kpi-nilai { font-size: 26px; font-weight: 800; letter-spacing: -.02em; }
.kpi-label { font-size: 12px; color: #475569; margin-top: 2px; }
.kpi-sub { font-size: 11px; color: #94a3b8; }
.banding { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: baseline;
  padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.banding-label { font-size: 13px; }
.banding-nilai { font-size: 22px; font-weight: 800; color: #dc2626;
  font-variant-numeric: tabular-nums; }
.banding-acuan { font-size: 15px; color: #94a3b8; font-variant-numeric: tabular-nums; }
.banding-satuan { font-size: 10px; color: #94a3b8; margin-left: 4px; font-weight: 500; }
.aksi-baris { display: grid; gap: 10px; }
.aksi { border-left: 4px solid #334155; background: #f8fafc; border-radius: 8px;
  padding: 10px 12px; }
.aksi-kepala { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.aksi-nomor { color: #fff; font-size: 11px; font-weight: 800; padding: 2px 8px;
  border-radius: 6px; }
.aksi-horizon { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
.aksi-teks { font-size: 13px; line-height: 1.5; }
.aksi-owner { font-size: 11px; color: #94a3b8; margin-top: 4px; }
.temuan { display: flex; gap: 8px; align-items: baseline; padding: 7px 0;
  border-bottom: 1px solid #f1f5f9; font-size: 12.5px; }
.temuan-label { font-family: ui-monospace, monospace; font-size: 11px; color: #0b7285;
  background: #ecfeff; padding: 1px 6px; border-radius: 4px; white-space: nowrap; }
.temuan-tanggal { margin-left: auto; color: #94a3b8; font-size: 11px; }
.bar-baris { display: grid; grid-template-columns: 150px 1fr 90px; gap: 10px; align-items: center;
  padding: 6px 0; font-size: 12.5px; }
.bar-jalur { background: #f1f5f9; border-radius: 999px; height: 10px; }
.bar-isi { background: linear-gradient(90deg, #0b7285, #dc2626); height: 10px;
  border-radius: 999px; }
.bar-nilai { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }
.fokus { font-size: 17px; font-weight: 700; line-height: 1.45; }
.fokus-sisa { margin: 8px 0 0; padding-left: 18px; font-size: 12.5px; color: #475569; }
.kaki { margin-top: 18px; font-size: 11px; color: #64748b; text-align: center; }
"""
