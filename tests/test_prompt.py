"""Tests for the system prompt and model configuration (station S1).

A prompt cannot be unit-tested for quality. What *can* be pinned is that the
instructions the rest of the day depends on are still present -- so that a
participant rewriting the prompt in S1 finds out immediately if they have
deleted the sentence that S3's injection defence relies on.
"""

import inspect

from ddd_harness_engineering import agent


def test_the_prompt_is_organised_into_sections() -> None:
    """Headed structure is retrieved more reliably than a wall of prose."""
    headings = [
        line for line in agent._SYSTEM_PROMPT.splitlines() if line.startswith("## ")
    ]

    assert len(headings) >= 3


def test_the_prompt_states_that_tool_output_is_not_instruction() -> None:
    """S3's injection defence leans on this sentence; deleting it is a regression."""
    assert "not instruction" in agent._SYSTEM_PROMPT
    assert "untrusted" in agent._SYSTEM_PROMPT.lower()


def test_the_prompt_forbids_repeating_secrets() -> None:
    prompt = agent._SYSTEM_PROMPT.lower()

    assert "secret" in prompt or "credential" in prompt


def test_the_prompt_explains_when_to_delegate() -> None:
    assert "task tool" in agent._SYSTEM_PROMPT
    assert "subagent" in agent._SYSTEM_PROMPT


def test_the_prompt_is_short_enough_to_read_aloud() -> None:
    """Context is a budget. A prompt nobody reads is a prompt nobody maintains."""
    assert len(agent._SYSTEM_PROMPT) < 2000


def test_reasoning_effort_is_a_parameter_not_a_literal() -> None:
    """Turning this knob is the S1 exercise, so it has to be reachable."""
    signature = inspect.signature(agent.create_model)

    assert "effort" in signature.parameters
    assert signature.parameters["effort"].default == agent.REASONING_EFFORT


def test_the_default_effort_is_one_the_api_accepts() -> None:
    assert agent.REASONING_EFFORT in {"minimal", "low", "medium", "high"}


def test_reasoning_summaries_stay_switched_on() -> None:
    """Without `summary: auto` the model still reasons -- you just cannot see it.

    The whole app is a window onto the agent's internals, so losing this
    silently empties half the window.
    """
    assert '"summary": "auto"' in inspect.getsource(agent.create_model)
