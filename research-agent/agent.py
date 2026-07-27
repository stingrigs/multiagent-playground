# ====================================
#  🔰 [RESEARCH AGENT] Agent
# ====================================

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from config import Settings
from prompts import SYSTEM_PROMPT
from tools import list_files, read_file, read_url, web_search, write_report

settings = Settings()

llm = ChatOpenAI(
    model=settings.model_name,
    api_key=settings.api_key,
)

tools = [web_search, read_url, write_report, list_files, read_file]

memory = InMemorySaver()

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=memory,
)
