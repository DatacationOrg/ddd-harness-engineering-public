"""The Files workspace is a proportional map plus a Windows-style explorer."""

from pathlib import Path

import pytest

from ddd_harness_engineering.ui_sandbox import (
    _Rect,
    _folder_label,
    _partition_rectangles,
    _storage_map_records,
    _visible_tree_options,
)


def _area(rectangle: _Rect) -> float:
    return rectangle.width * rectangle.height


def test_partition_preserves_total_area_and_weight_ratio() -> None:
    outer = _Rect(0, 0, 100, 50)

    rectangles = _partition_rectangles([("large", 3), ("small", 1)], outer)

    assert sum(_area(rectangle) for rectangle in rectangles.values()) == pytest.approx(
        _area(outer)
    )
    assert _area(rectangles["large"]) / _area(rectangles["small"]) == pytest.approx(3)


def test_storage_map_marks_only_workspace_files_writable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    downloads = tmp_path / "Downloads"
    workspace.mkdir()
    downloads.mkdir()
    report = workspace / "report.md"
    invoice = downloads / "invoice.pdf"
    report.write_bytes(b"report")
    invoice.write_bytes(b"invoice-data")

    leaves, groups = _storage_map_records(tmp_path, [report, invoice])

    by_path = {leaf["path"]: leaf for leaf in leaves}
    assert by_path["workspace/report.md"]["writable"] is True
    assert by_path["Downloads/invoice.pdf"]["writable"] is False
    assert next(group for group in groups if group["writable"])["label"] == "workspace/"


def test_folder_tree_uses_windows_style_markers() -> None:
    assert _folder_label(".", "northwind-freight") == "💻 northwind-freight"
    assert _folder_label("Clients/Acme", "northwind-freight").endswith("└─ 📁 Acme")
    assert _folder_label("workspace", "northwind-freight") == "└─ ✏️ workspace"


def test_folder_tree_expands_only_the_selected_branch() -> None:
    options = [
        ".",
        "archive",
        "archive/2019",
        "archive/2019/scans",
        "archive/2021",
        "Clients",
        "Clients/Acme",
    ]

    assert _visible_tree_options(options, ".") == [".", "archive", "Clients"]
    assert _visible_tree_options(options, "archive/2019") == [
        ".",
        "archive",
        "archive/2019",
        "archive/2019/scans",
        "archive/2021",
        "Clients",
    ]
