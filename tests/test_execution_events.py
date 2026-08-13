"""Tests for the event-classification layer behind the Execution Dashboard.

This layer turns raw langgraph stream output into `ExecutionEvent`s. Every payload
shape used here is one langgraph really emits for
`stream_mode=["messages", "tasks", "updates"]` with `subgraphs=True`:

    ((), "tasks",   {"id": ..., "name": "model", "input": ..., "triggers": ...})
    ((), "updates", {"model": {...}})
    ((), "tasks",   {"id": ..., "name": "model", "error": None, "result": ..., ...})

Note what is *missing*: a task payload carries no `event` or `type` key, so a start
and a finish can only be told apart by which keys are present. That is what
`_task_phase` does, and getting it wrong once hid every tool result from the
dashboard -- see `test_a_real_graph_reports_both_halves_of_every_step`.
"""

import json
from typing import TypedDict

from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from ddd_harness_engineering import agent
from ddd_harness_engineering.chat import AgentResponse, ExecutionEvent
from ddd_harness_engineering.ui_trace import visible_events

TASK_ID = "07c21485-164a-7dca-7ad3-a60ed4d06461"


def task_start_payload(name: str) -> dict[str, object]:
    """A `tasks` payload exactly as langgraph emits it when a node starts."""
    return {
        "id": TASK_ID,
        "name": name,
        "input": {"messages": []},
        "triggers": (f"branch:to:{name}",),
    }


def task_finish_payload(name: str) -> dict[str, object]:
    """A `tasks` payload exactly as langgraph emits it when a node finishes."""
    return {
        "id": TASK_ID,
        "name": name,
        "error": None,
        "result": {"messages": []},
        "interrupts": [],
    }


def make_event(step: int, title: str, scope: str = "main") -> ExecutionEvent:
    return ExecutionEvent(
        step=step, scope=scope, category="model", title=title, details="{}"
    )


# --- _task_phase ------------------------------------------------------------


def test_task_phase_reads_a_start_payload_as_started() -> None:
    assert agent._task_phase(task_start_payload("model")) == "started"


def test_task_phase_reads_a_finish_payload_as_finished() -> None:
    assert agent._task_phase(task_finish_payload("model")) == "finished"


def test_task_phase_treats_a_failed_task_as_finished() -> None:
    """A node that raised carries `error` but no `result` -- it has still finished."""
    failed: dict[str, object] = {
        "id": TASK_ID,
        "name": "tools",
        "error": ValueError("boom"),
        "interrupts": [],
    }

    assert agent._task_phase(failed) == "finished"


def test_the_two_halves_of_a_step_render_as_different_titles() -> None:
    """The dedupe filter compares titles, so identical titles lose the finish."""
    started = agent._format_event("tasks", (), task_start_payload("tools"), 0)
    finished = agent._format_event("tasks", (), task_finish_payload("tools"), 1)

    assert started is not None
    assert finished is not None
    assert started.title != finished.title


# --- _format_event ----------------------------------------------------------


def test_format_event_labels_the_model_node() -> None:
    event = agent._format_event("tasks", (), task_start_payload("model"), 3)

    assert event is not None
    assert (event.step, event.scope) == (3, "main")
    assert (event.category, event.title) == ("model", "Model step (started)")
    assert event.internal is False


def test_format_event_labels_the_tools_node() -> None:
    event = agent._format_event("tasks", (), task_finish_payload("tools"), 4)

    assert event is not None
    assert (event.category, event.title) == ("tool", "Tool execution (finished)")


def test_format_event_labels_the_delegation_node_as_a_subagent_call() -> None:
    """deepagents delegates through a node whose name contains `task`."""
    event = agent._format_event("tasks", (), task_start_payload("task"), 0)

    assert event is not None
    assert (event.category, event.title) == (
        "subagent",
        "Subagent call (started): task",
    )


def test_format_event_falls_back_to_a_generic_task_for_other_node_names() -> None:
    event = agent._format_event("tasks", (), task_start_payload("summarise"), 0)

    assert event is not None
    assert (event.category, event.title) == ("task", "Task (started): summarise")


def test_format_event_carries_the_scope_from_the_namespace() -> None:
    event = agent._format_event(
        "tasks", ("tools:9f1c",), task_start_payload("model"), 0
    )

    assert event is not None
    assert event.scope == "main > subagent"


def test_format_event_details_are_pretty_printed_json() -> None:
    """The dashboard shows `details` verbatim when a step is clicked."""
    event = agent._format_event(
        "tasks", ("tools:9f1c",), task_start_payload("model"), 0
    )

    assert event is not None
    details = json.loads(event.details)
    assert details["mode"] == "tasks"
    assert details["namespace"] == ["tools:9f1c"]
    assert details["payload"]["name"] == "model"


def test_noisy_middleware_tasks_are_marked_internal_rather_than_dropped() -> None:
    """The sidebar hides internal steps behind a toggle, so they must still exist."""
    for name in (
        "PatchToolCallsMiddleware.before_model",
        "TodoListMiddleware.after_model",
    ):
        event = agent._format_event("tasks", (), task_start_payload(name), 0)

        assert event is not None, name
        assert event.internal is True, name
        assert event.category == "internal", name


def test_format_event_reports_a_model_update() -> None:
    event = agent._format_event("updates", (), {"model": {"messages": []}}, 0)

    assert event is not None
    assert (event.category, event.title) == ("model", "Model updated")


def test_format_event_reports_a_state_update_naming_the_nodes() -> None:
    event = agent._format_event("updates", (), {"tools": {"messages": []}}, 0)

    assert event is not None
    assert (event.category, event.title) == ("state", "State updated: tools")


def test_noisy_middleware_updates_are_marked_internal_rather_than_dropped() -> None:
    payload = {"TodoListMiddleware.before_model": {"todos": []}}
    event = agent._format_event("updates", (), payload, 0)

    assert event is not None
    assert event.internal is True
    assert event.category == "internal"


def test_format_event_drops_an_empty_updates_payload() -> None:
    """An update naming no nodes says nothing, so it must not become a trace row."""
    assert agent._format_event("updates", (), {}, 0) is None


def test_format_event_ignores_message_chunks() -> None:
    """Message chunks are answer text; they are handled before classification."""
    assert (
        agent._format_event("messages", (), (AIMessageChunk(content="hi"), {}), 0)
        is None
    )


def test_format_event_survives_an_unexpected_task_payload() -> None:
    event = agent._format_event("tasks", (), "not a dict", 0)

    assert event is not None
    assert event.title == "Task event"


def test_format_event_survives_an_unexpected_update_payload() -> None:
    event = agent._format_event("updates", (), ["not a dict"], 0)

    assert event is not None
    assert event.title == "State update (list)"


# --- _format_scope ----------------------------------------------------------


def test_format_scope_of_the_root_graph_is_main() -> None:
    assert agent._format_scope(()) == "main"


def test_format_scope_names_a_subagent_hop() -> None:
    """S3 depends on the delegation being readable in the trace as a path."""
    assert agent._format_scope(("tools:9f1c",)) == "main > subagent"


def test_format_scope_renders_a_nested_namespace_as_a_path() -> None:
    namespace = ("tools:9f1c", "tools:2ab7")

    assert agent._format_scope(namespace) == "main > subagent > subagent"


def test_format_scope_strips_the_raw_task_uuid() -> None:
    """A namespace part is `<node>:<task-uuid>`; the uuid is noise on screen."""
    scope = agent._format_scope((f"summarise:{TASK_ID}",))

    assert scope == "main > summarise"
    assert TASK_ID not in scope


# --- _to_jsonable -----------------------------------------------------------


def test_to_jsonable_passes_primitives_through_unchanged() -> None:
    assert agent._to_jsonable("text") == "text"
    assert agent._to_jsonable(7) == 7
    assert agent._to_jsonable(1.5) == 1.5
    assert agent._to_jsonable(True) is True
    assert agent._to_jsonable(None) is None


def test_to_jsonable_walks_containers_and_turns_tuples_into_lists() -> None:
    value = {"triggers": ("branch:to:model",), "input": {"messages": [1, 2]}}

    assert agent._to_jsonable(value) == {
        "triggers": ["branch:to:model"],
        "input": {"messages": [1, 2]},
    }


def test_to_jsonable_stringifies_keys_that_are_not_strings() -> None:
    assert agent._to_jsonable({1: "one"}) == {"1": "one"}


def test_to_jsonable_degrades_an_unserialisable_object_to_its_repr() -> None:
    """A payload we cannot serialise must cost one field, not the whole trace row."""

    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    jsonable = agent._to_jsonable({"result": Opaque()})

    assert jsonable == {"result": "<opaque>"}
    assert json.dumps(jsonable) == '{"result": "<opaque>"}'


# --- _stream_parts ----------------------------------------------------------


def test_stream_parts_passes_through_the_three_tuple_shape() -> None:
    """The shape `subgraphs=True` plus a list `stream_mode` actually yields."""
    parts: list[object] = [(("tools:9f1c",), "tasks", {"name": "model"})]

    assert list(agent._stream_parts(iter(parts))) == [
        (("tools:9f1c",), "tasks", {"name": "model"})
    ]


def test_stream_parts_gives_a_mode_payload_pair_the_root_namespace() -> None:
    """Without `subgraphs=True` there is no namespace, so everything is `main`."""
    parts: list[object] = [("updates", {"model": {"messages": []}})]

    assert list(agent._stream_parts(iter(parts))) == [
        ((), "updates", {"model": {"messages": []}})
    ]


def test_stream_parts_retags_a_legacy_message_metadata_pair() -> None:
    """With only message streaming, langgraph yields `(message, metadata)` and no mode."""
    message = AIMessageChunk(content="Visible answer")
    parts: list[object] = [(message, {"langgraph_node": "model"})]

    namespace, mode, payload = next(iter(agent._stream_parts(iter(parts))))

    assert (namespace, mode) == ((), "messages")
    assert agent._extract_message(payload) is message


def test_stream_parts_skips_anything_that_is_not_a_tuple() -> None:
    assert list(agent._stream_parts(iter(["not a tuple"]))) == []


# --- AgentResponse.add_execution_event --------------------------------------


def test_a_consecutive_duplicate_event_is_dropped() -> None:
    response = AgentResponse()

    first = response.add_execution_event(make_event(0, "Model step (started)"))
    second = response.add_execution_event(make_event(1, "Model step (started)"))

    assert first is not None
    assert second is None
    assert len(response.execution_events) == 1


def test_a_repeated_event_is_kept_when_another_event_came_in_between() -> None:
    """Only *consecutive* repeats are noise; a second model step is real."""
    response = AgentResponse()

    response.add_execution_event(make_event(0, "Model step (started)"))
    response.add_execution_event(make_event(1, "Tool execution (started)"))
    response.add_execution_event(make_event(2, "Model step (started)"))

    assert [event.title for event in response.execution_events] == [
        "Model step (started)",
        "Tool execution (started)",
        "Model step (started)",
    ]


def test_step_numbers_stay_contiguous_when_events_are_dropped() -> None:
    """The caller's counter advances for dropped events too, so the number is
    assigned on insert -- otherwise the live trace and the sidebar disagree."""
    response = AgentResponse()

    for step, title in enumerate(["First", "First", "Second", "Second", "Third"]):
        response.add_execution_event(make_event(step, title))

    assert [event.step for event in response.execution_events] == [0, 1, 2]
    assert [event.title for event in response.execution_events] == [
        "First",
        "Second",
        "Third",
    ]


def test_the_trace_line_pairs_scope_with_title() -> None:
    response = AgentResponse()

    response.add_execution_event(
        make_event(9, "Tool execution (finished)", "main > subagent")
    )

    assert response.execution_trace == ["[main > subagent] Tool execution (finished)"]


def test_default_activity_hides_engine_noise_and_collapses_a_tool_lifecycle() -> None:
    events = [
        make_event(0, "Model step (started)"),
        ExecutionEvent(
            step=1,
            scope="main",
            category="tool",
            title="Tool execution (started): write_file",
            details="start",
            tool_name="write_file",
            tool_args='{"file_path": "workspace/a.md"}',
            intent="Save the requested note.",
            implication="Writes one sandbox file.",
            severity="medium",
        ),
        ExecutionEvent(
            step=2,
            scope="main",
            category="tool",
            title="Tool execution (finished): write_file",
            details="finish",
            tool_name="write_file",
            tool_result="saved",
            severity="medium",
        ),
        make_event(3, "Model step (finished)"),
    ]

    shown = visible_events(events, show_internal=False)

    assert len(shown) == 1
    assert shown[0].title == "Create or replace a file"
    assert shown[0].tool_args == '{"file_path": "workspace/a.md"}'
    assert shown[0].tool_result == "saved"
    assert shown[0].intent == "Save the requested note."


def test_technical_activity_keeps_the_raw_engineering_trace() -> None:
    events = [make_event(0, "Model step (started)"), make_event(1, "Model updated")]

    assert visible_events(events, show_internal=True) == events


# --- end to end against a real graph ----------------------------------------


def test_a_real_graph_reports_both_halves_of_every_step() -> None:
    """Regression test for the bug that hid every tool result from the dashboard.

    A hand-rolled fake can only prove we handle the shapes we imagined. This drives
    the whole chain -- `.stream()` -> `_stream_parts` -> `_format_event` ->
    `AgentResponse` -- with the shapes langgraph really emits, and asserts that the
    `(finished)` half of each step survives the consecutive-duplicate filter.
    """

    class State(TypedDict):
        steps: list[str]

    def model_node(state: State) -> State:
        return {"steps": [*state["steps"], "model"]}

    def tools_node(state: State) -> State:
        return {"steps": [*state["steps"], "tools"]}

    graph = StateGraph(State)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "model")
    graph.add_edge("model", "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile(checkpointer=InMemorySaver())

    response = AgentResponse()
    list(agent.stream_agent_response(compiled, {"steps": []}, response, "trace-thread"))

    assert response.execution_trace == [
        "[main] Model step (started)",
        "[main] Model updated",
        "[main] Model step (finished)",
        "[main] Tool execution (started)",
        "[main] State updated: tools",
        "[main] Tool execution (finished)",
    ]
    assert [event.step for event in response.execution_events] == [0, 1, 2, 3, 4, 5]
