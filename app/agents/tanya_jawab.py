"""Retrieval and question-answering — the surface for a question a human asks.

Two agents, two decisions, kept apart on purpose (Principle V):

* `retriever` decides **what to fetch** — how to phrase the search, whether to
  widen it, and when the evidence gathered is enough.
* `answerer` decides **what the evidence supports** — and, just as often, that
  it supports nothing and the honest reply is to say so.

Neither replaces the autonomous chain. `Scout → Investigator → Reporter` answers
the questions ARKA raises by itself; this answers the ones an engineer types.
They share the same knowledge and run side by side — FR-014, and the reason the
constitution refuses to let ARKA be called a chatbot.

Prompts are English; every string a reader sees is Indonesian.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools.tool_context import ToolContext

from app.core.config import get_settings
from app.retrieval.graphrag import as_prompt_context, retrieve

logger = logging.getLogger(__name__)

# Where the retriever leaves what it found, and the answerer picks it up.
KUNCI_KONTEKS = "konteks_retrieval"


async def cari_konteks(pertanyaan: str, tool_context: ToolContext) -> str:
    """Searches documents by meaning and traverses the graph around what it finds.

    Use the engineer's own wording — the search matches meaning, not keywords,
    so rephrasing into official vocabulary loses the very signal it needs.

    Args:
        pertanyaan: The question, in the words it was asked.
        tool_context: Injected by ADK.

    Returns:
        The gathered context, or a statement that nothing was close enough.
    """
    konteks = retrieve(pertanyaan)
    tool_context.state[KUNCI_KONTEKS] = {
        "pertanyaan": pertanyaan,
        "sitasi": konteks.citations,
        "pabrik": konteks.plants,
        "jumlah_potongan": len(konteks.chunks),
        "jumlah_fakta": len(konteks.facts),
        "kosong": konteks.is_empty,
        "teks": as_prompt_context(konteks),
    }

    if konteks.is_empty:
        logger.info("no context for: %s", pertanyaan[:60])
        return (
            "Tidak ada dokumen maupun kasus yang cukup dekat dengan pertanyaan ini. "
            "Sampaikan apa adanya bahwa pengetahuan yang tersedia tidak menjawabnya — "
            "jangan menyusun jawaban dari dugaan."
        )

    return (
        f"Ditemukan {len(konteks.chunks)} kutipan dokumen dan "
        f"{len(konteks.facts)} fakta graph dari pabrik: "
        f"{', '.join(konteks.plants) or 'tidak ada'}.\n\n"
        + as_prompt_context(konteks)
    )


async def perluas_pencarian(istilah_lain: str, tool_context: ToolContext) -> str:
    """Searches again with different wording when the first attempt found nothing.

    Call this at most once, with genuinely different phrasing — a synonym of the
    symptom, or the component involved. Repeating the same question in new
    clothes wastes a turn and returns the same emptiness.

    Args:
        istilah_lain: A different phrasing of the same question.
        tool_context: Injected by ADK.

    Returns:
        The gathered context, or confirmation that the knowledge simply is absent.
    """
    hasil = await cari_konteks(istilah_lain, tool_context)
    if "Tidak ada dokumen" in hasil:
        return (
            "Pencarian ulang juga tidak menemukan dasar. Ini bukan kegagalan "
            "pencarian — pengetahuan itu memang belum ada. Katakan demikian."
        )
    return hasil


retriever_agent = LlmAgent(
    name="retriever",
    model=get_settings().vertex_ai_model,
    description=(
        "Decides what to retrieve for a question — semantic document search "
        "combined with graph traversal around what it finds."
    ),
    tools=[cari_konteks, perluas_pencarian],
    instruction="""
# ROLE
You are the Retriever in ARKA. One decision is yours: **what evidence to gather
for the question in front of you**, and when what you have is enough.

# STEPS
1. Call `cari_konteks` with the engineer's own words. Do not translate the
   question into official terminology first — the search matches meaning, and
   the mismatch between how people speak and how records are written is exactly
   what it exists to bridge.
2. If nothing was close enough, you may call `perluas_pencarian` **once** with
   genuinely different phrasing — the component involved, or a synonym of the
   symptom.
3. Report what you gathered in one or two sentences. Do not answer the question;
   that is not your decision.

# HARD BOUNDARY
An empty result is a real finding, not a failure to try hard enough. Never
invent search terms to force a hit, and never present a weak match as though it
were relevant. The answerer relies on you to have been strict.

# LANGUAGE
Reply in Indonesian, briefly.
""",
)


answerer_agent = LlmAgent(
    name="answerer",
    model=get_settings().vertex_ai_model,
    description=(
        "Answers a reliability question from retrieved evidence, with citations, "
        "and says plainly when the evidence does not support an answer."
    ),
    instruction="""
# ROLE
You are the Answerer in ARKA. You answer a reliability engineer's question using
**only** the context the retriever gathered. One decision is yours: **what the
evidence supports** — including, often, that it supports nothing.

# THE CONTEXT
{konteks_retrieval?}

# HARD BOUNDARIES
1. **Answer only from the context above.** If it is empty or does not cover the
   question, say so plainly: the knowledge is not there. Never fill the gap from
   general knowledge about pumps, seals, or maintenance — a confident wrong
   answer about a machine is worse than no answer.
2. **Cite.** Every substantive claim names the document it rests on, using the
   identifier as it appears in the context, e.g. [DOC-INS-2024-0417].
3. **Never resolve a close call.** When the evidence points at two causes with
   similar support, present both and say the choice needs a human. Refusing to
   guess is the correct outcome, not an incomplete one.
4. **Never invent or recompute a number.** Figures appear only if they are in
   the context, written exactly as they appear there.

# SHAPE
Answer first, in two or three sentences. Then the supporting evidence, each line
carrying its citation. If something is missing that the engineer would need,
say what it is.

# LANGUAGE
Indonesian, technical and calm. Your reader is busy and knows the domain.
""",
)


# Retrieval then answering. The split keeps one decision per agent: what to
# gather, and what it supports.
tanya_jawab_agent = SequentialAgent(
    name="tanya_jawab",
    description=(
        "Answers a reliability engineer's question from the knowledge base, "
        "with citations, and admits when the knowledge is not there."
    ),
    sub_agents=[retriever_agent, answerer_agent],
)
