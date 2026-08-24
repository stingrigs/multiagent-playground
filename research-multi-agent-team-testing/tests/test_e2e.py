import os

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
from harness import (
    JUDGE_MODEL,
    THRESHOLDS,
    actual_output,
    load_golden_dataset,
    record,
    run_supervisor,
    slug,
    stratified_subset,
)

answer_relevancy = AnswerRelevancyMetric(threshold=THRESHOLDS["answer_relevancy"], model=JUDGE_MODEL)

correctness = GEval(
    name="Correctness",
    evaluation_steps=[
        "Check whether the facts in 'actual output' contradict 'expected output'",
        "Penalize omission of critical details",
        "Different wording of the same concept is acceptable",
    ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
    ],
    model=JUDGE_MODEL,
    threshold=THRESHOLDS["correctness"],
)

# project rule: REPORT_TEMPLATE requires traceable sources, not just clean prose
citation_presence = GEval(
    name="Citation Presence",
    evaluation_steps=[
        (
            "Check whether 'actual output' cites at least one concrete source per major "
            "claim (a URL, or a knowledge-base file name, ideally with a page number)"
        ),
        (
            "A 'Sources' section alone without any in-text attribution is not sufficient "
            "if the output makes multiple distinct claims"
        ),
        (
            "Vague attribution such as 'according to research' or 'studies show' without "
            "a concrete source does not count"
        ),
    ],
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT],
    model=JUDGE_MODEL,
    threshold=THRESHOLDS["citation_presence"],
)

_DATASET = load_golden_dataset()
_max_cases = os.getenv("EVAL_MAX_CASES")
if _max_cases:
    _DATASET = stratified_subset(_DATASET, int(_max_cases))

_IDS = [f"{g['category']}_{slug(g['input'])[:30]}" for g in _DATASET]


@pytest.mark.e2e
@pytest.mark.parametrize("golden", _DATASET, ids=_IDS)
def test_golden_dataset(golden):
    key = f"e2e_{slug(golden['input'])}"
    result = record(key, lambda: run_supervisor(golden["input"], thread_id=key))
    output = actual_output(result)

    test_case = LLMTestCase(
        input=golden["input"],
        actual_output=output,
        expected_output=golden["expected_output"],
    )

    metrics = [answer_relevancy, correctness]
    if golden["category"] in ("happy_path", "edge_case"):
        metrics.append(citation_presence)

    assert_test(test_case=test_case, metrics=metrics)
