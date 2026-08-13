"""Tests for the duplicate-finder tool (station S2).

Assertions run against deterministic contracts published by the sandbox seeder,
plus on-disk bytes from the seeded files, rather than against hardcoded paths.
"""

import hashlib
from pathlib import Path

import pytest

from ddd_harness_engineering.sandbox import SANDBOX_ROOT
from ddd_harness_engineering.tools.filesystem import (
    find_duplicate_files,
    find_duplicate_groups,
)
from scripts.seed_sandbox import (
    DUPLICATE_GROUP,
    NEAR_DUPLICATE_NAMES,
)


@pytest.fixture(scope="module", autouse=True)
def seeded_sandbox() -> None:
    if not SANDBOX_ROOT.is_dir() or not any(SANDBOX_ROOT.rglob("*")):
        pytest.skip(
            "Sandbox not generated. Run: uv run python scripts/seed_sandbox.py --reset"
        )


def test_finds_exactly_the_seeded_duplicate_group() -> None:
    expected_paths = sorted(DUPLICATE_GROUP)
    source = SANDBOX_ROOT / DUPLICATE_GROUP[0]
    source_bytes = source.read_bytes()
    expected_digest = hashlib.sha256(source_bytes).hexdigest()
    expected_size = len(source_bytes)

    groups = find_duplicate_groups(SANDBOX_ROOT)

    assert len(groups) == 1
    assert sorted(groups[0].paths) == expected_paths
    assert groups[0].digest == expected_digest
    assert groups[0].size_bytes == expected_size


def test_ignores_files_that_only_have_similar_names() -> None:
    """The report_final_FINAL_v2.xlsx trap: same idea, different bytes."""
    reported = {
        path for group in find_duplicate_groups(SANDBOX_ROOT) for path in group.paths
    }

    assert not reported.intersection(NEAR_DUPLICATE_NAMES)


def test_compares_contents_not_sizes(tmp_path: Path) -> None:
    """Same size, different bytes -- the trap a size-only deduper falls into."""
    (tmp_path / "a.bin").write_bytes(b"AAAA")
    (tmp_path / "b.bin").write_bytes(b"BBBB")

    assert find_duplicate_groups(tmp_path) == []


def test_finds_duplicates_regardless_of_name(tmp_path: Path) -> None:
    (tmp_path / "invoice.pdf").write_bytes(b"same")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "Copy of invoice (1).pdf").write_bytes(b"same")

    groups = find_duplicate_groups(tmp_path)

    assert len(groups) == 1
    assert len(groups[0].paths) == 2


def test_tool_reports_the_group_in_readable_text() -> None:
    report = find_duplicate_files()

    assert "1 group(s)" in report
    assert "INV-2025-0842.pdf" in report


def test_tool_refuses_to_scan_outside_the_sandbox() -> None:
    report = find_duplicate_files("../../..")

    assert "outside the sandbox" in report


def test_tool_explains_a_missing_directory_instead_of_raising() -> None:
    report = find_duplicate_files("no-such-folder")

    assert "No such directory" in report
    assert "ls" in report, "the message should tell the model what to do next"
