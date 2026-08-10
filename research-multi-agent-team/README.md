# Research Team

A multi-agent research system: a Supervisor coordinates a Planner, a Researcher, and a
Critic in an iterative plan → research → critique loop, then saves the final report
only after the user approves it. Extends the single-agent Research Agent with
independent sub-agents instead of one agent doing everything.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in OPENAI_API_KEY in .env
```

Build the knowledge base index (once, or whenever `data/` changes):

```bash
python ingest.py
```

## Run

```bash
source .venv/bin/activate && python main.py
```

Enter a question, watch the trace as the Supervisor calls each sub-agent, then approve,
edit, or reject the report before it's saved. The terminal trace is truncated per line to
stay readable; once a report is approved, the full untruncated trace for that turn is
saved next to it as `<same name>.log`.

## Architecture

```mermaid
graph LR
    U["user"] --> S["Supervisor"]
    S -->|"1. plan"| P["Planner"]
    P -->|"ResearchPlan"| S
    S -->|"2. research"| R["Researcher"]
    R -->|"findings"| S
    S -->|"3. critique"| C["Critic"]
    C -->|"CritiqueResult"| S
    S -.->|"verdict: REVISE"| R
    S -->|"4. verdict: APPROVE"| SR["save_report"]
    SR -.->|"HITL approval"| U
```

Planner, Researcher, and Critic are each a separate agent, wrapped as a tool the
Supervisor calls — each sees only the request it's given, not the Supervisor's full
conversation. The Supervisor never researches anything itself; it only calls tools and
synthesizes their output.

- **Planner** → `ResearchPlan`: goal, search queries, sources to check.
- **Researcher** executes the plan using `web_search`, `read_url`, and
  `knowledge_search` (the same hybrid-retrieval knowledge base as the base Research
  Agent).
- **Critic** independently re-verifies findings through the same sources and returns a
  structured verdict (`CritiqueResult`) on freshness, completeness, and structure. On
  `REVISE`, the Supervisor sends its feedback back to the Researcher, capped at
  `max_revision_rounds` rounds.
- Supervisor then calls `save_report`, gated on human approval: `approve` saves,
  `edit` sends feedback back for revision, `reject` cancels.

## Flow: HITL approval

```mermaid
sequenceDiagram
    actor User
    participant REPL as main.py
    participant Sup as Supervisor
    participant MW as HumanInTheLoopMiddleware

    User->>REPL: question
    REPL->>Sup: stream(messages, thread_id)
    Note over Sup: plan → research → critique loop (see Architecture)
    Sup->>MW: save_report(filename, content)
    MW-->>REPL: interrupt (action_requests, review_configs)
    REPL-->>User: ⏸ show filename + content preview

    alt approve
        User->>REPL: approve
        REPL->>Sup: resume({"decisions": [{"type": "approve"}]})
        Sup->>MW: save_report executes
        MW-->>REPL: file saved
        REPL-->>User: 🤖 confirmation
    else edit
        User->>REPL: edit + feedback
        REPL->>Sup: resume({"decisions": [{"type": "reject", "message": feedback}]})
        Sup->>Sup: revise report, call save_report again
        Sup->>MW: save_report(filename, revised content)
        MW-->>REPL: interrupt (fresh)
        REPL-->>User: ⏸ show revised preview, ask again
    else reject
        User->>REPL: reject
        REPL->>Sup: resume({"decisions": [{"type": "reject", "message": "cancelled"}]})
        Sup-->>REPL: 🤖 summary in chat, no retry
    end
```

`edit` isn't the middleware's own `edit` decision (that would replace the tool args
directly, skipping the revision step) — both `edit` and `reject` resolve to a `reject`
decision with different messages; only the message tells the Supervisor whether to
revise or give up.

## Configuration

`config.py` holds settings; `prompts.py` holds all four agents' system prompts.
Secrets are read from `.env` (template: `.env.example`) and never committed.

| Setting | Default | Meaning |
|---|---|---|
| `model_name` | `gpt-5.2` | Chat model |
| `max_revision_rounds` | `2` | Research↔critique cycles before proceeding anyway |
| `max_iterations` | `25` | Sub-agent tool-calling budget |
| `retrieval_top_k` | `10` | Hybrid retrieval candidates before reranking |
| `rerank_top_n` | `3` | Chunks kept after cross-encoder reranking |
