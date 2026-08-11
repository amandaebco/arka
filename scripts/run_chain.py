"""Run the full chain against the seeded database: investigate, then publish.

Nobody names the finding. The investigator reads open failures from the graph,
scores them, and writes a `Finding` into session state; the reporter picks it up
from the key it has always read and publishes a document.

    uv run python scripts/run_chain.py
    uv run python scripts/run_chain.py --tag PLT-G/FIL-412

Prerequisites: `docker compose up -d`, `alembic upgrade head`, and
`python -m app.synthetic.generator --reset`.
"""

import argparse
import asyncio

from google.adk.agents import SequentialAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.investigator import investigator_agent
from app.agents.reporter import reporter_agent
from app.bigquery.kesegaran import wajib_segar

APP_NAME = "arka_chain"


def build_chain() -> SequentialAgent:
    """Investigator hands over through session state; reporter reads it there."""
    return SequentialAgent(
        name="arka_chain",
        description="Investigate an open failure and publish the finding.",
        sub_agents=[investigator_agent, reporter_agent],
    )


async def run(tag: str | None) -> None:
    # Sebelum satu pun model dipanggil. Menerbitkan memo dari data basi lebih
    # mahal daripada gagal di sini: memo tidak tahu ia salah, dan pembacanya
    # tidak punya cara membedakannya dari memo yang benar.
    await wajib_segar()

    runner = InMemoryRunner(agent=build_chain(), app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id="demo"
    )

    request = (
        f"Selidiki kegagalan pada {tag} lalu terbitkan memo investigasinya."
        if tag
        else "Periksa kegagalan terbuka, selidiki yang paling layak, lalu terbitkan memonya."
    )

    async for event in runner.run_async(
        user_id="demo",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=request)]),
    ):
        if not (event.content and event.content.parts):
            continue
        for part in event.content.parts:
            if part.function_call:
                print(f"[{event.author}] → {part.function_call.name}")
            elif part.function_response:
                response = str(part.function_response.response)
                print(f"[{event.author}] ← {response[:220]}")
            elif part.text and part.text.strip():
                print(f"[{event.author}] {part.text.strip()[:300]}")

    artifacts = await runner.artifact_service.list_artifact_keys(
        app_name=APP_NAME, user_id="demo", session_id=session.id
    )
    print(f"\nArtifact: {artifacts or 'tidak ada'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ARKA chain end to end")
    parser.add_argument("--tag", help="Equipment tag to investigate; omit to let ARKA choose")
    asyncio.run(run(parser.parse_args().tag))


if __name__ == "__main__":
    main()
