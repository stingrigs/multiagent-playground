# ====================================
#  🔰 [RESEARCH TEAM] Supervisor
# ====================================

from config import Settings, make_llm  # noqa: I001

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from agents.critic import critic_agent
from agents.planner import planner_agent
from agents.research import research_agent
from prompts import SUPERVISOR_PROMPT
from tools import save_report

settings = Settings()

_SUB_CFG = {"recursion_limit": settings.recursion_limit}


def _ask(agent, text: str):
    return agent.invoke(
        {"messages": [{"role": "user", "content": text}]}, config=_SUB_CFG
    )


@tool
def plan(request: str) -> str:
    """Break a research request into a structured research plan."""
    print("  📋 planning…")
    try:
        result = _ask(planner_agent, request)
    except GraphRecursionError:
        return "Planner ran out of steps. Proceed by researching the request directly."
    structured = result.get("structured_response")
    if structured is None:
        return f"Planner returned no plan: {result['messages'][-1].text}"
    return structured.model_dump_json(indent=2)


@tool
def research(request: str) -> str:
    """Execute a research plan; pass the plan and, on revision, the critic's feedback."""
    print("  🔎 researching…")
    try:
        result = _ask(research_agent, request)
    except GraphRecursionError:
        return "Researcher ran out of steps; findings below are incomplete."
    return result["messages"][-1].text


@tool
def critique(findings: str, runtime: ToolRuntime) -> str:
    """Independently verify research findings; returns a structured critique."""
    print("  🧐 critiquing…")
    # last human msg = this turn's request (one long thread); HITL resume never adds a fake one
    request = next(
        (m.text for m in reversed(runtime.state["messages"]) if m.type == "human"), ""
    )
    prompt = f"Original request:\n{request}\n\nFindings to review:\n{findings}"
    try:
        result = _ask(critic_agent, prompt)
    except GraphRecursionError:
        return "Critic ran out of steps; treat findings as unverified."
    structured = result.get("structured_response")
    if structured is None:
        return f"Critic returned no verdict: {result['messages'][-1].text}"
    return structured.model_dump_json(indent=2)


supervisor = create_agent(
    model=make_llm(settings),
    tools=[plan, research, critique, save_report],
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
