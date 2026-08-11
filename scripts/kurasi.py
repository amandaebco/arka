"""Kurasi kandidat fakta — batch, tanpa memanggil model.

    uv run python scripts/kurasi.py           # laporkan saja, tidak menulis
    uv run python scripts/kurasi.py --terapkan # tulis keputusan yang aman
    uv run python scripts/kurasi.py --json

Ini jalur deterministik yang sama yang dilihat `curator_agent`, tanpa modelnya.
`CLAUDE.md` mengizinkan Curator turun menjadi skrip batch bila waktu habis; yang
ada sekarang keduanya, dan skrip ini juga yang membuat keputusan agent bisa
dibandingkan terhadap kebijakan tertulis.

**Bawaannya tidak menulis apa pun.** Kurasi mengubah pengetahuan yang dipakai
seluruh sistem menjawab; menjalankannya tanpa sengaja tidak boleh menghasilkan
perubahan apa pun.

Kode keluar:

    0  selesai, tidak ada yang perlu manusia
    1  selesai, ada yang menunggu keputusan manusia
    2  gagal
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.curation.repository import catat_keputusan, kandidat_belum_ditinjau, ringkas_status
from app.curation.scoring import Keputusan, nilai


async def kurasi(terapkan: bool) -> dict:
    from app.db.session import session_factory

    async with session_factory() as sesi:
        kandidat = await kandidat_belum_ditinjau(sesi)
        hasil = []
        for k in kandidat:
            v = nilai(k.kutipan, dibantah=k.dibantah)
            hasil.append(
                {
                    "source_key": k.source_key,
                    "pernyataan": k.statement,
                    "kutipan": len(k.kutipan),
                    "skor": str(v.skor.total),
                    "keputusan": v.keputusan.value,
                    "alasan": v.alasan,
                    "dibantah_oleh": list(k.dibantah_oleh),
                }
            )
            if terapkan and v.keputusan in (Keputusan.SETUJUI, Keputusan.TOLAK):
                await catat_keputusan(
                    sesi,
                    claim_id=k.claim_id,
                    diterima=v.keputusan is Keputusan.SETUJUI,
                    peninjau="Curator (batch)",
                    alasan=v.alasan,
                )
        if terapkan:
            await sesi.commit()
        status = await ringkas_status(sesi)

    return {"kandidat": hasil, "status": status, "diterapkan": terapkan}


def main() -> int:
    p = argparse.ArgumentParser(description="Kurasi kandidat fakta")
    p.add_argument("--terapkan", action="store_true", help="tulis keputusan yang aman")
    p.add_argument("--json", action="store_true", help="keluaran JSON")
    args = p.parse_args()

    try:
        hasil = asyncio.run(kurasi(args.terapkan))
    except Exception as exc:  # noqa: BLE001 — penjadwal butuh kode keluar, bukan jejak
        print(f"Kurasi gagal: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    perlu_manusia = [k for k in hasil["kandidat"] if k["keputusan"] == Keputusan.ESKALASI.value]

    if args.json:
        print(json.dumps(hasil, indent=2, ensure_ascii=False))
        return 1 if perlu_manusia else 0

    if not hasil["kandidat"]:
        print("Tidak ada kandidat yang menunggu tinjauan.")
        return 0

    print(f"{len(hasil['kandidat'])} kandidat ditinjau"
          + ("" if args.terapkan else " (mode laporan — tidak ada yang ditulis)") + ".\n")
    for k in hasil["kandidat"]:
        tanda = {"setujui": "✓", "tolak": "✗", "eskalasi": "→"}[k["keputusan"]]
        print(f"  {tanda} {k['source_key']:<22} skor {k['skor']:<8} {k['keputusan']}")
        print(f"      {k['alasan']}")
    print()
    if perlu_manusia:
        print(f"{len(perlu_manusia)} kandidat menunggu keputusan manusia:")
        for k in perlu_manusia:
            print(f"  - {k['source_key']}: {k['pernyataan'][:70]}")
    if not args.terapkan:
        print("\nJalankan dengan --terapkan untuk menulis keputusan yang aman.")
    return 1 if perlu_manusia else 0


if __name__ == "__main__":
    sys.exit(main())
