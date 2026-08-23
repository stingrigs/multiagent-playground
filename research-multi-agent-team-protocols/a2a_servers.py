# ====================================
#  🔰 [RESEARCH TEAM] A2A Servers
# ====================================

import asyncio
import sys

import uvicorn
from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Role
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.errors import GraphRecursionError
from starlette.applications import Starlette

from agents import critic, planner, research
from agents.spec import AgentSpec
from config import Settings

settings = Settings()

JSONRPC_PATH = "/a2a/jsonrpc"


class LangChainAgentExecutor(AgentExecutor):
    """Runs a LangChain agent per A2A request; the A2A/LangChain bridge."""

    def __init__(self, spec: AgentSpec, lc_agent):
        self.spec = spec
        self.lc_agent = lc_agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        try:
            result = await self.lc_agent.ainvoke(
                {"messages": [{"role": "user", "content": query}]},
                config={"recursion_limit": settings.recursion_limit},
            )
        except GraphRecursionError:
            reply = self.spec.out_of_steps
        else:
            # response_format agents (planner, critic) answer with a Pydantic model;
            # A2A carries text, so serialize it instead of dropping it
            structured = result.get("structured_response")
            text = result["messages"][-1].text
            if structured is not None:
                reply = structured.model_dump_json(indent=2)
            elif self.spec.structured:
                # the caller expects JSON — say so rather than passing prose off as a verdict
                reply = f"{self.spec.name} returned no structured result: {text}"
            else:
                reply = text
        await event_queue.enqueue_event(new_text_message(reply, role=Role.ROLE_AGENT))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass  # nothing to clean up in this request/response agent


def build_agent_server(spec: AgentSpec, lc_agent) -> Starlette:
    """Serve a LangChain agent over A2A: Agent Card for discovery, JSON-RPC for calls."""
    card = AgentCard(
        name=spec.name,
        description=spec.description,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id=spec.skill_id,
                name=spec.skill_name,
                description=spec.skill_description,
                tags=spec.skill_tags,
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"http://{settings.host}:{spec.port}{JSONRPC_PATH}",
            )
        ],
    )
    handler = DefaultRequestHandler(
        agent_executor=LangChainAgentExecutor(spec, lc_agent),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    return Starlette(
        routes=[
            *create_agent_card_routes(agent_card=card),  # /.well-known/agent-card.json
            *create_jsonrpc_routes(request_handler=handler, rpc_url=JSONRPC_PATH),
        ]
    )


async def load_search_tools() -> list:
    """All three agents share one SearchMCP; each takes the subset its spec names."""
    client = MultiServerMCPClient(
        {"search": {"transport": "http", "url": settings.search_mcp_url}}
    )
    try:
        return await client.get_tools()
    except Exception as e:  # noqa: BLE001 - transport/handshake failures vary
        sys.exit(
            f"Cannot reach SearchMCP at {settings.search_mcp_url}: "
            f"{type(e).__name__}: {e}\n"
            "Start it first: python mcp_servers/search_mcp.py"
        )


async def main() -> None:
    tools = await load_search_tools()
    by_name = {t.name: t for t in tools}

    servers = []
    for module in (planner, research, critic):
        spec = module.SPEC
        missing = [n for n in spec.tool_names if n not in by_name]
        if missing:
            sys.exit(f"SearchMCP does not expose {missing} — needed by {spec.name}")

        agent = module.build([by_name[n] for n in spec.tool_names])
        app = build_agent_server(spec, agent)
        config = uvicorn.Config(
            app, host=settings.host, port=spec.port, log_level="warning"
        )
        servers.append(uvicorn.Server(config))
        print(
            f"  {spec.name:11} http://{settings.host}:{spec.port}"
            f"  tools: {', '.join(spec.tool_names)}"
        )

    print("\nAgent Cards at /.well-known/agent-card.json — Ctrl-C to stop")
    await asyncio.gather(*(s.serve() for s in servers))


if __name__ == "__main__":
    print(f"Connecting to SearchMCP at {settings.search_mcp_url}...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
