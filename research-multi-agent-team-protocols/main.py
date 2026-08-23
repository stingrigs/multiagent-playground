# ====================================
#  🔰 [RESEARCH TEAM] Entry point
# ====================================

import asyncio
import json
from pathlib import Path

import httpx
from fastmcp import Client
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from agents import critic, planner, research
from config import Settings
from supervisor import build_supervisor

settings = Settings()

THREAD_ID = "session"
TRACE_PREVIEW = 120


def preview(text: str, limit: int = TRACE_PREVIEW) -> str:
    """Terminal display only — the log and the saved report get the full text."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"


# --- 🔻 Preflight: every hop is now a separate process


async def read_mcp_resource(url: str, resource: str) -> dict:
    """Resources are application-controlled — the REPL reads them, no agent does."""
    async with Client(url) as client:
        contents = await client.read_resource(resource)
        return json.loads(contents[0].text)


async def fetch_agent_card(base_url: str) -> dict:
    """A2A discovery is a plain HTTP GET, no SDK required."""
    async with httpx.AsyncClient(timeout=10) as http:
        response = await http.get(f"{base_url}/.well-known/agent-card.json")
        response.raise_for_status()
        return response.json()


def _unreachable(name: str, url: str, start_cmd: str, error: Exception) -> None:
    print(f"⚠️  {name} unreachable at {url}: {type(error).__name__}: {error}")
    print(f"    Start it with: {start_cmd}")


async def preflight() -> bool:
    """Checks all five ports and names the one that's down."""
    resources = {}
    mcp_servers = [
        (
            "SearchMCP",
            settings.search_mcp_url,
            "resource://knowledge-base-stats",
            "search_mcp",
        ),
        ("ReportMCP", settings.report_mcp_url, "resource://output-dir", "report_mcp"),
    ]
    for name, url, resource, script in mcp_servers:
        try:
            resources[name] = await read_mcp_resource(url, resource)
        except Exception as e:  # noqa: BLE001 - transport/handshake failures vary
            _unreachable(name, url, f"python mcp_servers/{script}.py", e)
            return False
        print(f"  ✅ {name:11} {url}")

    for module in (planner, research, critic):
        spec = module.SPEC
        url = f"http://{settings.host}:{spec.port}"
        try:
            card = await fetch_agent_card(url)
        except Exception as e:  # noqa: BLE001 - transport failures vary
            _unreachable(spec.name, url, "python a2a_servers.py", e)
            return False
        skills = ", ".join(s["name"] for s in card["skills"])
        print(f"  ✅ {card['name']:11} {url}  skills: {skills}")

    stats = resources["SearchMCP"]
    report = resources["ReportMCP"]
    print(
        f"\n  Knowledge base: {stats.get('documents')} documents, "
        f"{stats.get('chunks', 0)} chunks ({stats.get('status')})"
    )
    print(f"  Reports: {len(report.get('reports', []))} in {report.get('path')}")
    return True


# --- 🔻 Supervisor turn


async def stream_supervisor(supervisor, payload, config, trace: list) -> tuple:
    """Returns (pending Interrupt or None, saved report path or None).
    Prints a truncated preview per line; trace collects the untruncated text."""
    answered = False
    interrupt_ = None
    saved_path = None

    def emit(display: str, full: str) -> None:
        print(display)
        trace.append(full)

    emit("🤔 thinking...", "🤔 thinking...")
    try:
        async for chunk in supervisor.astream(payload, config=config):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupt_ = update[0]
                    continue
                # after_model middleware yields None every turn, not just on interrupt
                if not update:
                    continue
                for msg in update.get("messages", []):
                    # MCP tools answer in content blocks, not plain strings — .text flattens both
                    text = msg.text
                    if node == "model":
                        for call in msg.tool_calls or []:
                            emit(
                                f"  🔧 {call['name']}({preview(call['args'])})",
                                f"  🔧 {call['name']}({call['args']})",
                            )
                        if text:
                            emit(f"\n🤖 {text}", f"\n🤖 {text}")
                            if not msg.tool_calls:
                                answered = True
                    elif node == "tools":
                        emit(f"     ↳ {preview(text)}", f"     ↳ {text}")
                        if msg.name == "save_report" and text.startswith(
                            "Report saved to "
                        ):
                            saved_path = text.removeprefix("Report saved to ").strip()
                if node == "tools":
                    emit("🤔 thinking...", "🤔 thinking...")
    except GraphRecursionError:
        if not answered:
            emit(
                f"\n⚠️  Stopped after {settings.supervisor_recursion_limit} steps"
                " without finishing. Try narrowing the question.",
                f"\n⚠️  Stopped after {settings.supervisor_recursion_limit} steps"
                " without finishing.",
            )
        return None, saved_path
    return interrupt_, saved_path


# --- 🔻 HITL approval


def _decision_for(choice: str, feedback: str) -> dict:
    if choice == "approve":
        return {"type": "approve"}
    if choice == "edit":
        return {
            "type": "reject",
            "message": (
                "Not saved. Revise the report per this feedback, then call "
                f"save_report again: {feedback}"
            ),
        }
    return {
        "type": "reject",
        "message": (
            "The user cancelled the save. Do not call save_report again; "
            "summarize the findings in your reply instead."
        ),
    }


def review_actions(interrupt_) -> list[dict]:
    decisions = []
    for action in interrupt_.value["action_requests"]:
        args = action["args"]
        print(f"\n{'=' * 60}")
        print("⏸️  ACTION REQUIRES APPROVAL")
        print(f"{'=' * 60}")
        print(f"  Tool: {action.get('name')}")
        print(f"  File: {args.get('filename')}")
        print(f"  Preview: {preview(args.get('content', ''), limit=600)}")

        while True:
            try:
                choice = input("\n👉 approve / edit / reject: ").strip().lower()
            except EOFError:
                choice = "reject"
                break
            if choice in ("approve", "edit", "reject"):
                break
            print("  Type approve, edit, or reject.")

        feedback = ""
        if choice == "edit":
            try:
                feedback = input("✏️  Your feedback: ").strip()
            except EOFError:
                feedback = ""

        decisions.append(_decision_for(choice, feedback))
    return decisions


async def run_turn(supervisor, user_input: str) -> None:
    config = {
        "configurable": {"thread_id": THREAD_ID},
        "recursion_limit": settings.supervisor_recursion_limit,
    }
    payload = {"messages": [("user", user_input)]}
    trace: list[str] = []
    saved_path = None

    while True:
        interrupt_, path = await stream_supervisor(supervisor, payload, config, trace)
        saved_path = path or saved_path
        if interrupt_ is None:
            break
        payload = Command(resume={"decisions": review_actions(interrupt_)})

    if saved_path:
        try:
            Path(saved_path).with_suffix(".log").write_text(
                "\n".join(trace), encoding="utf-8"
            )
        except OSError as e:
            # the report is already saved by ReportMCP — a missing log is not a failed turn
            print(f"⚠️  Could not write the trace log: {e}")


async def main() -> None:
    print("Checking protocol endpoints...")
    if not await preflight():
        return

    supervisor = await build_supervisor()

    print("\nResearch Team (type 'exit' to quit)")
    print("-" * 40)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        try:
            await run_turn(supervisor, user_input)
        except Exception as e:  # noqa: BLE001 - one bad turn must not end the session
            print(f"\n⚠️  {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
