"""Run the full publication chain in a live ADK session.

Everything else exercises the pieces: the tests cover the deterministic layers,
and `render_infografis.py` drives the visual path directly. This is the only
script that proves the chain itself — that `reporter` settles the blocks, that
`designer` reads them from session state rather than guessing, and that the
reviewers actually run between them.

    uv run python scripts/jalankan_penerbitan.py
    uv run python scripts/jalankan_penerbitan.py --hanya-designer

A session here is in-memory: no database, no deployment. What it does spend is
model calls and one drawing, so it is a deliberate act rather than part of the
test suite.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import app.agents  # noqa: F401 — installs the Vertex environment variables
from app.agents.designer import DEFAULT_PERSONA, KUNCI_BLOK, KUNCI_JEJAK, PERSONA
from app.agents.reporter import KUNCI_TEMUAN
from app.synthetic.finding_contoh import finding_contoh

APP = "arka-penerbitan"
USER = "pengembang"


async def run(hanya_designer: bool, persona: str) -> int:
    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from app.agents.qa import designer_terjaga, penerbitan_lengkap
    from app.reporting.blocks import URUTAN_BAKU

    finding = finding_contoh()
    agent = designer_terjaga if hanya_designer else penerbitan_lengkap

    sessions = InMemorySessionService()
    state = {KUNCI_TEMUAN: finding.model_dump(mode="json")}
    if hanya_designer:
        # Without the reporter in the chain, its handover has to be supplied —
        # otherwise the designer would be inventing the block selection it is
        # forbidden from making.
        state[KUNCI_BLOK] = list(URUTAN_BAKU)

    session = await sessions.create_session(app_name=APP, user_id=USER, state=state)
    runner = Runner(
        app_name=APP,
        agent=agent,
        session_service=sessions,
        artifact_service=InMemoryArtifactService(),
    )

    pesan = (
        f"Terbitkan infografis untuk temuan yang sudah ada di sesi ini, persona {persona}."
        if hanya_designer
        else f"Terbitkan memo untuk temuan di sesi ini, lalu infografisnya "
        f"untuk persona {persona}."
    )

    print(f"Agent    : {agent.name}")
    print(f"Persona  : {persona}")
    print(f"Temuan   : {finding.finding_id} — {finding.equipment_tag}")
    print("-" * 60)

    async for event in runner.run_async(
        user_id=USER,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=pesan)]),
    ):
        _report(event)

    akhir = await sessions.get_session(app_name=APP, user_id=USER, session_id=session.id)
    print("-" * 60)
    print("Artifact :", akhir.state.get("berkas_infografis") or "-")
    print("Jejak    :", akhir.state.get(KUNCI_JEJAK, "-"))
    return 0


def _report(event) -> None:
    """Print one line per meaningful step, not the whole event stream."""
    penulis = getattr(event, "author", "?")
    isi = getattr(event, "content", None)
    if not isi or not getattr(isi, "parts", None):
        return

    for bagian in isi.parts:
        panggilan = getattr(bagian, "function_call", None)
        jawaban = getattr(bagian, "function_response", None)
        if panggilan:
            print(f"[{penulis}] → {panggilan.name}({_ringkas(panggilan.args)})")
        elif jawaban:
            hasil = str(jawaban.response)
            print(f"[{penulis}] ← {jawaban.name}: {hasil[:160]}")
        elif getattr(bagian, "text", None):
            teks = bagian.text.strip()
            if teks:
                print(f"[{penulis}] {teks[:200]}")


def _ringkas(args) -> str:
    if not args:
        return ""
    ringkas = {k: (v[:40] if isinstance(v, str) else v) for k, v in dict(args).items()}
    return json.dumps(ringkas, ensure_ascii=False)[:120]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hanya-designer",
        action="store_true",
        help="lewati reporter; pakai urutan blok bawaan sebagai serah-terima",
    )
    parser.add_argument("--persona", default=DEFAULT_PERSONA, choices=sorted(PERSONA))
    args = parser.parse_args()
    return asyncio.run(run(args.hanya_designer, args.persona))


if __name__ == "__main__":
    raise SystemExit(main())
