# ====================================
#  🔰 [RESEARCH TEAM] SearchMCP
# ====================================

import json
import pickle
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

# run as `python mcp_servers/search_mcp.py` -> sys.path[0] is mcp_servers/, not the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import trafilatura
from ddgs import DDGS
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from trafilatura.settings import use_config

from config import Settings
from ingest import CHUNKS_FILENAME
from retriever import get_retriever

settings = Settings()

mcp = FastMCP(name="SearchMCP")

trafilatura_config = use_config()
trafilatura_config.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(settings.request_timeout))


# --- 🔻 [RESOURCE]: Knowledge Base Stats


@mcp.resource("resource://knowledge-base-stats")
def knowledge_base_stats() -> str:
    """Size and freshness of the local knowledge base index."""
    data_dir = Path(settings.data_dir)
    index_path = Path(settings.index_dir) / "index.faiss"

    stats = {
        "documents": len(list(data_dir.glob("*.pdf"))),
        "data_dir": str(data_dir.resolve()),
    }

    if not index_path.exists():
        stats["status"] = "not built — run `python ingest.py`"
        return json.dumps(stats)

    chunks_path = Path(settings.index_dir) / CHUNKS_FILENAME
    stats["status"] = "ready"
    stats["last_updated"] = datetime.fromtimestamp(
        index_path.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    if chunks_path.exists():
        with chunks_path.open("rb") as f:
            stats["chunks"] = len(pickle.load(f))

    return json.dumps(stats)


# --- 🔻 [TOOL]: Web Search


class SearchResult(BaseModel):
    model_config = ConfigDict(strict=True)

    title: str
    url: str
    snippet: str


@mcp.tool
def web_search(
    query: str,
    max_results: Annotated[
        int, Field(ge=1, le=settings.max_search_results)
    ] = settings.max_search_results,
) -> list[dict]:
    """Search the web for information."""
    try:
        raw_results = DDGS().text(query, max_results=max_results)
    except Exception as e:  # noqa: BLE001 - DDGS scrapes; failures vary
        return [{"error": f"Search failed: {e}"}]

    try:
        results = [
            SearchResult(title=r["title"], url=r["href"], snippet=r["body"])
            for r in raw_results
        ]
    except (ValidationError, KeyError) as e:
        return [{"error": f"DDGS returned an unexpected result shape: {e}"}]

    return [r.model_dump() for r in results]


# --- 🔻 [TOOL]: Read URL


@mcp.tool
def read_url(
    url: str,
    offset: Annotated[
        int, Field(ge=0, description="Character to start reading from")
    ] = 0,
) -> str:
    """Read the main text content of a web page."""
    downloaded = trafilatura.fetch_url(url, config=trafilatura_config)
    if downloaded is None:
        return f"Failed to fetch {url}: invalid URL, timeout, or page unavailable."

    try:
        text = trafilatura.extract(downloaded, config=trafilatura_config)
    except Exception as e:  # noqa: BLE001 - extraction on arbitrary HTML; failures vary
        return f"Failed to extract text from {url}: {type(e).__name__}: {e}"
    if text is None:
        return f"No readable text extracted from {url}."

    total = len(text)
    if offset >= total:
        return f"Offset {offset} is past the end of {url} ({total} characters)."

    end = offset + settings.max_url_content_length
    chunk = text[offset:end]
    if end < total:
        return f"{chunk}\n\n[characters {offset}-{end} of {total}; read on with offset={end}]"

    return chunk


# --- 🔻 [TOOL]: Knowledge Search

_knowledge_retriever = None
# FastMCP runs sync tools in a threadpool, and three agents share this server
_retriever_lock = threading.Lock()


def _get_knowledge_retriever():
    """Cached after first build — rebuilding costs seconds (BM25 + reranker load)."""
    global _knowledge_retriever
    with _retriever_lock:
        if _knowledge_retriever is None:
            _knowledge_retriever = get_retriever()
    return _knowledge_retriever


@mcp.tool
def knowledge_search(query: str) -> str:
    """Search the local knowledge base (ingested PDFs in data/). Use for
    questions about the content of those documents, not for current events
    or anything outside them."""
    try:
        retriever = _get_knowledge_retriever()
    except (FileNotFoundError, RuntimeError) as e:
        return str(e)

    try:
        docs = retriever.invoke(query)
    except Exception as e:  # noqa: BLE001 - embedding/rerank calls; failures vary
        return f"Knowledge search failed: {type(e).__name__}: {e}"
    if not docs:
        return "No relevant results found in the knowledge base."

    results = []
    for d in docs:
        source = Path(d.metadata.get("source", "unknown")).name
        page = d.metadata.get("page")
        label = f"{source}, page {page + 1}" if page is not None else source
        results.append(f"[{label}]\n{d.page_content}")

    return "\n\n---\n\n".join(results)


if __name__ == "__main__":
    print(f"SearchMCP on {settings.search_mcp_url}")
    mcp.run(
        transport="http",
        host=settings.host,
        port=settings.search_mcp_port,
        log_level="warning",
    )
