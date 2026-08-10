# ====================================
#  🔰 [RESEARCH TEAM] Research Agent
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent

from prompts import RESEARCH_PROMPT
from tools import knowledge_search, read_url, web_search

settings = Settings()

research_agent = create_agent(
    model=make_llm(settings),
    tools=[web_search, read_url, knowledge_search],
    system_prompt=RESEARCH_PROMPT,
    name="researcher",
)
