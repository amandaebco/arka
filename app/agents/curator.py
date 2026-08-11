"""Curator — memutuskan kandidat fakta mana yang aman diterima tanpa manusia.

Agent kelima, dan satu-satunya yang berjalan **ortogonal** terhadap rantai
`Scout → Investigator → Reporter → Designer`. Rantai itu menjawab pertanyaan
yang diangkat ARKA sendiri; Curator menjaga apa yang boleh masuk ke pengetahuan
yang dipakai menjawabnya.

Prinsip III melarang agent menulis fakta. Yang ditulis Curator bukan fakta,
melainkan **keputusan tentang fakta**: catatan tinjauan beserta perubahan
`review_status`. Klaim yang diterima adalah klaim yang lolos kurasi, bukan klaim
yang diputuskan sendiri oleh model yang mengusulkannya.

## Pembagian keputusan

Skor dihitung `app.curation.scoring` — nol model. Yang menjadi keputusan Curator
adalah **mana yang aman diterima tanpa manusia**: sebuah kebijakan, bukan sebuah
angka. Model boleh lebih berhati-hati daripada ambang; ia tidak boleh lebih
longgar.

## Batas yang ditegakkan kode, bukan prompt

Klaim yang **dibantah** klaim lain tidak dapat disetujui lewat jalur ini —
`putuskan_kandidat` menolaknya, apa pun yang diminta model. Pertentangan adalah
justru keadaan yang menuntut manusia, dan sebuah prompt yang melarangnya hanya
berlaku selama model menurut. Larangan yang penting ditulis di kode.

Hal yang sama berlaku untuk klaim di bawah ambang tolak: model tidak dapat
menerimanya, hanya dapat menolaknya lebih tegas.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext

from app.core.config import get_settings
from app.curation.repository import (
    catat_keputusan,
    kandidat_belum_ditinjau,
    ringkas_status,
)
from app.curation.scoring import AMAN_OTOMATIS, TERLALU_LEMAH, Keputusan, nilai

logger = logging.getLogger(__name__)

# Tempat kandidat ditinggalkan tool pertama supaya tool kedua tidak perlu
# menghitung ulang — dan supaya keputusan dinilai atas angka yang sama dengan
# yang dilihat model.
KUNCI_KANDIDAT = "kandidat_kurasi"

PERINGKAT = "Curator (otomatis)"


class KeputusanDitolak(RuntimeError):
    """Model meminta sesuatu yang tidak boleh dilakukan jalur ini."""


async def _sesi():
    from app.db.session import session_factory

    return session_factory()


async def daftar_kandidat(tool_context: ToolContext) -> str:
    """Lists every candidate fact awaiting review, with its computed score.

    The scores are deterministic and already carry a recommendation. Read them
    before deciding: your decision is which of these are safe to accept without
    a human, not what the evidence is worth.

    Args:
        tool_context: Injected by ADK.

    Returns:
        One line per candidate, or a statement that nothing is waiting.
    """
    pabrik = await _sesi()
    async with pabrik as sesi:
        kandidat = await kandidat_belum_ditinjau(sesi)

    if not kandidat:
        tool_context.state[KUNCI_KANDIDAT] = {}
        return "Tidak ada kandidat yang menunggu tinjauan."

    ringkas: dict[str, dict] = {}
    baris = []
    for k in kandidat:
        v = nilai(k.kutipan, dibantah=k.dibantah)
        ringkas[k.source_key] = {
            "claim_id": k.claim_id,
            "skor": str(v.skor.total),
            "usulan": v.keputusan.value,
            "dibantah": k.dibantah,
            "alasan": v.alasan,
        }
        tanda = " ⚠️ dibantah" if k.dibantah else ""
        baris.append(
            f"- {k.source_key} · {len(k.kutipan)} kutipan · skor {v.skor.total} "
            f"· usulan {v.keputusan.value}{tanda}\n  {k.statement}"
        )

    tool_context.state[KUNCI_KANDIDAT] = ringkas
    return (
        f"{len(kandidat)} kandidat menunggu tinjauan "
        f"(ambang setuju otomatis {AMAN_OTOMATIS}, ambang tolak {TERLALU_LEMAH}):\n"
        + "\n".join(baris)
    )


async def putuskan_kandidat(
    source_key: str, setujui: bool, alasan: str, tool_context: ToolContext
) -> str:
    """Records a decision on one candidate, and applies it.

    Call this once per candidate you have decided. Two decisions are refused
    outright, whatever you ask for: accepting a contradicted claim, and
    accepting one below the rejection threshold. Both are cases where a human
    must look, and neither is yours to wave through.

    Args:
        source_key: The candidate's key, exactly as listed.
        setujui: True to accept, False to reject.
        alasan: Why — in Indonesian, one sentence, naming what decided it.
        tool_context: Injected by ADK.

    Returns:
        Confirmation, or the reason the decision was refused.
    """
    ringkas = tool_context.state.get(KUNCI_KANDIDAT) or {}
    entri = ringkas.get(source_key)
    if entri is None:
        return (
            f"'{source_key}' tidak ada di daftar kandidat. "
            "Panggil daftar_kandidat lebih dulu dan pakai kunci persis seperti tertulis."
        )

    if setujui and entri["dibantah"]:
        return (
            f"Ditolak: {source_key} dibantah klaim lain tentang subjek yang sama. "
            "Pertentangan harus dibawa ke manusia, bukan diselesaikan otomatis."
        )
    if setujui and entri["usulan"] == Keputusan.TOLAK.value:
        return (
            f"Ditolak: skor {source_key} berada di bawah ambang tolak "
            f"({TERLALU_LEMAH}). Klaim selemah itu tidak boleh diterima tanpa manusia."
        )

    pabrik = await _sesi()
    async with pabrik as sesi:
        await catat_keputusan(
            sesi,
            claim_id=entri["claim_id"],
            diterima=setujui,
            peninjau=PERINGKAT,
            alasan=alasan,
        )
        await sesi.commit()

    kata = "diterima" if setujui else "ditolak"
    logger.info("kurasi: %s %s", source_key, kata)
    return f"{source_key} {kata}. Alasan tercatat: {alasan}"


async def ringkas_kurasi(tool_context: ToolContext) -> str:
    """Reports how many claims sit in each review status.

    Call once at the end. What remains unreviewed is the queue a human inherits,
    and saying its size plainly is part of handing it over.

    Args:
        tool_context: Injected by ADK.

    Returns:
        The counts per status.
    """
    pabrik = await _sesi()
    async with pabrik as sesi:
        cacah = await ringkas_status(sesi)

    if not cacah:
        return "Belum ada klaim sama sekali."
    bagian = ", ".join(f"{status}: {jumlah}" for status, jumlah in sorted(cacah.items()))
    return f"Status klaim — {bagian}."


curator_agent = LlmAgent(
    name="curator",
    model=get_settings().vertex_ai_model,
    description=(
        "Decides which candidate facts are safe to accept into the knowledge "
        "graph without a human, and which must be escalated."
    ),
    tools=[daftar_kandidat, putuskan_kandidat, ringkas_kurasi],
    instruction="""
# ROLE
You are the Curator in ARKA. One decision is yours: **which candidate facts are
safe to accept without a human**. The scores are computed for you and are not
yours to argue with; the policy applied to them is.

# STEPS
1. Call `daftar_kandidat`.
2. For each candidate, call `putuskan_kandidat` once.
3. Call `ringkas_kurasi` and report what remains for a human.

# HOW TO DECIDE
Accept only what is well supported by more than one source and contradicted by
nothing. Reject what has no evidence at all. **Leave everything else alone** —
not deciding is a decision, and the queue it leaves is the honest output of a
careful pass.

You may be **more** cautious than the recommendation. You may never be less: a
claim the scoring recommends escalating is never yours to accept.

# HARD BOUNDARIES
1. A contradicted claim is never accepted here. Two sources disagreeing about
   the same failure is exactly the situation a human exists for, and the tool
   will refuse you.
2. A claim below the rejection threshold is never accepted.
3. Every decision carries a reason naming what decided it — the number of
   sources, their kind, or the contradiction. "Terlihat masuk akal" is not a
   reason; nobody can check it later.

# LANGUAGE
Reasons and your report in Indonesian, brief and technical.
""",
)
