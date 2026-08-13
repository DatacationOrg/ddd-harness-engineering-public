"""The agent's whole world, rendered as a storage map and file explorer.

Two things are on show here, and they are different:

- A proportional map makes large folders and files visible at a glance.
- A Windows-style tree and details pane make the actual paths browsable.
- ``workspace/`` is marked as the only writable part of the drive.

The UI is read-only and rooted at the sandbox for the same reason the agent is.
"""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ddd_harness_engineering.sandbox import WORKSPACE_DIR, sandbox_root

_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})
_TEXT_SUFFIXES = frozenset(
    {".py", ".txt", ".md", ".csv", ".json", ".log", ".yaml", ".yml"}
)
_MAX_PREVIEW_CHARS = 4000
_MAX_TREE_ENTRIES = 400
_MAP_WIDTH = 100.0
_MAP_HEIGHT = 58.0
_MAP_GAP = 0.35
_ROOT_FOLDER = "."
_FOLDER_COLORS = (
    "#166534",
    "#0f766e",
    "#0369a1",
    "#1d4ed8",
    "#0f172a",
    "#9a3412",
    "#b45309",
    "#a16207",
    "#065f46",
    "#0c4a6e",
    "#334155",
)
_WORKSPACE_COLOR = "#2563eb"


@dataclass(frozen=True)
class _Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height


def render_sandbox_panel() -> None:
    root = _sandbox_or_none()
    if root is None:
        st.caption(
            "No sandbox found. Generate it with "
            "`uv run python scripts/seed_sandbox.py --reset`."
        )
        return

    files = [path for path in root.rglob("*") if path.is_file()]
    directories = [path for path in root.rglob("*") if path.is_dir()]

    columns = st.columns(3)
    columns[0].metric("Files", f"{len(files):,}")
    columns[1].metric("Folders", f"{len(directories):,}")
    columns[2].metric(
        "Size", f"{sum(path.stat().st_size for path in files) / 1_000_000:.1f} MB"
    )
    st.caption(f"Root `{root}` — everything the agent can see lives under here.")

    view = st.segmented_control(
        "Files view",
        ["Explorer", "Storage map"],
        default="Explorer",
        key="sandbox_view",
        label_visibility="collapsed",
    )
    if view == "Storage map":
        _render_storage_map(root, files)
    else:
        _render_explorer(root, files, directories)


def _render_storage_map(root: Path, files: list[Path]) -> None:
    st.markdown("**Storage map**")
    st.caption(
        "Area represents file size. Hover for details; the dotted blue boundary "
        f"marks `{WORKSPACE_DIR}/`, the writable folder."
    )

    leaves, groups = _storage_map_records(root, files)
    if not leaves:
        st.caption("The sandbox contains no files.")
        return

    layers: list[dict[str, Any]] = [
        {
            "data": {"values": leaves},
            "mark": {
                "type": "rect",
                "stroke": "#111827",
                "strokeWidth": 0.7,
                "cornerRadius": 2,
            },
            "encoding": {
                "x": _map_axis("x"),
                "x2": {"field": "x2"},
                "y": _map_axis("y"),
                "y2": {"field": "y2"},
                "color": {
                    "field": "color",
                    "type": "nominal",
                    "scale": None,
                    "legend": None,
                },
                "opacity": {
                    "condition": {"test": "datum.writable", "value": 0.96},
                    "value": 0.78,
                },
                "tooltip": [
                    {"field": "path", "type": "nominal", "title": "File"},
                    {
                        "field": "size",
                        "type": "quantitative",
                        "title": "Bytes",
                        "format": ",",
                    },
                    {"field": "kind", "type": "nominal", "title": "Type"},
                    {"field": "access", "type": "nominal", "title": "Access"},
                ],
            },
        },
        {
            "data": {"values": [group for group in groups if group["show_label"]]},
            "mark": {
                "type": "text",
                "align": "left",
                "baseline": "top",
                "dx": 6,
                "dy": 6,
                "fontSize": 12,
                "fontWeight": 700,
                "color": "#f8fafc",
            },
            "encoding": {
                "x": _map_axis("x"),
                "y": _map_axis("y"),
                "text": {"field": "label"},
            },
        },
    ]

    workspace = next((group for group in groups if group["writable"]), None)
    if workspace:
        layers.append(
            {
                "data": {"values": [workspace]},
                "mark": {
                    "type": "rect",
                    "fillOpacity": 0,
                    "stroke": "#60a5fa",
                    "strokeWidth": 3,
                    "strokeDash": [5, 4],
                },
                "encoding": {
                    "x": _map_axis("x"),
                    "x2": {"field": "x2"},
                    "y": _map_axis("y"),
                    "y2": {"field": "y2"},
                },
            }
        )

    st.vega_lite_chart(
        spec={
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "height": 390,
            "background": "transparent",
            "config": {"view": {"stroke": None}},
            "layer": layers,
        },
        width="stretch",
        theme=None,
        key="sandbox_storage_map",
    )


def _render_explorer(root: Path, files: list[Path], directories: list[Path]) -> None:
    st.markdown("**File Explorer**")
    tree, contents = st.columns([2, 5], gap="medium")

    all_options = [
        _ROOT_FOLDER,
        *sorted((_relative(path, root) for path in directories), key=str.casefold),
    ]
    all_options = all_options[:_MAX_TREE_ENTRIES]
    if st.session_state.get("sandbox_folder") not in all_options:
        st.session_state.sandbox_folder = _ROOT_FOLDER
    current_relative = str(st.session_state.sandbox_folder)
    options = _visible_tree_options(all_options, current_relative)

    with tree:
        st.caption("FOLDERS")
        for relative in options:
            if st.button(
                _folder_label(relative, root.name),
                key=f"folder_nav_{_widget_fragment(relative)}",
                type="primary" if relative == current_relative else "secondary",
                width="stretch",
            ):
                st.session_state.sandbox_folder = relative
                st.rerun()

    current = root if current_relative == _ROOT_FOLDER else root / current_relative
    entries = sorted(
        current.iterdir(),
        key=lambda path: (not path.is_dir(), path.name.casefold()),
    )

    with contents:
        breadcrumb = "  ›  ".join(
            [
                "This PC",
                root.name,
                *([] if current == root else current.relative_to(root).parts),
            ]
        )
        st.caption(breadcrumb)

        rows = [_explorer_row(path) for path in entries]
        event = st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            height=330,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"sandbox_entries_{_widget_fragment(current_relative)}",
            column_config={
                "Icon": st.column_config.TextColumn("", width="small"),
                "Name": st.column_config.TextColumn("Name", width="large"),
                "Type": st.column_config.TextColumn("Type", width="medium"),
                "Size": st.column_config.TextColumn("Size", width="small"),
                "Modified": st.column_config.TextColumn(
                    "Date modified", width="medium"
                ),
            },
        )
        selected = list(event.selection.rows)
        if not selected:
            st.caption("Select a folder to open it, or a file to preview it.")
            return

        chosen = entries[selected[0]]
        if chosen.is_dir():
            st.session_state.sandbox_folder = _relative(chosen, root)
            st.rerun()

        _render_file_preview(chosen, root)


def _render_file_preview(path: Path, root: Path) -> None:
    stat = path.stat()
    st.markdown(f"**{path.name}**")
    st.caption(
        f"{_relative(path, root)} · {_format_size(stat.st_size)} · "
        f"{datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M}"
    )

    suffix = path.suffix.lower()
    if suffix in _IMAGE_SUFFIXES:
        st.image(str(path))
        return
    if suffix == ".csv":
        try:
            st.dataframe(pd.read_csv(path, nrows=200), width="stretch", hide_index=True)
        except (OSError, pd.errors.ParserError) as error:
            st.error(f"Could not preview this CSV: {error}")
        return
    if suffix == ".json":
        try:
            st.json(json.loads(path.read_text(encoding="utf-8", errors="replace")))
        except (OSError, json.JSONDecodeError) as error:
            st.error(f"Could not preview this JSON file: {error}")
        return
    if suffix in _TEXT_SUFFIXES:
        st.code(_read_preview(path), language=_language_for(suffix))
        return
    st.caption("No inline preview is available for this file type.")


def _storage_map_records(
    root: Path, files: list[Path]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[Path]] = {}
    for path in files:
        relative = path.relative_to(root)
        group = relative.parts[0] if len(relative.parts) > 1 else "(root files)"
        grouped.setdefault(group, []).append(path)

    group_weights = [
        (group, float(sum(max(path.stat().st_size, 1) for path in paths)))
        for group, paths in grouped.items()
    ]
    group_rectangles = _partition_rectangles(
        group_weights, _Rect(0, 0, _MAP_WIDTH, _MAP_HEIGHT)
    )

    leaves: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    ordered_groups = sorted(grouped, key=str.casefold)
    colors = {
        group: (
            _WORKSPACE_COLOR
            if group == WORKSPACE_DIR
            else _FOLDER_COLORS[index % len(_FOLDER_COLORS)]
        )
        for index, group in enumerate(ordered_groups)
    }

    for group, rectangle in group_rectangles.items():
        writable = group == WORKSPACE_DIR
        groups.append(
            {
                "label": f"{group}/" if group != "(root files)" else group,
                "x": rectangle.x,
                "x2": rectangle.x2,
                "y": rectangle.y,
                "y2": rectangle.y2,
                "show_label": rectangle.width >= 9 and rectangle.height >= 5,
                "writable": writable,
            }
        )

        inner = _inset(rectangle, _MAP_GAP)
        paths = grouped[group]
        file_rectangles = _partition_rectangles(
            [
                (_relative(path, root), float(max(path.stat().st_size, 1)))
                for path in paths
            ],
            inner,
        )
        by_relative = {_relative(path, root): path for path in paths}
        for relative, file_rectangle in file_rectangles.items():
            path = by_relative[relative]
            size = path.stat().st_size
            leaves.append(
                {
                    "path": relative,
                    "size": size,
                    "kind": path.suffix.removeprefix(".").upper() or "File",
                    "access": "Writable" if writable else "Read only",
                    "writable": writable,
                    "color": colors[group],
                    "x": file_rectangle.x,
                    "x2": file_rectangle.x2,
                    "y": file_rectangle.y,
                    "y2": file_rectangle.y2,
                }
            )

    return leaves, groups


def _partition_rectangles(
    weighted_items: list[tuple[str, float]], rectangle: _Rect
) -> dict[str, _Rect]:
    """Recursively split a rectangle while preserving proportional area."""
    items = sorted(
        ((name, max(weight, 1.0)) for name, weight in weighted_items),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    if not items:
        return {}
    if len(items) == 1:
        return {items[0][0]: rectangle}

    total = sum(weight for _, weight in items)
    running = 0.0
    split_at = 1
    best_distance = float("inf")
    for index in range(1, len(items)):
        running += items[index - 1][1]
        distance = abs(total / 2 - running)
        if distance < best_distance:
            best_distance = distance
            split_at = index

    first = items[:split_at]
    second = items[split_at:]
    first_weight = sum(weight for _, weight in first)
    ratio = first_weight / total

    if rectangle.width >= rectangle.height:
        first_rectangle = _Rect(
            rectangle.x, rectangle.y, rectangle.width * ratio, rectangle.height
        )
        second_rectangle = _Rect(
            first_rectangle.x2,
            rectangle.y,
            rectangle.width - first_rectangle.width,
            rectangle.height,
        )
    else:
        first_rectangle = _Rect(
            rectangle.x, rectangle.y, rectangle.width, rectangle.height * ratio
        )
        second_rectangle = _Rect(
            rectangle.x,
            first_rectangle.y2,
            rectangle.width,
            rectangle.height - first_rectangle.height,
        )

    return {
        **_partition_rectangles(first, first_rectangle),
        **_partition_rectangles(second, second_rectangle),
    }


def _inset(rectangle: _Rect, amount: float) -> _Rect:
    horizontal = min(amount, rectangle.width / 4)
    vertical = min(amount, rectangle.height / 4)
    return _Rect(
        rectangle.x + horizontal,
        rectangle.y + vertical,
        max(rectangle.width - 2 * horizontal, 0.01),
        max(rectangle.height - 2 * vertical, 0.01),
    )


def _map_axis(field: str) -> dict[str, Any]:
    domain = [0, _MAP_WIDTH] if field == "x" else [0, _MAP_HEIGHT]
    return {
        "field": field,
        "type": "quantitative",
        "axis": None,
        "scale": {"domain": domain, "nice": False, "zero": False},
    }


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _folder_label(relative: str, root_name: str) -> str:
    if relative == _ROOT_FOLDER:
        return f"💻 {root_name}"
    parts = relative.split("/")
    branch = "    " * (len(parts) - 1) + "└─"
    marker = "✏️" if parts[0] == WORKSPACE_DIR else "📁"
    return f"{branch} {marker} {parts[-1]}"


def _visible_tree_options(options: list[str], current: str) -> list[str]:
    """Show top-level folders and only the expanded path's descendants."""
    ancestors = {_ROOT_FOLDER}
    if current != _ROOT_FOLDER:
        parts = current.split("/")
        ancestors.update("/".join(parts[:index]) for index in range(1, len(parts) + 1))

    visible: list[str] = []
    for option in options:
        if option == _ROOT_FOLDER:
            visible.append(option)
            continue
        parent = option.rpartition("/")[0] or _ROOT_FOLDER
        if parent in ancestors:
            visible.append(option)
    return visible


def _explorer_row(path: Path) -> dict[str, str]:
    stat = path.stat()
    is_directory = path.is_dir()
    return {
        "Icon": "📁" if is_directory else _file_icon(path.suffix.lower()),
        "Name": path.name,
        "Type": "File folder" if is_directory else _file_type(path),
        "Size": "" if is_directory else _format_size(stat.st_size),
        "Modified": f"{datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M}",
    }


def _file_icon(suffix: str) -> str:
    if suffix in _IMAGE_SUFFIXES:
        return "🖼️"
    if suffix == ".csv":
        return "📊"
    if suffix in {".xlsx", ".xls"}:
        return "📗"
    if suffix in {".md", ".txt", ".log"}:
        return "📄"
    if suffix in {".py", ".json", ".yaml", ".yml"}:
        return "🧩"
    if suffix == ".pdf":
        return "📕"
    return "📄"


def _file_type(path: Path) -> str:
    return {
        ".csv": "CSV file",
        ".xlsx": "Excel workbook",
        ".xls": "Excel workbook",
        ".png": "PNG image",
        ".jpg": "JPEG image",
        ".jpeg": "JPEG image",
        ".md": "Markdown document",
        ".py": "Python file",
        ".json": "JSON file",
        ".pdf": "PDF document",
    }.get(path.suffix.lower(), f"{path.suffix.removeprefix('.').upper()} file")


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{value:,.0f} {unit}" if unit == "bytes" else f"{value:,.1f} {unit}"
        value /= 1000
    return f"{size:,} bytes"


def _widget_fragment(value: str) -> str:
    return (
        "root" if value == _ROOT_FOLDER else value.replace("/", "_").replace(" ", "_")
    )


def _read_preview(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"Could not read this file: {error}"

    if len(text) <= _MAX_PREVIEW_CHARS:
        return text
    return f"{text[:_MAX_PREVIEW_CHARS]}\n... [truncated]"


def _language_for(suffix: str) -> str:
    return {
        ".py": "python",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def _is_within(path: Path, directory: Path) -> bool:
    return directory in path.parents


def _sandbox_or_none() -> Path | None:
    """The sandbox root, or None when it has not been seeded."""
    try:
        return sandbox_root()
    except RuntimeError:
        return None
