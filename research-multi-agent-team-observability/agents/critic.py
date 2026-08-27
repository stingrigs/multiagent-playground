# ====================================
#  🔰 [RESEARCH TEAM] Critic Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from datetime import date

from langchain.agents import create_agent

from prompts import CRITIC, load_prompt
from schemas import CritiqueResult
from tools import knowledge_search, read_url, web_search

settings = Settings()
today = date.today().isoformat()  # noqa: DTZ011 - freshness anchor for a local REPL, not a server

critic_agent = create_agent(
    model=make_llm(settings),
    tools=[web_search, read_url, knowledge_search],
    system_prompt=load_prompt(CRITIC, today=today),
    response_format=CritiqueResult,
    name="critic",
)
