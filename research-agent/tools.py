# ====================================
#  🔰 [RESEARCH AGENT] Tools
# ====================================

from pathlib import Path
from typing import Annotated

import trafilatura
from ddgs import DDGS
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from trafilatura.settings import use_config

from config import Settings

settings = Settings()

trafilatura_config = use_config()
trafilatura_config.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(settings.request_timeout))


# --- 🔻 Output directory helpers


def output_path(filename: str) -> Path:
    """Resolve a filename inside output_dir. Strips any directory
    components — filenames come from the LLM, not from us.
    Raises ValueError if nothing usable remains."""
    name = Path(filename.strip()).name
    if not name or name in {".", ".."}:
        raise ValueError(f"Invalid filename: {filename!r}")
    return Path(settings.output_dir) / name


# --- 🔻 [TOOL]: Write Report


@tool
def write_report(
    filename: Annotated[
        str, Field(description="File name only, no path. E.g. 'rag_comparison.md'")
    ],
    content: Annotated[str, Field(description="Full report body in Markdown")],
) -> str:
    """Tool to save a Markdown report to the output directory."""
    try:
        path = output_path(filename)
    except ValueError as e:
        return str(e)

    if path.suffix != ".md":
        path = path.with_name(f"{path.name}.md")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"Failed to write {path.name}: {e}"

    return f"Report saved to {path.resolve()}"


# --- 🔻 [TOOL]: List Files


@tool
def list_files() -> list[str]:
    """Tool to list reports previously saved in the output directory."""
    output_dir = Path(settings.output_dir)
    if not output_dir.is_dir():
        return []
    return sorted(p.name for p in output_dir.iterdir() if p.is_file())


# --- 🔻 [TOOL]: Read File


@tool
def read_file(
    filename: Annotated[str, Field(description="File name as returned by list_files")],
    offset: Annotated[
        int, Field(ge=0, description="Character to start reading from")
    ] = 0,
) -> str:
    """Tool to read back a report previously saved in the output directory."""
    try:
        path = output_path(filename)
    except ValueError as e:
        return str(e)

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"File not found: {path.name}. Use list_files to see what exists."
    except OSError as e:
        return f"Failed to read {path.name}: {e}"

    total = len(text)
    if offset >= total:
        return f"Offset {offset} is past the end of {path.name} ({total} characters)."

    end = offset + settings.max_file_content_length
    chunk = text[offset:end]
    if end < total:
        return (
            f"{chunk}\n\n[characters {offset}-{end} of {total}; read on with"
            f" offset={end}. Read the whole file before rewriting it.]"
        )

    return chunk


# --- 🔻 [TOOL]: Web Search


class SearchResult(BaseModel):
    """Search result model for web search tool"""

    model_config = ConfigDict(strict=True)

    title: str
    url: str
    snippet: str


@tool
def web_search(
    query: str,
    max_results: Annotated[
        int, Field(ge=1, le=settings.max_search_results)
    ] = settings.max_search_results,
) -> list[dict]:
    """Tool to search the web for information."""
    try:
        raw_results = DDGS().text(query, max_results=max_results)
    except Exception as e:
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


@tool
def read_url(
    url: str,
    offset: Annotated[
        int, Field(ge=0, description="Character to start reading from")
    ] = 0,
) -> str:
    """Tool to read the main text content of a web page."""
    downloaded = trafilatura.fetch_url(url, config=trafilatura_config)
    if downloaded is None:
        return f"Failed to fetch {url}: invalid URL, timeout, or page unavailable."

    text = trafilatura.extract(downloaded, config=trafilatura_config)
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
