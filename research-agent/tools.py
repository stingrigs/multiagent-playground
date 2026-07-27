# ====================================
#  🔰 [RESEARCH AGENT] Tools
# ====================================

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import trafilatura
from ddgs import DDGS
from pydantic import BaseModel, ConfigDict, ValidationError
from trafilatura.settings import use_config

from config import settings

trafilatura_config = use_config()
trafilatura_config.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(settings.request_timeout))


# --- 🔻 Shared helpers


def output_path(filename: str) -> Path:
    """Resolve a filename inside output_dir. Strips any directory
    components — filenames come from the LLM, not from us.
    Raises ValueError if nothing usable remains."""
    name = Path(filename.strip()).name
    if not name or name in {".", ".."}:
        raise ValueError(f"Invalid filename: {filename!r}")
    return Path(settings.output_dir) / name


def unreachable_reason(url: str) -> str | None:
    """None if the URL is safe to fetch, otherwise why it is refused.

    The model chooses these URLs, and a page it read can suggest the next one,
    so without this an injected link could point the fetcher at the host's own
    network — loopback, LAN, or a cloud metadata endpoint. Checked at resolve
    time; the fetch re-resolves, so a rebinding DNS server can still slip
    through."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"Refused {url}: only http and https are allowed."

    host = parsed.hostname
    if not host:
        return f"Refused {url}: no host in URL."

    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return f"Failed to fetch {url}: host {host} could not be resolved."

    for info in addresses:
        ip = ipaddress.ip_address(info[4][0])
        # An IPv6-mapped IPv4 address (::ffff:127.0.0.1) must be judged as
        # its IPv4 self, not as a generic IPv6 address.
        ip = getattr(ip, "ipv4_mapped", None) or ip
        if not ip.is_global:
            return f"Refused {url}: {host} resolves to non-public address {ip}."

    return None


def paged(text: str, offset: int, limit: int, label: str, tail: str = "") -> str:
    """One bounded chunk of a longer text. The continuation marker is a
    protocol the model relies on — read_url and read_file must phrase it
    identically, which is why this lives in one place."""
    offset = max(0, offset)
    total = len(text)
    if offset >= total:
        return f"Offset {offset} is past the end of {label} ({total} characters)."

    end = offset + limit
    if end < total:
        return (
            f"{text[offset:end]}\n\n"
            f"[characters {offset}-{end} of {total}; read on with offset={end}.{tail}]"
        )

    return text[offset:]


# --- 🔻 [TOOL]: Web Search


WEB_SEARCH_SCHEMA = {
    "type": "function",
    "name": "web_search",
    "description": (
        "Search the web. Returns a list of results, each with 'title', 'url' "
        "and 'snippet'. Snippets are short excerpts, not full page text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords, not a full question.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": settings.max_search_results,
                "description": (
                    f"How many results to return. Use "
                    f"{settings.max_search_results} unless you want fewer."
                ),
            },
        },
        "required": ["query", "max_results"],
    },
}


class SearchResult(BaseModel):
    """Boundary contract for one DDGS result — DDGS scrapes DuckDuckGo and
    occasionally returns malformed entries."""

    model_config = ConfigDict(strict=True)

    title: str
    url: str
    snippet: str


def web_search(
    query: str, max_results: int = settings.max_search_results
) -> list[dict]:
    # Schema bounds are advisory — nothing rejects an out-of-range value.
    max_results = min(max(1, max_results), settings.max_search_results)

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


READ_URL_SCHEMA = {
    "type": "function",
    "name": "read_url",
    "description": (
        "Read the main text of a web page. Long pages are returned in "
        f"{settings.max_url_content_length}-character chunks; the reply says "
        "which offset to use to continue."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL including scheme."},
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "Character to start reading from. Use 0 to start.",
            },
        },
        "required": ["url", "offset"],
    },
}


_url_text_cache: dict[str, str] = {}


def read_url(url: str, offset: int = 0) -> str:
    refusal = unreachable_reason(url)
    if refusal:
        return refusal

    text = _url_text_cache.get(url)
    if text is None:
        downloaded = trafilatura.fetch_url(url, config=trafilatura_config)
        if downloaded is None:
            return f"Failed to fetch {url}: invalid URL, timeout, or page unavailable."

        try:
            text = trafilatura.extract(downloaded, config=trafilatura_config)
        except Exception as e:  # noqa: BLE001 - extraction on arbitrary HTML; failures vary
            return f"Failed to extract text from {url}: {type(e).__name__}: {e}"
        if text is None:
            return f"No readable text extracted from {url}."

        _url_text_cache[url] = text

    return paged(text, offset, settings.max_url_content_length, url)


# --- 🔻 [TOOL]: Write Report


WRITE_REPORT_SCHEMA = {
    "type": "function",
    "name": "write_report",
    "description": (
        "Save a Markdown report to the output directory. Replaces the whole "
        "file if one of that name exists — pass the complete report, not an "
        "addition to it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "File name only, no path. E.g. 'rag_comparison.md'",
            },
            "content": {
                "type": "string",
                "description": "Full report body in Markdown.",
            },
        },
        "required": ["filename", "content"],
    },
}


# Safe to replace outright. Anything else (e.g. "rag.v2") gets .md appended
# instead — replacing it would collide "rag.v2" and "rag.v3" into one file.
REPLACEABLE_SUFFIXES = {".txt", ".text", ".markdown"}


def write_report(filename: str, content: str) -> str:
    try:
        path = output_path(filename)
    except ValueError as e:
        return str(e)

    if path.suffix in REPLACEABLE_SUFFIXES:
        path = path.with_suffix(".md")
    elif path.suffix != ".md":
        path = path.with_name(f"{path.name}.md")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"Failed to write {path.name}: {e}"

    return f"Report saved to {path.resolve()}"


# --- 🔻 [TOOL]: List Files


LIST_FILES_SCHEMA = {
    "type": "function",
    "name": "list_files",
    "description": "List reports already saved in the output directory.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def list_files() -> list[str]:
    output_dir = Path(settings.output_dir)
    if not output_dir.is_dir():
        return []
    # write_report only ever produces .md — anything else (.DS_Store) is not
    # a report and would just invite a pointless read_file call.
    return sorted(p.name for p in output_dir.iterdir() if p.suffix == ".md")


# --- 🔻 [TOOL]: Read File


READ_FILE_SCHEMA = {
    "type": "function",
    "name": "read_file",
    "description": (
        "Read back a report saved earlier. Long files are returned in "
        f"{settings.max_file_content_length}-character chunks; the reply says "
        "which offset to use to continue."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "File name as returned by list_files.",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "Character to start reading from. Use 0 to start.",
            },
        },
        "required": ["filename", "offset"],
    },
}


def read_file(filename: str, offset: int = 0) -> str:
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

    return paged(
        text,
        offset,
        settings.max_file_content_length,
        path.name,
        tail=" Read the whole file before rewriting it.",
    )


# --- 🔻 What the model is offered, and what runs when it picks one

TOOL_SCHEMAS = [
    WEB_SEARCH_SCHEMA,
    READ_URL_SCHEMA,
    WRITE_REPORT_SCHEMA,
    LIST_FILES_SCHEMA,
    READ_FILE_SCHEMA,
]

TOOL_REGISTRY = {
    "web_search": web_search,
    "read_url": read_url,
    "write_report": write_report,
    "list_files": list_files,
    "read_file": read_file,
}
