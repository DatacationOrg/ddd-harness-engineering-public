"""Filesystem analysis tools.

`find_duplicate_files` is the worked example for station S2: a tool that does
something the model genuinely cannot do for itself. The model can read files;
it cannot hash four hundred of them.
"""

# MODULE S2 STARTER PLACEHOLDER:
# Keep duplicate detection scaffold visible in starter branches so participants
# know exactly where to implement and test module 2 behavior.

from dataclasses import dataclass, field
import hashlib
from pathlib import Path

from ddd_harness_engineering.sandbox import sandbox_root

_CHUNK_BYTES = 1 << 20
_MAX_REPORTED_GROUPS = 20


@dataclass(frozen=True)
class DuplicateGroup:
    """A set of files with byte-identical contents."""

    digest: str
    size_bytes: int
    paths: list[str] = field(default_factory=list)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicate_groups(root: Path) -> list[DuplicateGroup]:
    """Group files under `root` by identical content.

    Sizes are compared first and only same-size candidates are hashed, so the
    expensive work is done on the few files that could possibly match. Files
    that cannot be read are skipped rather than aborting the scan.
    """
    by_size: dict[int, list[Path]] = {}
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        try:
            by_size.setdefault(candidate.stat().st_size, []).append(candidate)
        except OSError:
            continue

    groups: list[DuplicateGroup] = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            # A unique size cannot have a duplicate; never hash it.
            continue

        by_digest: dict[str, list[Path]] = {}
        for candidate in candidates:
            try:
                by_digest.setdefault(_file_digest(candidate), []).append(candidate)
            except OSError:
                continue

        for digest, matches in by_digest.items():
            if len(matches) > 1:
                groups.append(
                    DuplicateGroup(
                        digest=digest,
                        size_bytes=size,
                        paths=sorted(
                            match.relative_to(root).as_posix() for match in matches
                        ),
                    )
                )

    groups.sort(key=lambda group: (-group.size_bytes, group.paths[0]))
    return groups


def find_duplicate_files(subdirectory: str = "") -> str:
    """Find files whose contents are byte-for-byte identical.

    Use this before reorganising, archiving or deleting anything, to find which
    files are genuinely redundant copies. Compares contents, so it is not fooled
    by files that were renamed, and does not report files that merely have
    similar names.

    Args:
        subdirectory: Optional folder to limit the scan to, relative to the
            sandbox root. Leave empty to scan everything.

    Returns:
        A summary listing each set of identical files, or a message saying none
        were found.
    """
    # MODULE S2 STARTER PLACEHOLDER:
    # Starter branches can replace this implementation body with
    # TODO/NotImplemented scaffolding for participants to complete.
    try:
        root = sandbox_root()
    except RuntimeError as error:
        return str(error)

    target = (root / subdirectory).resolve() if subdirectory else root
    if not str(target).startswith(str(root.resolve())):
        return (
            f"Refusing to scan {subdirectory!r}: it is outside the sandbox. "
            "Pass a path relative to the sandbox root."
        )
    if not target.is_dir():
        return (
            f"No such directory: {subdirectory!r}. "
            "Use ls to see what exists, then try again."
        )

    groups = find_duplicate_groups(target)
    if not groups:
        return f"No duplicate files found under {subdirectory or '.'}."

    wasted = sum(group.size_bytes * (len(group.paths) - 1) for group in groups)
    lines = [
        f"Found {len(groups)} group(s) of identical files "
        f"under {subdirectory or '.'}, wasting {wasted:,} bytes.",
    ]
    for index, group in enumerate(groups[:_MAX_REPORTED_GROUPS], start=1):
        lines.append(
            f"\n{index}. {len(group.paths)} copies, {group.size_bytes:,} bytes each "
            f"(sha256 {group.digest[:12]}):"
        )
        lines.extend(f"   - {path}" for path in group.paths)

    if len(groups) > _MAX_REPORTED_GROUPS:
        lines.append(
            f"\n...and {len(groups) - _MAX_REPORTED_GROUPS} more group(s) not shown."
        )
    return "\n".join(lines)
