"""Kontrak `Finding` — serah-terima dari investigator ke reporter.

Ini adalah satu-satunya permukaan yang dilihat reporter. Selama investigator
menghasilkan objek ini, reporter tidak perlu tahu apakah isinya berasal dari
penelusuran graph, dari prompt manual, atau dari fixture pengujian.

Semua angka di sini sudah final dan deterministik. Reporter dan model bahasa
hanya boleh membaca, tidak pernah menghitung ulang.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Keyakinan = Literal["tinggi", "sedang", "rendah"]


class Sitasi(BaseModel):
    """Rujukan ke satu dokumen sumber. Tidak pernah dibuang dari memo."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str = Field(description="ID kanonik dokumen di tabel documents")
    judul: str
    tipe_dokumen: str = Field(description="mis. inspection_report, technician_note")
    tanggal: date | None = None
    lokator: str | None = Field(
        default=None, description="Penunjuk bagian, mis. 'hlm. 3' atau '§2.1'"
    )
    kutipan: str | None = Field(default=None, description="Petikan verbatim pendukung klaim")


class RincianSkor(BaseModel):
    """Uraian skor deteksi. Dihitung di modul deteksi, bukan di sini."""

    model_config = ConfigDict(frozen=True)

    symptom_overlap: Decimal
    component_match: Decimal
    corroboration: Decimal
    recency: Decimal
    total: Decimal


class KandidatPenyebab(BaseModel):
    """Satu hipotesis penyebab beserta skor dan pendukungnya."""

    model_config = ConfigDict(frozen=True)

    cause_id: str
    nama: str
    deskripsi: str | None = None
    skor: RincianSkor
    sitasi: list[Sitasi] = Field(default_factory=list)


class Preseden(BaseModel):
    """Kasus historis serupa di pabrik lain — inti nilai jual ARKA."""

    model_config = ConfigDict(frozen=True)

    failure_event_id: str
    pabrik: str
    equipment_tag: str
    # Penyebab terverifikasi kasus ini. Dibawa serta supaya pembaca -- termasuk
    # tampilan -- bisa menghubungkan tiap preseden ke kandidat yang ia dukung,
    # tanpa menebak dari kesamaan nama.
    cause_id: str | None = None
    tanggal_kejadian: date
    gejala: list[str] = Field(default_factory=list)
    penyelesaian: str | None = Field(default=None, description="Solusi yang terbukti berhasil")
    # Sitasi yang menyebut kasus ini secara khusus -- dokumen yang judul atau
    # kutipannya menyebut pabrik atau tag mesinnya. Dipisah dari `sitasi`, yang
    # berlaku untuk seluruh temuan: pembaca berhak tahu mana rujukan yang benar-
    # benar tentang kasus ini dan mana yang sekadar relevan bagi temuannya.
    sitasi_khusus: list[Sitasi] = Field(default_factory=list)
    downtime_jam: Decimal | None = None
    sitasi: list[Sitasi] = Field(default_factory=list)


class MataRantai(BaseModel):
    """Satu simpul pada rantai kausal Symptom → Cause → Damage → Part."""

    model_config = ConfigDict(frozen=True)

    peran: Literal["symptom", "cause", "damage", "part"]
    label: str
    detail: str | None = None


class SparepartKritis(BaseModel):
    """Kekritisan dinamis sparepart. Nilai jualnya ada pada selisih terhadap master data."""

    model_config = ConfigDict(frozen=True)

    part_number: str
    nama: str
    criticality: Decimal = Field(description="Kekritisan dinamis hasil perhitungan ARKA")
    static_criticality: Decimal = Field(description="Kekritisan statis di master data")
    lead_time_minggu: int | None = None
    jumlah_vendor: int | None = None
    pabrik_terdampak: list[str] = Field(default_factory=list)

    @property
    def selisih(self) -> Decimal:
        """Selisih terhadap master data. Positif berarti ARKA menilai lebih kritis."""
        return self.criticality - self.static_criticality


class LangkahPenalaran(BaseModel):
    """Satu hop pada jejak penelusuran. Ditampilkan apa adanya, tidak diringkas model."""

    model_config = ConfigDict(frozen=True)

    urutan: int
    aksi: str = Field(description="Apa yang ditelusuri, mis. 'traversal Equipment → Component'")
    hasil: str = Field(description="Apa yang ditemukan")
    jumlah_simpul: int | None = None


class Rekomendasi(BaseModel):
    model_config = ConfigDict(frozen=True)

    tindakan: str
    prioritas: Literal["segera", "terjadwal", "pantau"]
    dasar: str | None = Field(default=None, description="Alasan singkat, merujuk temuan")


class Finding(BaseModel):
    """Keluaran investigator — masukan tunggal bagi reporter."""

    model_config = ConfigDict(frozen=True)

    finding_id: str
    dibuat_pada: date

    equipment_tag: str
    pabrik: str
    model_equipment: str | None = None

    gejala: list[str] = Field(default_factory=list)
    # Kode gejala, sejajar urutan dengan `gejala`. Nama untuk dibaca manusia,
    # kode untuk dicocokkan -- dan irisan kode inilah yang menerangkan kenapa
    # sebuah preseden terpilih, jadi tampilan membutuhkan keduanya.
    gejala_kode: list[str] = Field(default_factory=list)
    keyakinan: Keyakinan = "sedang"
    perlu_eskalasi: bool = Field(
        default=False,
        description="True bila dua kandidat teratas berselisih ≤0,05 — butuh putusan manusia",
    )
    alasan_eskalasi: str | None = None

    kandidat: list[KandidatPenyebab] = Field(default_factory=list)
    preseden: list[Preseden] = Field(default_factory=list)
    rantai_kausal: list[MataRantai] = Field(default_factory=list)
    sparepart: list[SparepartKritis] = Field(default_factory=list)
    jejak_penalaran: list[LangkahPenalaran] = Field(default_factory=list)
    rekomendasi: list[Rekomendasi] = Field(default_factory=list)

    @property
    def kandidat_terurut(self) -> list[KandidatPenyebab]:
        return sorted(self.kandidat, key=lambda k: k.skor.total, reverse=True)

    def semua_sitasi(self) -> list[Sitasi]:
        """Seluruh sitasi unik, terurut stabil. Dasar blok daftar pustaka."""
        terlihat: dict[str, Sitasi] = {}
        for kandidat in self.kandidat_terurut:
            for sitasi in kandidat.sitasi:
                terlihat.setdefault(sitasi.canonical_id, sitasi)
        for preseden in self.preseden:
            for sitasi in preseden.sitasi:
                terlihat.setdefault(sitasi.canonical_id, sitasi)
        return list(terlihat.values())
