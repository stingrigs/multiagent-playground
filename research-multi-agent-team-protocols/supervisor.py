# ====================================
#  🔰 [RESEARCH TEAM] Supervisor
# ====================================

import uuid

import httpx
from a2a.client import ClientConfig, create_client
from a2a.helpers import get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import ToolRuntime, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver

from config import Settings, make_llm
from prompts import SUPERVISOR_PROMPT

settings = Settings()


async def call_a2a_agent(base_url: str, text: str) -> str:
    """create_client fetches the Agent Card itself, so base_url is enough."""
    async with httpx.AsyncClient(timeout=settings.a2a_timeout) as http_client:
        client = await create_client(
            base_url, client_config=ClientConfig(httpx_client=http_client)
        )
        message = Message(
            role=Role.ROLE_USER,
            message_id=str(uuid.uuid4()),
            parts=[Part(text=text)],
        )
        replies = []
        async for event in client.send_message(SendMessageRequest(message=message)):
            if event.HasField("message"):
                replies.append(get_message_text(event.message))
        return "\n".join(replies)


async def _delegate(base_url: str, agent: str, text: str) -> str:
    """Tools return error text rather than raising — the Supervisor adapts."""
    try:
        return await call_a2a_agent(base_url, text)
    except Exception as e:  # noqa: BLE001 - network/protocol failures vary
        return f"{agent} unreachable at {base_url}: {type(e).__name__}: {e}"


@tool
async def delegate_to_planner(request: str) -> str:
    """Break a research request into a structured research plan."""
    print("  📋 planning…")
    return await _delegate(settings.planner_url, "Planner", request)


@tool
async def delegate_to_researcher(request: str) -> str:
    """Execute a research plan; pass the plan and, on revision, the critic's feedback."""
    print("  🔎 researching…")
    return await _delegate(settings.researcher_url, "Researcher", request)


@tool
async def delegate_to_critic(findings: str, runtime: ToolRuntime) -> str:
    """Independently verify research findings; returns a structured critique."""
    print("  🧐 critiquing…")
    # last human msg = this turn's request (one long thread); HITL resume never adds a fake one
    request = next(
        (m.text for m in reversed(runtime.state["messages"]) if m.type == "human"), ""
    )
    prompt = f"Original request:\n{request}\n\nFindings to review:\n{findings}"
    return await _delegate(settings.critic_url, "Critic", prompt)


async def load_report_tool():
    """save_report lives on ReportMCP; HITL gates it by name once it's a LangChain tool."""
    client = MultiServerMCPClient(
        {"report": {"transport": "http", "url": settings.report_mcp_url}}
    )
    tools = await client.get_tools()
    save_report = next((t for t in tools if t.name == "save_report"), None)
    if save_report is None:
        raise RuntimeError(
            f"ReportMCP at {settings.report_mcp_url} exposes no save_report tool"
        )
    return save_report


async def build_supervisor():
    return create_agent(
        model=make_llm(settings),
        tools=[
            delegate_to_planner,
            delegate_to_researcher,
            delegate_to_critic,
            await load_report_tool(),
        ],
        system_prompt=SUPERVISOR_PROMPT.format(
            max_revision_rounds=settings.max_revision_rounds
        ),
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={"save_report": True},
                description_prefix="Report pending approval",
            ),
        ],
        checkpointer=InMemorySaver(),
        name="supervisor",
    )
