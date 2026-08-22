# ====================================
#  🔰 [RESEARCH TEAM] Entry point
# ====================================

from pathlib import Path

from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from config import Settings
from supervisor import supervisor

settings = Settings()

THREAD_ID = "session"
TRACE_PREVIEW = 120


def preview(text: str, limit: int = TRACE_PREVIEW) -> str:
    """Terminal display only — the log and the saved report get the full text."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"


def stream_supervisor(payload, config, trace: list) -> tuple:
    """Returns (pending Interrupt or None, answered, saved report path or None).
    Prints a truncated preview per line; trace collects the untruncated text."""
    answered = False
    interrupt_ = None
    saved_path = None

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
                        if msg.content:
                            emit(f"\n🤖 {msg.content}", f"\n🤖 {msg.content}")
                            if not msg.tool_calls:
                                answered = True
                    elif node == "tools":
                        emit(f"     ↳ {preview(msg.content)}", f"     ↳ {msg.content}")
                        if msg.name == "save_report" and msg.content.startswith(
                            "Report saved to "
                        ):
                            saved_path = msg.content.removeprefix(
                                "Report saved to "
                            ).strip()
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
        return None, answered, saved_path
    return interrupt_, answered, saved_path


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


def run_turn(user_input: str) -> None:
    config = {
        "configurable": {"thread_id": THREAD_ID},
        "recursion_limit": settings.supervisor_recursion_limit,
    }
    payload = {"messages": [("user", user_input)]}
    trace: list[str] = []
    saved_path = None

    while True:
        interrupt_, _, path = stream_supervisor(payload, config, trace)
        saved_path = path or saved_path
        if interrupt_ is None:
            break
        payload = Command(resume={"decisions": review_actions(interrupt_)})

    if saved_path:
        Path(saved_path).with_suffix(".log").write_text(
            "\n".join(trace), encoding="utf-8"
        )


def main() -> None:
    print("Research Team (type 'exit' to quit)")
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
        except Exception as e:  # noqa: BLE001 - one bad turn must not end the session
            print(f"\n⚠️  {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
