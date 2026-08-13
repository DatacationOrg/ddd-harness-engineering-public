"""A small MCP server for the workshop (station S6).

Run directly, it speaks MCP over stdio:

    uv run python scripts/freight_mcp_server.py

You are not expected to run it by hand -- `ddd_harness_engineering/mcp_tools.py`
spawns it. It exists so the station has a server we control.

**Why not an off-the-shelf server?** We tried. `mcp-server-fetch` pinned to a
recent release fails on import against `mcp` 1.28.1, because `McpError` was
renamed to `MCPError` upstream. That is a fair illustration of MCP's real
operational cost -- two independently versioned processes have to agree -- but
it is a poor thing to discover live, in front of a room, on someone else's
laptop. Owning the server removes the network, the version drift and the
supply-chain question in one move.

It deliberately publishes **twelve** tools, of which the client allowlists
three. That is the point of the station: connect it unfiltered and watch tool
selection degrade, then put the filter back.
"""

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sys

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_ROOT = PROJECT_ROOT / "sandbox" / "northwind-freight"

mcp = FastMCP(
    "northwind-freight",
    instructions="Read-only utilities over the Northwind Freight document drive.",
)


def _safe(relative: str) -> Path:
    """Resolve a path inside the sandbox, refusing anything that escapes.

    A server is a separate process with its own privileges. It cannot rely on
    the client's guardrails, so it enforces its own.
    """
    target = (SANDBOX_ROOT / relative.lstrip("/")).resolve()
    if not str(target).startswith(str(SANDBOX_ROOT.resolve())):
        raise ValueError(f"Path escapes the sandbox: {relative!r}")
    return target


# --- The three tools the client actually allowlists -------------------------


@mcp.tool()
def file_stats(relative_path: str = "") -> str:
    """Count files, directories and total bytes under a folder in the drive."""
    root = _safe(relative_path)
    if not root.is_dir():
        return f"Not a directory: {relative_path!r}"
    files = [p for p in root.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    dirs = sum(1 for p in root.rglob("*") if p.is_dir())
    return f"{len(files)} files, {dirs} directories, {total:,} bytes under {relative_path or '.'}"


@mcp.tool()
def file_checksum(relative_path: str) -> str:
    """Return the sha256 checksum of one file, for confirming two files match."""
    target = _safe(relative_path)
    if not target.is_file():
        return f"Not a file: {relative_path!r}"
    return hashlib.sha256(target.read_bytes()).hexdigest()


@mcp.tool()
def oldest_files(limit: int = 10) -> str:
    """List the least recently modified files, to find archive candidates."""
    files = sorted(
        (p for p in SANDBOX_ROOT.rglob("*") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
    )[: max(1, min(limit, 50))]
    return "\n".join(
        f"{datetime.fromtimestamp(p.stat().st_mtime, UTC):%Y-%m-%d}  "
        f"{p.relative_to(SANDBOX_ROOT).as_posix()}"
        for p in files
    )


# --- Nine more, so the bloated-toolset demo has something to bloat with ------
#
# Note how similar several of these are to each other and to the agent's
# built-in ls/glob/grep. That overlap is the failure mode, not the count.


@mcp.tool()
def count_files(relative_path: str = "") -> str:
    """Count files in a folder."""
    return str(sum(1 for p in _safe(relative_path).rglob("*") if p.is_file()))


@mcp.tool()
def count_directories(relative_path: str = "") -> str:
    """Count directories in a folder."""
    return str(sum(1 for p in _safe(relative_path).rglob("*") if p.is_dir()))


@mcp.tool()
def total_size(relative_path: str = "") -> str:
    """Total bytes of a folder."""
    return str(
        sum(p.stat().st_size for p in _safe(relative_path).rglob("*") if p.is_file())
    )


@mcp.tool()
def largest_files(limit: int = 5) -> str:
    """List the largest files."""
    files = sorted(
        (p for p in SANDBOX_ROOT.rglob("*") if p.is_file()),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )[:limit]
    return "\n".join(
        f"{p.stat().st_size:>10,}  {p.relative_to(SANDBOX_ROOT)}" for p in files
    )


@mcp.tool()
def newest_files(limit: int = 5) -> str:
    """List the most recently modified files."""
    files = sorted(
        (p for p in SANDBOX_ROOT.rglob("*") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    return "\n".join(p.relative_to(SANDBOX_ROOT).as_posix() for p in files)


@mcp.tool()
def empty_files() -> str:
    """List zero-byte files."""
    return "\n".join(
        p.relative_to(SANDBOX_ROOT).as_posix()
        for p in SANDBOX_ROOT.rglob("*")
        if p.is_file() and p.stat().st_size == 0
    )


@mcp.tool()
def files_by_extension(extension: str) -> str:
    """List files with a given extension."""
    return "\n".join(
        p.relative_to(SANDBOX_ROOT).as_posix()
        for p in SANDBOX_ROOT.rglob(f"*.{extension.lstrip('.')}")
    )


@mcp.tool()
def extension_summary() -> str:
    """Count files per extension."""
    counts: dict[str, int] = {}
    for path in SANDBOX_ROOT.rglob("*"):
        if path.is_file():
            counts[path.suffix or "(none)"] = counts.get(path.suffix or "(none)", 0) + 1
    return "\n".join(f"{ext}: {n}" for ext, n in sorted(counts.items()))


@mcp.tool()
def directory_tree(relative_path: str = "", depth: int = 2) -> str:
    """Show a folder tree."""
    root = _safe(relative_path)
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if len(rel.parts) <= depth:
            lines.append(f"{'  ' * (len(rel.parts) - 1)}{rel.name}")
    return "\n".join(lines[:200])


if __name__ == "__main__":
    if not SANDBOX_ROOT.is_dir():
        print(
            f"Sandbox missing at {SANDBOX_ROOT}. "
            "Run: uv run python scripts/seed_sandbox.py --reset",
            file=sys.stderr,
        )
        raise SystemExit(1)
    mcp.run(transport="stdio")
