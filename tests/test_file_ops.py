"""The reorganisation tools, and the two rules that make them safe to hand over.

`move_file`, `copy_file` and `delete_file` are the only tools in the harness
that rearrange the user's drive rather than reading it or adding to it. Two
properties carry that weight, and both are tested here rather than trusted:

1. They cannot act outside the sandbox root, whatever path they are handed.
2. They never overwrite. A move onto an existing file changes nothing at all.

Every test runs against a temporary root, patched over `sandbox_root`, so the
real generated sandbox is never touched.
"""

from pathlib import Path

import pytest

from ddd_harness_engineering.tools import file_ops

_ESCAPES = [
    "../../.env",
    "/../../.env",
    "..\\..\\.env",
    "C:\\Windows\\System32\\drivers\\etc\\hosts",
]


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway sandbox, with one file in it, standing in for the real one."""
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "Downloads" / "scan.pdf").write_text("contract", encoding="utf-8")
    monkeypatch.setattr(file_ops, "sandbox_root", lambda: tmp_path)
    return tmp_path


def test_move_relocates_a_file(root: Path) -> None:
    result = file_ops.move_file("/Downloads/scan.pdf", "/Clients/Bergmann/signed.pdf")

    assert "Moved" in result
    assert not (root / "Downloads" / "scan.pdf").exists()
    assert (root / "Clients" / "Bergmann" / "signed.pdf").read_text(
        encoding="utf-8"
    ) == "contract"


def test_move_accepts_paths_without_a_leading_slash(root: Path) -> None:
    """The agent sees two path shapes and will use both. Accept both."""
    result = file_ops.move_file("Downloads/scan.pdf", "Downloads/renamed.pdf")

    assert "Moved" in result
    assert (root / "Downloads" / "renamed.pdf").exists()


def test_move_creates_missing_parent_folders(root: Path) -> None:
    file_ops.move_file("/Downloads/scan.pdf", "/a/b/c/scan.pdf")

    assert (root / "a" / "b" / "c" / "scan.pdf").exists()


def test_move_refuses_to_overwrite_and_changes_nothing(root: Path) -> None:
    """The destructive half of a move is clobbering the destination."""
    (root / "existing.pdf").write_text("important", encoding="utf-8")

    result = file_ops.move_file("/Downloads/scan.pdf", "/existing.pdf")

    assert "already exists" in result
    assert (root / "existing.pdf").read_text(encoding="utf-8") == "important"
    assert (root / "Downloads" / "scan.pdf").exists(), "source must survive a refusal"


def test_move_reports_a_missing_source(root: Path) -> None:
    result = file_ops.move_file("/Downloads/nope.pdf", "/elsewhere.pdf")

    assert "does not exist" in result


def test_copy_leaves_the_original_in_place(root: Path) -> None:
    result = file_ops.copy_file("/Downloads/scan.pdf", "/backup/scan.pdf")

    assert "Copied" in result
    assert (root / "Downloads" / "scan.pdf").exists()
    assert (root / "backup" / "scan.pdf").read_text(encoding="utf-8") == "contract"


def test_delete_removes_one_file(root: Path) -> None:
    result = file_ops.delete_file("/Downloads/scan.pdf")

    assert "Deleted" in result
    assert not (root / "Downloads" / "scan.pdf").exists()


def test_delete_refuses_a_folder(root: Path) -> None:
    """Deleting a tree on one approval is a blast radius nobody asked for."""
    result = file_ops.delete_file("/Downloads")

    assert "folder" in result
    assert (root / "Downloads").is_dir()


@pytest.mark.parametrize("escape", _ESCAPES)
def test_escapes_are_refused_by_every_tool(root: Path, escape: str) -> None:
    outside = root.parent / ".env"
    outside.write_text("MICROSOFT_FOUNDRY_KEY=secret", encoding="utf-8")

    assert "outside the sandbox" in file_ops.delete_file(escape)
    assert "outside the sandbox" in file_ops.move_file(escape, "/stolen.env")
    assert "outside the sandbox" in file_ops.move_file("/Downloads/scan.pdf", escape)
    assert "outside the sandbox" in file_ops.copy_file(escape, "/stolen.env")

    assert outside.exists(), "the file outside the sandbox must be untouched"
    assert not (root / "stolen.env").exists()


def test_a_leading_slash_means_the_sandbox_root_not_the_host(root: Path) -> None:
    """`/etc/passwd` is the sandbox's own `/etc`, matching the file tools.

    It is contained rather than refused, which is the point: the leading slash
    is the agent's virtual root, so the host's `/etc/passwd` is not addressable
    at all -- there is no path that reaches it.
    """
    (root / "etc").mkdir()
    (root / "etc" / "passwd").write_text("the sandbox's own copy", encoding="utf-8")

    result = file_ops.delete_file("/etc/passwd")

    assert "Deleted" in result
    assert not (root / "etc" / "passwd").exists(), "the sandbox copy is the target"


def test_a_symlink_out_of_the_sandbox_is_refused(root: Path) -> None:
    """resolve() follows the link, so containment is checked where it lands."""
    outside = root.parent / "secrets.txt"
    outside.write_text("key", encoding="utf-8")
    try:
        (root / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks need elevated privileges on this machine")

    assert "outside the sandbox" in file_ops.delete_file("/link.txt")
    assert outside.exists()
