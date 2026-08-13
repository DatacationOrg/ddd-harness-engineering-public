"""Where the agent is allowed to act.

The sandbox is a generated fictional company drive (see
`scripts/seed_sandbox.py`). Pointing the agent's backend at it is what turns
"please don't touch anything important" from a hope into a boundary: the agent
cannot name a path outside its root, so `~/.ssh` and `.env` are not merely
discouraged, they are unreachable.
"""

from pathlib import Path

from ddd_harness_engineering import PROJECT_ROOT

SANDBOX_ROOT = PROJECT_ROOT / "sandbox" / "northwind-freight"
"""Root of the agent's filesystem. Everything it can see lives under here."""

WORKSPACE_DIR = "workspace"
"""The only directory the agent may write to. Everything else is read-only."""


def sandbox_root() -> Path:
    """Return the sandbox root, failing loudly if it has not been generated.

    A missing sandbox is the most likely first-run error, so say what to do
    about it rather than letting the backend raise something cryptic later.
    """
    if not SANDBOX_ROOT.is_dir():
        raise RuntimeError(
            f"The sandbox does not exist at {SANDBOX_ROOT}. "
            "Generate it with: uv run python scripts/seed_sandbox.py --reset"
        )
    return SANDBOX_ROOT
