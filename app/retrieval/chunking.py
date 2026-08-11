"""Memotong dokumen menjadi bagian yang bisa dicari dan dikutip.

Sebelum modul ini, satu dokumen adalah satu potongan. Itu cukup selama korpusnya
empat laporan pendek, dan menyesatkan begitu tidak.

Dua hal rusak kalau dokumen tidak dipotong. **Pencariannya**: satu vektor untuk
seluruh laporan merata-ratakan setiap gagasan di dalamnya, sehingga laporan yang
membahas lima hal tidak cocok kuat dengan satu pun dari kelimanya. Dan
**sitasinya**: rujukan ke sebuah dokumen tiga puluh halaman menyuruh pembaca
mencari sendiri kalimat yang dimaksud — yang persis pekerjaan yang seharusnya
dihapus ARKA.

## Yang menentukan batas potongan

Dipotong di **batas paragraf** lebih dulu, karena di situlah penulisnya sendiri
menandai pergantian gagasan. Paragraf yang terlalu panjang dipecah di batas
kalimat. Tidak pernah di tengah kata.

Antar potongan diberi **tumpang tindih**: kalimat yang menjelaskan temuan sering
berada tepat di batas, dan potongan yang dipisah bersih akan membelah pertanyaan
dari jawabannya. Tumpang tindih membayar sedikit penyimpanan untuk menghindari
kelas kegagalan yang tidak terlihat — hasil pencarian yang benar-benar ada di
korpus tetapi tidak pernah muncul karena terbelah dua.

`start_offset` dan `end_offset` menunjuk ke teks aslinya, jadi setiap kutipan
bisa dilacak balik ke posisinya. Kolomnya sudah ada di `document_chunks` sejak
awal; sebelum ini isinya selalu 0 dan panjang dokumen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Sasaran panjang potongan, dalam karakter. Dipilih supaya satu potongan memuat
# satu gagasan utuh — temuan beserta tindakannya — tanpa menjadi ringkasan
# beberapa hal sekaligus. Bukan batas keras: paragraf yang sedikit lebih panjang
# dibiarkan utuh ketimbang dibelah di tempat yang salah.
TARGET_KARAKTER = 700

# Batas keras. Di atas ini paragraf dipecah per kalimat, apa pun isinya.
MAKS_KARAKTER = 1_100

# Tumpang tindih antar potongan.
TUMPANG_TINDIH = 120

# Potongan yang lebih pendek dari ini digabung ke tetangganya. Serpihan satu
# kalimat mencemari hasil pencarian: skornya bisa tinggi karena pendek, lalu
# tidak membawa konteks apa pun untuk dibaca.
MIN_KARAKTER = 120

_PARAGRAF = re.compile(r"\n\s*\n")
# Akhir kalimat: titik/tanya/seru diikuti spasi dan huruf besar. Singkatan
# seperti "No." tidak diikuti huruf besar dan karenanya tidak memecah.
_KALIMAT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass(frozen=True)
class Potongan:
    """Satu bagian dokumen, beserta letaknya di teks asli."""

    indeks: int
    isi: str
    start_offset: int
    end_offset: int

    @property
    def panjang(self) -> int:
        return len(self.isi)


def _blok(teks: str) -> list[tuple[str, int]]:
    """Paragraf, dipecah per kalimat bila terlalu panjang. Dengan offsetnya."""
    hasil: list[tuple[str, int]] = []
    posisi = 0
    for paragraf in _PARAGRAF.split(teks):
        mulai = teks.find(paragraf, posisi)
        if mulai < 0:  # pragma: no cover — hanya bila teks dimodifikasi di tengah
            mulai = posisi
        posisi = mulai + len(paragraf)

        bersih = paragraf.strip()
        if not bersih:
            continue
        geser = paragraf.index(bersih) if bersih in paragraf else 0

        if len(bersih) <= MAKS_KARAKTER:
            hasil.append((bersih, mulai + geser))
            continue

        # Terlalu panjang: pecah per kalimat, tetap lacak offsetnya.
        dalam = mulai + geser
        for kalimat in _KALIMAT.split(bersih):
            k = kalimat.strip()
            if not k:
                continue
            letak = teks.find(k, dalam)
            hasil.append((k, letak if letak >= 0 else dalam))
            dalam = (letak if letak >= 0 else dalam) + len(k)
    return hasil


def _ekor(teks: str, panjang: int) -> str:
    """Ujung teks sepanjang `panjang`, dipotong di batas kata."""
    if panjang <= 0 or len(teks) <= panjang:
        return teks
    potong = teks[-panjang:]
    spasi = potong.find(" ")
    return potong[spasi + 1 :] if spasi != -1 else potong


def potong(
    teks: str,
    *,
    target: int = TARGET_KARAKTER,
    maksimum: int = MAKS_KARAKTER,
    tumpang_tindih: int = TUMPANG_TINDIH,
    minimum: int = MIN_KARAKTER,
) -> list[Potongan]:
    """Potong satu dokumen. Mengembalikan potongan berurutan.

    Dokumen yang lebih pendek dari `target` dikembalikan utuh sebagai satu
    potongan — memotongnya hanya akan menghasilkan serpihan.

    Args:
        teks: Isi dokumen.
        target: Panjang yang dituju per potongan.
        maksimum: Di atas ini paragraf dipecah per kalimat.
        tumpang_tindih: Karakter dari ekor potongan sebelumnya yang diulang.
        minimum: Potongan lebih pendek dari ini digabung ke tetangganya.

    Returns:
        Potongan berurutan. Kosong hanya bila teksnya kosong.
    """
    bersih = (teks or "").strip()
    if not bersih:
        return []
    if len(bersih) <= target:
        awal = teks.index(bersih)
        return [Potongan(0, bersih, awal, awal + len(bersih))]

    blok = _blok(teks)
    if not blok:  # pragma: no cover — teks tidak kosong pasti punya blok
        return []

    mentah: list[tuple[str, int, int]] = []
    kumpul: list[str] = []
    mulai = blok[0][1]
    akhir = mulai

    for isi, letak in blok:
        calon = len("\n\n".join([*kumpul, isi]))
        if kumpul and calon > maksimum:
            mentah.append(("\n\n".join(kumpul), mulai, akhir))
            kumpul = [isi]
            mulai, akhir = letak, letak + len(isi)
            continue

        kumpul.append(isi)
        akhir = letak + len(isi)
        if len("\n\n".join(kumpul)) >= target:
            mentah.append(("\n\n".join(kumpul), mulai, akhir))
            kumpul = []
            mulai = akhir

    if kumpul:
        gabung = "\n\n".join(kumpul)
        # Sisa yang terlalu pendek menempel ke potongan sebelumnya, bukan
        # berdiri sendiri sebagai serpihan.
        if mentah and len(gabung) < minimum:
            isi_lama, awal_lama, _ = mentah[-1]
            mentah[-1] = (f"{isi_lama}\n\n{gabung}", awal_lama, akhir)
        else:
            mentah.append((gabung, mulai, akhir))

    hasil: list[Potongan] = []
    for i, (isi, a, b) in enumerate(mentah):
        if i and tumpang_tindih:
            ekor = _ekor(mentah[i - 1][0], tumpang_tindih)
            isi = f"{ekor}\n\n{isi}" if ekor else isi
        hasil.append(Potongan(i, isi, a, b))
    return hasil
