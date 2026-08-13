"""User-facing context for tool calls.

Tool schemas are written for the model. An approval request is written for the
person who carries the risk. This module translates between the two without
changing the arguments that are eventually sent to the tool.
"""

from dataclasses import dataclass
from typing import Any, Literal

Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ToolContext:
    """The information a person needs before allowing a tool call."""

    title: str
    intent: str
    implication: str
    severity: Severity


def describe_tool_call(
    name: str,
    args: dict[str, Any] | None = None,
    *,
    intent: str | None = None,
) -> ToolContext:
    """Describe a tool call in user language, with a safe fallback intent.

    ``intent`` is normally the model's own sentence from immediately before
    the call. The deterministic fallback keeps the approval UI useful when a
    provider emits a tool call without accompanying text.
    """
    arguments = args or {}
    target = _target(arguments)
    supplied_intent = _clean_intent(intent)

    if name == "write_file":
        return ToolContext(
            title="Create or replace a file",
            intent=supplied_intent or f"Save generated content to {target}.",
            implication=(
                f"This writes to {target}. If the file exists, its contents may be "
                "replaced. The change remains in the sandbox until it is reset."
            ),
            severity="medium",
        )

    if name == "edit_file":
        return ToolContext(
            title="Modify a file",
            intent=supplied_intent or f"Change selected content in {target}.",
            implication=(
                f"This changes {target} in place. A broad replacement can affect "
                "more text than expected."
            ),
            severity="medium",
        )

    if name in {"move_file", "copy_file"}:
        source = _path_arg(arguments, "source")
        destination = _path_arg(arguments, "destination")
        moving = name == "move_file"
        verb = "Move" if moving else "Copy"
        return ToolContext(
            title=f"{verb} a file",
            intent=supplied_intent or f"{verb} {source} to {destination}.",
            implication=(
                f"This {verb.lower()}s {source} to {destination}"
                + (
                    ". The file will no longer be at its old location, so anything "
                    "referring to it by the old path will not find it."
                    if moving
                    else ", leaving the original in place."
                )
            ),
            severity="medium",
        )

    if name == "delete_file":
        target_file = _path_arg(arguments, "path")
        return ToolContext(
            title="Delete a file",
            intent=supplied_intent or f"Delete {target_file}.",
            implication=(
                f"This permanently removes {target_file}. There is no undo and no "
                "recycle bin. If it was not truly a redundant copy, it is gone."
            ),
            severity="high",
        )

    if name == "execute":
        command = str(arguments.get("command") or arguments.get("cmd") or "a command")
        return ToolContext(
            title="Run a sandbox command",
            intent=supplied_intent
            or f"Run `{_shorten(command, 120)}` to continue the task.",
            implication=(
                "This starts a local process inside the project sandbox. It can use "
                "compute and create or modify sandbox files."
            ),
            severity="high",
        )

    if name in {
        "read_file",
        "ls",
        "glob",
        "grep",
        "find_duplicate_files",
        "get_current_project_context",
    }:
        return ToolContext(
            title="Inspect sandbox data",
            intent=supplied_intent or f"Read information from {target}.",
            implication="This reads sandbox data and does not intentionally change files.",
            severity="low",
        )

    if name == "task":
        subagent = str(arguments.get("subagent_type") or "a specialist")
        return ToolContext(
            title="Delegate to a specialist",
            intent=supplied_intent
            or f"Ask {subagent} to handle a focused part of the task.",
            implication=(
                "This starts a separate agent context. It can use only the tools assigned "
                "to that specialist."
            ),
            severity="low",
        )

    return ToolContext(
        title=f"Use {name.replace('_', ' ')}",
        intent=supplied_intent or f"Use {name} to continue the requested task.",
        implication=(
            "This invokes an external capability. Review its arguments and result for "
            "the exact effect."
        ),
        severity="medium",
    )


def _target(args: dict[str, Any]) -> str:
    for key in ("file_path", "path", "pattern"):
        value = args.get(key)
        if value:
            return f"`{_shorten(str(value), 100)}`"
    return "the sandbox"


def _path_arg(args: dict[str, Any], key: str) -> str:
    """One named path argument, or a readable stand-in if it is missing."""
    value = args.get(key)
    return f"`{_shorten(str(value), 100)}`" if value else "an unspecified path"


def _clean_intent(intent: str | None) -> str | None:
    if not intent:
        return None
    cleaned = " ".join(intent.split())
    if not cleaned or cleaned.startswith("Tool execution requires approval"):
        return None
    return _shorten(cleaned, 280)


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"
