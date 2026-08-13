"""Connecting the agent to MCP servers (station S6).

MCP is why you do not write an integration per service: a server publishes
tools over a standard protocol and any client can use them. It is also the
fastest way to hand an agent an enormous amount of capability by accident,
which is why `TOOL_ALLOWLIST` exists.

Two frictions worth knowing before you start:

- **Loading tools is async; Streamlit is not.** Tools are fetched once, at
  agent-construction time, so a single `asyncio.run` at startup is enough. Do
  not reach for this per turn.
- **A Node prerequisite is not free.** The obvious filesystem server is
  `npx`-based, which would mean installing Node for a room of Python
  developers. The server here is a Python script in this repo, so the whole
  day stays inside one toolchain -- and inside one pinned dependency set.
- **MCP tools are async-only.** They arrive with `coroutine` set and `func`
  unset, so the sync path raises. See `as_sync_tool`.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
import sys
from typing import Any, cast

from langchain_core.tools import BaseTool

from ddd_harness_engineering import PROJECT_ROOT

SERVER_SCRIPT = PROJECT_ROOT / "scripts" / "freight_mcp_server.py"

MCP_SERVERS: dict[str, dict[str, Any]] = {
    "northwind": {
        "transport": "stdio",
        "command": sys.executable,
        "args": [str(SERVER_SCRIPT)],
    }
}
"""Servers to connect. Keep this short; every server adds tools to the prompt.

This one lives in the repo. An off-the-shelf server was tried first and pinned
-- `mcp-server-fetch` -- and it fails on import against `mcp` 1.28.1 because
`McpError` was renamed upstream to `MCPError`. Two independently versioned
processes having to agree is MCP's real operational cost, and it is a poor
thing to discover live on someone else's laptop. `sys.executable` is used
rather than `uvx` or `python` because the spawned process must be the project
venv, and a bare `python` is not on PATH on Windows.
"""

TOOL_ALLOWLIST: frozenset[str] = frozenset(
    {"file_stats", "file_checksum", "oldest_files"}
)
"""Which of the server's tools the agent actually gets.

Anthropic's own guidance names bloated, overlapping tool sets as the single
most common agent failure mode: the model has to choose, and choosing badly
between forty similar tools is a bigger risk than lacking one. Empty means
"everything the server offers" -- try it, watch tool selection degrade, then
put the filter back.
"""

CONNECT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class McpLoadReport:
    """What the last connection attempt actually got.

    The scorecard asks participants to list every tool each server contributes
    *without reconnecting to check*, and to say what they dropped and why. That
    is only answerable if the load records itself, so it does.
    """

    attempted: bool = False
    connected: bool = False
    error: str | None = None
    offered: tuple[str, ...] = ()
    handed_over: tuple[str, ...] = ()

    @property
    def dropped(self) -> tuple[str, ...]:
        return tuple(name for name in self.offered if name not in self.handed_over)


_LAST_LOAD = McpLoadReport()


def mcp_status() -> McpLoadReport:
    """The result of this process's MCP load, for the harness panel.

    Module-level because `load_mcp_tools` runs exactly once per process, at
    agent construction, behind Streamlit's `cache_resource`.
    """
    return _LAST_LOAD


def filter_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """Narrow a server's tool list to what the task actually needs."""
    if not TOOL_ALLOWLIST:
        return list(tools)
    return [tool for tool in tools if tool.name in TOOL_ALLOWLIST]


async def _load(servers: dict[str, dict[str, Any]]) -> list[BaseTool]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(connections=cast_connections(servers))
    return await client.get_tools()


def cast_connections(servers: dict[str, dict[str, Any]]) -> Any:
    """The connection dicts are TypedDicts at runtime; hand them over as-is."""
    return servers


def load_mcp_tools(
    servers: dict[str, dict[str, Any]] | None = None,
) -> list[BaseTool]:
    """Fetch and filter tools from the configured MCP servers.

    Never raises. A server that is missing, slow or broken degrades the agent
    to its built-in tools rather than preventing it from starting -- a dead
    dependency should not take the whole workshop down.
    """
    global _LAST_LOAD

    servers = MCP_SERVERS if servers is None else servers
    if not servers:
        _LAST_LOAD = McpLoadReport(attempted=False)
        return []

    try:
        tools = asyncio.run(
            asyncio.wait_for(_load(servers), timeout=CONNECT_TIMEOUT_SECONDS)
        )
    except Exception as error:  # noqa: BLE001 - startup must survive a bad server
        import logging

        logging.getLogger(__name__).warning(
            "MCP tools unavailable (%s: %s); continuing without them.",
            type(error).__name__,
            error,
        )
        # A dead server used to be visible only in a log line nobody reads. The
        # panel reads this instead, so silent degradation stays observable.
        _LAST_LOAD = McpLoadReport(
            attempted=True,
            connected=False,
            error=f"{type(error).__name__}: {error}",
        )
        return []

    handed_over = filter_tools(tools)
    _LAST_LOAD = McpLoadReport(
        attempted=True,
        connected=True,
        offered=tuple(tool.name for tool in tools),
        handed_over=tuple(tool.name for tool in handed_over),
    )
    return [as_sync_tool(tool) for tool in handed_over]


def blocks_to_text(result: Any) -> str:
    """Flatten an MCP result into plain text.

    MCP tools return LangChain content blocks -- `[{'type': 'text', 'text': ...}]`
    -- not strings. Anyone asserting against a plain string gets a confusing
    failure, so normalise once, here.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts = [
            str(block.get("text", ""))
            for block in result
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part) or str(result)
    return str(result)


def as_sync_tool(tool: BaseTool) -> BaseTool:
    """Give an async-only MCP tool a synchronous entry point.

    MCP tools arrive with `coroutine` set and `func` unset, so calling one on
    the sync path raises "StructuredTool does not support sync invocation".
    The Streamlit app streams synchronously, so without this bridge every MCP
    tool call fails at runtime -- and only at runtime, once the model finally
    decides to use one.

    The coroutine is run in a worker thread with its own event loop, which
    keeps it clear of whatever loop the caller may already be running.
    """
    from concurrent.futures import ThreadPoolExecutor

    from langchain_core.tools import StructuredTool

    async def _call(**kwargs: Any) -> str:
        return blocks_to_text(await tool.ainvoke(kwargs))

    def _sync_call(**kwargs: Any) -> str:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(_call(**kwargs))).result()

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=cast("Any", tool.args_schema),
        func=_sync_call,
        coroutine=_call,
    )


def describe_tools(tools: Sequence[BaseTool]) -> str:
    """One line per tool, for showing participants what a server actually gave."""
    if not tools:
        return "No MCP tools loaded."
    return "\n".join(f"- {tool.name}: {tool.description[:100]}" for tool in tools)
