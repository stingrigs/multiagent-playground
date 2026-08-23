# ====================================
#  🔰 [RESEARCH TEAM] Critic Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent

from agents.spec import AgentSpec
from prompts import CRITIC_PROMPT
from schemas import CritiqueResult

settings = Settings()

SPEC = AgentSpec(
    name="Critic",
    description="Independently verifies research findings and returns a verdict.",
    skill_id="critique",
    skill_name="Review research findings",
    skill_description=(
        "Re-checks load-bearing claims through the same sources, then returns a "
        "CritiqueResult: verdict, freshness, completeness, structure, and gaps."
    ),
    skill_tags=["review", "fact-checking"],
    tool_names=("web_search", "read_url", "knowledge_search"),
    port=settings.critic_port,
    structured=True,
    out_of_steps="Critic ran out of steps; treat the findings as unverified.",
)


def build(tools):
    return create_agent(
        model=make_llm(settings),
        tools=tools,
        system_prompt=CRITIC_PROMPT,
        response_format=CritiqueResult,
        name="critic",
    )
