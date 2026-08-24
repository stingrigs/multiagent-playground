from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
from harness import JUDGE_MODEL, THRESHOLDS, invoke_agent, record, slug

from agents.research import research_agent

# stricter than FaithfulnessMetric -- flags any unsupported claim, not just contradictions
groundedness = GEval(
    name="Groundedness",
    evaluation_steps=[
        "Extract every factual claim from 'actual output'",
        "For each claim, check if it can be directly supported by 'retrieval context'",
        "Claims not present in retrieval context count as ungrounded, even if true",
        "Score = number of grounded claims / total claims",
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT],
    model=JUDGE_MODEL,
    threshold=THRESHOLDS["groundedness"],
)

faithfulness = FaithfulnessMetric(threshold=THRESHOLDS["faithfulness"], model=JUDGE_MODEL)

RESEARCH_REQUEST = (
    "Research plan: goal is to explain the three stages of a RAG pipeline "
    "(ingestion, retrieval, generation) using the local knowledge base. "
    "sources_to_check: knowledge_base."
)


def _researched() -> dict:
    return record(f"researcher_{slug(RESEARCH_REQUEST)}", lambda: invoke_agent(research_agent, RESEARCH_REQUEST))


def test_research_grounded():
    result = _researched()
    assert result["retrieval_context"], "expected knowledge_search/web_search context to be captured"

    test_case = LLMTestCase(
        input=RESEARCH_REQUEST,
        actual_output=result["output"],
        retrieval_context=result["retrieval_context"],
    )
    assert_test(test_case=test_case, metrics=[groundedness, faithfulness])
