# invoke_agent bypasses the Supervisor so a sub-agent's own tool calls are visible --
# the Supervisor's stream only shows its own tools (plan/research/critique/save_report)

import json
import os
import re
from pathlib import Path

from config import Settings
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

JUDGE_MODEL = "gpt-5.4-mini"

THRESHOLDS = {
    "plan_quality": 0.7,
    "critique_quality": 0.7,
    "groundedness": 0.7,
    "faithfulness": 0.7,  # same axis as groundedness, built-in metric, same bar
    "tool_correctness": 0.5,  # name-only match, loose on purpose
    "answer_relevancy": 0.7,
    "correctness": 0.6,  # looser than the others -- paraphrase-tolerant
    "citation_presence": 0.6,  # custom metric; same bar as correctness
}

RUNS_DIR = Path(__file__).resolve().parent / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

DATASET_PATH = Path(__file__).resolve().parent / "golden_dataset.json"

settings = Settings()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def load_golden_dataset() -> list[dict]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def goldens_by_category(dataset: list[dict], category: str) -> list[dict]:
    return [g for g in dataset if g["category"] == category]


def stratified_subset(dataset: list[dict], n: int) -> list[dict]:
    """First n goldens, round-robining across categories so a partial run still
    covers happy/edge/failure instead of draining one category first."""
    if n >= len(dataset):
        return dataset
    buckets = {}
    for g in dataset:
        buckets.setdefault(g["category"], []).append(g)
    order = list(buckets)
    result = []
    i = 0
    while len(result) < n:
        cat = order[i % len(order)]
        if buckets[cat]:
            result.append(buckets[cat].pop(0))
        i += 1
    return result


def record(key: str, produce):
    """Cache-or-run: skip re-running if tests/runs/<key>.json exists, unless EVAL_REFRESH=1."""
    path = RUNS_DIR / f"{key}.json"
    if path.exists() and not os.getenv("EVAL_REFRESH"):
        return json.loads(path.read_text(encoding="utf-8"))
    result = produce()
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def _stringify(content) -> str:
    return content if isinstance(content, str) else str(content)


def extract_tool_calls(messages) -> list[dict]:
    calls = []
    for m in messages:
        for call in getattr(m, "tool_calls", None) or []:
            calls.append({"name": call["name"], "args": call["args"]})
    return calls


def extract_tool_responses(messages) -> list[dict]:
    responses = []
    for m in messages:
        if getattr(m, "type", None) == "tool":
            responses.append({"name": m.name, "content": _stringify(m.content)})
    return responses


def extract_retrieval_context(tool_responses: list[dict]) -> list[str]:
    """knowledge_search results are already citation-labelled and separator-joined
    (see tools.knowledge_search); web_search results are kept as one block each."""
    context = []
    for r in tool_responses:
        if r["name"] == "knowledge_search":
            context.extend(
                part.strip() for part in r["content"].split("\n\n---\n\n") if part.strip()
            )
        elif r["name"] == "web_search":
            context.append(r["content"])
    return context


def invoke_agent(agent, text: str) -> dict:
    """Component-level: invoke one sub-agent directly, skipping the Supervisor."""
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": text}]},
            config={"recursion_limit": settings.recursion_limit},
        )
    except GraphRecursionError:
        return {
            "input": text,
            "output": "Agent ran out of steps before completing.",
            "structured_response": None,
            "tool_calls": [],
            "tool_responses": [],
            "retrieval_context": [],
        }

    messages = result["messages"]
    structured = result.get("structured_response")
    tool_responses = extract_tool_responses(messages)
    return {
        "input": text,
        "output": messages[-1].text if messages else "",
        "structured_response": structured.model_dump() if structured is not None else None,
        "tool_calls": extract_tool_calls(messages),
        "tool_responses": tool_responses,
        "retrieval_context": extract_retrieval_context(tool_responses),
    }


def run_supervisor(request: str, thread_id: str, max_resumes: int = 10) -> dict:
    """Drives the full Supervisor pipeline to completion, auto-approving the
    save_report HITL interrupt (mirrors main._decision_for's 'approve' path)."""
    from supervisor import supervisor  # deferred: importing builds all four agents

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.supervisor_recursion_limit,
    }
    payload = {"messages": [("user", request)]}
    tool_calls: list[dict] = []
    tool_responses: list[dict] = []
    final_text = ""
    report_path = None
    resumes = 0

    while True:
        interrupt_ = None
        try:
            for chunk in supervisor.stream(payload, config=config):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        interrupt_ = update[0]
                        continue
                    if not update:
                        continue
                    for msg in update.get("messages", []):
                        if node == "model":
                            for call in msg.tool_calls or []:
                                tool_calls.append({"name": call["name"], "args": call["args"]})
                            if msg.content and not msg.tool_calls:
                                final_text = msg.content
                        elif node == "tools":
                            content = _stringify(msg.content)
                            tool_responses.append({"name": msg.name, "content": content})
                            if msg.name == "save_report" and content.startswith(
                                "Report saved to "
                            ):
                                report_path = content.removeprefix("Report saved to ").strip()
        except GraphRecursionError:
            break

        if interrupt_ is None:
            break
        resumes += 1
        if resumes > max_resumes:
            raise RuntimeError(
                f"run_supervisor: exceeded {max_resumes} HITL resumes for thread {thread_id!r}"
            )
        n_actions = len(interrupt_.value["action_requests"])
        payload = Command(resume={"decisions": [{"type": "approve"}] * n_actions})

    return {
        "input": request,
        "output": final_text,
        "tool_calls": tool_calls,
        "tool_responses": tool_responses,
        "retrieval_context": extract_retrieval_context(tool_responses),
        "report_path": report_path,
    }


def actual_output(result: dict) -> str:
    """Report content when one was saved, else the final assistant message --
    failure-case goldens legitimately never call save_report."""
    if result.get("report_path"):
        return Path(result["report_path"]).read_text(encoding="utf-8")
    return result["output"]
