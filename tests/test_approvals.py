"""Tests for the human-in-the-loop approval path (station S7).

The decision builders are checked against `HumanInTheLoopMiddleware`'s own
`_process_decision`, so a change to langchain's approval contract fails here
rather than silently at the workshop.
"""

import json

from typing import Any, cast

from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig
from langchain_core.messages import AIMessage, ToolCall

from ddd_harness_engineering import agent
from ddd_harness_engineering.ui_chat import _approval_event

_ALL_DECISIONS = cast(
    "InterruptOnConfig",
    {"allowed_decisions": ["approve", "edit", "reject", "respond"]},
)


def _tool_call() -> ToolCall:
    return ToolCall(
        type="tool_call",
        name="write_file",
        args={"file_path": "notes.md", "content": "hello"},
        id="call-1",
    )


def _process(decision: dict[str, Any]):
    """Run a decision through the middleware exactly as the graph would."""
    return HumanInTheLoopMiddleware._process_decision(  # pyright: ignore[reportPrivateUsage]
        cast("Any", decision), _tool_call(), _ALL_DECISIONS
    )


def test_approve_runs_the_call_unchanged() -> None:
    revised, message = _process(agent.approve())

    assert revised is not None
    assert revised["args"] == {"file_path": "notes.md", "content": "hello"}
    assert message is None


def test_edit_replaces_the_arguments() -> None:
    """The decision nobody expects: right idea, wrong path."""
    revised, message = _process(
        agent.edit(
            "write_file", {"file_path": "workspace/notes.md", "content": "hello"}
        )
    )

    assert revised is not None
    assert revised["args"]["file_path"] == "workspace/notes.md"
    assert revised["id"] == "call-1", "the original call id must be preserved"
    assert message is None


def test_reject_feeds_the_reason_back_to_the_model() -> None:
    _, message = _process(agent.reject("Write into workspace/ instead."))

    assert message is not None
    assert message.status == "error"
    assert "workspace/" in str(message.content)


def test_reject_without_a_reason_still_explains_itself() -> None:
    _, message = _process(agent.reject())

    assert message is not None
    assert "rejected" in str(message.content).lower()


def test_approval_resume_wraps_decisions_in_the_expected_envelope() -> None:
    command = agent.approval_resume([agent.approve(), agent.reject("no")])

    assert command.resume == {
        "decisions": [{"type": "approve"}, {"type": "reject", "message": "no"}]
    }


def test_pending_actions_flattens_a_real_interrupt_payload() -> None:
    """Mirrors the `HITLRequest` the middleware raises for two hanging calls."""
    payload = [
        {
            "action_requests": [
                {
                    "name": "write_file",
                    "args": {"file_path": "a.md"},
                    "description": "d1",
                },
                {
                    "name": "edit_file",
                    "args": {"file_path": "b.md"},
                    "description": "d2",
                },
            ],
            "review_configs": [
                {
                    "action_name": "write_file",
                    "allowed_decisions": ["approve", "reject"],
                },
                {
                    "action_name": "edit_file",
                    "allowed_decisions": ["approve", "edit", "reject"],
                },
            ],
        }
    ]

    actions = agent.pending_actions(payload)

    assert [a["name"] for a in actions] == ["write_file", "edit_file"]
    assert actions[0]["allowed_decisions"] == ["approve", "reject"]
    assert actions[1]["args"] == {"file_path": "b.md"}
    assert actions[0]["description"] == "d1"
    assert actions[0]["intent"] == "d1"
    assert actions[0]["implication"]
    assert actions[0]["severity"] == "medium"
    assert actions[0]["title"] == "Create or replace a file"


def test_pending_actions_is_empty_when_nothing_is_pending() -> None:
    assert agent.pending_actions([]) == []


def test_pending_actions_survives_a_missing_review_config() -> None:
    actions = agent.pending_actions(
        [{"action_requests": [{"name": "write_file", "args": {}}]}]
    )

    assert len(actions) == 1
    assert actions[0]["allowed_decisions"] == ["approve", "edit", "reject"]


def test_interrupt_on_defaults_cover_the_write_tools() -> None:
    """Reads stay instant; only tools that change something stop for review."""
    middleware = HumanInTheLoopMiddleware(agent._INTERRUPT_ON)  # pyright: ignore[reportPrivateUsage]

    assert set(middleware.interrupt_on) == {
        "write_file",
        "edit_file",
        "execute",
        "move_file",
        "copy_file",
        "delete_file",
    }
    assert "read_file" not in middleware.interrupt_on
    assert "ls" not in middleware.interrupt_on
    assert "find_duplicate_files" not in middleware.interrupt_on
    assert all(
        config["allowed_decisions"] == ["approve", "edit", "reject"]
        for config in middleware.interrupt_on.values()
    )


def test_approval_description_uses_the_models_own_intent() -> None:
    tool_call = ToolCall(
        type="tool_call",
        name="write_file",
        args={"file_path": "workspace/a.md", "content": "hello"},
        id="call-intent",
    )
    state = {
        "messages": [
            AIMessage(
                content="Save the summary where the user requested it.",
                tool_calls=[tool_call],
            )
        ]
    }

    assert (
        agent._approval_intent(tool_call, state, None)
        == "Save the summary where the user requested it."
    )


def test_a_read_only_turn_is_not_interrupted() -> None:
    """No pending write means no pause, so browsing never blocks on a human."""
    middleware = HumanInTheLoopMiddleware(agent._INTERRUPT_ON)  # pyright: ignore[reportPrivateUsage]
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    ToolCall(type="tool_call", name="ls", args={}, id="call-2")
                ],
            )
        ]
    }

    assert middleware.after_model(cast("Any", state), cast("Any", None)) is None


def test_each_human_decision_leaves_a_distinct_activity_event() -> None:
    action = {
        "name": "write_file",
        "args": {"file_path": "workspace/a.md"},
        "intent": "Save the requested note.",
        "implication": "Writes one sandbox file.",
        "severity": "medium",
    }

    approved = _approval_event(action, "approve", "allowed once")
    edited = _approval_event(action, "edit", "edited and allowed", {})
    rejected = _approval_event(action, "reject", "denied")

    assert [approved.title, edited.title, rejected.title] == [
        "Allowed by user: write_file",
        "Edited and allowed by user: write_file",
        "Denied by user: write_file",
    ]
    assert json.loads(edited.details)["effective_args"] == {}
    assert "not run" in str(rejected.tool_result)
