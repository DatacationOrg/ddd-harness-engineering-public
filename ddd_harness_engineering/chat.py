from dataclasses import dataclass, field, replace
from typing import Any, Literal

from ddd_harness_engineering.tool_context import Severity

ChatRole = Literal["user", "assistant"]
ExecutionCategory = Literal[
    "model",
    "tool",
    "subagent",
    "state",
    "task",
    "approval",
    # A guardrail refused the call before it ran. Kept distinct from `error`
    # because a refusal is the harness working, not the harness breaking.
    "guardrail",
    "error",
    "internal",
]

# Tool output goes into the trace verbatim, and `execute` can return a whole
# CSV. Truncate for the row; the untouched payload is still in `details`.
MAX_RESULT_CHARS = 2000


def truncate_result(text: str, limit: int = MAX_RESULT_CHARS) -> str:
    """Shorten tool output, saying so rather than trailing off silently."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return f"{text[:limit]}\n... [{dropped} more characters]"


@dataclass(frozen=True)
class ExecutionEvent:
    step: int
    scope: str
    category: ExecutionCategory
    title: str
    details: str
    internal: bool = False
    # Set on tool rows. The scorecard asks that every tool call show its
    # arguments *and* its result, not just its name, so all three travel
    # together as fields rather than buried in the `details` JSON.
    tool_name: str | None = None
    tool_args: str | None = None
    tool_result: str | None = None
    intent: str | None = None
    implication: str | None = None
    severity: Severity | None = None
    error: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str
    reasoning: str | None = None
    reasoning_label: str | None = None
    execution_trace: list[str] = field(default_factory=list)
    execution_events: list[ExecutionEvent] = field(default_factory=list)
    # Kept on the message, not just on the in-flight response, so comparing two
    # reasoning efforts survives the rerun that ends the turn.
    usage: dict[str, int] = field(default_factory=dict)
    latency_s: float | None = None

    def to_agent_message(self) -> dict[str, str]:
        return dict(role=self.role, content=self.content)


@dataclass
class AgentResponse:
    reasoning: str | None = None
    execution_trace: list[str] = field(default_factory=list)
    execution_events: list[ExecutionEvent] = field(default_factory=list)
    # Set when the graph pauses on `interrupt_on`; each entry describes a tool
    # call awaiting a human decision. Stays empty until interrupts are enabled.
    pending_approval: list[Any] = field(default_factory=list)
    # Token counts and wall-clock, accumulated across every leg of the turn.
    usage: dict[str, int] = field(default_factory=dict)
    latency_s: float | None = None
    # What the human decided at each approval gate. Approve, edit and reject
    # have to leave visibly different records, which is what S7 checks.
    approval_log: list[str] = field(default_factory=list)

    def add_reasoning(self, reasoning: str) -> None:
        if reasoning and reasoning != self.reasoning:
            self.reasoning = f"{self.reasoning or ''}{reasoning}"

    def add_usage(self, usage: dict[str, int]) -> None:
        """Sum token counts across the turn's model calls."""
        for key, value in usage.items():
            if isinstance(value, int):
                self.usage[key] = self.usage.get(key, 0) + value

    def add_latency(self, seconds: float) -> None:
        self.latency_s = (self.latency_s or 0.0) + seconds

    def add_execution_event(self, event: ExecutionEvent) -> ExecutionEvent | None:
        """Record a step, dropping consecutive duplicates.

        Returns the stored event, or None if it was dropped as a duplicate.
        """
        previous = self.execution_events[-1] if self.execution_events else None
        if (
            previous
            and previous.scope == event.scope
            and previous.category == event.category
            and previous.title == event.title
        ):
            return None

        # Renumber on the way in. The upstream counter also counts events this
        # filter drops, which would leave gaps and make the live trace and the
        # dashboard show different numbers for the same step.
        stored = replace(event, step=len(self.execution_events))
        self.execution_events.append(stored)
        line = f"[{stored.scope}] {stored.title}"
        if not self.execution_trace or self.execution_trace[-1] != line:
            self.execution_trace.append(line)
        return stored


def to_agent_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [message.to_agent_message() for message in messages]


def stream_response_to_text(response: str | list[Any]) -> str:
    if isinstance(response, str):
        return response
    return "".join(str(item) for item in response)
