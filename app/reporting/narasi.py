"""Penyaring narasi model — penegakan aturan "model tidak menyentuh angka".

Prompt sudah melarang reporter menuliskan angka, tetapi prompt adalah imbauan.
Modul ini menjadikannya batas yang berlaku: kalimat narasi yang memuat besaran
dibuang sebelum sampai ke dokumen.

Yang dibuang hanya kalimat pelanggarnya, bukan seluruh narasi. Narasi adalah
pengantar kualitatif — kehilangan satu kalimat tidak merusak dokumen, sedangkan
satu angka salah ketik merusak kredibilitas seluruhnya.

Angka yang sah tetap muncul di dokumen: dirender langsung dari `Finding` oleh
`app.reporting.blocks`, tanpa melewati model.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Bilangan pokok dalam bentuk kata. `satu` sengaja tidak masuk daftar: hampir
# selalu idiomatik ("salah satu", "satu-satunya", "satu per satu") sehingga
# menyaringnya lebih banyak merugikan daripada menolong.
_KATA_BILANGAN = (
    "dua",
    "tiga",
    "empat",
    "lima",
    "enam",
    "tujuh",
    "delapan",
    "sembilan",
    "sepuluh",
    "sebelas",
    "belas",
    "puluh",
    "ratus",
    "ribu",
    "juta",
    "miliar",
    "seperempat",
    "setengah",
    "separuh",
)

# Bilangan tingkat (`kedua`, `ketiga`) dibiarkan lewat: dalam bahasa Indonesia
# lazimnya menyatakan urutan atau "kedua-duanya", bukan mencacah.
# Akhiran `-an` ikut tertangkap: "belasan", "puluhan", "ribuan" sama-sama
# menyatakan besaran meski kabur.
_POLA_KATA = re.compile(
    r"(?<!ke)\b(" + "|".join(_KATA_BILANGAN) + r")(?:an)?\b",
    re.IGNORECASE,
)

# Digit apa pun: skor, tanggal, jam henti, persentase, nomor dokumen.
_POLA_DIGIT = re.compile(r"\d")

# Pemenggal kalimat sederhana; tanda baca penutup ikut terbawa potongan.
_POLA_KALIMAT = re.compile(r"(?<=[.!?])\s+")


def memuat_angka(teks: str) -> bool:
    """Benar bila teks memuat besaran, baik sebagai digit maupun kata bilangan."""
    return bool(_POLA_DIGIT.search(teks) or _POLA_KATA.search(teks))


def bersihkan_narasi(teks: str | None, label: str = "narasi") -> str | None:
    """Buang kalimat bermuatan angka dari satu narasi.

    Returns:
        Narasi tanpa kalimat pelanggar, atau None bila tidak tersisa apa pun.
    """
    if not teks or not teks.strip():
        return None

    kalimat = [k for k in _POLA_KALIMAT.split(teks.strip()) if k.strip()]
    aman = [k for k in kalimat if not memuat_angka(k)]

    dibuang = len(kalimat) - len(aman)
    if dibuang:
        logger.warning(
            "Narasi %s: %d kalimat dibuang karena memuat angka — %s",
            label,
            dibuang,
            "; ".join(k.strip() for k in kalimat if memuat_angka(k)),
        )

    hasil = " ".join(k.strip() for k in aman).strip()
    return hasil or None


def bersihkan_peta_narasi(narasi: dict[str, str] | None) -> tuple[dict[str, str], list[str]]:
    """Bersihkan seluruh narasi sekaligus.

    Returns:
        Pasangan (narasi bersih, id blok yang narasinya diubah atau digugurkan).
        Daftar kedua dipakai memberi tahu model bahwa batas itu nyata.
    """
    if not narasi:
        return {}, []

    bersih: dict[str, str] = {}
    ditolak: list[str] = []
    for id_blok, teks in narasi.items():
        if not isinstance(teks, str):
            continue
        hasil = bersihkan_narasi(teks, label=id_blok)
        if hasil != (teks.strip() or None):
            ditolak.append(id_blok)
        if hasil:
            bersih[id_blok] = hasil
    return bersih, ditolak
