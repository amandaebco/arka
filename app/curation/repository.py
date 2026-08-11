"""Membaca kandidat fakta, dan mencatat keputusan atasnya.

Satu-satunya modul kurasi yang menyentuh penyimpanan. Berbeda dari
`app/detection/`, di sini **ada penulisan** — tetapi yang ditulis bukan fakta,
melainkan *keputusan tentang* fakta: `claim_reviews` beserta perubahan
`review_status`. Prinsip III tetap utuh, karena klaim yang diterima adalah klaim
yang lolos kurasi, bukan klaim yang ditulis agent atas kehendaknya sendiri.

Selalu PostgreSQL. Kurasi mengubah keadaan, dan keadaan hanya boleh berubah di
satu tempat — mirror BigQuery dibangun ulang dari sana, tidak ditulis langsung.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.scoring import Kutipan
from app.models.knowledge import (
    Claim,
    ClaimEvidence,
    ClaimReview,
    Document,
    DocumentChunk,
    DocumentVersion,
    Evidence,
)

logger = logging.getLogger(__name__)

BELUM_DITINJAU = "unreviewed"
DITERIMA = "accepted"
DITOLAK = "rejected"


@dataclass(frozen=True)
class KandidatKlaim:
    """Satu klaim yang menunggu keputusan, beserta bukti yang menopangnya."""

    claim_id: str
    source_key: str
    claim_type: str
    statement: str
    subject: str | None
    confidence: Decimal
    failure_event_id: str | None
    kutipan: list[Kutipan] = field(default_factory=list)
    dibantah_oleh: tuple[str, ...] = ()

    @property
    def dibantah(self) -> bool:
        return bool(self.dibantah_oleh)


async def kandidat_belum_ditinjau(sesi: AsyncSession) -> list[KandidatKlaim]:
    """Setiap klaim yang belum diputuskan, beserta kutipan penopangnya.

    Pertentangan dideteksi di sini, bukan diserahkan ke pemanggil: dua klaim
    `probable_cause` atas kegagalan yang sama saling membantah menurut definisi,
    dan pemanggil yang harus mengingat aturan itu sendiri cepat atau lambat akan
    lupa.
    """
    rows = (
        await sesi.execute(
            select(Claim).where(Claim.review_status == BELUM_DITINJAU).order_by(Claim.source_key)
        )
    ).scalars().all()
    if not rows:
        return []

    bukti = await _kutipan_per_klaim(sesi, [c.id for c in rows])
    lawan = _pertentangan(rows)

    return [
        KandidatKlaim(
            claim_id=str(c.id),
            source_key=c.source_key,
            claim_type=c.claim_type,
            statement=c.statement,
            subject=c.subject_text,
            confidence=c.confidence,
            failure_event_id=str(c.failure_event_id) if c.failure_event_id else None,
            kutipan=bukti.get(c.id, []),
            dibantah_oleh=lawan.get(c.id, ()),
        )
        for c in rows
    ]


def _pertentangan(klaim: list[Claim]) -> dict:
    """Klaim `probable_cause` yang menunjuk penyebab berbeda atas kegagalan sama."""
    per_kegagalan: dict = {}
    for c in klaim:
        if c.claim_type != "probable_cause" or c.failure_event_id is None:
            continue
        per_kegagalan.setdefault(c.failure_event_id, []).append(c)

    hasil: dict = {}
    for daftar in per_kegagalan.values():
        penyebab = {c.proposed_cause_id for c in daftar}
        if len(penyebab) < 2:
            continue
        for c in daftar:
            hasil[c.id] = tuple(
                sorted(o.source_key for o in daftar if o.proposed_cause_id != c.proposed_cause_id)
            )
    return hasil


async def _kutipan_per_klaim(sesi: AsyncSession, claim_ids: list) -> dict:
    """Kutipan penopang tiap klaim, beserta jenis dokumen asalnya."""
    rows = (
        await sesi.execute(
            select(
                ClaimEvidence.claim_id,
                Document.document_type,
                Evidence.confidence,
                Evidence.quote_text,
            )
            .join(Evidence, Evidence.id == ClaimEvidence.evidence_id)
            .join(DocumentChunk, DocumentChunk.id == Evidence.document_chunk_id)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(ClaimEvidence.claim_id.in_(claim_ids))
        )
    ).all()

    hasil: dict = {}
    for claim_id, jenis, keyakinan, kutipan in rows:
        hasil.setdefault(claim_id, []).append(Kutipan(jenis, keyakinan, kutipan or ""))
    return hasil


async def catat_keputusan(
    sesi: AsyncSession,
    *,
    claim_id: str,
    diterima: bool,
    peninjau: str,
    alasan: str,
) -> None:
    """Tulis catatan tinjauan dan ubah status klaim.

    Keduanya dalam satu transaksi. Status yang berubah tanpa catatan yang
    menjelaskannya adalah fakta yang tidak bisa dipertanggungjawabkan — dan
    seluruh alasan lapisan ini ada adalah supaya itu tidak terjadi.
    """
    import uuid as _uuid

    klaim = await sesi.get(Claim, _uuid.UUID(claim_id))
    if klaim is None:  # pragma: no cover — pemanggil membaca dari tabel yang sama
        raise ValueError(f"klaim {claim_id} tidak ditemukan")

    klaim.review_status = DITERIMA if diterima else DITOLAK
    sesi.add(
        ClaimReview(
            claim_id=klaim.id,
            reviewer=peninjau,
            decision=DITERIMA if diterima else DITOLAK,
            comment=alasan,
            reviewed_at=datetime.now(UTC),
        )
    )
    logger.info("klaim %s → %s oleh %s", klaim.source_key, klaim.review_status, peninjau)


async def ringkas_status(sesi: AsyncSession) -> dict[str, int]:
    """Berapa klaim di tiap status. Dipakai laporan batch dan tes."""
    from sqlalchemy import func

    rows = (
        await sesi.execute(select(Claim.review_status, func.count()).group_by(Claim.review_status))
    ).all()
    return {status: int(jumlah) for status, jumlah in rows}
