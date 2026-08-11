"""Seberapa kuat sebuah kandidat fakta berdiri — dihitung, bukan ditafsirkan.

Prinsip III melarang agent menulis fakta ke graph. Temuan masuk sebagai klaim
`unreviewed` dan menunggu persetujuan. Modul ini menghitung seberapa kuat tiap
klaim berdiri; **Curator** yang memutuskan mana yang aman disetujui otomatis dan
mana yang harus dibawa ke manusia.

Pembagian itu sama dengan yang berlaku di lapisan deteksi, dan alasannya sama:
salah memilih klaim mana yang diangkat lebih dulu tidak fatal, tetapi salah
menerima fakta ke dalam graph adalah kesalahan yang akan dikutip berkali-kali
setelahnya. Angkanya karena itu tidak pernah disentuh model.

## Empat komponen

    bukti          0,35   min(jumlah kutipan / 3, 1,0)
    keyakinan      0,30   rata-rata keyakinan ekstraksi tiap kutipan
    kewenangan     0,20   jenis dokumen yang menopangnya
    kesepakatan    0,15   1,0 bila tidak ada klaim yang membantahnya

`kesepakatan` bukan sekadar komponen keempat. Klaim yang **dibantah** klaim lain
tentang subjek yang sama tidak pernah boleh disetujui otomatis berapa pun
skornya — pertentangan adalah justru keadaan yang menuntut manusia, dan
merata-ratakannya dengan tiga komponen lain akan membuatnya bisa tertutup oleh
bukti yang banyak. Karena itu ia juga dikembalikan sebagai penanda tersendiri.

Keterlacakan: spec 004 FR-001 … FR-007.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

BOBOT: dict[str, Decimal] = {
    "bukti": Decimal("0.35"),
    "keyakinan": Decimal("0.30"),
    "kewenangan": Decimal("0.20"),
    "kesepakatan": Decimal("0.15"),
}

# Berapa kutipan sebelum `bukti` penuh. Tiga, sama dengan `corroboration` di
# lapisan deteksi: satu kutipan adalah satu orang menulis satu kalimat, dua bisa
# saling menyalin, tiga mulai menjadi pola.
BUKTI_PENUH = 3

# Kewenangan per jenis dokumen. Analisis mode kegagalan dan standar perawatan
# ditinjau sebelum terbit; catatan teknisi ditulis saat pekerjaan berlangsung dan
# tidak pernah ditinjau siapa pun. Keduanya sah dikutip, tetapi tidak sama
# beratnya untuk menerima fakta baru.
KEWENANGAN: dict[str, Decimal] = {
    "fmea": Decimal("1.00"),
    "rcps": Decimal("1.00"),
    "manual": Decimal("0.90"),
    "datasheet": Decimal("0.90"),
    "inspection_report": Decimal("0.75"),
    "technician_note": Decimal("0.45"),
    "other": Decimal("0.30"),
}
KEWENANGAN_TAK_DIKENAL = Decimal("0.30")

# Ambang keputusan. Diterbitkan sebagai kebijakan, sama seperti ambang deteksi:
# yang disetel ketika hasilnya tidak sesuai harapan adalah datanya, bukan ini.
AMAN_OTOMATIS = Decimal("0.75")
TERLALU_LEMAH = Decimal("0.40")


class Keputusan(StrEnum):
    SETUJUI = "setujui"
    ESKALASI = "eskalasi"
    TOLAK = "tolak"


@dataclass(frozen=True)
class Kutipan:
    """Satu potongan bukti yang menopang klaim."""

    document_type: str
    confidence: Decimal
    quote_text: str = ""


@dataclass(frozen=True)
class SkorKlaim:
    """Rincian skor, dibuka per komponen supaya bisa dibantah."""

    bukti: Decimal
    keyakinan: Decimal
    kewenangan: Decimal
    kesepakatan: Decimal
    total: Decimal
    dibantah: bool

    @property
    def komponen(self) -> dict[str, Decimal]:
        return {
            "bukti": self.bukti,
            "keyakinan": self.keyakinan,
            "kewenangan": self.kewenangan,
            "kesepakatan": self.kesepakatan,
        }


@dataclass(frozen=True)
class Vonis:
    """Keputusan beserta alasan yang bisa dibaca manusia."""

    keputusan: Keputusan
    skor: SkorKlaim
    alasan: str


def _bulat(nilai: Decimal) -> Decimal:
    return nilai.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _rata(nilai: list[Decimal]) -> Decimal:
    return sum(nilai, Decimal(0)) / Decimal(len(nilai)) if nilai else Decimal(0)


def skor_klaim(kutipan: list[Kutipan], *, dibantah: bool = False) -> SkorKlaim:
    """Hitung kekuatan satu klaim dari kutipan yang menopangnya.

    Args:
        kutipan: Bukti yang menopang klaim ini. Boleh kosong.
        dibantah: Ada klaim lain yang menyatakan sebaliknya tentang subjek yang
            sama.

    Returns:
        Rincian per komponen beserta totalnya.
    """
    bukti = min(Decimal(len(kutipan)) / Decimal(BUKTI_PENUH), Decimal(1))
    keyakinan = _rata([k.confidence for k in kutipan])
    kewenangan = _rata(
        [KEWENANGAN.get(k.document_type, KEWENANGAN_TAK_DIKENAL) for k in kutipan]
    )
    kesepakatan = Decimal(0) if dibantah else Decimal(1)

    total = (
        BOBOT["bukti"] * bukti
        + BOBOT["keyakinan"] * keyakinan
        + BOBOT["kewenangan"] * kewenangan
        + BOBOT["kesepakatan"] * kesepakatan
    )
    return SkorKlaim(
        bukti=_bulat(bukti),
        keyakinan=_bulat(keyakinan),
        kewenangan=_bulat(kewenangan),
        kesepakatan=_bulat(kesepakatan),
        total=_bulat(total),
        dibantah=dibantah,
    )


def putuskan(skor: SkorKlaim) -> Vonis:
    """Terjemahkan skor menjadi keputusan.

    Pertentangan diperiksa **sebelum** ambang. Klaim yang dibantah menuntut
    manusia berapa pun skornya: bukti yang banyak di satu sisi tidak
    menyelesaikan perselisihan, ia hanya membuat salah satu pihak terlihat lebih
    ramai.
    """
    if skor.dibantah:
        return Vonis(
            Keputusan.ESKALASI,
            skor,
            "Ada klaim lain yang menyatakan sebaliknya tentang subjek yang sama.",
        )
    if skor.total >= AMAN_OTOMATIS:
        return Vonis(
            Keputusan.SETUJUI,
            skor,
            f"Bukti konsisten dan berwenang; skor {skor.total} di atas ambang {AMAN_OTOMATIS}.",
        )
    if skor.total < TERLALU_LEMAH:
        return Vonis(
            Keputusan.TOLAK,
            skor,
            f"Dukungan terlalu tipis; skor {skor.total} di bawah ambang {TERLALU_LEMAH}.",
        )
    return Vonis(
        Keputusan.ESKALASI,
        skor,
        f"Skor {skor.total} berada di antara ambang tolak dan ambang setuju otomatis.",
    )


def nilai(kutipan: list[Kutipan], *, dibantah: bool = False) -> Vonis:
    """Skor sekaligus keputusannya — jalur yang dipakai pemanggil."""
    return putuskan(skor_klaim(kutipan, dibantah=dibantah))
