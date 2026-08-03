# ====================================
#  🔰 [RESEARCH AGENT] Entry point
# ====================================

from agent import Agent

TRACE_PREVIEW = 120


def preview(value) -> str:
    """Shorten a value for the terminal trace. Display only — what gets
    written to a report is untouched."""
    flat = " ".join(str(value).split())
    return flat if len(flat) <= TRACE_PREVIEW else f"{flat[:TRACE_PREVIEW]}…"


def render(event: str, payload) -> None:
    if event == "thinking":
        print("🤔 thinking...")
    elif event == "thought":
        text = str(payload).removeprefix("Thought:").strip()
        print(f"💭 Thought: {text}")
    elif event == "tool_call":
        name, args = payload
        print(f"🔧 Tool call: {name}({preview(args)})")
    elif event == "tool_result":
        _, result = payload
        print(f"📎 Result: {preview(result)}")
    elif event == "wrap_up":
        print(f"⏳ {payload} rounds left — wrapping up.")
    elif event == "answer":
        print(f"\n🤖 {payload}")
    elif event == "limit_reached":
        # An answer usually still follows: the loop makes one final call
        # with tools disabled after emitting this.
        print(
            f"\n⚠️  Hit the {payload}-round limit — concluding from what was gathered."
        )


def main() -> None:
    print("Research Agent (type 'exit' to quit)")
    print("-" * 40)

    # One Agent for the whole session — its messages list is the memory.
    agent = Agent()

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
            for event, payload in agent.run(user_input):
                render(event, payload)
        except KeyboardInterrupt:
            # Abandon this turn, not the whole session.
            agent.abort_incomplete_calls()
            print("\n⚠️  Interrupted. Ask something else, or 'exit' to quit.")
        except Exception as e:  # noqa: BLE001 - one bad turn must not end the session
            agent.abort_incomplete_calls(reason=f"Aborted: {type(e).__name__}: {e}")
            print(f"\n⚠️  {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
