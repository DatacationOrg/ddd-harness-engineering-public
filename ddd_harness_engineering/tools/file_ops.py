"""Sandbox-safe move/copy/delete tools used in module M2."""

# MODULE M2 STARTER PLACEHOLDER:
# Keep move/copy/delete scaffold visible in starter branches. Participants fill
# these insertion points while preserving sandbox boundary checks.

from pathlib import Path

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
    # MODULE M2 STARTER PLACEHOLDER:
    # TODO: Implement sandbox-safe move behavior for module M2.
    return (
        "TODO: Implement move_file for module M2. "
        "Validate source and destination inside the sandbox, "
        "reject overwrites, and return clear user-facing messages."
    )


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
    # MODULE M2 STARTER PLACEHOLDER:
    # TODO: Implement sandbox-safe copy behavior for module M2.
    return (
        "TODO: Implement copy_file for module M2. "
        "Validate sandbox boundaries, disallow folder copies, "
        "and return clear user-facing messages."
    )


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
    # MODULE M2 STARTER PLACEHOLDER:
    # TODO: Implement sandbox-safe delete behavior for module M2.
    return (
        "TODO: Implement delete_file for module M2. "
        "Allow deleting one file inside the sandbox, reject folders, "
        "and return clear user-facing messages."
    )
