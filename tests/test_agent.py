from collections.abc import Iterator
from typing import Any, TypedDict, cast

from langchain_core.messages import AIMessageChunk, BaseMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pytest import MonkeyPatch

from ddd_harness_engineering import agent
from ddd_harness_engineering.chat import AgentResponse, ChatMessage


class FakeAgent:
    def stream(
        self, agent_input: object, stream_mode: object = None, **kwargs: object
    ) -> Iterator[tuple[BaseMessage, dict[str, object]]]:
        yield ToolMessage(content="internal tool output", tool_call_id="call-1"), {}
        yield (
            AIMessageChunk(content=[{"type": "reasoning", "reasoning": "Thinking"}]),
            {},
        )
        yield AIMessageChunk(content="Visible answer"), {}


class FakeStructuredModel:
    def invoke(self, messages: object) -> agent.FollowUpSuggestions:
        return agent.FollowUpSuggestions(questions=["One?", "Two?", "Three?"])


class FakeModel:
    def with_structured_output(
        self, schema: object, method: str | None = None
    ) -> FakeStructuredModel:
        return FakeStructuredModel()


def test_stream_agent_response_only_yields_ai_messages() -> None:
    response = AgentResponse()
    reasoning_chunks: list[str] = []

    chunks = agent.stream_agent_response(
        FakeAgent(),
        agent.new_turn_input("Hello"),
        response,
        "test-thread",
        on_reasoning=reasoning_chunks.append,
    )

    assert "".join(chunks) == "Visible answer"
    assert reasoning_chunks == ["Thinking"]


def test_new_turn_input_sends_only_the_new_message() -> None:
    # History lives in the checkpointer, so replaying it here would duplicate it.
    assert agent.new_turn_input("Hello") == {
        "messages": [{"role": "user", "content": "Hello"}]
    }


def test_thread_config_selects_the_conversation() -> None:
    assert agent.thread_config("abc") == {"configurable": {"thread_id": "abc"}}


def test_interrupt_is_extracted_and_resumable() -> None:
    """Guards the human-in-the-loop path against a change in langgraph's payload shape.

    Uses a real graph rather than a fake, because the thing under test is
    exactly how langgraph reports a pause.
    """

    class State(TypedDict):
        val: str

    def pausing_node(state: State) -> State:
        decision = interrupt({"action": "delete_file", "args": {"path": "x.txt"}})
        return {"val": f"resumed with {decision}"}

    graph = StateGraph(State)
    graph.add_node("pausing_node", pausing_node)
    graph.add_edge(START, "pausing_node")
    graph.add_edge("pausing_node", END)
    compiled = graph.compile(checkpointer=InMemorySaver())

    response = AgentResponse()
    list(
        agent.stream_agent_response(
            compiled,
            agent.new_turn_input("start"),
            response,
            "interrupt-thread",
        )
    )

    assert response.pending_approval == [
        {"action": "delete_file", "args": {"path": "x.txt"}}
    ]
    # The pause must be observable in the dashboard, not just in state.
    assert any(event.category == "approval" for event in response.execution_events)

    resumed = compiled.invoke(
        agent.resume_input("approved"),
        config=cast("Any", agent.thread_config("interrupt-thread")),
    )
    assert resumed["val"] == "resumed with approved"


def test_generate_follow_up_questions(monkeypatch: MonkeyPatch) -> None:
    def create_fake_model(*, streaming: bool) -> FakeModel:
        return FakeModel()

    monkeypatch.setattr(agent, "create_model", create_fake_model)

    questions = agent.generate_follow_up_questions(
        [ChatMessage(role="assistant", content="An answer")]
    )

    assert questions == ["One?", "Two?", "Three?"]
