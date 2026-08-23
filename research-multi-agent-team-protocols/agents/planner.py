# ====================================
#  🔰 [RESEARCH TEAM] Planner Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent

from agents.spec import AgentSpec
from prompts import PLANNER_PROMPT
from schemas import ResearchPlan

settings = Settings()

SPEC = AgentSpec(
    name="Planner",
    description="Decomposes a research request into a structured research plan.",
    skill_id="plan",
    skill_name="Plan a research task",
    skill_description=(
        "Probes the knowledge base and the web, then returns a ResearchPlan: "
        "goal, search queries, sources to check, and output format."
    ),
    skill_tags=["planning", "decomposition"],
    tool_names=("web_search", "knowledge_search"),
    port=settings.planner_port,
    structured=True,
    out_of_steps=(
        "Planner ran out of steps. Proceed by researching the request directly."
    ),
)


def build(tools):
    return create_agent(
        model=make_llm(settings),
        tools=tools,
        system_prompt=PLANNER_PROMPT,
        response_format=ResearchPlan,
        name="planner",
    )
