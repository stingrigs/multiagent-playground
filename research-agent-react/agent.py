# ====================================
#  🔰 [RESEARCH AGENT] ReAct loop
# ====================================

import json
from collections.abc import Iterator
from typing import Any

from openai import OpenAI
from openai.types.responses import Response

from config import settings
from prompts import SYSTEM_PROMPT
from tools import TOOL_REGISTRY, TOOL_SCHEMAS

Event = tuple[str, Any]

# Schemas and functions are maintained by hand — make sure every schema has
# an implementation and vice versa, before the model gets offered either.
assert {s["name"] for s in TOOL_SCHEMAS} == set(TOOL_REGISTRY), (
    "tool schemas and registry disagree"
)


def _as_text(result: object) -> str:
    """Tool output has to reach the API as a string."""
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


class Agent:
    """Holds the conversation. One instance == one session's memory."""

    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            timeout=settings.llm_timeout,
        )
        self.messages: list[Any] = []

    def _ask_model(self, tool_choice: str = "auto") -> Response:
        response = self.client.responses.create(
            model=settings.model_name,
            instructions=SYSTEM_PROMPT,
            input=self.messages,
            tools=TOOL_SCHEMAS,
            tool_choice=tool_choice,
        )
        self.messages.extend(response.output)
        return response

    def abort_incomplete_calls(self, reason: str = "Interrupted by user.") -> None:
        """A function_call left without a function_call_output makes the API
        reject every later request in the session."""
        started = {
            item.call_id
            for item in self.messages
            if not isinstance(item, dict) and item.type == "function_call"
        }
        finished = {
            item["call_id"]
            for item in self.messages
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        }
        for call_id in started - finished:
            self.messages.append(
                {"type": "function_call_output", "call_id": call_id, "output": reason}
            )

    def _call_tool(self, name: str, raw_args: str) -> str:
        """Any failure comes back as text for the model to read, never as an
        exception that would stop the loop."""
        func = TOOL_REGISTRY.get(name)
        if func is None:
            return f"Unknown tool: {name}"

        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            return f"Could not parse arguments for {name}: {e}"

        try:
            return _as_text(func(**args))
        except TypeError as e:
            return f"Bad arguments for {name}: {e}"
        except Exception as e:  # noqa: BLE001 - any tool failure becomes text
            return f"{name} failed: {type(e).__name__}: {e}"

    def run(self, user_input: str) -> Iterator[Event]:
        """One user turn. Events: thinking, wrap_up, thought, answer,
        tool_call, tool_result, limit_reached."""
        self.messages.append({"role": "user", "content": user_input})

        for remaining in range(settings.max_iterations, 0, -1):
            # The system prompt quotes these numbers, but only the loop sees
            # the live count.
            if remaining == settings.wrap_up_at:
                self.messages.append(
                    {
                        "role": "developer",
                        "content": (
                            f"{remaining} rounds left in this turn. Stop"
                            " searching and call write_report now with what you"
                            " already have."
                        ),
                    }
                )
                yield "wrap_up", remaining

            yield "thinking", None
            response = self._ask_model()

            calls = [item for item in response.output if item.type == "function_call"]

            # Text next to tool calls is the Thought of the ReAct cycle; text
            # on its own is the final answer.
            if text := response.output_text.strip():
                yield ("thought" if calls else "answer"), text

            if not calls:
                return

            for call in calls:
                yield "tool_call", (call.name, call.arguments)
                result = self._call_tool(call.name, call.arguments)
                yield "tool_result", (call.name, result)

                self.messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result,
                    }
                )

        # Budget exhausted mid-research: one last call with tools off, so the
        # user still gets a conclusion from what was gathered.
        yield "limit_reached", settings.max_iterations
        yield "thinking", None
        if text := self._ask_model(tool_choice="none").output_text.strip():
            yield "answer", text
