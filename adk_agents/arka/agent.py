"""The full ARKA chain: scan the fleet, investigate, publish.

Scout decides what deserves attention, the investigator decides how far to
follow the evidence, and the reporter decides what the document says. Each hands
over through session state, so none of them needs to know the others exist.

This is the entry point a served runtime exposes — `adk api_server adk_agents`
picks it up alongside the individual agents, which stay available for demoing
one link at a time.
"""

from google.adk.agents import SequentialAgent

from app.agents.investigator import investigator_agent
from app.agents.reporter import reporter_agent
from app.agents.scout import scout_agent

root_agent = SequentialAgent(
    name="arka",
    description=(
        "Scans open equipment failures across the fleet, investigates the one "
        "that most deserves attention, and publishes the finding as a document."
    ),
    sub_agents=[scout_agent, investigator_agent, reporter_agent],
)
