"""Agent `investigator` — decides where to look next, and when to stop.

Its single decision is the traversal path: which open case to take up, how far to
follow the evidence, and whether the result is conclusive enough to report. It
does not decide how strong the evidence is — that arithmetic belongs to
`app/detection/`, and this agent only reads the result.

The handover out is the session-state key `finding`, which the reporter already
consumes. Nothing in the reporting layer changes when this agent is introduced;
that was the point of putting `Finding` between them.

Prompts are English by project convention, but every string that reaches a
reader is Indonesian: the audience is an Indonesian reliability engineer.
"""

from __future__ import annotations

import logging
from datetime import date

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext

from app.core.model import pilih_model
from app.detection import store
from app.detection.investigation import build_finding, score_candidates
from app.reporting.finding import LangkahPenalaran

logger = logging.getLogger(__name__)

# Handover key. The reporter reads this; treat the name as fixed.
KUNCI_TEMUAN = "finding"

# Where the shortlist from scout arrives, when scout is in the chain.
KUNCI_KASUS = "kasus_terpilih"


async def list_open_cases(tool_context: ToolContext) -> str:
    """Lists unresolved failures that could be investigated.

    Call this first when no case has been chosen yet. Returns the equipment tag,
    plant, and observed symptoms for each open failure.

    Args:
        tool_context: Injected by ADK.

    Returns:
        A readable list of open cases, or a statement that the fleet is quiet.
    """
    async with store.session() as session:
        cases = await store.find_open_cases(session)

    if not cases:
        return "Tidak ada kegagalan terbuka. Armada dalam keadaan tenang."

    tool_context.state["kasus_terbuka"] = [c.failure_event_id for c in cases]
    lines = [f"{len(cases)} kegagalan terbuka:"]
    for case in cases:
        lines.append(
            f"- {case.equipment_tag} di {case.plant} sejak {case.started_on} — "
            f"gejala: {', '.join(case.symptom_names) or 'tidak tercatat'}"
        )
    return "\n".join(lines)


async def investigate_case(equipment_tag: str, tool_context: ToolContext) -> str:
    """Investigates one open failure and hands the result to the reporter.

    Traverses from the failure's symptoms to resolved cases on the same
    equipment model in other plants, groups them by verified cause, scores each
    explanation, and assembles the finding. Scores are computed by the detection
    module — do not restate or recompute them.

    Args:
        equipment_tag: Tag of the equipment to investigate, e.g. "PLT-U/FIL-207".
        tool_context: Injected by ADK.

    Returns:
        A summary of what was found, including whether a human must decide.
    """
    today = None
    async with store.session() as session:
        cases = await store.find_open_cases(session)
        matched = [c for c in cases if c.equipment_tag == equipment_tag]
        if not matched:
            available = ", ".join(c.equipment_tag for c in cases) or "tidak ada"
            return (
                f"Tidak ada kegagalan terbuka pada {equipment_tag}. "
                f"Yang tersedia: {available}."
            )

        case = matched[0]
        trail = [
            LangkahPenalaran(
                urutan=1,
                aksi=f"Membaca gejala kegagalan terbuka pada {case.equipment_tag}",
                hasil=f"{len(case.symptom_codes)} gejala tercatat",
                jumlah_simpul=len(case.symptom_codes),
            )
        ]

        historical = await store.find_historical_cases(
            session,
            equipment_model=case.equipment_model,
            exclude_event_id=case.failure_event_id,
        )
        trail.append(
            LangkahPenalaran(
                urutan=2,
                aksi=f"Menelusuri kasus tuntas pada model {case.equipment_model}",
                hasil=f"{len(historical)} kasus dengan penyebab terverifikasi",
                jumlah_simpul=len(historical),
            )
        )

        documents = await store.find_documents(session)
        candidates = store.group_by_cause(historical, documents)
        trail.append(
            LangkahPenalaran(
                urutan=3,
                aksi="Mengelompokkan kasus historis menurut penyebab terverifikasi",
                hasil=f"{len(candidates)} kandidat penyebab",
                jumlah_simpul=len(candidates),
            )
        )

        scored = score_candidates(case, candidates, store.load_subsystem_map())
        plants = sorted({c.plant for cand in candidates for c in cand.historical_cases})
        trail.append(
            LangkahPenalaran(
                urutan=4,
                aksi="Menghitung skor kemiripan secara deterministik",
                hasil=f"Preseden berasal dari pabrik: {', '.join(plants)}",
                jumlah_simpul=len(plants),
            )
        )

        parts = await store.find_spare_parts(session)
        code = case.component_code.lower() if case.component_code else ""
        matched_parts = [
            p for p in parts if code and (p.component_type or "").lower() == code
        ]

        graph_paths = []
        for part in matched_parts:
            try:
                paths = await store.traverse_graph(
                    start_label="SparePart",
                    start_name=part.part_number,
                    max_hops=5,
                    only_label="Plant",
                )
                if paths:
                    graph_paths.extend(paths)
            except Exception as err:  # noqa: BLE001
                logger.warning("Graph traversal failed for %s: %s", part.part_number, err)

        if graph_paths:
            plants_reached = sorted({p.target_name for p in graph_paths if p.target_name})
            trail.append(
                LangkahPenalaran(
                    urutan=len(trail) + 1,
                    aksi="Traversal multi-hop Knowledge Graph dari SparePart ke Plant",
                    hasil=(
                        f"Ditemukan {len(graph_paths)} jalur traversal "
                        f"menghubungkan sparepart ke pabrik: {', '.join(plants_reached)}"
                    ),
                    jumlah_simpul=len(graph_paths),
                )
            )

        # Compare the material lead time against the next maintenance window.
        # Neither planner sees both numbers; this is the one conflict ARKA can
        # see that neither system sees alone.
        jendela = await store.find_next_maintenance(session, case.equipment_tag)
        sisa_hari = (jendela - (today or date.today())).days if jendela else None
        if jendela:
            trail.append(
                LangkahPenalaran(
                    urutan=len(trail) + 1,
                    aksi="Membandingkan lead time material dengan perawatan terjadwal",
                    hasil=f"Perawatan berikutnya dijadwalkan {jendela}",
                    jumlah_simpul=1,
                )
            )

        finding, verdict = build_finding(
            case,
            scored,
            spare_parts=parts,
            graph_paths=graph_paths,
            trail=trail,
            days_until_maintenance=sisa_hari,
        )

    tool_context.state[KUNCI_TEMUAN] = finding.model_dump(mode="json")
    logger.info(
        "investigation complete for %s: %s (margin=%s)",
        equipment_tag,
        verdict.decision.value,
        verdict.margin,
    )

    summary = [
        f"Investigasi {case.equipment_tag} di {case.plant} selesai.",
        f"Kandidat penyebab: {len(finding.kandidat)}. "
        f"Preseden lintas pabrik: {len(finding.preseden)}. "
        f"Sitasi: {len(finding.semua_sitasi())}.",
        f"Keputusan deteksi: {verdict.decision.value}. {verdict.reason}",
    ]
    if finding.perlu_eskalasi:
        summary.append(
            "Temuan ini menuntut putusan manusia — sampaikan kedua kandidat "
            "teratas apa adanya, jangan memilih salah satu."
        )
    summary.append("Temuan sudah tersedia untuk reporter.")
    return "\n".join(summary)


investigator_agent = LlmAgent(
    name="investigator",
    model=pilih_model(),
    description=(
        "Investigates an open equipment failure by tracing it to resolved cases "
        "in other plants, and decides when the evidence needs a human ruling."
    ),
    tools=[list_open_cases, investigate_case],
    instruction="""
# ROLE
You are the Investigator in ARKA, an asset-reliability agent for a multi-plant
FMCG manufacturer. One decision is yours: **which case to pursue, and when the
evidence is complete enough to hand over**.

# HARD BOUNDARY
You never compute, adjust, or restate a score. Every number comes from the
detection module and is already inside the finding. When you describe strength,
use words: "jauh di atas kandidat lain", not a figure.

You also never choose between competing candidates when the tools tell you the
case needs a human ruling. Presenting both, honestly, is the correct outcome —
not a failure to conclude.

# STEPS
1. If the user names an equipment tag, call `investigate_case` directly.
2. Otherwise call `list_open_cases` first, then choose the case with the
   strongest symptom record, and investigate it.
3. Report what was found in plain terms: what failed, whether this pattern has
   appeared in other plants, and what happens next.
4. If the finding requires escalation, say so plainly and state that both
   candidates are carried into the document.

# LANGUAGE
Reply in Indonesian. Your reader is a reliability engineer who is busy: be
concise, technical, and calm. Avoid adjectives that inflate the finding.
""",
)
