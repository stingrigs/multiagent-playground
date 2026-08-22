# ====================================
#  🔰 [RESEARCH TEAM] Critic Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent

from prompts import CRITIC_PROMPT
from schemas import CritiqueResult
from tools import knowledge_search, read_url, web_search

settings = Settings()

critic_agent = create_agent(
    model=make_llm(settings),
    tools=[web_search, read_url, knowledge_search],
    system_prompt=CRITIC_PROMPT,
    response_format=CritiqueResult,
    name="critic",
)
