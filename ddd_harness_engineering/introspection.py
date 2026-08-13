"""What is actually wired into this harness, station by station.

The eight stations each change one part of the agent, and a participant needs to
be able to answer two questions about their own harness at any moment: *is this
component wired up*, and *what exactly is in it*. Neither is answerable from the
chat, and several are not answerable from the trace either -- three of the eight
acceptance checks are assertions about **absence** (`web_search` is absent from
the main agent, the MCP list is shorter than the server's, a path is refused),
and an append-only event log cannot show absence.

So this module reads the configuration and reports it. Two rules follow from
where it gets used:

- **It never raises.** Participants run this from `solutions/s1` through
  `solutions/s8`, where later stations are deliberately unwired -- no
  `interrupt_on`, empty subagent stubs, no skills directory, a `StateBackend`
  instead of a rooted one. A missing component has to render as "not configured
  yet", never as a stack trace over the whole panel.
- **It reports, it does not judge.** `wired` answers "is this component present",
  not "is this component correct". Whether the tool descriptions are any good is
  the exercise, not something a dataclass can score.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

from ddd_harness_engineering import env
from ddd_harness_engineering.sandbox import WORKSPACE_DIR

_T = TypeVar("_T")


@dataclass(frozen=True)
class Detail:
    """One labelled fact about a station, and optionally what it contains.

    `body` holds the thing itself -- the prompt text, a skill's rules, a tool's
    docstring -- so the panel can show what is configured rather than only that
    something is.
    """

    label: str
    value: str
    body: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class StationStatus:
    station: str
    title: str
    component: str
    wired: bool
    summary: str
    details: list[Detail] = field(default_factory=list)
    # What proves it, phrased as the acceptance check from the event plan.
    check: str = ""


def describe_harness() -> list[StationStatus]:
    """Read the current configuration as eight station reports."""
    return [
        _describe_model_and_prompt(),
        _describe_tools_and_environment(),
        _describe_subagents(),
        _describe_interpreter(),
        _describe_skills(),
        _describe_mcp(),
        _describe_human_in_the_loop(),
        _describe_evals(),
    ]


# --- S1 ---------------------------------------------------------------------


def _describe_model_and_prompt() -> StationStatus:
    prompt = _safe(lambda: str(_agent_attr("_SYSTEM_PROMPT", "")), "")
    effort = _safe(lambda: str(_agent_attr("REASONING_EFFORT", "unknown")), "unknown")
    deployment = _safe(lambda: env.MICROSOFT_FOUNDRY_DEPLOYMENT, "unknown")

    return StationStatus(
        station="S1",
        title="Model, Prompt & Context",
        component="Model · Prompt · Context engineering",
        wired=bool(prompt),
        summary=f"{deployment} at `{effort}` effort · {len(prompt):,}-char system prompt",
        check="A prompt change produces a visibly different trace; "
        "effort change moves step and token counts.",
        details=[
            Detail("Deployment", deployment),
            Detail("Reasoning effort", effort),
            Detail(
                "System prompt",
                f"{len(prompt):,} characters",
                body=prompt or "No system prompt configured.",
                language="markdown",
            ),
        ],
    )


# --- S2 ---------------------------------------------------------------------


def _describe_tools_and_environment() -> StationStatus:
    tools = _main_tools()
    backend = _backend_report()

    return StationStatus(
        station="S2",
        title="Tools & Environment",
        component="Tools · Environment/sandbox · Guardrails",
        wired=bool(tools) and backend.rooted,
        summary=(
            f"{len(tools)} repo tool(s) · {backend.kind} rooted at "
            f"`{backend.root or 'unrooted'}`"
        ),
        check="`find_duplicate_files` returns the seeded group; `read ../../.env` "
        "is refused; the refusal appears in the trace.",
        details=[
            *(
                Detail(f"Tool · {name}", "main agent", body=description)
                for name, description in tools
            ),
            Detail("Backend", backend.kind),
            Detail("Root", backend.root or "not rooted"),
            Detail(
                "Path containment",
                "virtual_mode=True" if backend.virtual_mode else "virtual_mode=False",
                body=(
                    "Absolute paths and `..` are resolved inside the root."
                    if backend.virtual_mode
                    else "With virtual_mode=False, absolute paths and `..` bypass "
                    "root_dir -- the root becomes a suggestion, not a boundary."
                ),
            ),
            Detail(
                "Blast radius",
                f"writes land under {WORKSPACE_DIR}/ inside the root",
                body=_permissions_note(),
            ),
        ],
    )


def _permissions_note() -> str:
    """Why declared write permissions are not in force, when they are not."""
    declared = _safe(lambda: _agent_attr("_PERMISSIONS", None), None)
    if declared is None:
        return "No FilesystemPermission rules are defined."

    return (
        "`_PERMISSIONS` is defined but deliberately NOT passed to the agent. "
        "deepagents 0.6.12 raises NotImplementedError when `permissions` is "
        "combined with an execute-capable backend, so granting a shell (S4) and "
        "declaring write rules (S2) are mutually exclusive. Write control rests "
        "on the command allowlist, the approval gate and the sandbox root "
        "instead. Swap the backend for a plain FilesystemBackend to get it back."
    )


# --- S3 ---------------------------------------------------------------------


def _describe_subagents() -> StationStatus:
    subagents = _safe(
        lambda: cast("list[dict[str, Any]]", _agent_attr("_SUBAGENTS", [])), []
    )
    main_names = {name for name, _ in _main_tools()}

    details: list[Detail] = []
    exclusive: list[str] = []
    for spec in subagents:
        name = str(spec.get("name", "?"))
        own = _tool_names(spec.get("tools"))
        # A tool on a subagent and not on the main agent is least privilege made
        # structural. Naming the difference is what makes the absence provable.
        scoped = sorted(own - main_names)
        exclusive.extend(scoped)
        details.append(
            Detail(
                f"Subagent · {name}",
                # No `tools` key means it inherits the parent's list, which is
                # the opposite of least privilege and worth saying out loud.
                ", ".join(sorted(own)) if own else "inherits every main-agent tool",
                body=str(spec.get("system_prompt") or "No system prompt set."),
                language="markdown",
            )
        )

    details.append(
        Detail(
            "Main agent tools",
            ", ".join(sorted(main_names)) or "none",
            body="Compare against the subagent lists above. A tool that appears "
            "there and not here is unreachable from the main agent.",
        )
    )
    if exclusive:
        details.append(
            Detail(
                "Scoped to a subagent only",
                ", ".join(sorted(set(exclusive))),
                body="Confirmed absent from the main agent's toolset.",
            )
        )

    configured = [spec for spec in subagents if spec.get("system_prompt")]
    return StationStatus(
        station="S3",
        title="Subagents & Orchestration",
        component="Orchestration · Context engineering · Guardrails",
        wired=bool(configured),
        summary=(
            f"{len(configured)} subagent(s)"
            + (
                f" · {', '.join(sorted(set(exclusive)))} scoped away from main"
                if exclusive
                else ""
            )
        ),
        check="Trace shows a `main > subagent` hop; `web_search` is absent from "
        "the main agent's toolset; the planted injection does not change "
        "behaviour after mitigation.",
        details=details,
    )


# --- S4 ---------------------------------------------------------------------


def _describe_interpreter() -> StationStatus:
    backend = _backend_report()
    guardrails = _module("ddd_harness_engineering.guardrails")
    allowed = sorted(
        _safe(lambda: set(getattr(guardrails, "ALLOWED_COMMANDS", [])), set())
    )
    blocked = _safe(lambda: tuple(getattr(guardrails, "BLOCKED_SUBSTRINGS", ())), ())

    return StationStatus(
        station="S4",
        title="The interpreter",
        component="Environment · Guardrails",
        wired=backend.can_execute,
        summary=(
            f"shell {'available' if backend.can_execute else 'unavailable'}"
            + (f" · {len(allowed)} allowed command(s)" if allowed else "")
        ),
        check="A chart lands in workspace/; a blocked command is refused and logged.",
        details=[
            Detail(
                "execute tool",
                "available" if backend.can_execute else "not available",
                body="`execute` appears only when the backend implements "
                "SandboxBackendProtocol. Locally that is LocalShellBackend, "
                "which grants shell access on this machine with no isolation.",
            ),
            Detail(
                "Command allowlist",
                ", ".join(allowed) or "not configured",
                body="Anything outside this list is refused with a reason the "
                "model can act on. This is a smaller blast radius, not a sandbox.",
            ),
            Detail(
                "Blocked shell syntax",
                " ".join(repr(token) for token in blocked) or "not configured",
                body="Chaining, piping and redirection are refused before the "
                "program name is even checked, because `ls; rm -rf /` starts "
                "with an allowed command.",
            ),
            Detail(
                "Output cap",
                f"{_safe(lambda: getattr(guardrails, 'MAX_OUTPUT_CHARS', 0), 0):,} chars",
            ),
        ],
    )


# --- S5 ---------------------------------------------------------------------


def _describe_skills() -> StationStatus:
    skills = _installed_skills()

    return StationStatus(
        station="S5",
        title="Skills",
        component="Skills",
        wired=bool(skills),
        summary=f"{len(skills)} skill(s) installed"
        if skills
        else "no skills installed",
        check="The agent applies the SKILL.md convention without being told it "
        "in chat.",
        details=[
            Detail(
                f"Skill · {skill['name']}",
                str(skill.get("allowed-tools") or "all tools"),
                body=(
                    f"**description** (this is all the model sees until the skill "
                    f"is invoked)\n\n{skill.get('description', '')}\n\n---\n\n"
                    f"{skill['body']}"
                ),
                language="markdown",
            )
            for skill in skills
        ]
        or [
            Detail(
                "Skills directory",
                _skills_dir_label(),
                body="No SKILL.md found. A skill is procedural knowledge -- how "
                "the work should be done -- and costs no tokens until invoked.",
            )
        ],
    )


def _skills_dir_label() -> str:
    directory = _skills_dir()
    return str(directory) if directory else "not configured"


def _skills_dir() -> Path | None:
    home = _safe(lambda: cast("Path", _agent_attr("AGENT_HOME", None)), None)
    if not isinstance(home, Path):
        return None
    candidate = home / "skills"
    return candidate if candidate.is_dir() else None


def _installed_skills() -> list[dict[str, str]]:
    """Parse each SKILL.md's frontmatter and body.

    Only the frontmatter reaches the model until the skill is invoked, which is
    the whole point of the station, so the two are kept visibly separate.
    """
    directory = _skills_dir()
    if directory is None:
        return []

    skills: list[dict[str, str]] = []
    for path in sorted(directory.glob("*/SKILL.md")):
        text = _safe(lambda p=path: p.read_text(encoding="utf-8"), "")
        frontmatter, body = _split_frontmatter(text)
        frontmatter.setdefault("name", path.parent.name)
        frontmatter["body"] = body
        skills.append(frontmatter)
    return skills


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a `---`-delimited YAML header from the markdown body.

    Deliberately not a YAML parser: skill frontmatter here is flat `key: value`
    lines, and this module must not gain a dependency to render a panel.
    """
    if not text.startswith("---"):
        return {}, text

    _, _, remainder = text.partition("---")
    header, separator, body = remainder.partition("\n---")
    if not separator:
        return {}, text

    parsed: dict[str, str] = {}
    for line in header.splitlines():
        key, colon, value = line.partition(":")
        if colon and key.strip():
            parsed[key.strip()] = value.strip()
    return parsed, body.strip()


# --- S6 ---------------------------------------------------------------------


def _describe_mcp() -> StationStatus:
    mcp = _module("ddd_harness_engineering.mcp_tools")
    status = _safe(lambda: getattr(mcp, "mcp_status")(), None)
    servers = _safe(lambda: cast("dict[str, Any]", getattr(mcp, "MCP_SERVERS", {})), {})

    offered = tuple(getattr(status, "offered", ()) or ())
    handed_over = tuple(getattr(status, "handed_over", ()) or ())
    dropped = tuple(getattr(status, "dropped", ()) or ())
    connected = bool(getattr(status, "connected", False))
    error = getattr(status, "error", None)
    attempted = bool(getattr(status, "attempted", False))

    details = [
        Detail("Servers", ", ".join(servers) or "none configured"),
        Detail(
            "Connection",
            "connected"
            if connected
            else ("failed" if attempted else "not attempted this process"),
            body=str(error) if error else None,
        ),
    ]
    if offered or handed_over:
        details.extend(
            [
                Detail(
                    "Offered by the server",
                    f"{len(offered)} tool(s)",
                    body=", ".join(offered) or "none",
                ),
                Detail(
                    "Handed to the model",
                    f"{len(handed_over)} tool(s)",
                    body=", ".join(handed_over) or "none",
                ),
                Detail(
                    "Dropped by the allowlist",
                    f"{len(dropped)} tool(s)",
                    body=(", ".join(dropped) or "nothing dropped")
                    + "\n\nBloated, overlapping tool sets are the most common "
                    "agent failure mode: the model has to choose, and choosing "
                    "badly between forty similar tools is the bigger risk.",
                ),
            ]
        )

    return StationStatus(
        station="S6",
        title="MCP",
        component="MCP",
        wired=connected and bool(handed_over),
        summary=(
            f"{len(handed_over)} of {len(offered)} tool(s) handed over"
            if connected
            else ("connection failed" if attempted else "not connected")
        ),
        check="MCP tools appear in the trace; the filtered list is shorter than "
        "the server's full list.",
        details=details,
    )


# --- S7 ---------------------------------------------------------------------


def _describe_human_in_the_loop() -> StationStatus:
    gated = _safe(
        lambda: cast("dict[str, Any]", _agent_attr("_INTERRUPT_ON", {}) or {}), {}
    )

    return StationStatus(
        station="S7",
        title="Human in the loop",
        component="Human in the loop · Memory & state",
        wired=bool(gated),
        summary=f"{len(gated)} tool(s) require approval"
        if gated
        else "no approval gate configured",
        check="The graph pauses; the dialog renders the pending call and args; "
        "approve/edit/reject each produce a distinct observable outcome; state "
        "survives the Streamlit rerun.",
        details=[
            Detail(
                "Gated tools",
                ", ".join(sorted(gated)) or "none",
                body="Anything absent is auto-approved, so reading stays instant "
                "and only writes stop for review.",
            ),
            Detail(
                "Checkpointer",
                "InMemorySaver",
                body="No checkpointer, no pause: an interrupt needs saved state "
                "to resume from. In-memory means the thread dies with the "
                "process, and editing agent.py rebuilds the cached agent.",
            ),
        ],
    )


# --- S8 ---------------------------------------------------------------------


def _describe_evals() -> StationStatus:
    directory = _safe(lambda: _project_root() / "tests" / "evals", None)
    files = (
        sorted(path.name for path in directory.glob("test_*.py"))
        if directory and directory.is_dir()
        else []
    )

    return StationStatus(
        station="S8",
        title="Observability & evals",
        component="Observability & evals",
        wired=bool(files),
        summary=f"{len(files)} eval module(s)" if files else "no evals found",
        check="Three evals pass locally and in CI; deliberately breaking a "
        "guardrail turns exactly one red.",
        details=[
            Detail(
                "Eval modules",
                ", ".join(files) or "none",
                body="Run them with `uv run pytest tests/evals`. Evals in CI, "
                "not vibes -- this is the station that catches the regression "
                "when someone edits a prompt next month.",
            ),
            Detail(
                "Narration check",
                "walk one full trace end to end",
                body="Open Activity, enable Technical details, and narrate every "
                "step out loud. Any "
                "step you cannot explain is a bug you have not found yet.",
            ),
        ],
    )


# --- reading the configuration safely ---------------------------------------


@dataclass(frozen=True)
class _BackendReport:
    kind: str = "unknown"
    root: str | None = None
    virtual_mode: bool = False
    rooted: bool = False
    can_execute: bool = False


def _backend_report() -> _BackendReport:
    """Describe the configured backend without building an agent.

    Constructing the backend is cheap and side-effect free, but it can raise --
    `sandbox_root()` fails loudly when the sandbox has not been seeded -- so the
    whole probe is guarded.
    """

    def probe() -> _BackendReport:
        backend = getattr(_agent_module(), "create_backend")()
        default = getattr(backend, "default", backend)
        # deepagents takes `root_dir` as the constructor argument but stores it
        # as `cwd`, so read both rather than trusting the parameter name.
        root = getattr(default, "root_dir", None) or getattr(default, "cwd", None)
        return _BackendReport(
            kind=type(default).__name__,
            root=str(root) if root else None,
            virtual_mode=bool(getattr(default, "virtual_mode", False)),
            rooted=root is not None,
            # What makes the `execute` tool appear at all.
            can_execute=hasattr(default, "execute"),
        )

    return _safe(probe, _BackendReport())


def _main_tools() -> list[tuple[str, str]]:
    """The main agent's repo tools as (name, description) pairs."""

    def probe() -> list[tuple[str, str]]:
        tools = getattr(_agent_module(), "main_tools")()
        return [
            (str(tool.name), str(tool.description or "No description."))
            for tool in tools
        ]

    return _safe(probe, [])


def _tool_names(tools: object) -> set[str]:
    if not isinstance(tools, (list, tuple)):
        return set()
    names: set[str] = set()
    for tool in cast("list[object]", list(tools)):
        name = getattr(tool, "name", None)
        if isinstance(name, str):
            names.add(name)
    return names


def _agent_module() -> Any:
    return _module("ddd_harness_engineering.agent")


def _agent_attr(name: str, default: object) -> Any:
    return getattr(_agent_module(), name, default)


def _project_root() -> Path:
    from ddd_harness_engineering import PROJECT_ROOT

    return PROJECT_ROOT


def _module(name: str) -> Any:
    """Import a module by name, or return a stand-in with no attributes.

    Imported late and by name so a branch that has not created a module yet --
    or one whose import fails -- degrades to "not configured" rather than
    taking the panel down with it.
    """
    from importlib import import_module

    try:
        return import_module(name)
    except Exception:  # noqa: BLE001 - the panel must render regardless
        return object()


def _safe(read: Callable[[], _T], default: _T) -> _T:
    """Run a configuration read, falling back rather than raising.

    Broad by design. This module's whole job is to report on harnesses that are
    half-built, and every station it describes is optional on some branch.
    """
    try:
        return read()
    except Exception:  # noqa: BLE001 - see the module docstring
        return default
