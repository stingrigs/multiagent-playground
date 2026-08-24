from deepeval import assert_test
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall
from harness import THRESHOLDS, invoke_agent, record, slug

from agents.planner import planner_agent
from agents.research import research_agent

tool_correctness = ToolCorrectnessMetric(threshold=THRESHOLDS["tool_correctness"])


def _to_tool_calls(recorded: list[dict]) -> list[ToolCall]:
    return [ToolCall(name=c["name"], input_parameters=c["args"]) for c in recorded]


def test_planner_uses_search_tools():
    """Planner should probe with knowledge_search and/or web_search before planning."""
    request = "Compare naive RAG vs sentence-window retrieval"
    result = record(f"planner_{slug(request)}", lambda: invoke_agent(planner_agent, request))

    test_case = LLMTestCase(
        input=request,
        actual_output=result["output"] or "",
        tools_called=_to_tool_calls(result["tool_calls"]),
        expected_tools=[ToolCall(name="knowledge_search"), ToolCall(name="web_search")],
    )
    assert_test(test_case=test_case, metrics=[tool_correctness])


def test_researcher_uses_plan_sources():
    """Researcher should use the tools implied by the plan's sources_to_check."""
    request = (
        "Research plan: goal is to explain the three stages of a RAG pipeline "
        "(ingestion, retrieval, generation) using the local knowledge base. "
        "sources_to_check: knowledge_base."
    )
    result = record(f"researcher_{slug(request)}", lambda: invoke_agent(research_agent, request))

    test_case = LLMTestCase(
        input=request,
        actual_output=result["output"] or "",
        tools_called=_to_tool_calls(result["tool_calls"]),
        expected_tools=[ToolCall(name="knowledge_search")],
    )
    assert_test(test_case=test_case, metrics=[tool_correctness])


def test_supervisor_saves_after_approve(happy_path_run):
    """Supervisor should call plan -> research -> critique -> save_report on a
    straightforward happy-path request."""
    result = happy_path_run

    test_case = LLMTestCase(
        input=result["input"],
        actual_output=result["output"] or "",
        tools_called=_to_tool_calls(result["tool_calls"]),
        expected_tools=[
            ToolCall(name="plan"),
            ToolCall(name="research"),
            ToolCall(name="critique"),
            ToolCall(name="save_report"),
        ],
    )
    assert_test(test_case=test_case, metrics=[tool_correctness])
    assert result["report_path"], "expected save_report to have been called and approved"
