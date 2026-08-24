import json

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
from harness import JUDGE_MODEL, THRESHOLDS, invoke_agent, record, slug

from agents.planner import planner_agent

plan_quality = GEval(
    name="Plan Quality",
    evaluation_steps=[
        "Check that the plan contains specific search queries (not vague)",
        "Check that sources_to_check includes relevant sources for the topic",
        "Check that the output_format matches what the user asked for",
    ],
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
    model=JUDGE_MODEL,
    threshold=THRESHOLDS["plan_quality"],
)

PLANNER_REQUESTS = [
    "Compare naive RAG vs sentence-window retrieval",
    "What does hybrid retrieval (BM25 + dense embeddings) buy you over dense-only retrieval?",
]


def _planned(request_text: str) -> dict:
    return record(f"planner_{slug(request_text)}", lambda: invoke_agent(planner_agent, request_text))


@pytest.mark.parametrize("request_text", PLANNER_REQUESTS)
def test_plan_quality(request_text):
    result = _planned(request_text)
    plan = result["structured_response"]
    assert plan is not None, "planner returned no structured_response"

    test_case = LLMTestCase(
        input=request_text,
        actual_output=json.dumps(plan, indent=2),
    )
    assert_test(test_case=test_case, metrics=[plan_quality])


def test_plan_has_valid_contract():
    """Deterministic check that the plan matches what PLANNER_PROMPT contracts for."""
    result = _planned(PLANNER_REQUESTS[0])
    plan = result["structured_response"]
    assert plan is not None, "planner returned no structured_response"

    assert plan["goal"].strip()
    assert plan["output_format"].strip()
    assert 3 <= len(plan["search_queries"]) <= 6
    assert set(plan["sources_to_check"]) <= {"knowledge_base", "web"}
