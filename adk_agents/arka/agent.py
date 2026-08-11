"""The full ARKA chain: scan the fleet, investigate, publish.

Scout decides what deserves attention, the investigator decides how far to
follow the evidence, and the reporter decides what the document says. Each hands
over through session state, so none of them needs to know the others exist.

This is the entry point a served runtime exposes — `adk api_server adk_agents`
picks it up alongside the individual agents, which stay available for demoing
one link at a time.
"""

from copy import deepcopy

from google.adk.agents import BaseAgent, SequentialAgent

from app.agents.investigator import investigator_agent
from app.agents.reporter import reporter_agent
from app.agents.scout import scout_agent


def _lepas(agent: BaseAgent) -> BaseAgent:
    """Return a detached copy, so this chain never competes for ownership.

    ADK lets an agent instance have exactly one parent. `reporter_agent` is also
    a child of the quality loop in `app.agents.qa`, so whichever module was
    imported second used to raise `already has a parent` and take its whole
    endpoint down with it — `designer`, `reporter`, and `penerbitan` all returned
    500 while `arka` happened to load first and survive.

    Copying here rather than in `qa` keeps the fix where the duplication is: this
    module is a thin serving wrapper, and the quality loop is the definition.
    """
    salinan = deepcopy(agent)
    salinan.parent_agent = None
    return salinan


root_agent = SequentialAgent(
    name="arka",
    description=(
        "Scans open equipment failures across the fleet, investigates the one "
        "that most deserves attention, and publishes the finding as a document."
    ),
    sub_agents=[_lepas(scout_agent), _lepas(investigator_agent), _lepas(reporter_agent)],
)
