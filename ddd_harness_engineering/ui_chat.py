"""The chat pane: history, the live turn, and the approval gate.

The one thing worth reading carefully here is `AssistantTurnRenderer`. The answer
streams into the side chat panel while the execution trace paints into the
Activity workspace, and a Streamlit container belongs to wherever it was created
-- so the renderer cannot make its own trace slot. The workspace creates and
hands it one.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
import json
from typing import Any

import streamlit as st
from langgraph.types import Command

from ddd_harness_engineering import ui_styling, ui_trace
from ddd_harness_engineering.agent import approve, edit, reject, stream_agent_response
from ddd_harness_engineering.chat import (
    AgentResponse,
    ChatMessage,
    ExecutionEvent,
    stream_response_to_text,
)


@dataclass
class AssistantTurnRenderer:
    agent: Any
    # A new user turn, or a `resume_input(...)` continuing a paused graph.
    agent_input: dict[str, Any] | Command
    thread_id: str
    # Created by the caller in the harness pane. Passed in rather than made
    # here, because a container renders where it was born.
    trace_slot: Any
    show_internal: bool = False
    agent_response: AgentResponse = field(default_factory=AgentResponse)
    reasoning_label: str = field(default_factory=ui_styling.get_generation_status)
    answer_started: bool = False
    reasoning_started: bool = False
    reasoning_status: Any = field(init=False)
    reasoning_content: Any = field(init=False)

    def __post_init__(self) -> None:
        self.reasoning_status = st.status(
            self.reasoning_label,
            expanded=False,
            type="compact",
        )
        self.reasoning_content = self.reasoning_status.empty()

    def stream(self) -> Iterator[str]:
        chunks = stream_agent_response(
            self.agent,
            self.agent_input,
            self.agent_response,
            self.thread_id,
            on_reasoning=self.show_reasoning,
            on_event=self.show_event,
        )
        for chunk in chunks:
            self.start_answer()
            yield chunk
        self.complete_reasoning()

    def show_event(self, event: ExecutionEvent) -> None:
        del event  # the whole trace is repainted from the accumulated list
        ui_trace.render_live(
            self.trace_slot,
            self.agent_response.execution_events,
            show_internal=self.show_internal,
        )

    def show_reasoning(self, reasoning: str) -> None:
        self.reasoning_started = True
        self.reasoning_status.update(expanded=not self.answer_started)
        self.reasoning_content.markdown(self.agent_response.reasoning or reasoning)

    def start_answer(self) -> None:
        if self.answer_started:
            return

        self.answer_started = True
        if self.reasoning_started:
            self.reasoning_status.update(state="complete", expanded=False)
        else:
            self.reasoning_status.empty()

    def complete_reasoning(self) -> None:
        if self.reasoning_started and not self.answer_started:
            self.reasoning_status.update(state="complete", expanded=False)

    def to_message(self, streamed_response: str | list[Any]) -> ChatMessage:
        return ChatMessage(
            role="assistant",
            content=stream_response_to_text(streamed_response),
            reasoning=self.agent_response.reasoning,
            reasoning_label=self.reasoning_label,
            execution_trace=list(self.agent_response.execution_trace),
            execution_events=list(self.agent_response.execution_events),
            usage=dict(self.agent_response.usage),
            latency_s=self.agent_response.latency_s,
        )


@dataclass
class PausedTurn:
    """A turn stopped mid-flight while the agent waits on a human decision.

    Held in session state across the rerun that renders the approval dialog.
    `answer` and `response` accumulate, because one turn can pause repeatedly.
    """

    answer: str
    response: AgentResponse
    reasoning_label: str
    actions: list[dict[str, Any]]


def render_messages(messages: list[ChatMessage]) -> None:
    for message in messages:
        render_message(message)


def render_message(message: ChatMessage) -> None:
    with st.chat_message(message.role):
        if message.reasoning:
            status = st.status(
                message.reasoning_label or "Reasoning",
                expanded=False,
                state="complete",
                type="compact",
            )
            status.markdown(message.reasoning)
        st.write(message.content)


def render_follow_up_questions(
    messages: list[ChatMessage],
    questions: list[str],
    on_select: Any,
) -> None:
    if not questions:
        return

    widget_key = f"follow_up_{len(messages)}"
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.pills(
            "Continue the conversation",
            questions,
            key=widget_key,
            label_visibility="collapsed",
            on_change=on_select,
            args=(widget_key,),
        )


def append_user_message(messages: list[ChatMessage], prompt: str) -> None:
    messages.append(ChatMessage(role="user", content=prompt))
    with st.chat_message("user"):
        st.write(prompt)


@st.dialog("Approve tool call", width="large")
def approval_dialog(paused: PausedTurn) -> None:
    """Collect one decision per pending tool call, then resume the graph.

    This is the same gate Claude Code shows before it edits a file — from the
    inside. Three answers are possible, and the middle one is the interesting
    one: you can correct the arguments instead of accepting or refusing.
    """
    # MODULE S3 STARTER PLACEHOLDER:
    # Keep this dialog entry point explicit in starter branches. Participants
    # complete decision capture and resume wiring here.
    st.markdown("The agent is waiting for your decision.")
    st.caption(
        "Review why it wants each action and what could change. Nothing below "
        "has run yet."
    )

    decisions: list[dict[str, Any]] = []
    outcomes: list[str] = []
    decision_events: list[ExecutionEvent] = []
    for index, action in enumerate(paused.actions):
        allowed = [
            decision
            for decision in action["allowed_decisions"]
            if decision in {"approve", "edit", "reject"}
        ] or ["approve", "edit", "reject"]
        with st.container(border=True):
            heading, risk = st.columns([4, 1], vertical_alignment="center")
            heading.markdown(f"#### {action['title']}")
            heading.caption(f"Tool: `{action['name']}`")
            risk.markdown(f"**{str(action['severity']).upper()}**")
            risk.caption("impact")

            st.markdown("**Intent — why the agent wants this**")
            st.write(action["intent"])
            st.markdown("**Impact — what allowing it can change**")
            st.write(action["implication"])

            with st.expander("Review exact arguments", expanded=False):
                st.code(json.dumps(action["args"], indent=2), language="json")

            choice = st.radio(
                "Your decision",
                allowed,
                key=f"decision_{index}",
                horizontal=True,
                format_func=_decision_label,
            )

            if choice == "edit":
                edited = st.text_area(
                    "Arguments to run instead",
                    value=json.dumps(action["args"], indent=2),
                    key=f"edit_args_{index}",
                    height=160,
                )
                try:
                    edited_args = json.loads(edited)
                except json.JSONDecodeError as error:
                    st.error(f"Arguments must be valid JSON: {error}")
                    return
                if not isinstance(edited_args, dict):
                    st.error("Arguments must be a JSON object with named fields.")
                    return
                decisions.append(edit(action["name"], edited_args))
                outcome = f"edited and allowed `{action['name']}`"
                outcomes.append(outcome)
                decision_events.append(
                    _approval_event(action, "edit", outcome, edited_args)
                )
            elif choice == "reject":
                note = st.text_input(
                    "Reason for denying (the agent can adapt to this)",
                    key=f"reject_note_{index}",
                    placeholder="Wrong folder — write into workspace/ instead.",
                )
                decisions.append(reject(note or None))
                outcome = f"denied `{action['name']}`" + (f": {note}" if note else "")
                outcomes.append(outcome)
                decision_events.append(_approval_event(action, "reject", outcome))
            else:
                decisions.append(approve())
                outcome = f"allowed `{action['name']}` once"
                outcomes.append(outcome)
                decision_events.append(_approval_event(action, "approve", outcome))

    if st.button(
        "Continue with these decisions", type="primary", use_container_width=True
    ):
        st.session_state.resume_decisions = decisions
        # Kept so the panel can show that approve, edit and reject each left a
        # different record — which is precisely what S7's check asks for.
        paused.response.approval_log.extend(outcomes)
        for event in decision_events:
            paused.response.add_execution_event(event)
        st.rerun()


def _decision_label(decision: str) -> str:
    return {
        "approve": "Allow once",
        "edit": "Edit and allow",
        "reject": "Deny",
        "respond": "Answer instead",
    }.get(decision, decision.replace("_", " ").title())


def _approval_event(
    action: dict[str, Any],
    decision: str,
    outcome: str,
    effective_args: dict[str, Any] | None = None,
) -> ExecutionEvent:
    titles = {
        "approve": "Allowed by user",
        "edit": "Edited and allowed by user",
        "reject": "Denied by user",
    }
    details = {
        "decision": decision,
        "tool": action["name"],
        "original_args": action["args"],
        "effective_args": effective_args
        if effective_args is not None
        else action["args"],
        "outcome": outcome,
    }
    result = (
        "The tool was not run. The agent received the user's denial."
        if decision == "reject"
        else "The graph resumed with the user's permission."
    )
    return ExecutionEvent(
        step=0,
        scope="main",
        category="approval",
        title=f"{titles[decision]}: {action['name']}",
        details=json.dumps(details, indent=2),
        tool_name=str(action["name"]),
        tool_args=json.dumps(details["effective_args"], indent=2),
        tool_result=result,
        intent=str(action["intent"]),
        implication=str(action["implication"]),
        severity=action["severity"],
    )
