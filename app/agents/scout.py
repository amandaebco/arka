"""Agent `scout` — decides what is worth investigating.

Scout is the reason ARKA is an agent rather than a query tool: nobody tells it
which failure to look at. It scans every open failure across the fleet, scores
each against resolved cases elsewhere, and hands the investigator a shortlist.

Its single decision is admission — what clears the bar. It never explains *why*
a cause is likely; that reasoning belongs to the investigator, and duplicating
it here would give two modules the same decision.

Two behaviours are load-bearing and stated as rules rather than preferences:

* An empty shortlist is a successful outcome. A quiet fleet is good news, and an
  agent that lowers its bar to avoid returning nothing is worse than useless.
* What was skipped is always reported. A filter nobody can audit is a filter
  nobody should trust.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext

from app.core.config import get_settings
from app.detection import store
from app.detection.investigation import rank_screened, screen_case
from app.detection.scoring import THRESHOLD_IGNORE

logger = logging.getLogger(__name__)

# Handover key into the investigator.
KUNCI_KASUS = "kasus_terpilih"


async def scan_fleet(tool_context: ToolContext) -> str:
    """Scans every open failure across the fleet and shortlists what deserves attention.

    Scores each open failure against resolved cases on the same equipment model
    in other plants. Cases below the ignore threshold are left out, and their
    count is reported so the filter can be questioned.

    Args:
        tool_context: Injected by ADK.

    Returns:
        The shortlist with each case's decision, plus how many were skipped.
    """
    async with store.session() as session:
        open_cases = await store.find_open_cases(session)
        if not open_cases:
            tool_context.state[KUNCI_KASUS] = []
            return "Tidak ada kegagalan terbuka di seluruh armada. Tidak ada yang perlu diselidiki."

        documents = await store.find_documents(session)
        subsystems = store.load_subsystem_map()

        screened = []
        for case in open_cases:
            historical = await store.find_historical_cases(
                session,
                equipment_model=case.equipment_model,
                exclude_event_id=case.failure_event_id,
            )
            candidates = store.group_by_cause(historical, documents)
            screened.append(screen_case(case, candidates, subsystems))

    ranked = rank_screened(screened)
    shortlist = [c for c in ranked if c.worth_investigating]
    skipped = [c for c in ranked if not c.worth_investigating]

    tool_context.state[KUNCI_KASUS] = [
        {
            "equipment_tag": c.open_case.equipment_tag,
            "plant": c.open_case.plant,
            "top_score": str(c.verdict.top_score),
            "decision": c.verdict.decision.value,
        }
        for c in shortlist
    ]
    tool_context.state["kasus_diabaikan"] = [
        {
            "equipment_tag": c.open_case.equipment_tag,
            "top_score": str(c.verdict.top_score),
            "reason": c.verdict.reason,
        }
        for c in skipped
    ]
    logger.info("scanned %d open cases, %d shortlisted", len(ranked), len(shortlist))

    lines = [f"Memeriksa {len(ranked)} kegagalan terbuka di seluruh armada."]
    if shortlist:
        lines.append(f"{len(shortlist)} layak diselidiki:")
        for c in shortlist:
            lines.append(
                f"- {c.open_case.equipment_tag} di {c.open_case.plant} "
                f"({c.verdict.decision.value}) — {c.verdict.reason}"
            )
    else:
        lines.append(
            "Tidak ada yang melewati ambang. Tidak ada temuan yang perlu diteruskan."
        )
    if skipped:
        lines.append(f"{len(skipped)} diabaikan karena bukti di bawah ambang.")
    return "\n".join(lines)


async def explain_skip(equipment_tag: str, tool_context: ToolContext) -> str:
    """Explains why one open failure was left out of the shortlist.

    Call this when the user asks about a case that was not taken up.

    Args:
        equipment_tag: Tag of the equipment that was skipped.
        tool_context: Injected by ADK.

    Returns:
        The recorded reason, or a note that the case was shortlisted after all.
    """
    skipped = tool_context.state.get("kasus_diabaikan") or []
    for entry in skipped:
        if entry["equipment_tag"] == equipment_tag:
            return (
                f"{equipment_tag} tidak diteruskan. Kandidat terkuatnya berada di "
                f"bawah ambang pengabaian. {entry['reason']}"
            )

    shortlisted = tool_context.state.get(KUNCI_KASUS) or []
    if any(entry["equipment_tag"] == equipment_tag for entry in shortlisted):
        return f"{equipment_tag} justru masuk daftar pendek dan layak diselidiki."
    return f"{equipment_tag} tidak ada dalam pemeriksaan terakhir. Jalankan pemindaian lebih dulu."


scout_agent = LlmAgent(
    name="scout",
    model=get_settings().vertex_ai_model,
    description=(
        "Scans open failures across the fleet and decides which deserve "
        "investigation, reporting what it skipped and why."
    ),
    tools=[scan_fleet, explain_skip],
    instruction=f"""
# ROLE
You are the Scout in ARKA. One decision is yours: **what deserves a human's
attention**. Nobody hands you a case to look at — you find them.

# HARD BOUNDARY
You never explain why a failure happened. That is the investigator's decision,
and duplicating it here would give two modules the same job. You report only
that a case clears the bar, and how clearly.

You never compute or restate a score. The screening tool has already done the
arithmetic; describe strength in words, not figures.

# WHAT AN EMPTY SHORTLIST MEANS
A quiet fleet is a successful outcome, not a failure to find something. Never
lower the bar to produce a result. If nothing clears the threshold (currently
{THRESHOLD_IGNORE}), say so plainly and stop.

# STEPS
1. Call `scan_fleet`.
2. Report what you examined, what cleared the bar, and how many you set aside.
   Always mention the skipped count — a filter nobody can question is a filter
   nobody should trust.
3. If asked about a specific case that was set aside, call `explain_skip`.
4. Hand the shortlist onward without ranking it further; the order is already
   decided by evidence strength and how long each case has waited.

# LANGUAGE
Reply in Indonesian, concisely. Your reader is a reliability engineer deciding
where to spend the morning.
""",
)
