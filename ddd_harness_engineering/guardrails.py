"""A command allowlist for the interpreter (station S4).

Giving an agent shell execution is the largest single capability jump in the
whole day, and deepagents says so itself. From `backends/local_shell.py`:

    This backend grants agents BOTH direct filesystem access AND unrestricted
    shell execution on your local machine ... NO sandboxing or isolation.

The library is warning you in its own docstring. This middleware is the answer:
`execute` calls are inspected before they run, and anything outside a small
allowlist is refused with an explanation the model can act on.

What this is and is not:

- It **is** a meaningful reduction in blast radius for a workshop laptop.
- It is **not** a sandbox. It parses a command string, and command strings are
  adversarial input. A determined attacker who controls the model's output has
  many shapes to try. Real isolation is a container or a VM, not a regex.

That distinction is the point of the station. Layer it: this allowlist, plus the
filesystem root from S2, plus the approval gate from S7.
"""

from dataclasses import dataclass
import shlex
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

ALLOWED_COMMANDS = frozenset(
    {
        "python",
        "python3",
        "uv",
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "find",
        "grep",
        "echo",
        "pwd",
    }
)
"""Commands the agent may run. Deliberately short -- add to it consciously."""

BLOCKED_SUBSTRINGS = (
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    ">",
    "<",
    "\n",
)
"""Shell metacharacters that chain, redirect or substitute another command.

`ls; rm -rf /` starts with an allowed command. Chaining is how an allowlist gets
walked straight past, so the shape is refused before the name is even checked.
"""

MAX_OUTPUT_CHARS = 4000
"""Cap on captured output, so a runaway command cannot flood the context window."""

EXECUTE_TIMEOUT_SECONDS = 60
"""Lower than deepagents' 120s default: a workshop exercise should not hang."""

REFUSAL_PREFIX = "Refused: "
"""Marks a refusal, so the trace can tell one apart from a tool that broke.

Both readers of this string live in this repo: `check_command` writes it, and
`agent.py` matches on it to label the step `guardrail` rather than `error`. A
refusal is the harness working; an error is the harness failing, and S2 and S4
both ask participants to point at the difference in the trace.
"""


def python_executable() -> str:
    """Absolute path to the interpreter the agent should run.

    Not simply "python". `LocalShellBackend` spawns a plain shell that does not
    inherit the project venv, and on Windows neither `python`, `python3` nor
    `uv` is on that shell's PATH -- verified. A bare `python` therefore fails
    with "not recognized", which reads like a broken exercise rather than a
    misconfigured PATH. Handing the model the absolute path avoids the whole
    detour; the allowlist normalises it back to `python`, so it stays allowed.
    """
    import sys

    return sys.executable


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str = ""


def check_command(command: str) -> Verdict:
    """Decide whether a shell command may run.

    Refusals explain themselves, because the model is expected to read the
    refusal and try something else rather than give up or retry identically.
    """
    if not command or not command.strip():
        return Verdict(False, f"{REFUSAL_PREFIX}the command was empty.")

    for token in BLOCKED_SUBSTRINGS:
        if token in command:
            label = "newline" if token == "\n" else f"{token!r}"
            return Verdict(
                False,
                f"{REFUSAL_PREFIX}the command contains {label}. Chaining, piping "
                "and redirection are not permitted. Run one simple command at a "
                "time, or write a Python script into workspace/ and run that.",
            )

    try:
        parts = shlex.split(command)
    except ValueError as error:
        return Verdict(False, f"{REFUSAL_PREFIX}could not parse the command ({error}).")

    if not parts:
        return Verdict(False, f"{REFUSAL_PREFIX}the command was empty.")

    program = parts[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    program = program.removesuffix(".exe")

    if program not in ALLOWED_COMMANDS:
        return Verdict(
            False,
            f"Refused: {program!r} is not an allowed command. "
            f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}. "
            "For anything else, write a Python script into workspace/ and run "
            "it with python.",
        )

    return Verdict(True)


def truncate_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n...[{dropped:,} characters truncated]"


class CommandAllowlistMiddleware(AgentMiddleware[Any, Any, Any]):
    """Refuse `execute` calls that fall outside the allowlist.

    Uses `wrap_tool_call`, which sits between the model's request and the tool,
    so a refusal never reaches the shell at all.
    """

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Any],
    ) -> Any:
        tool_call = getattr(request, "tool_call", None) or {}
        if tool_call.get("name") != "execute":
            return handler(request)

        command = str(tool_call.get("args", {}).get("command", ""))
        verdict = check_command(command)
        if not verdict.allowed:
            # Return a ToolMessage instead of raising: the model sees why it was
            # refused and can adapt, and the refusal lands in the trace.
            return ToolMessage(
                content=verdict.reason,
                name="execute",
                tool_call_id=str(tool_call.get("id", "")),
                status="error",
            )

        result = handler(request)
        if isinstance(result, ToolMessage) and isinstance(result.content, str):
            result.content = truncate_output(result.content)
        return result
