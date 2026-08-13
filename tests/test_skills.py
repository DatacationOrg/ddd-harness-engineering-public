"""Tests that the agent's skill is actually discovered (station S5).

Worth having, because every failure mode here is silent. A skill in the wrong
place, with a mistyped frontmatter key, or with a vague description simply does
not fire -- nothing raises, and the agent behaves as if the skill was never
written. These tests turn silence into a red test.
"""

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import _list_skills_with_errors

from ddd_harness_engineering.agent import AGENT_HOME, SKILLS_SOURCE


def _load():
    backend = FilesystemBackend(root_dir=AGENT_HOME, virtual_mode=True)
    return _list_skills_with_errors(backend, SKILLS_SOURCE)


def test_the_skill_is_discovered_without_errors() -> None:
    skills, error = _load()

    assert error is None
    assert [skill["name"] for skill in skills] == ["file-triage"]


def test_the_description_says_when_to_use_it() -> None:
    """Progressive disclosure means the description is all the model sees first.

    If it does not describe the trigger, the skill never fires.
    """
    (skill,) = _load()[0]

    assert "Use whenever" in skill["description"]
    assert len(skill["description"]) > 80


def test_allowed_tools_are_parsed() -> None:
    """The frontmatter key is `allowed-tools`, hyphenated.

    `allowed_tools` with an underscore parses to an empty list and silently
    grants everything -- a real trap, hence this test.
    """
    (skill,) = _load()[0]

    assert skill["allowed_tools"] == ["ls", "glob", "grep", "read_file", "write_file"]
    assert "execute" not in skill["allowed_tools"]


def test_the_skill_encodes_the_rules_that_matter() -> None:
    """The point of a skill is behaviour the prompt would otherwise have to carry."""
    body = (AGENT_HOME / "skills" / "file-triage" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "Never delete" in body
    assert "Compare **contents**, never names" in body
    assert "workspace/" in body


def test_skills_live_under_the_backend_root_not_the_repo_root() -> None:
    """A path relative to the repo instead of the backend is the other silent failure."""
    (skill,) = _load()[0]

    assert skill["path"] == "/skills/file-triage/SKILL.md"
    assert (AGENT_HOME / "skills" / "file-triage" / "SKILL.md").is_file()
