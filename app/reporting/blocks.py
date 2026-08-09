"""Blok memo — potongan konten yang dirakit deterministik dari `Finding`.

Pembagian tugas yang tidak boleh dilanggar:

* Modul ini menyusun **isi** setiap blok dari data. Angka, skor, dan sitasi
  masuk apa adanya, tanpa perantara model bahasa.
* Reporter (LLM) hanya memilih **blok mana** yang dipakai, **urutannya**, dan
  menulis **narasi** pengantar.

Blok yang tidak punya data akan melaporkan dirinya kosong lewat `tersedia`,
sehingga reporter tidak bisa memilih blok hampa.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.reporting.finding import Finding
from app.reporting.grafik import grafik_untuk
from app.reporting.narasi import bersihkan_narasi

IdBlok = Literal[
    "ringkasan",
    "kandidat_penyebab",
    "preseden_lintas_pabrik",
    "rantai_kausal",
    "sparepart_kritis",
    "jejak_penalaran",
    "rekomendasi",
    "sitasi",
]

# Blok yang selalu ikut, berapa pun pilihan model. Sitasi adalah dasar
# keterlacakan ARKA — memo tanpa sitasi tidak boleh terbit.
BLOK_WAJIB: tuple[IdBlok, ...] = ("ringkasan", "sitasi")

# Urutan baku bila model tidak menentukan urutan yang sah.
URUTAN_BAKU: tuple[IdBlok, ...] = (
    "ringkasan",
    "kandidat_penyebab",
    "preseden_lintas_pabrik",
    "rantai_kausal",
    "sparepart_kritis",
    "rekomendasi",
    "jejak_penalaran",
    "sitasi",
)


@dataclass(frozen=True)
class Blok:
    """Satu blok siap render."""

    id: IdBlok
    judul: str
    tersedia: bool
    data: dict = field(default_factory=dict)
    narasi: str | None = None


def susun_blok(finding: Finding) -> dict[IdBlok, Blok]:
    """Bangun seluruh blok yang mungkin dari satu `Finding`.

    Selalu mengembalikan kedelapan blok. Blok tanpa data ditandai
    `tersedia=False` agar penyaringan terjadi di satu tempat saja.
    """
    kandidat = finding.kandidat_terurut
    sitasi = finding.semua_sitasi()

    semua = {
        "ringkasan": Blok(
            id="ringkasan",
            judul="Ringkasan",
            tersedia=True,
            data={
                "equipment_tag": finding.equipment_tag,
                "pabrik": finding.pabrik,
                "model_equipment": finding.model_equipment,
                "gejala": finding.gejala,
                "keyakinan": finding.keyakinan,
                "perlu_eskalasi": finding.perlu_eskalasi,
                "alasan_eskalasi": finding.alasan_eskalasi,
                "penyebab_teratas": kandidat[0] if kandidat else None,
                "jumlah_preseden": len(finding.preseden),
                "jumlah_sitasi": len(sitasi),
            },
        ),
        "kandidat_penyebab": Blok(
            id="kandidat_penyebab",
            judul="Kandidat Penyebab",
            tersedia=bool(kandidat),
            data={"kandidat": kandidat},
        ),
        "preseden_lintas_pabrik": Blok(
            id="preseden_lintas_pabrik",
            judul="Preseden Lintas Pabrik",
            tersedia=bool(finding.preseden),
            data={
                "preseden": sorted(
                    finding.preseden, key=lambda p: p.tanggal_kejadian, reverse=True
                ),
                "pabrik_terlibat": sorted({p.pabrik for p in finding.preseden}),
            },
        ),
        "rantai_kausal": Blok(
            id="rantai_kausal",
            judul="Rantai Kausal",
            tersedia=bool(finding.rantai_kausal),
            data={"mata_rantai": finding.rantai_kausal},
        ),
        "sparepart_kritis": Blok(
            id="sparepart_kritis",
            judul="Kekritisan Sparepart",
            tersedia=bool(finding.sparepart),
            data={
                # Selisih terbesar lebih dulu — itulah yang tidak terlihat di master data.
                "sparepart": sorted(finding.sparepart, key=lambda s: s.selisih, reverse=True)
            },
        ),
        "jejak_penalaran": Blok(
            id="jejak_penalaran",
            judul="Jejak Penalaran",
            tersedia=bool(finding.jejak_penalaran),
            data={"langkah": sorted(finding.jejak_penalaran, key=lambda x: x.urutan)},
        ),
        "rekomendasi": Blok(
            id="rekomendasi",
            judul="Rekomendasi",
            tersedia=bool(finding.rekomendasi),
            data={"rekomendasi": finding.rekomendasi},
        ),
        "sitasi": Blok(
            id="sitasi",
            judul="Dokumen Sumber",
            tersedia=bool(sitasi),
            data={"sitasi": sitasi},
        ),
    }

    # Grafik dirakit dari data yang sama, sekali di sini, supaya tidak ada
    # jalur lain yang bisa menyuntikkan gambar ke dokumen.
    for id_blok, blok in semua.items():
        if blok.tersedia:
            blok.data["grafik"] = grafik_untuk(id_blok, finding)

    return semua


def pilih_blok(
    semua: dict[IdBlok, Blok],
    urutan_diminta: list[str] | None = None,
    narasi: dict[str, str] | None = None,
) -> list[Blok]:
    """Terapkan pilihan reporter di atas blok yang tersedia.

    Pilihan model diperlakukan sebagai usulan, bukan perintah: id yang tidak
    dikenal diabaikan, blok kosong disaring, dan `BLOK_WAJIB` tetap masuk
    sekalipun model lupa menyebutnya. Narasi disaring dari kalimat bermuatan
    angka — lihat `app.reporting.narasi`.
    """
    narasi = narasi or {}

    if urutan_diminta:
        terpilih: list[IdBlok] = []
        for kandidat_id in urutan_diminta:
            if kandidat_id in semua and kandidat_id not in terpilih:
                terpilih.append(kandidat_id)  # type: ignore[arg-type]
    else:
        terpilih = list(URUTAN_BAKU)

    for wajib in BLOK_WAJIB:
        if wajib not in terpilih:
            # Ringkasan membuka memo, sitasi menutupnya.
            if wajib == "ringkasan":
                terpilih.insert(0, wajib)
            else:
                terpilih.append(wajib)

    hasil: list[Blok] = []
    for blok_id in terpilih:
        blok = semua[blok_id]
        if not blok.tersedia:
            continue
        teks = bersihkan_narasi(narasi.get(blok_id), label=blok_id)
        hasil.append(Blok(**{**blok.__dict__, "narasi": teks}) if teks else blok)
    return hasil
