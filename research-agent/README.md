# Research Agent

An agent that takes a question from the user, autonomously searches for information using a set of tools (`web_search`, `read_url`, `write_report`), and produces a structured Markdown report. Built with LangChain (`create_react_agent`) with conversation memory via `MemorySaver`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in your API key in .env
```

## Run

```bash
python main.py
```

Interactive mode: enter a question, the agent searches/reads pages, and saves the report to `output/`.

## Example interaction

```
User: "Compare three approaches to building RAG: naive, sentence-window, and parent-child retrieval"

Agent:
  Thought: Need to find information about each approach separately
  → web_search("naive RAG pipeline approach")
  → web_search("sentence window retrieval RAG")
  → web_search("parent child retrieval RAG")
  → read_url("https://...article comparing the approaches...")
  → web_search("RAG approaches comparison tradeoffs 2024")

Final Answer: [structured Markdown report comparing the three approaches]

Output: → research_report.md
```

## Architecture

- `main.py` — entry point, REPL loop
- `agent.py` — LLM, tools, memory setup, `create_react_agent`
- `tools.py` — tool implementations (`web_search`, `read_url`, `write_report`)
- `config.py` — system prompt, settings (Pydantic Settings), constants
- `example_output/` — sample generated report

## Configuration

Environment variables are read from `.env` (template — `.env.example`), never committed to git.
