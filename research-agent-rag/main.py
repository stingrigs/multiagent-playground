# ====================================
#  🔰 [RESEARCH AGENT] Entry point
# ====================================

from langgraph.errors import GraphRecursionError

from agent import agent
from config import Settings

settings = Settings()

THREAD_ID = "session"
TRACE_PREVIEW = 120


def preview(text: str, limit: int = TRACE_PREVIEW) -> str:
    """Trace display only — the saved report is untouched."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"


def run_turn(user_input: str) -> None:
    config = {
        "configurable": {"thread_id": THREAD_ID},
        "recursion_limit": settings.recursion_limit,
    }
    answered = False

    print("🤔 thinking...")
    try:
        for chunk in agent.stream({"messages": [("user", user_input)]}, config=config):
            for node, payload in chunk.items():
                for msg in payload.get("messages", []):
                    if node == "model":
                        for call in msg.tool_calls or []:
                            print(f"  🔧 {call['name']}({preview(call['args'])})")
                        if msg.content:
                            print(f"\n🤖 {msg.content}")
                            # commentary alongside tool_calls isn't the final answer
                            if not msg.tool_calls:
                                answered = True
                    elif node == "tools":
                        print(f"     ↳ {preview(msg.content)}")
                if node == "tools":
                    print("🤔 thinking...")  # next model call; a pause here is normal
    except GraphRecursionError:
        if not answered:  # limit can trip on the same step that answered
            print(
                f"\n⚠️  Stopped after {settings.max_iterations} steps without an"
                " answer. Try narrowing the question."
            )


def main() -> None:
    print("Research Agent (type 'exit' to quit)")
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
