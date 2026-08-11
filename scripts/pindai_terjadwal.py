"""Scheduled fleet scan — the unattended entry point.

Runs the screening decision over every open failure and reports what deserves
attention. No model is involved: this is the deterministic core alone, so a
scheduled run costs nothing but a database query and cannot drift.

    uv run python scripts/pindai_terjadwal.py            # human-readable
    uv run python scripts/pindai_terjadwal.py --json     # for a scheduler
    ARKA_STORE=bigquery uv run python scripts/pindai_terjadwal.py

Exit codes are meaningful, so a scheduler can act on them without parsing text:

    0  scan completed, nothing needs attention
    1  scan completed, at least one case deserves investigation
    2  scan failed — including a BigQuery copy that is stale against PostgreSQL

The split matters for how this gets deployed. A cron entry or Cloud Scheduler
job runs this, and only escalates to a full investigation — which does call a
model — when there is something to investigate. Screening every morning is
cheap; investigating every morning would not be.
"""

import argparse
import asyncio
import json
import sys

from app.bigquery.kesegaran import wajib_segar
from app.detection import store
from app.detection.investigation import rank_screened, screen_case


async def scan() -> list[dict]:
    # Menolak menjawab dari salinan yang basi. Pemindaian terjadwal justru yang
    # paling rentan: ia berjalan tanpa ditunggui, jadi tidak ada yang melihat
    # bahwa jawabannya berasal dari data kemarin.
    await wajib_segar()

    async with store.session() as session:
        open_cases = await store.find_open_cases(session)
        if not open_cases:
            return []

        documents = await store.find_documents(session)
        subsystems = store.load_subsystem_map()
        screened = []
        for case in open_cases:
            historical = await store.find_historical_cases(
                session,
                equipment_model=case.equipment_model,
                exclude_event_id=case.failure_event_id,
            )
            screened.append(
                screen_case(case, store.group_by_cause(historical, documents), subsystems)
            )

    return [
        {
            "equipment_tag": c.open_case.equipment_tag,
            "plant": c.open_case.plant,
            "open_since": c.open_case.started_on.isoformat(),
            "top_score": str(c.verdict.top_score),
            "decision": c.verdict.decision.value,
            "reason": c.verdict.reason,
            "worth_investigating": c.worth_investigating,
        }
        for c in rank_screened(screened)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan the fleet for cases worth investigating")
    parser.add_argument("--json", action="store_true", help="Emit JSON for a scheduler")
    argumen = parser.parse_args()

    try:
        hasil = asyncio.run(scan())
    except Exception as exc:  # noqa: BLE001 — a scheduler needs an exit code, not a trace
        print(f"Pemindaian gagal: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    layak = [c for c in hasil if c["worth_investigating"]]

    if argumen.json:
        print(json.dumps({"scanned": len(hasil), "shortlisted": layak}, indent=2))
    else:
        print(f"Memeriksa {len(hasil)} kegagalan terbuka.")
        for c in layak:
            print(
                f"  {c['equipment_tag']} di {c['plant']} — {c['decision']} "
                f"(terbuka sejak {c['open_since']})"
            )
        diabaikan = len(hasil) - len(layak)
        if diabaikan:
            print(f"  {diabaikan} diabaikan karena bukti di bawah ambang.")
        if not layak:
            print("  Tidak ada yang perlu diteruskan.")

    raise SystemExit(1 if layak else 0)


if __name__ == "__main__":
    main()
