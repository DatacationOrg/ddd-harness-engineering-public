"""Tool calls should be understandable before a person approves them."""

from ddd_harness_engineering.tool_context import describe_tool_call


def test_model_supplied_intent_is_kept_separate_from_tool_arguments() -> None:
    context = describe_tool_call(
        "write_file",
        {"file_path": "workspace/report.md", "content": "..."},
        intent="Save the requested audit report for the user.",
    )

    assert context.intent == "Save the requested audit report for the user."
    assert context.title == "Create or replace a file"
    assert "workspace/report.md" in context.implication
    assert context.severity == "medium"


def test_execute_is_high_impact_and_has_a_useful_fallback_intent() -> None:
    context = describe_tool_call("execute", {"command": "python workspace/chart.py"})

    assert context.severity == "high"
    assert "python workspace/chart.py" in context.intent
    assert "local process" in context.implication


def test_read_only_tools_are_low_impact() -> None:
    context = describe_tool_call("read_file", {"file_path": "data/shipments.csv"})

    assert context.severity == "low"
    assert "does not intentionally change files" in context.implication


def test_generic_middleware_description_is_not_mistaken_for_model_intent() -> None:
    context = describe_tool_call(
        "edit_file",
        {"file_path": "workspace/report.md"},
        intent="Tool execution requires approval\n\nTool: edit_file",
    )

    assert context.intent == "Change selected content in `workspace/report.md`."
