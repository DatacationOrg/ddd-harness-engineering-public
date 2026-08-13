import pytest

from ddd_harness_engineering.chat import ExecutionEvent
from ddd_harness_engineering.ui_templates import load_template, render_template
from ddd_harness_engineering.ui_trace import _row_html


def test_loads_a_packaged_style_template() -> None:
    template = load_template("styles/user_chat.html")

    assert template.startswith("<style>")
    assert "stChatMessageAvatarUser" in template


def test_renders_dynamic_template_values() -> None:
    rendered = render_template(
        "styles/workspace_layout.html",
        right_pad="min(445px, 36vw)",
    )

    assert "--workspace-right-pad:min(445px, 36vw)" in rendered
    assert "$right_pad" not in rendered


def test_missing_template_values_are_reported() -> None:
    with pytest.raises(KeyError, match="right_pad"):
        render_template("styles/workspace_layout.html")


def test_trace_row_uses_templates_and_escapes_event_content() -> None:
    event = ExecutionEvent(
        step=0,
        scope="main > researcher",
        category="tool",
        title="Called a tool: lookup <unsafe>",
        details="{}",
        tool_name="lookup <unsafe>",
        intent="Find <the answer>",
        severity="low",
    )

    rendered = _row_html(event)

    assert 'class="trace-row trace-depth-1"' in rendered
    assert 'class="trace-badge trace-tool"' in rendered
    assert "lookup &lt;unsafe&gt;" in rendered
    assert "Find &lt;the answer&gt;" in rendered
    assert "lookup <unsafe>" not in rendered
