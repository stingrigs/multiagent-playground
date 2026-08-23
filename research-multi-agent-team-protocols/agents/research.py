# ====================================
#  🔰 [RESEARCH TEAM] Research Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent

from agents.spec import AgentSpec
from prompts import RESEARCH_PROMPT

settings = Settings()

SPEC = AgentSpec(
    name="Researcher",
    description="Executes a research plan and returns findings with sources.",
    skill_id="research",
    skill_name="Execute a research plan",
    skill_description=(
        "Runs the plan's queries against the knowledge base and the web, then "
        "returns findings organized by sub-topic, each with its source."
    ),
    skill_tags=["research", "web-search", "rag"],
    tool_names=("web_search", "read_url", "knowledge_search"),
    port=settings.researcher_port,
    structured=False,
    out_of_steps="Researcher ran out of steps; findings so far are incomplete.",
)


def build(tools):
    return create_agent(
        model=make_llm(settings),
        tools=tools,
        system_prompt=RESEARCH_PROMPT,
        name="researcher",
    )
