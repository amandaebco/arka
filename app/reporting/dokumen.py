"""Jenis dokumen — chrome yang berbeda di atas isi yang sama.

Memo, nota dinas, dan laporan menyajikan `Finding` yang identik. Yang berbeda
hanya dua hal, dan keduanya murah:

1. **Chrome** — kop, penomoran surat, blok tanda tangan, derajat formalitas.
2. **Kebijakan blok bawaan** — seberapa lengkap isinya bila reporter tidak
   menentukan urutan sendiri.

Angka, skor, dan sitasi tidak pernah ikut berubah antar jenis. Satu temuan
yang sama harus menghasilkan nilai yang sama persis di ketiga bentuk.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.reporting.blocks import URUTAN_BAKU, IdBlok


class KonteksDokumen(BaseModel):
    """Kelengkapan administratif surat.

    Sengaja dipisah dari `Finding`: ini urusan tata persuratan, bukan hasil
    investigasi. Investigator tidak perlu tahu apa pun tentang nomor surat.
    """

    model_config = ConfigDict(frozen=True)

    # Keterangan tambahan yang murni untuk dibaca, diisi lapisan API dan tidak
    # pernah menyentuh skor. Dipisah dari `Finding` dengan sengaja: `Finding`
    # adalah bukti yang dipakai mengambil keputusan, sedangkan ini catatan
    # pelengkap yang boleh hilang tanpa mengubah satu angka pun.
    langkah_perawatan: tuple[dict, ...] = ()

    nomor: str | None = Field(default=None, description="Nomor surat, mis. 001/ARKA/VIII/2026")
    kepada: str | None = None
    dari: str | None = None
    perihal: str | None = None
    tembusan: list[str] = Field(default_factory=list)
    penanda_tangan: str | None = None
    jabatan_penanda_tangan: str | None = None
    periode: str | None = Field(default=None, description="Periode laporan, mis. 'Juli 2026'")

    # Identitas unit penerbit. Kop dokumen adalah milik unit yang bertanggung
    # jawab atas isinya; ARKA sebagai penyusun tinggal di kaki dokumen.
    unit_penerbit: str | None = Field(
        default=None, description="Nama unit yang menerbitkan, mis. 'Unit Keandalan Aset'"
    )
    logo: str | None = Field(
        default=None,
        description=(
            "Lencana unit sebagai data URI. Wajib data URI — kop halaman PDF "
            "dirender Chromium di konteks terpisah yang tidak memuat sumber luar."
        ),
    )
    url_dashboard: str | None = Field(
        default=None,
        description="URL publik GCS tempat dashboard disimpan untuk QR code",
    )


    @field_validator("logo")
    @classmethod
    def _wajib_data_uri(cls, nilai: str | None) -> str | None:
        """Tolak tautan luar.

        Bukan sekadar soal rapi: URL jarak jauh diam-diam gagal dimuat saat
        render PDF, sehingga dokumen terbit tanpa logo tanpa ada yang tahu.
        Lebih baik ditolak saat pemanggilan.
        """
        if nilai and not nilai.startswith("data:"):
            raise ValueError("logo harus berupa data URI, bukan tautan atau path berkas")
        return nilai


@dataclass(frozen=True)
class JenisDokumen:
    id: str
    label: str
    berkas_template: str
    urutan_bawaan: tuple[IdBlok, ...]
    butuh_kop_surat: bool = False


# Memo — paling ringkas, untuk dibaca reliability engineer di lapangan.
# Jejak penalaran dan rantai kausal dilepas agar muat satu halaman.
_MEMO = JenisDokumen(
    id="memo",
    label="Memo Investigasi",
    berkas_template="memo.html.j2",
    urutan_bawaan=(
        "ringkasan",
        "kandidat_penyebab",
        "preseden_lintas_pabrik",
        "rekomendasi",
        "sitasi",
    ),
)

# Nota dinas — korespondensi antar unit. Preseden didahulukan karena justru
# pengulangan lintas pabrik itulah yang menuntut keputusan penerima.
_NOTA_DINAS = JenisDokumen(
    id="nota_dinas",
    label="Nota Dinas",
    berkas_template="nota_dinas.html.j2",
    urutan_bawaan=(
        "ringkasan",
        "preseden_lintas_pabrik",
        "kandidat_penyebab",
        "sparepart_kritis",
        "rekomendasi",
        "sitasi",
    ),
    butuh_kop_surat=True,
)

# Laporan — rekap lengkap. Semua blok, termasuk jejak penalaran untuk pembaca
# yang ingin mengaudit cara ARKA sampai pada kesimpulannya.
_LAPORAN = JenisDokumen(
    id="laporan",
    label="Laporan Investigasi",
    berkas_template="laporan.html.j2",
    urutan_bawaan=URUTAN_BAKU,
)

# Infografis — Ringkasan visual 1 halaman dari Designer Agent.
_INFOGRAFIS = JenisDokumen(
    id="infografis",
    label="Infografis Ringkas",
    berkas_template="infografis.html.j2",
    urutan_bawaan=URUTAN_BAKU,
)

# Dashboard Executive — Dark Glassmorphism Interactive Web Dashboard.
_DASHBOARD = JenisDokumen(
    id="dashboard",
    label="Dashboard Executive",
    berkas_template="dashboard.html.j2",
    urutan_bawaan=URUTAN_BAKU,
)

JENIS: dict[str, JenisDokumen] = {
    j.id: j for j in (_MEMO, _NOTA_DINAS, _LAPORAN, _INFOGRAFIS, _DASHBOARD)
}



JENIS_BAWAAN = "memo"


def ambil_jenis(id_jenis: str | None) -> JenisDokumen:
    """Ambil jenis dokumen, mundur ke memo bila tidak dikenali.

    Pilihan jenis datang dari model bahasa, jadi nilai asing diperlakukan
    sebagai salah ketik — bukan alasan menggagalkan penerbitan.
    """
    if not id_jenis:
        return JENIS[JENIS_BAWAAN]
    return JENIS.get(id_jenis.strip().lower(), JENIS[JENIS_BAWAAN])
