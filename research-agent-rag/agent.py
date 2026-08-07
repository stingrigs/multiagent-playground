# ====================================
#  🔰 [RESEARCH AGENT] Agent
# ====================================

from config import Settings  # noqa: I001 - sets env vars before any ML import below

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from prompts import SYSTEM_PROMPT
from tools import (
    knowledge_search,
    list_files,
    read_file,
    read_url,
    web_search,
    write_report,
)

settings = Settings()

llm = ChatOpenAI(
    model=settings.model_name,
    api_key=settings.api_key,
    timeout=settings.llm_timeout,
)

tools = [knowledge_search, web_search, read_url, write_report, list_files, read_file]

memory = InMemorySaver()

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=memory,
)
