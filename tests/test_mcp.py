"""Tests for the MCP integration (station S6).

No test spawns the real server: the client is substituted, so CI stays fast and
does not depend on a subprocess. The real round trip is exercised manually --
see the module docstring in `ddd_harness_engineering/mcp_tools.py`.
"""

from typing import Any, cast

from langchain_core.tools import StructuredTool

from ddd_harness_engineering import mcp_tools as mcp


def _tool(name: str) -> StructuredTool:
    """A stand-in shaped like a real MCP tool: async-only, returns blocks."""

    async def _call(relative_path: str = "") -> list[dict[str, str]]:
        return [{"type": "text", "text": f"{name}:{relative_path}"}]

    return cast(
        "StructuredTool",
        StructuredTool.from_function(
            coroutine=_call, name=name, description=f"{name} description"
        ),
    )


def test_the_allowlist_narrows_a_bloated_server() -> None:
    """The server publishes twelve tools; the agent should see three.

    Anthropic names bloated, overlapping tool sets as the most common agent
    failure mode -- the risk is the model choosing badly, not the count itself.
    """
    published = [
        _tool(name)
        for name in (
            "file_stats",
            "file_checksum",
            "oldest_files",
            "count_files",
            "count_directories",
            "total_size",
            "largest_files",
            "newest_files",
            "empty_files",
            "files_by_extension",
            "extension_summary",
            "directory_tree",
        )
    ]

    kept = mcp.filter_tools(published)

    assert sorted(tool.name for tool in kept) == [
        "file_checksum",
        "file_stats",
        "oldest_files",
    ]


def test_an_empty_allowlist_keeps_everything(monkeypatch: Any) -> None:
    """Try this in the workshop, then watch tool selection degrade."""
    monkeypatch.setattr(mcp, "TOOL_ALLOWLIST", frozenset())
    published = [_tool("a"), _tool("b")]

    assert mcp.filter_tools(published) == published


def test_content_blocks_are_flattened_to_text() -> None:
    """MCP returns blocks, not strings. Asserting against a string surprises people."""
    blocks = [{"type": "text", "text": "42"}, {"type": "text", "text": "43"}]

    assert mcp.blocks_to_text(blocks) == "42\n43"


def test_flattening_passes_a_plain_string_through() -> None:
    assert mcp.blocks_to_text("already text") == "already text"


def test_an_async_only_tool_gains_a_sync_entry_point() -> None:
    """The bridge that stops every MCP call failing on Streamlit's sync path."""
    async_only = _tool("file_stats")
    assert async_only.func is None, "precondition: MCP tools arrive async-only"

    bridged = cast("StructuredTool", mcp.as_sync_tool(async_only))

    assert bridged.func is not None
    assert bridged.coroutine is not None
    assert bridged.name == "file_stats"
    assert bridged.invoke({"relative_path": "data"}) == "file_stats:data"


def test_a_broken_server_degrades_instead_of_breaking_startup(
    monkeypatch: Any,
) -> None:
    """A dead dependency should not take the whole workshop down."""

    async def explode(_servers: Any) -> list[Any]:
        raise RuntimeError("server not found")

    monkeypatch.setattr(mcp, "_load", explode)

    assert mcp.load_mcp_tools() == []


def test_no_servers_configured_is_not_an_error() -> None:
    assert mcp.load_mcp_tools({}) == []


def test_the_server_is_spawned_with_the_project_interpreter() -> None:
    """`python` is not on PATH on Windows; the venv interpreter must be explicit."""
    import sys

    connection = mcp.MCP_SERVERS["northwind"]

    assert connection["command"] == sys.executable
    assert mcp.SERVER_SCRIPT.is_file()
