# Research Team under Test

The same multi-agent research system as `research-multi-agent-team` — Supervisor
coordinating a Planner, a Researcher, and a Critic in an iterative plan → research →
critique loop, then saving the final report only after human approval — plus a
DeepEval eval suite: 24 tests across component, tool-correctness, and end-to-end
layers, backed by a 15-example golden dataset.

The system under test (`config.py`, `supervisor.py`, `agents/`, `tools.py`,
`retriever.py`, `ingest.py`, `prompts.py`, `schemas.py`, `main.py`) is unchanged from
the base project — this folder only adds `tests/`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in OPENAI_API_KEY in .env
```

`data/` and `index/` ship with this copy, so `ingest.py` doesn't need to be re-run.

## Run

```bash
source .venv/bin/activate && python main.py           # the app itself, unchanged
deepeval test run tests/                               # the full eval suite
deepeval test run tests/ -m "not e2e"                   # component + tool tests only
MODEL_NAME=gpt-5.4-nano python main.py                  # override the chat model
```

## Evaluation

Tests operate at three layers:

- **Component-level** (`test_planner.py`, `test_researcher.py`, `test_critic.py`) —
  each sub-agent invoked directly (`agents.planner.planner_agent.invoke(...)`,
  bypassing the Supervisor), so its own tool calls and retrieval context are visible.
  The Supervisor's message stream only shows *its* tools (`plan`/`research`/
  `critique`/`save_report`), not what happens inside them — component tests are the
  only way to see a sub-agent's internal `knowledge_search`/`web_search` calls.
- **Tool correctness** (`test_tools.py`) — deterministic name-based comparison of
  `tools_called` vs `expected_tools`, no LLM judge.
- **End-to-end** (`test_e2e.py`) — the full Supervisor pipeline over the golden
  dataset, auto-approving the `save_report` HITL step.

| Metric | Threshold | Layer | Rationale |
|---|---|---|---|
| Plan Quality (GEval) | 0.7 | Planner | Specific queries, correct sources, matching format |
| Groundedness (GEval) | 0.7 | Researcher | Strict: every claim must trace to retrieval context, even if true |
| Faithfulness (built-in) | 0.7 | Researcher | Looser axis: flags only outright contradictions — reported alongside Groundedness to show the difference |
| Critique Quality (GEval) | 0.7 | Critic | Actionable revision requests; verdict/gaps consistency |
| Tool Correctness | 0.5 | Planner/Researcher/Supervisor | Name-only match; revision-loop length is prompt-driven, not code-enforced |
| Answer Relevancy (built-in) | 0.7 | E2E | Referenceless: does the output address the input |
| Correctness (GEval) | 0.6 | E2E | Reference-based against `expected_output`; paraphrase-tolerant |
| Citation Presence (GEval, custom) | 0.6 | E2E (happy/edge only) | Project rule: `REPORT_TEMPLATE` mandates a Sources section |

**Judge:** `gpt-5.4-mini` — same vendor as the system under test (`gpt-5.2`), so
results may carry some family bias. GEval-based metrics can also vary slightly
between runs on identical input; small threshold-adjacent swings aren't necessarily
regressions.

## Golden dataset

`tests/golden_dataset.json` — 15 examples, 5 per category:

- **happy_path** — RAG/LangChain/LLM questions answerable from the ingested PDFs and
  the web (retrieval comparisons, pipeline stages, reranking, agents vs chains).
- **edge_case** — ambiguous, ultra-narrow, ultra-broad, non-English, and
  format-constrained requests.
- **failure_case** — out-of-domain, nonsense input, and requests for personalized
  medical/financial advice or unknowable facts. `expected_output` for these describes
  the correct refusal/scoping behavior, not a fabricated answer.

Hand-authored — Ragas's pinned `langchain-community` version conflicts with this
project's.

`golden_dataset.json` is versioned. `tests/runs/` (recorded agent outputs, see
Caching below) is derived and gitignored.

## Baseline

Establish a baseline after any prompt or config change:

```bash
deepeval test run tests/ -m "not e2e"              # component + tool-correctness, fast
EVAL_MAX_CASES=3 deepeval test run tests/ -m e2e    # sanity check a few goldens first
deepeval test run tests/                             # full 15-golden run
```

E2E runs go through `gpt-5.2` by default and cost real money; override `MODEL_NAME`
(e.g. `gpt-5.4-nano`) for cheaper exploratory runs. Partial failures are expected —
the goal is a baseline to improve from, not a green board on day one.

## Caching

Every agent/Supervisor invocation is recorded to `tests/runs/<key>.json` on first run.
Later `deepeval test run` invocations reuse the recording and only re-run the judge —
so re-running the suite after a prompt change to just the Critic, for example, doesn't
re-pay for Planner/Researcher calls it didn't touch. Set `EVAL_REFRESH=1` to force a
fresh run and overwrite the cache. `EVAL_MAX_CASES=n` (in `test_e2e.py`) subsets the
golden dataset for a quick smoke run instead of the full 15.

The first full run is slow: 15 end-to-end pipeline runs (Supervisor → Planner →
Researcher → Critic) plus judge calls — expect tens of minutes.

## Layout

```
research-multi-agent-team-testing/
├── conftest.py              # chdir + sys.path setup, required before any project import (new)
├── pytest.ini                # registers the `e2e` marker (new)
├── tests/
│   ├── golden_dataset.json   # 15 examples, 5/5/5 split (new)
│   ├── harness.py            # cache-or-run recording, agent invocation, extractors (new)
│   ├── conftest.py           # golden_dataset / happy_path_run fixtures (new)
│   ├── test_planner.py       # Plan Quality GEval + deterministic contract check (new)
│   ├── test_researcher.py    # Groundedness GEval + Faithfulness (new)
│   ├── test_critic.py        # Critique Quality GEval, solid vs thin findings (new)
│   ├── test_tools.py         # ToolCorrectnessMetric, 3 cases (new)
│   ├── test_e2e.py           # full pipeline over the golden dataset (new)
│   └── runs/                 # cached recordings, gitignored, generated
├── agents/                   # unchanged from research-multi-agent-team
├── config.py, supervisor.py, tools.py, retriever.py, ingest.py, prompts.py,
│   schemas.py, main.py       # unchanged
└── data/, index/             # unchanged
```

## Configuration

Same settings as the base project (`config.py`), plus the eval-specific values above.

| Setting | Default | Meaning |
|---|---|---|
| `model_name` (env `MODEL_NAME`) | `gpt-5.2` | Chat model for the system under test |
| `max_revision_rounds` | `1` | Research↔critique cycles before proceeding anyway |
| `max_iterations` | `25` | Sub-agent tool-calling budget |
| `retrieval_top_k` | `10` | Hybrid retrieval candidates before reranking |
| `rerank_top_n` | `3` | Chunks kept after cross-encoder reranking |
| `JUDGE_MODEL` (`tests/harness.py`) | `gpt-5.4-mini` | LLM-as-a-Judge for all GEval/built-in metrics |
