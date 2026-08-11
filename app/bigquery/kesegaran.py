"""Menolak jalan di atas salinan yang basi.

BigQuery adalah sumber, tetapi di lingkungan pengembangan isinya disalin dari
PostgreSQL oleh `scripts/migrasi_bigquery.py`. Mode kegagalannya bukan
"salinannya salah" — itu akan ketahuan. Mode kegagalannya adalah **"basi tanpa
peringatan"**: jalur emas diubah, migrasi lupa dijalankan, dan ARKA menjawab
dengan percaya diri dari data kemarin. Tidak ada yang merah, tidak ada yang
lambat, hanya angka yang salah.

Modul ini mematikan kata "tanpa peringatan". Salinannya tetap salinan.

## Kapan penjaga ini diam

Di produksi tidak ada PostgreSQL — data masuk ke BigQuery dari sistem sumber
dan generator sintetis tidak ikut ter-deploy. Jadi bila PostgreSQL tidak dapat
dihubungi, itu **bukan kegagalan**, melainkan tanda tidak ada apa pun untuk
dibandingkan. Penjaga melewatkan diri dan mengatakannya. Penjaga yang menuntut
PostgreSQL hadir akan menghalangi persis lingkungan yang paling tidak
membutuhkannya.

Diam juga ketika `ARKA_STORE=postgres`: tidak ada salinan yang dibaca.

## Apa yang tertangkap, dan apa yang lolos

Dua lapis, keduanya satu kueri per sisi supaya cukup murah untuk dijalankan
sebelum tiap rantai:

1. **Cacah baris seluruh tabel.** Menangkap baris yang bertambah atau hilang.
2. **Sidik jari teks pada tabel yang dibaca penilaian.** Menangkap baris yang
   berubah isinya padahal cacahnya tetap — justru skenario "jalur emas diubah",
   yang tidak akan pernah tertangkap oleh cacah saja.

Yang **lolos**: perubahan pada kolom di luar sidik jari — angka, tanggal,
`downtime_minutes`. Kolom itu sengaja tidak ikut karena PostgreSQL dan BigQuery
memformat angka dan waktu secara berbeda, dan sidik jari yang berbeda karena
format akan berbunyi terus sampai orang berhenti mempercayainya. Penjaga yang
diabaikan lebih buruk daripada tidak ada penjaga.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum

from app.bigquery import config
from app.bigquery.schema import all_tables

logger = logging.getLogger(__name__)


class Status(StrEnum):
    COCOK = "cocok"
    BASI = "basi"
    DILEWATI_BUKAN_BIGQUERY = "bukan_bigquery"
    DILEWATI_TANPA_POSTGRES = "tanpa_postgres"


# Tabel yang isinya menentukan angka, beserta kolom teks yang disidik-jari.
# Hanya kolom teks: lihat docstring soal beda format angka dan waktu.
SIDIK_JARI: dict[str, tuple[str, ...]] = {
    "failure_events": ("canonical_id", "status"),
    "symptoms": ("canonical_id", "code", "name"),
    "causes": ("canonical_id", "code", "name"),
    "spare_parts": ("canonical_id", "part_number", "component_type"),
    "equipment": ("canonical_id", "tag_number", "model"),
    "components": ("canonical_id", "component_type"),
    "documents": ("canonical_id", "title"),
}


class SalinanBasi(RuntimeError):
    """BigQuery tidak sepadan dengan PostgreSQL."""


@dataclass(frozen=True)
class Laporan:
    status: Status
    beda: tuple[str, ...] = ()

    @property
    def aman(self) -> bool:
        return self.status is not Status.BASI

    def pesan(self) -> str:
        if self.status is Status.COCOK:
            return "BigQuery sepadan dengan PostgreSQL."
        if self.status is Status.DILEWATI_BUKAN_BIGQUERY:
            return "ARKA_STORE=postgres — tidak ada salinan yang dibaca."
        if self.status is Status.DILEWATI_TANPA_POSTGRES:
            return "PostgreSQL tidak dapat dihubungi — BigQuery dianggap sumber langsung."
        daftar = "\n".join(f"  - {b}" for b in self.beda)
        return (
            "BigQuery basi terhadap PostgreSQL:\n"
            f"{daftar}\n\n"
            "Jalankan: uv run python scripts/migrasi_bigquery.py"
        )


def _sql_cacah_bigquery() -> str:
    bagian = [
        f"SELECT '{t.name}' AS tabel, COUNT(*) AS n FROM {config.table_ref(t.name)}"
        for t in all_tables()
    ]
    return "\nUNION ALL\n".join(bagian)


def _sql_cacah_postgres() -> str:
    bagian = [f"SELECT '{t.name}' AS tabel, COUNT(*) AS n FROM {t.name}" for t in all_tables()]
    return "\nUNION ALL\n".join(bagian)


def _ekspresi_sidik(kolom: tuple[str, ...], *, bigquery_dialek: bool) -> str:
    """Gabungan kolom teks satu baris, dinormalkan sama di kedua dialek."""
    gabung = ", '|', ".join(f"IFNULL({k}, '')" if bigquery_dialek else f"COALESCE({k}, '')"
                            for k in kolom)
    return f"CONCAT({gabung})"


def _sql_sidik_bigquery() -> str:
    bagian = []
    for tabel, kolom in SIDIK_JARI.items():
        baris = _ekspresi_sidik(kolom, bigquery_dialek=True)
        bagian.append(
            f"SELECT '{tabel}' AS tabel, "
            f"TO_HEX(MD5(STRING_AGG({baris}, '\\n' ORDER BY {baris}))) AS sidik "
            f"FROM {config.table_ref(tabel)}"
        )
    return "\nUNION ALL\n".join(bagian)


def _sql_sidik_postgres() -> str:
    """Sidik jari PostgreSQL, diurutkan byte-wise agar sepadan dengan BigQuery.

    `COLLATE "C"` bukan hiasan. Tanpanya PostgreSQL mengurutkan menurut collation
    locale basis data, sedangkan BigQuery mengurutkan menurut byte — dan tanda
    hubung pada `FAILURE-LATAR-00001` diperlakukan berbeda oleh keduanya. Isi
    yang identik lalu menghasilkan urutan gabungan yang berbeda, MD5 yang
    berbeda, dan penjaga yang berbunyi setiap kali walau tidak ada yang salah.
    Terjadi pada percobaan pertama, dan penjaga yang berbunyi palsu akan
    diabaikan dalam sehari.
    """
    bagian = []
    for tabel, kolom in SIDIK_JARI.items():
        baris = _ekspresi_sidik(kolom, bigquery_dialek=False)
        bagian.append(
            f"SELECT '{tabel}' AS tabel, "
            f"MD5(STRING_AGG({baris}, E'\\n' ORDER BY {baris} COLLATE \"C\")) AS sidik "
            f"FROM {tabel}"
        )
    return "\nUNION ALL\n".join(bagian)


async def periksa() -> Laporan:
    """Bandingkan kedua sisi. Tidak melempar; pemanggil yang memutuskan."""
    from app.detection.store import BIGQUERY, active_store

    if active_store() != BIGQUERY:
        return Laporan(Status.DILEWATI_BUKAN_BIGQUERY)

    pg = await _baca_postgres()
    if pg is None:
        return Laporan(Status.DILEWATI_TANPA_POSTGRES)
    pg_cacah, pg_sidik = pg
    bq_cacah, bq_sidik = await asyncio.to_thread(_baca_bigquery)

    beda: list[str] = []
    for tabel in sorted(pg_cacah):
        a, b = pg_cacah[tabel], bq_cacah.get(tabel)
        if b is None:
            beda.append(f"{tabel}: tidak ada di BigQuery")
        elif a != b:
            beda.append(f"{tabel}: postgres {a:,} baris, bigquery {b:,}")

    for tabel in sorted(pg_sidik):
        if tabel in {b.split(":")[0] for b in beda}:
            continue  # cacahnya sudah beda; sidik jari tidak menambah informasi
        if pg_sidik[tabel] != bq_sidik.get(tabel):
            beda.append(f"{tabel}: jumlah baris sama tetapi isinya berbeda")

    if beda:
        return Laporan(Status.BASI, tuple(beda))
    return Laporan(Status.COCOK)


async def _baca_postgres() -> tuple[dict[str, int], dict[str, str]] | None:
    """Cacah dan sidik jari dari PostgreSQL, atau None kalau tidak terhubung."""
    from sqlalchemy import text

    try:
        from app.db.session import session_factory

        async with session_factory() as sesi:
            cacah = {
                r.tabel: int(r.n) for r in (await sesi.execute(text(_sql_cacah_postgres())))
            }
            sidik = {
                r.tabel: (r.sidik or "") for r in (await sesi.execute(text(_sql_sidik_postgres())))
            }
            return cacah, sidik
    except Exception as e:  # noqa: BLE001 — ketiadaan PostgreSQL bukan kesalahan
        logger.info(
            "PostgreSQL tidak dapat dihubungi (%s) — pemeriksaan dilewati", type(e).__name__
        )
        return None


def _baca_bigquery() -> tuple[dict[str, int], dict[str, str]]:
    from google.cloud import bigquery

    klien = bigquery.Client(project=config.project())
    cacah = {r.tabel: int(r.n) for r in klien.query(_sql_cacah_bigquery()).result()}
    sidik = {r.tabel: (r.sidik or "") for r in klien.query(_sql_sidik_bigquery()).result()}
    return cacah, sidik


async def wajib_segar() -> Laporan:
    """Periksa, dan lempar `SalinanBasi` kalau tidak sepadan.

    Dipanggil di awal rantai. Berhenti sebelum menjawab lebih murah daripada
    menjawab dengan angka kemarin: pembacanya tidak punya cara membedakan.
    """
    laporan = await periksa()
    if not laporan.aman:
        raise SalinanBasi(laporan.pesan())
    logger.info("kesegaran: %s", laporan.pesan())
    return laporan
