# ====================================
#  🔰 [RESEARCH TEAM] Entry point
# ====================================

import traceback
from pathlib import Path

from langfuse import observe, propagate_attributes
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from config import Settings
from observability import SESSION_ID, TAGS, USER_ID, handler, langfuse
from supervisor import supervisor

settings = Settings()

THREAD_ID = SESSION_ID
TRACE_PREVIEW = 120


def preview(text: str, limit: int = TRACE_PREVIEW) -> str:
    """Terminal display only — the log and the saved report get the full text."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"


def stream_supervisor(payload, config, trace: list) -> tuple:
    """Returns (pending Interrupt or None, final answer text, saved report content or None,
    saved report filename or None). Prints a truncated preview per line; trace collects
    the untruncated text."""
    final_text = ""
    interrupt_ = None
    pending_content = None  # captured on the tool call; not yet approved
    report_content = None  # confirmed once the tools node reports the write
    report_name = None

    def emit(display: str, full: str) -> None:
        print(display)
        trace.append(full)

    emit("🤔 thinking...", "🤔 thinking...")
    try:
        for chunk in supervisor.stream(payload, config=config):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    interrupt_ = update[0]
                    continue
                # after_model middleware yields None every turn, not just on interrupt
                if not update:
                    continue
                for msg in update.get("messages", []):
                    if node == "model":
                        for call in msg.tool_calls or []:
                            emit(
                                f"  🔧 {call['name']}({preview(call['args'])})",
                                f"  🔧 {call['name']}({call['args']})",
                            )
                            if call["name"] == "save_report":
                                pending_content = call["args"].get("content")
                        if msg.content:
                            emit(f"\n🤖 {msg.content}", f"\n🤖 {msg.content}")
                            if not msg.tool_calls:
                                final_text = msg.content
                    elif node == "tools":
                        emit(f"     ↳ {preview(msg.content)}", f"     ↳ {msg.content}")
                        if msg.name == "save_report" and msg.content.startswith(
                            "Report saved to "
                        ):
                            saved_path = msg.content.removeprefix(
                                "Report saved to "
                            ).strip()
                            report_content = pending_content
                            report_name = Path(saved_path).name
                if node == "tools":
                    emit("🤔 thinking...", "🤔 thinking...")
    except GraphRecursionError:
        if not final_text:
            emit(
                f"\n⚠️  Stopped after {settings.supervisor_recursion_limit} steps"
                " without finishing. Try narrowing the question.",
                f"\n⚠️  Stopped after {settings.supervisor_recursion_limit} steps"
                " without finishing.",
            )
        return None, final_text, report_content, report_name
    return interrupt_, final_text, report_content, report_name


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
        print(f"\n{args.get('content', '')}\n")

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


@observe(name="research-turn")
def run_turn(user_input: str) -> str:
    """Returns the saved report, or the chat answer if nothing was saved.
    @observe records it as the trace output — what the evaluators read as {{output}}."""
    config = {
        "configurable": {"thread_id": THREAD_ID},
        "recursion_limit": settings.supervisor_recursion_limit,
        "callbacks": [handler],
    }
    payload = {"messages": [("user", user_input)]}
    trace: list[str] = []
    report_content = None
    report_name = None
    final_text = ""

    with propagate_attributes(session_id=SESSION_ID, user_id=USER_ID, tags=TAGS):
        while True:
            interrupt_, text, content, name = stream_supervisor(payload, config, trace)
            final_text = text or final_text
            report_content = content or report_content
            report_name = name or report_name
            if interrupt_ is None:
                break
            payload = Command(resume={"decisions": review_actions(interrupt_)})

    if report_content is None:
        return final_text

    log_name = Path(Path(report_name).name).with_suffix(".log")
    (Path(settings.output_dir) / log_name).write_text(
        "\n".join(trace), encoding="utf-8"
    )
    return report_content


def main() -> None:
    print("Research Team (type 'exit' to quit)")
    print(f"Langfuse session: {SESSION_ID}")
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
            run_turn(user_input)
        except Exception:  # noqa: BLE001 - one bad turn must not end the session
            traceback.print_exc()
        finally:
            langfuse.flush()  # spans are batched; push them before the next prompt


if __name__ == "__main__":
    main()
