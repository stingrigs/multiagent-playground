# ====================================
#  🔰 [RESEARCH TEAM] ReportMCP
# ====================================

import json
import sys
from pathlib import Path
from typing import Annotated

# run as `python mcp_servers/report_mcp.py` -> sys.path[0] is mcp_servers/, not the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP
from pydantic import Field

from config import Settings

settings = Settings()

mcp = FastMCP(name="ReportMCP")


def output_path(filename: str) -> Path:
    """Strips directory components — filenames come from the LLM, not from us."""
    name = Path(filename.strip()).name
    if not name or name in {".", ".."}:
        raise ValueError(f"Invalid filename: {filename!r}")
    return Path(settings.output_dir) / name


# --- 🔻 [RESOURCE]: Output Directory


@mcp.resource("resource://output-dir")
def output_dir() -> str:
    """Where reports are written, and what has been written so far."""
    directory = Path(settings.output_dir)
    reports = (
        sorted(p.name for p in directory.glob("*.md")) if directory.exists() else []
    )
    return json.dumps({"path": str(directory.resolve()), "reports": reports})


# --- 🔻 [TOOL]: Save Report


@mcp.tool
def save_report(
    filename: Annotated[
        str, Field(description="File name only, no path. E.g. 'rag_comparison.md'")
    ],
    content: Annotated[str, Field(description="Full report body in Markdown")],
) -> str:
    """Save a Markdown report to the output directory."""
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


if __name__ == "__main__":
    print(f"ReportMCP on {settings.report_mcp_url}")
    mcp.run(
        transport="http",
        host=settings.host,
        port=settings.report_mcp_port,
        log_level="warning",
    )
