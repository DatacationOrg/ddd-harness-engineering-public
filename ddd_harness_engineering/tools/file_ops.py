"""Sandbox-safe move/copy/delete tools used in module S2."""

# MODULE S2 STARTER PLACEHOLDER:
# Keep move/copy/delete scaffold visible in starter branches. Participants fill
# these insertion points while preserving sandbox boundary checks.

from pathlib import Path
import shutil

from ddd_harness_engineering.sandbox import sandbox_root


def _resolve(path: str) -> Path:
    """Resolve an agent-supplied path against the sandbox root.

    Accepts `/foo` and `foo` style paths and rejects anything outside root.
    """
    root = sandbox_root().resolve()
    cleaned = str(path).strip().replace("\\", "/").lstrip("/")
    if not cleaned:
        raise ValueError("The path is empty.")

    # resolve() normalizes traversal and symlinks before containment checks.
    resolved = (root / cleaned).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(
            f"Refusing to touch {path!r}: it is outside the sandbox. "
            "Use a path relative to the sandbox root."
        )
    return resolved


def _display(path: Path) -> str:
    """Render a resolved path back in the namespace the agent speaks."""
    return "/" + path.relative_to(sandbox_root().resolve()).as_posix()


def _prepare(source: str, destination: str, verb: str) -> tuple[Path, Path] | str:
    """Validate both ends of a move or copy, or explain what is wrong."""
    try:
        source_path = _resolve(source)
        destination_path = _resolve(destination)
    except ValueError as error:
        return str(error)

    if not source_path.exists():
        return (
            f"Nothing to {verb}: {source!r} does not exist. "
            "Use ls or glob to check the name, then try again."
        )
    if destination_path.exists():
        return (
            f"Refusing to {verb}: {_display(destination_path)} already exists. "
            "Nothing was changed. Pick another name, or delete that file first."
        )
    return source_path, destination_path


def move_file(source: str, destination: str) -> str:
    """Move or rename a file or folder inside the sandbox.

    Use this to tidy up: put a file into a different folder, give it a clearer
    name, or both at once. A rename is simply a move whose destination sits in
    the same folder. Prefer this over writing a script -- it is one step, it is
    shown to the user for approval with both paths visible, and it cannot
    silently clobber anything.

    Missing parent folders of the destination are created for you.

    Args:
        source: The file or folder to move, for example `/Downloads/scan.pdf`.
        destination: Where it should end up, for example
            `/Clients/Bergmann_Logistik/2026-02-19_contract.pdf`.

    Returns:
        A sentence confirming the move, or explaining why nothing was moved.
    """
    # MODULE S2 STARTER PLACEHOLDER:
    # Starter branches can temporarily replace core logic with TODO scaffolds.
    prepared = _prepare(source, destination, "move")
    if isinstance(prepared, str):
        return prepared
    source_path, destination_path = prepared

    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
    except OSError as error:
        return f"Could not move {source!r}: {error}"

    return f"Moved {_display(source_path)} to {_display(destination_path)}."


def copy_file(source: str, destination: str) -> str:
    """Copy a file inside the sandbox, leaving the original where it is.

    Use this when both copies should exist afterwards. If you actually want the
    file to end up somewhere else, use `move_file` instead -- copying and then
    deleting leaves a window where the drive holds two copies, and one more
    thing that can go wrong.

    Missing parent folders of the destination are created for you.

    Args:
        source: The file to copy, for example `/data/shipments.csv`.
        destination: Where the copy should go, for example
            `/data/exports/shipments_backup.csv`.

    Returns:
        A sentence confirming the copy, or explaining why nothing was copied.
    """
    # MODULE S2 STARTER PLACEHOLDER:
    # Starter branches can temporarily replace core logic with TODO scaffolds.
    prepared = _prepare(source, destination, "copy")
    if isinstance(prepared, str):
        return prepared
    source_path, destination_path = prepared

    if source_path.is_dir():
        return (
            f"Refusing to copy {_display(source_path)}: it is a folder. "
            "Copy the files inside it individually."
        )

    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source_path), str(destination_path))
    except OSError as error:
        return f"Could not copy {source!r}: {error}"

    return f"Copied {_display(source_path)} to {_display(destination_path)}."


def delete_file(path: str) -> str:
    """Permanently delete one file from the sandbox.

    There is no undo and no recycle bin. Before deleting what looks like a
    redundant copy, confirm it really is one -- `find_duplicate_files` compares
    contents, whereas similar names prove nothing.

    Deletes a single file only. To clear out a folder, delete its files one at
    a time, so that each one is approved on its own merits.

    Args:
        path: The file to delete, for example `/Downloads/invoice_final_v2.pdf`.

    Returns:
        A sentence confirming the deletion, or explaining why nothing was
        deleted.
    """
    # MODULE S2 STARTER PLACEHOLDER:
    # Starter branches can temporarily replace core logic with TODO scaffolds.
    try:
        target = _resolve(path)
    except ValueError as error:
        return str(error)

    if not target.exists():
        return f"Nothing to delete: {path!r} does not exist."
    if target.is_dir():
        return (
            f"Refusing to delete {_display(target)}: it is a folder, and this "
            "tool deletes one file at a time. Delete the files inside it individually."
        )

    display = _display(target)
    try:
        target.unlink()
    except OSError as error:
        return f"Could not delete {path!r}: {error}"

    return f"Deleted {display}. This cannot be undone."
