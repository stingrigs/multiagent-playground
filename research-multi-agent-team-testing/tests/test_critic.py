import json

from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams
from harness import JUDGE_MODEL, THRESHOLDS, invoke_agent, record

from agents.critic import critic_agent

critique_quality = GEval(
    name="Critique Quality",
    evaluation_steps=[
        "Check that the critique identifies specific issues, not vague complaints",
        "Check that revision_requests are actionable (researcher can act on them)",
        "If verdict is APPROVE, gaps list should be empty or contain only minor items",
        "If verdict is REVISE, there must be at least one revision_request",
    ],
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
    model=JUDGE_MODEL,
    threshold=THRESHOLDS["critique_quality"],
)

ORIGINAL_REQUEST = "Explain the three stages of a RAG pipeline: ingestion, retrieval, generation"

SOLID_FINDINGS = """
Ingestion: source documents are split into chunks (typically a few hundred tokens each,
with some overlap) and converted into vector embeddings using an embedding model, then
stored in a vector database such as FAISS or Pinecone.
Source: retrieval-augmented-generation.pdf, page 2

Retrieval: given a user query, its embedding is computed and compared against the stored
document embeddings (e.g. via cosine similarity or a hybrid BM25 + dense search) to find
the most relevant chunks.
Source: retrieval-augmented-generation.pdf, page 3

Generation: the retrieved chunks are inserted into the LLM's prompt as context, and the
model generates a response grounded in that context rather than only its parametric
knowledge.
Source: retrieval-augmented-generation.pdf, page 4
"""

THIN_FINDINGS = "RAG has three parts: you put documents in, you search them, and you get an answer out."


def _critique(findings: str, key: str) -> dict:
    prompt = f"Original request:\n{ORIGINAL_REQUEST}\n\nFindings to review:\n{findings}"
    return record(key, lambda: invoke_agent(critic_agent, prompt))


def test_critique_solid_findings():
    result = _critique(SOLID_FINDINGS, "critic_solid_findings")
    critique = result["structured_response"]
    assert critique is not None, "critic returned no structured_response"

    test_case = LLMTestCase(
        input=ORIGINAL_REQUEST,
        actual_output=json.dumps(critique, indent=2),
    )
    assert_test(test_case=test_case, metrics=[critique_quality])

    if critique["verdict"] == "APPROVE":
        assert len(critique["gaps"]) <= 1
    else:
        assert critique["revision_requests"]


def test_critique_thin_findings():
    result = _critique(THIN_FINDINGS, "critic_thin_findings")
    critique = result["structured_response"]
    assert critique is not None, "critic returned no structured_response"

    test_case = LLMTestCase(
        input=ORIGINAL_REQUEST,
        actual_output=json.dumps(critique, indent=2),
    )
    assert_test(test_case=test_case, metrics=[critique_quality])

    assert critique["verdict"] == "REVISE"
    assert critique["revision_requests"]
