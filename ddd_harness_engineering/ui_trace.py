"""Rendering the execution trace.

One renderer serves the live turn and past turns in the Activity workspace. The chat
does not repeat the trace. Sharing the row renderer keeps step numbering, tool
results and styling consistent between live and historical activity.

The row shape is the point. The scorecard asks that "every tool call in the
trace shows its arguments *and* its result, not just its name", and that a
subagent hop be something you can point at. So a row carries its category as a
colour, its tool name inline, and its depth as an indent -- `main > subagent`
reads as a step to the right.
"""

from dataclasses import replace
from html import escape
from typing import Any

import streamlit as st

from ddd_harness_engineering.chat import ExecutionEvent
from ddd_harness_engineering.tool_context import describe_tool_call
from ddd_harness_engineering.ui_templates import render_template

_CATEGORY_LABELS: dict[str, str] = {
    "model": "model",
    "tool": "tool",
    "subagent": "subagent",
    "state": "state",
    "task": "task",
    "approval": "approval",
    "guardrail": "refused",
    "error": "error",
    "internal": "internal",
}

# Categories that stay visible whatever the filter says. A refusal is the
# evidence S2 and S4 ask participants to point at; it is never noise.
_ALWAYS_VISIBLE = frozenset({"guardrail", "error", "approval"})
_ACTIVITY_CATEGORIES = frozenset({"tool", "subagent", *_ALWAYS_VISIBLE})


def visible_events(
    events: list[ExecutionEvent], *, show_internal: bool
) -> list[ExecutionEvent]:
    """Return either the complete engineering trace or concise user activity."""
    if show_internal:
        return list(events)
    meaningful = [
        event
        for event in events
        if event.category in _ACTIVITY_CATEGORIES
        and (not event.internal or event.category in _ALWAYS_VISIBLE)
    ]
    return [
        replace(event, step=index)
        for index, event in enumerate(_collapse_tool_lifecycle(meaningful))
    ]


def _events_for_display(events: list[ExecutionEvent]) -> list[ExecutionEvent]:
    """Show most recent activity first so current tool work stays in view."""
    return list(reversed(events))


def _collapse_tool_lifecycle(events: list[ExecutionEvent]) -> list[ExecutionEvent]:
    """Combine a tool's noisy started/finished pair into one useful activity."""
    collapsed: list[ExecutionEvent] = []
    pending: dict[tuple[str, str, str], int] = {}

    for event in events:
        phase = _lifecycle_phase(event)
        key = (event.scope, event.category, event.tool_name or "")
        if phase == "started" and event.tool_name:
            pending[key] = len(collapsed)
            collapsed.append(replace(event, title=f"Preparing: {_tool_title(event)}"))
            continue

        if phase == "finished" and event.tool_name and key in pending:
            index = pending.pop(key)
            started = collapsed[index]
            collapsed[index] = replace(
                started,
                title=_tool_title(started),
                details=event.details,
                tool_result=event.tool_result,
                error=event.error,
            )
            continue

        collapsed.append(event)

    return collapsed


def _lifecycle_phase(event: ExecutionEvent) -> str | None:
    for phase in ("started", "finished"):
        if f"({phase})" in event.title:
            return phase
    return None


def _tool_title(event: ExecutionEvent) -> str:
    if not event.tool_name:
        return _row_title(event)
    return describe_tool_call(event.tool_name.split(",", 1)[0]).title


def render_rows(events: list[ExecutionEvent]) -> None:
    """Draw the trace as indented, colour-coded rows."""
    st.html("\n".join(_row_html(event) for event in events))


def _row_html(event: ExecutionEvent) -> str:
    depth = min(event.scope.count(">"), 3)
    category = event.category if event.category in _CATEGORY_LABELS else "task"
    tool = (
        render_template(
            "components/trace_tool.html",
            tool_name=escape(event.tool_name),
        )
        if event.tool_name
        else ""
    )
    severity = (
        render_template(
            "components/trace_severity.html",
            severity=escape(event.severity),
        )
        if event.severity
        else ""
    )
    intent = (
        render_template(
            "components/trace_intent.html",
            intent=escape(event.intent),
        )
        if event.intent and event.category in _ACTIVITY_CATEGORIES
        else ""
    )
    return render_template(
        "components/trace_row.html",
        depth=depth,
        step=f"{event.step + 1:02d}",
        category=category,
        category_label=escape(_CATEGORY_LABELS[category]),
        title=escape(_row_title(event)),
        tool=tool,
        severity=severity,
        intent=intent,
    )


def _row_title(event: ExecutionEvent) -> str:
    """The title with the tool name stripped, since the row shows it separately."""
    if event.tool_name and event.title.endswith(f": {event.tool_name}"):
        return event.title.removesuffix(f": {event.tool_name}")
    return event.title


def render_live(
    container: Any, events: list[ExecutionEvent], *, show_internal: bool = False
) -> None:
    """Repaint the whole trace into a container owned by another column.

    The container is created by the caller, in the pane it belongs to, and
    passed in -- a Streamlit container belongs to wherever it was created, so
    the answer can stream on the left while this paints on the right.
    """
    with container.container():
        shown = visible_events(events, show_internal=show_internal)
        if not shown:
            st.caption("Working… meaningful actions will appear here.")
            return
        render_rows(_events_for_display(shown))


def render_turn(
    events: list[ExecutionEvent],
    *,
    show_internal: bool,
    key_prefix: str,
) -> None:
    """Draw one turn's trace plus a detail pane for the selected step."""
    shown = _events_for_display(visible_events(events, show_internal=show_internal))
    if not shown:
        st.caption("No tools or approvals were needed for this turn.")
        return

    render_rows(shown)
    st.divider()

    chosen_index = st.selectbox(
        "Inspect a step",
        range(len(shown)),
        format_func=lambda index: (
            f"{shown[index].step + 1:02d}. {_row_title(shown[index])}"
            + (f" ({shown[index].tool_name})" if shown[index].tool_name else "")
        ),
        key=f"{key_prefix}_step",
    )
    _render_step_detail(shown[chosen_index])


def _render_step_detail(event: ExecutionEvent) -> None:
    if event.intent:
        st.markdown("**Intent — why the agent wants this**")
        st.write(event.intent)

    if event.implication:
        st.markdown("**Impact — what allowing it can change**")
        st.write(event.implication)

    severity = f" · {event.severity} impact" if event.severity else ""
    st.caption(f"{event.category}{severity} · scope `{event.scope}`")

    # Arguments and result first, raw payload last: the first two are what the
    # step actually did, the third is where you go when you doubt the first two.
    if event.tool_args:
        st.markdown("**Arguments**")
        st.code(event.tool_args, language="json")

    if event.tool_result:
        st.markdown("**Result** — what the model saw")
        st.code(event.tool_result, language="text")

    if event.error:
        st.markdown("**Error**")
        st.code(event.error, language="text")

    with st.expander("Raw langgraph payload", expanded=False):
        st.code(event.details, language="json")


def render_metrics(
    *,
    steps: int,
    usage: dict[str, int],
    latency_s: float | None,
) -> None:
    """Step count, tokens and latency — the three numbers S1 compares.

    Turning reasoning effort up and down is the exercise; without these it is a
    change you can only feel, not measure.
    """
    columns = st.columns(3)
    columns[0].metric("Steps", steps)
    total_tokens = usage.get("total_tokens") or usage.get(
        "input_tokens", 0
    ) + usage.get("output_tokens", 0)
    columns[1].metric("Tokens", f"{total_tokens:,}" if total_tokens else "—")
    columns[2].metric("Latency", f"{latency_s:.1f}s" if latency_s else "—")

    breakdown = ", ".join(
        f"{key.replace('_tokens', '')} {value:,}"
        for key, value in sorted(usage.items())
        if key != "total_tokens" and value
    )
    if breakdown:
        st.caption(breakdown)
