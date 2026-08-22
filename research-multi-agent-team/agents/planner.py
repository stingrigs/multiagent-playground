# ====================================
#  🔰 [RESEARCH TEAM] Planner Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent

from prompts import PLANNER_PROMPT
from schemas import ResearchPlan
from tools import knowledge_search, web_search

settings = Settings()

planner_agent = create_agent(
    model=make_llm(settings),
    tools=[web_search, knowledge_search],
    system_prompt=PLANNER_PROMPT,
    response_format=ResearchPlan,
    name="planner",
)
