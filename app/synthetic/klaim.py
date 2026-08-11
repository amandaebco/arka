"""Kandidat fakta yang menunggu kurasi.

Curator memutuskan pemetaan mana yang aman disetujui otomatis. Tanpa kandidat
untuk diputuskan, ia hanya kerangka. Modul ini menulis kandidat tersebut —
klaim `unreviewed` beserta kutipan yang menopangnya, mengutip potongan dokumen
yang benar-benar ada.

## Empat bentuk, sengaja

Sebuah penyaring hanya bisa dibantah kalau ia menghadapi keempatnya:

1. **Kuat** — beberapa kutipan dari dokumen yang ditinjau sebelum terbit.
   Inilah yang boleh lolos otomatis.
2. **Tipis** — satu kutipan dari catatan teknisi. Cukup untuk dipertimbangkan,
   tidak cukup untuk diterima tanpa manusia.
3. **Bertentangan** — dua klaim menunjuk penyebab berbeda atas kegagalan yang
   sama. Keduanya harus dieskalasi; ini keadaan yang paling menuntut manusia dan
   paling mudah tertutup kalau skor dirata-ratakan begitu saja.
4. **Tanpa bukti** — pernyataan tanpa satu pun kutipan. Harus ditolak.

Tanpa bentuk keempat, "Curator menolak yang lemah" tidak pernah terbukti; tanpa
bentuk ketiga, "Curator tahu kapan berhenti" tidak pernah terbukti.

## Kutipannya nyata

`quote_text` diambil dari isi potongan dokumen, dan `start_offset`/`end_offset`
menunjuk ke dalam potongan itu. Bukti yang mengutip teks yang tidak ada di
dokumennya adalah persis kesalahan yang seluruh lapisan sitasi dibangun untuk
mencegah — memalsukannya di data uji berarti menguji sistem terhadap dunia yang
lebih mudah daripada dunia nyata.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Claim, ClaimEvidence, Document, DocumentChunk, DocumentVersion
from app.models.reliability import Cause, FailureEvent
from app.synthetic.jalur_emas import id_stabil

logger = logging.getLogger(__name__)

# Panjang kutipan yang diambil dari potongan dokumen.
PANJANG_KUTIPAN = 180


async def _potongan(sesi: AsyncSession) -> list[tuple]:
    """Potongan dokumen jalur emas, beserta jenis dokumennya."""
    rows = (
        await sesi.execute(
            select(DocumentChunk.id, DocumentChunk.content, Document.document_type)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(Document.canonical_id.notlike("DOC-LATAR-%"))
            .order_by(Document.canonical_id, DocumentChunk.chunk_index)
        )
    ).all()
    return list(rows)


def _kutip(isi: str) -> tuple[str, int, int]:
    """Petikan verbatim dari awal potongan, beserta letaknya."""
    teks = (isi or "").strip()[:PANJANG_KUTIPAN]
    return teks, 0, max(len(teks), 1)


async def tulis_kandidat(sesi: AsyncSession, seed: int) -> dict[str, int]:
    """Tulis klaim `unreviewed` beserta buktinya.

    Returns:
        Cacah per bentuk kandidat.
    """
    from app.models.knowledge import Evidence

    potongan = await _potongan(sesi)
    if not potongan:  # pragma: no cover — generator selalu menulis dokumen
        return {"klaim_kandidat": 0}

    kegagalan = {
        f.canonical_id: f
        for f in (await sesi.execute(select(FailureEvent))).scalars()
        if f.canonical_id.startswith("FAILURE-")
    }
    penyebab = {c.canonical_id: c for c in (await sesi.execute(select(Cause))).scalars()}

    hidup = kegagalan.get("FAILURE-KASUS-HIDUP-UTARA")
    barat = kegagalan.get("FAILURE-PRESEDEN-BARAT")
    seal = penyebab.get("PNY-SEAL-DEGRADASI")
    torsi = penyebab.get("PNY-TORSI-MENYIMPANG")

    dibuat: dict[str, int] = {"kuat": 0, "tipis": 0, "bertentangan": 0, "tanpa_bukti": 0}
    nomor = 0

    def buat_bukti(chunk_id, isi, keyakinan: str):
        nonlocal nomor
        nomor += 1
        teks, awal, akhir = _kutip(isi)
        obj = Evidence(
            id=id_stabil(seed, f"bukti:{nomor}"),
            document_chunk_id=chunk_id,
            evidence_type="quote",
            quote_text=teks,
            start_offset=awal,
            end_offset=akhir,
            extraction_method="sintetis",
            extractor_version="1.0",
            confidence=Decimal(keyakinan),
            evidence_format="text",
        )
        sesi.add(obj)
        return obj

    async def buat_klaim(
        kunci: str,
        jenis: str,
        pernyataan: str,
        keyakinan: str,
        *,
        kejadian=None,
        usul_penyebab=None,
        bukti: list | None = None,
    ):
        klaim = Claim(
            id=id_stabil(seed, f"klaim:{kunci}"),
            failure_event_id=kejadian.id if kejadian is not None else None,
            proposed_cause_id=usul_penyebab.id if usul_penyebab is not None else None,
            source_key=kunci,
            claim_type=jenis,
            assertion_status="suspected",
            statement=pernyataan,
            subject_text=kejadian.canonical_id if kejadian is not None else None,
            confidence=Decimal(keyakinan),
            review_status="unreviewed",
            extraction_method="sintetis",
            extractor_version="1.0",
        )
        sesi.add(klaim)
        await sesi.flush()
        for b in bukti or []:
            sesi.add(ClaimEvidence(claim_id=klaim.id, evidence_id=b.id))
        return klaim

    tertinjau = [p for p in potongan if p[2] in ("fmea", "manual", "datasheet")]
    inspeksi = [p for p in potongan if p[2] == "inspection_report"]
    sumber_kuat = (tertinjau + inspeksi)[:3] or potongan[:3]

    # 1. Kuat — beberapa kutipan dari dokumen yang ditinjau sebelum terbit.
    if barat is not None and seal is not None:
        bukti = [buat_bukti(p[0], p[1], "0.92") for p in sumber_kuat]
        await buat_klaim(
            "KLAIM-SEAL-KUAT",
            "probable_cause",
            "Degradasi seal kepala pengisi berulang pada armada RF-8000 "
            "berkaitan dengan batch material di bawah spesifikasi.",
            "0.90",
            kejadian=barat,
            usul_penyebab=seal,
            bukti=bukti,
        )
        dibuat["kuat"] += 1

    # 2. Tipis — satu kutipan, dari sumber yang tidak pernah ditinjau siapa pun.
    if inspeksi:
        bukti = [buat_bukti(inspeksi[0][0], inspeksi[0][1], "0.55")]
        await buat_klaim(
            "KLAIM-NOZEL-TIPIS",
            "observation",
            "Nozel pengisi diduga ikut memburuk pada unit yang sama, "
            "meski belum ada pengukuran pendukung.",
            "0.50",
            bukti=bukti,
        )
        dibuat["tipis"] += 1

    # 3. Bertentangan — dua penyebab berbeda atas kegagalan yang sama.
    if hidup is not None and seal is not None and torsi is not None:
        await buat_klaim(
            "KLAIM-HIDUP-SEAL",
            "probable_cause",
            "Kegagalan pada PLT-U/FIL-207 disebabkan degradasi seal.",
            "0.72",
            kejadian=hidup,
            usul_penyebab=seal,
            bukti=[buat_bukti(p[0], p[1], "0.80") for p in sumber_kuat[:2]],
        )
        await buat_klaim(
            "KLAIM-HIDUP-TORSI",
            "probable_cause",
            "Kegagalan pada PLT-U/FIL-207 disebabkan penyimpangan torsi "
            "pasca perawatan terjadwal.",
            "0.70",
            kejadian=hidup,
            usul_penyebab=torsi,
            bukti=[buat_bukti(p[0], p[1], "0.78") for p in sumber_kuat[:2]],
        )
        dibuat["bertentangan"] += 2

    # 4. Tanpa bukti — harus ditolak.
    await buat_klaim(
        "KLAIM-TANPA-BUKTI",
        "risk",
        "Seluruh armada RF-8000 berisiko mengalami kegagalan serupa "
        "dalam tiga bulan ke depan.",
        "0.40",
    )
    dibuat["tanpa_bukti"] += 1

    await sesi.flush()
    total = sum(dibuat.values())
    logger.info("kandidat klaim: %s", dibuat)
    return {"klaim_kandidat": total, **{f"klaim_{k}": v for k, v in dibuat.items()}}
