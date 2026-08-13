"""The harness panel: what is wired, and what is in it.

One section per station. Each says whether that component is configured, what it
actually contains -- the prompt text, the skill's rules, the tool's docstring,
the MCP tool lists -- and whether this session has produced the evidence its
acceptance check asks for.

Two things it deliberately does that a trace cannot:

- **It shows absence.** Three of the eight acceptance checks are negative
  assertions: `web_search` is absent from the main agent, the MCP list is
  strictly shorter than the server's, a path is refused. An append-only event
  log has nothing to show for any of them.
- **It shows the unwired.** Run this from `solutions/s3` and stations S4 to S8
  read "not configured yet", which turns the panel into the assignment tracker.
"""

from html import escape

import streamlit as st

from ddd_harness_engineering.chat import ChatMessage, ExecutionEvent
from ddd_harness_engineering.introspection import (
    StationStatus,
    describe_harness,
)
from ddd_harness_engineering.ui_templates import render_template


def render_harness_panel(messages: list[ChatMessage]) -> None:
    stations = describe_harness()
    evidence = _collect_evidence(messages)

    wired = sum(1 for station in stations if station.wired)
    st.caption(f"{wired} of {len(stations)} stations wired in this harness.")

    for station in stations:
        with st.expander(
            f"{'✅' if station.wired else '⬜'} {station.station} · {station.title}",
            expanded=False,
        ):
            _render_station(station, evidence.get(station.station))


def _render_station(station: StationStatus, evidence: str | None) -> None:
    st.markdown(f"**{station.summary}**")
    st.caption(station.component)

    if not station.wired:
        st.info(
            "Not configured yet — this is the station's exercise.",
            icon=":material/build:",
        )

    if station.check:
        st.html(
            render_template(
                "components/station_check.html",
                check=escape(station.check),
            )
        )

    # Evidence from this session, which is the half the configuration cannot
    # prove: a hop actually happened, a command was actually refused.
    if evidence:
        st.success(evidence, icon=":material/check_circle:")

    for detail in station.details:
        st.markdown(f"- **{detail.label}** — {detail.value}")

    _render_detail_picker(station)


def _render_detail_picker(station: StationStatus) -> None:
    """Show one detail's contents at a time.

    A selectbox rather than an expander per detail, because Streamlit forbids
    nesting expanders and every station is already inside one. It also keeps the
    prompt and the skill bodies -- which are long -- from burying the summary.
    """
    inspectable = {detail.label: detail for detail in station.details if detail.body}
    if not inspectable:
        return

    chosen = st.selectbox(
        "Inspect",
        list(inspectable),
        key=f"harness_{station.station}_detail",
    )
    detail = inspectable[chosen]
    if detail.language == "markdown":
        st.markdown(detail.body or "")
    elif detail.language:
        st.code(detail.body or "", language=detail.language)
    else:
        st.markdown(detail.body or "")


def _collect_evidence(messages: list[ChatMessage]) -> dict[str, str]:
    """What this conversation has actually demonstrated, per station.

    Read from the trace rather than from the config, because "it is configured"
    and "it happened" are different claims and the scorecard only accepts the
    second one: a box is honest only if you can show it.
    """
    events = [event for message in messages for event in message.execution_events]
    if not events:
        return {}

    evidence: dict[str, str] = {}

    if any(">" in event.scope for event in events):
        evidence["S3"] = "A `main > subagent` hop happened this session."

    refusals = [event for event in events if event.category == "guardrail"]
    if refusals:
        note = f"{len(refusals)} guardrail refusal(s) recorded this session."
        evidence["S2"] = note
        evidence["S4"] = note

    if any(event.category == "approval" for event in events):
        evidence["S7"] = "The graph paused for approval this session."

    mcp_tools = {"file_stats", "file_checksum", "oldest_files"}
    if any(event.tool_name in mcp_tools for event in events):
        evidence["S6"] = "An MCP tool was called this session."

    if _skill_was_read(events):
        evidence["S5"] = "A SKILL.md was read this session."

    return evidence


def _skill_was_read(events: list[ExecutionEvent]) -> bool:
    """Whether a skill was pulled in beyond its frontmatter.

    Skills are progressively disclosed: only the description is loaded until the
    model decides to read the body, so a `read_file` on a SKILL.md is the moment
    the skill actually fired.
    """
    return any(event.tool_args and "SKILL.md" in event.tool_args for event in events)
