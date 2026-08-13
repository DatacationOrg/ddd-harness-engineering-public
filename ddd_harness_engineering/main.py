"""The app: workspace-first content with a screen-edge chat panel.

Activity, Harness, and Files share one main content panel. Chat lives in a
collapsible side panel anchored to the right edge of the screen, independent of
the workspace layout. Activity is the trace's only home.

Rendering order in ``main`` is load-bearing. The chat input is read inside the
side panel, the Activity panel creates its live slot, and only then may the
response stream into chat while events repaint that slot.
"""

from typing import Any, cast
from uuid import uuid4

import streamlit as st
from langgraph.types import Command

from ddd_harness_engineering import ui_styling, ui_trace
from ddd_harness_engineering.agent import (
    approval_resume,
    create_agent,
    generate_follow_up_questions,
    module_fingerprint,
    new_turn_input,
    pending_actions,
)
from ddd_harness_engineering.chat import (
    AgentResponse,
    ChatMessage,
    stream_response_to_text,
)
from ddd_harness_engineering.ui_chat import (
    AssistantTurnRenderer,
    PausedTurn,
    append_user_message,
    approval_dialog,
    render_follow_up_questions,
    render_messages,
)
from ddd_harness_engineering.ui_harness import render_harness_panel
from ddd_harness_engineering.ui_sandbox import render_sandbox_panel

_TITLE = "Datacation Deep Dive"
_WORKSPACE_SECTIONS = ("Activity", "Harness", "Files")


def _workspace_label(section: str) -> str:
    return {
        "Activity": "Activity feed",
        "Harness": "Harness map",
        "Files": "File explorer",
    }.get(section, section)


st.set_page_config(
    page_title=_TITLE,
    page_icon="https://www.datacation.nl/favicon.ico",
    layout="wide",
)

ui_styling.add_user_chat_alignment()
ui_styling.add_reasoning_styling()
ui_styling.add_follow_up_styling()
ui_styling.add_trace_styling()
# Compatibility for a Streamlit process that imported the brief intermediate
# version where workspace CSS had its own hook. A fresh process applies it from
# `add_trace_styling`; an older cached module simply has no extra hook to call.
_legacy_workspace_styling = getattr(ui_styling, "add_workspace_styling", None)
if callable(_legacy_workspace_styling):
    _legacy_workspace_styling()


@st.cache_resource(show_spinner="Building the agent...")
def _build_agent(fingerprint: str) -> Any:
    """Build the agent once per process, not once per turn.

    `fingerprint` is not used by the body — it is the cache key. Passing the
    current revision of agent.py means saving that file rebuilds the agent on
    the next rerun, so edits are visible immediately.
    """
    del fingerprint
    return create_agent()


def _get_agent() -> Any:
    return _build_agent(module_fingerprint())


def _get_thread_id() -> str:
    """Identify this conversation to the checkpointer."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid4())
    return cast("str", st.session_state.thread_id)


def _reset_conversation() -> None:
    """Drop the rendered history and start a fresh checkpointer thread."""
    st.session_state.messages = []
    st.session_state.follow_up_questions = []
    st.session_state.thread_id = str(uuid4())
    st.session_state.paused_turn = None
    st.session_state.resume_decisions = None
    # The trace viewer's selections are keyed by turn, so they outlive the
    # conversation they describe unless they go too.
    for key in [key for key in st.session_state if str(key).startswith("trace_turn")]:
        del st.session_state[key]


def _get_messages() -> list[ChatMessage]:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    return cast("list[ChatMessage]", st.session_state.messages)


def _get_follow_up_questions() -> list[str]:
    if "follow_up_questions" not in st.session_state:
        st.session_state.follow_up_questions = []
    return cast("list[str]", st.session_state.follow_up_questions)


def _clear_follow_up_questions() -> None:
    st.session_state.follow_up_questions = []


def _select_follow_up(widget_key: str) -> None:
    st.session_state.pending_prompt = st.session_state[widget_key]
    st.session_state.workspace_view = "Activity"
    st.session_state.chat_open = True
    _clear_follow_up_questions()


def _begin_prompt() -> None:
    _clear_follow_up_questions()
    st.session_state.workspace_view = "Activity"
    st.session_state.chat_open = True


def _show_internal() -> bool:
    return bool(st.session_state.get("show_internal", False))


def _render_header() -> None:
    st.markdown(
        """
        <a href="https://www.datacation.nl/" target="_blank" rel="noopener noreferrer">
            <img src="https://www.datacation.nl/assets/datacation-logo-dark.svg"
                 alt="Datacation"
                 style="height:34px; width:auto; margin-bottom:0.45rem;" />
        </a>
        """,
        unsafe_allow_html=True,
    )
    st.title(_TITLE)
    st.caption(
        "A professional demo surface for observing agent decisions, tools, and file activity in real time."
    )
    markers = st.columns(3)
    markers[0].caption("Workspace-first layout")
    markers[1].caption("Live execution telemetry")
    markers[2].caption("Human approval controls")
    ui_styling.add_footer()


def _render_activity_controls(*, disabled: bool) -> None:
    """Keep session controls beside the activity they affect."""
    detail_control, reset_control = st.columns([3, 2], vertical_alignment="center")
    detail_control.toggle(
        "Technical details",
        value=False,
        key="show_internal",
        help="Show model, state, task, and middleware events in addition to "
        "user-relevant actions.",
    )
    if reset_control.button(
        "New conversation",
        use_container_width=True,
        disabled=disabled,
        help="Clear this chat and start a new checkpoint thread.",
    ):
        _reset_conversation()
        st.rerun()
    st.caption(f"Session `{_get_thread_id()[:8]}`")


def _render_trace_tab(messages: list[ChatMessage]) -> None:
    turns = [
        (index, message)
        for index, message in enumerate(messages)
        if message.role == "assistant" and message.execution_events
    ]
    if not turns:
        st.caption("No execution traces yet. Ask a question first.")
        return

    # Numbered by assistant turn, not by position in `messages` — otherwise the
    # first answer is labelled "Turn 2" because a user message precedes it. The
    # widget keys use the same ordinal, so the label and the state agree.
    labels = [
        f"Turn {ordinal} — {len(message.execution_events)} steps"
        for ordinal, (_, message) in enumerate(turns, start=1)
    ]
    chosen = st.selectbox(
        "Conversation turn",
        labels,
        index=len(labels) - 1,
        key="trace_turn",
    )
    ordinal = labels.index(chosen)
    _, message = turns[ordinal]

    if _show_internal():
        ui_trace.render_metrics(
            steps=len(message.execution_events),
            usage=message.usage,
            latency_s=message.latency_s,
        )
    ui_trace.render_turn(
        message.execution_events,
        show_internal=_show_internal(),
        key_prefix=f"trace_turn_{ordinal}",
    )


def _read_prompt() -> str | None:
    chat_prompt = st.chat_input(
        "Ask the agent anything",
        submit_mode="disable",
        on_submit=_begin_prompt,
    )
    pending_prompt = st.session_state.pop("pending_prompt", None)
    return cast("str | None", pending_prompt or chat_prompt)


def _chat_is_open() -> bool:
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False
    return bool(st.session_state.chat_open)


def _set_chat_open(opened: bool) -> None:
    st.session_state.chat_open = opened


def _render_chat_panel(
    messages: list[ChatMessage], paused: PausedTurn | None
) -> tuple[Any, str | None]:
    """Render the screen-edge chat panel and return its live-turn slot and prompt."""
    if not _chat_is_open():
        with st.container(key="chat_peek"):
            st.button(
                "Open Chat",
                key="open_chat",
                help="Open chat from the right edge",
                on_click=_set_chat_open,
                args=(True,),
                use_container_width=True,
            )
        return None, None

    with st.container(border=True, key="chat_overlay"):
        title, close = st.columns([4, 1], vertical_alignment="center")
        title.markdown("### Chat")
        close.button(
            "Close",
            key="close_chat",
            help="Collapse chat to the side",
            disabled=paused is not None,
            on_click=_set_chat_open,
            args=(False,),
            use_container_width=True,
        )
        st.caption("Ask, review permissions, and continue the conversation.")

        with st.container(key="chat_history"):
            render_messages(messages)
            turn_slot = st.empty()
            if paused is None:
                render_follow_up_questions(
                    messages, _get_follow_up_questions(), _select_follow_up
                )

        prompt = None if paused else _read_prompt()
        return turn_slot, prompt


def _render_workspace(messages: list[ChatMessage], *, streaming: bool) -> Any:
    """Render vertical navigation and the selected content panel."""
    with st.container(key="workspace_shell"):
        navigation, panel = st.columns([1, 5], gap="medium")

        with navigation:
            st.caption("WORKSPACE")
            selected = st.radio(
                "Workspace section",
                list(_WORKSPACE_SECTIONS),
                format_func=_workspace_label,
                key="workspace_view",
                label_visibility="collapsed",
            )

        with panel:
            with st.container(border=True, key="workspace_panel"):
                if selected == "Activity":
                    st.subheader("Activity")
                    st.caption("What the agent did and what needs your attention.")
                    _render_activity_controls(disabled=streaming)
                    live_slot = st.empty()
                    if not streaming:
                        _render_trace_tab(messages)
                    return live_slot

                if selected == "Harness":
                    st.subheader("Harness")
                    st.caption("What is wired into the agent, station by station.")
                    render_harness_panel(messages)
                else:
                    st.subheader("Files")
                    st.caption("The sandbox the agent can inspect and change.")
                    render_sandbox_panel()

                return st.empty()


def _get_paused_turn() -> PausedTurn | None:
    return cast("PausedTurn | None", st.session_state.get("paused_turn"))


def _continue_turn(
    messages: list[ChatMessage],
    agent_input: dict[str, Any] | Command,
    trace_slot: Any,
    paused: PausedTurn | None = None,
) -> None:
    """Stream one leg of a turn. It ends in an answer, or in another pause."""
    with st.chat_message("assistant"):
        if paused and paused.answer:
            # Replay what was already said, since the rerun cleared the page.
            st.markdown(paused.answer)
        renderer = AssistantTurnRenderer(
            agent=_get_agent(),
            agent_input=agent_input,
            thread_id=_get_thread_id(),
            trace_slot=trace_slot,
            show_internal=_show_internal(),
            agent_response=paused.response if paused else AgentResponse(),
            reasoning_label=(
                paused.reasoning_label if paused else ui_styling.get_generation_status()
            ),
        )
        streamed_response = st.write_stream(renderer.stream())

    answer = (paused.answer if paused else "") + stream_response_to_text(
        streamed_response
    )

    actions = pending_actions(renderer.agent_response.pending_approval)
    # MODULE S3 STARTER PLACEHOLDER:
    # Starter branches keep this pause/resume insertion point visible while
    # approval orchestration is intentionally incomplete.
    if actions:
        st.session_state.paused_turn = PausedTurn(
            answer=answer,
            response=renderer.agent_response,
            reasoning_label=renderer.reasoning_label,
            actions=actions,
        )
        st.rerun()

    st.session_state.paused_turn = None
    messages.append(renderer.to_message(answer))
    st.session_state.follow_up_questions = generate_follow_up_questions(messages)
    st.rerun()


def _handle_prompt(messages: list[ChatMessage], prompt: str, trace_slot: Any) -> None:
    append_user_message(messages, prompt)
    _continue_turn(messages, new_turn_input(prompt), trace_slot)


def main() -> None:
    _render_header()
    # S6 status is populated when MCP tools are loaded during agent build.
    # Build once on app load so the harness panel reports wiring immediately.
    _get_agent()

    messages = _get_messages()
    paused = _get_paused_turn()
    decisions = cast(
        "list[dict[str, Any]] | None", st.session_state.pop("resume_decisions", None)
    )
    resuming = decisions is not None and paused is not None
    if paused is not None or resuming:
        st.session_state.chat_open = True
        st.session_state.workspace_view = "Activity"

    ui_styling.set_workspace_layout(chat_open=_chat_is_open())
    turn_slot, prompt = _render_chat_panel(messages, paused)

    streaming = resuming or bool(prompt)
    live_slot = _render_workspace(messages, streaming=streaming)

    if turn_slot is None:
        return

    # A turn has three ways in: a new prompt, a decision that resumes a paused
    # graph, or a pause waiting for that decision. The placeholder keeps every
    # one in the scrollable drawer above its input.
    with turn_slot.container():
        if resuming:
            _continue_turn(
                messages,
                approval_resume(cast("list[dict[str, Any]]", decisions)),
                live_slot,
                paused,
            )
            return

        if paused is not None:
            if paused.answer:
                # Keep what the agent already said on screen behind the dialog.
                with st.chat_message("assistant"):
                    st.markdown(paused.answer)
            approval_dialog(paused)
            return

        if prompt:
            _handle_prompt(messages, prompt, live_slot)


main()
