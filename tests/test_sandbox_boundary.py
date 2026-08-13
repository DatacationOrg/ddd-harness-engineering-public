"""The sandbox boundary is a real wall, and these tests prove it (station S2).

Worth reading before the workshop, because the default is a trap.
`FilesystemBackend(root_dir=...)` looks like it confines the agent. It does not:
with `virtual_mode=False` (the default in deepagents 0.6.12), deepagents' own
deprecation warning says absolute paths and `..` bypass `root_dir` -- and they
do, all the way into the user's home directory.

That makes this the sharpest demonstration in the day: the configuration that
*looks* safe is the one that reads your `.env`.
"""

from pathlib import Path

import pytest
from deepagents.backends import FilesystemBackend

from ddd_harness_engineering.sandbox import sandbox_root

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

_ESCAPES = [
    "/../../.env",
    "../../.env",
    "/etc/passwd",
]


def _contained_backend() -> FilesystemBackend:
    """The backend as the agent actually configures it."""
    return FilesystemBackend(root_dir=sandbox_root(), virtual_mode=True)


def _read_succeeded(backend: FilesystemBackend, path: str) -> bool:
    try:
        return getattr(backend.read(path), "error", None) is None
    except ValueError, OSError:
        return False


def test_a_path_inside_the_sandbox_is_readable() -> None:
    assert _read_succeeded(_contained_backend(), "/data/README.md")


@pytest.mark.parametrize("escape", _ESCAPES)
def test_paths_outside_the_sandbox_are_refused(escape: str) -> None:
    assert not _read_succeeded(_contained_backend(), escape)


def test_the_users_home_directory_is_unreachable() -> None:
    """The one that matters. `.env`, `.ssh` and `.gitconfig` all live up here."""
    assert not _read_succeeded(_contained_backend(), str(Path.home() / ".gitconfig"))


def test_the_default_backend_does_not_contain_the_agent() -> None:
    """Documents the trap, and fails loudly if deepagents ever changes the default.

    If this test starts failing, `virtual_mode=False` has become safe and the
    warning in `agent.py` should be revisited -- do not simply delete the test.
    """
    leaky = FilesystemBackend(root_dir=sandbox_root(), virtual_mode=False)

    assert _read_succeeded(leaky, str(Path.home() / ".gitconfig")), (
        "virtual_mode=False is expected to leak outside root_dir; "
        "if it no longer does, the guardrail rationale needs updating"
    )
