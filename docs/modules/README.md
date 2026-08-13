# Module Progression Guide (m1 -> m2 -> m3)

This workshop runs as a cumulative assignment path:

0. `s0` = starter (M1 unsolved)
1. `m1` = module 1 complete
2. `m2` = module 2 complete (built on `m1`)
3. `m3` = module 3 complete (built on `m2`)

Each module starts in a red state where the module is not implemented and the code contains explicit scaffold placeholders (TODO/commented scaffold/NotImplementedError) at the exact implementation points.

## Module READMEs

1. [M1 assignment](m1/README.md)
2. [M2 assignment](m2/README.md)
3. [M3 assignment](m3/README.md)

## Quick File Map

1. M1 edits: `ddd_harness_engineering/agent.py`
2. M2 edits: `ddd_harness_engineering/tools/filesystem.py`, `ddd_harness_engineering/tools/file_ops.py`, `ddd_harness_engineering/tools/web.py`, `ddd_harness_engineering/agent.py`
3. M3 edits: `ddd_harness_engineering/agent.py`, `ddd_harness_engineering/ui_chat.py`, `ddd_harness_engineering/main.py`, `ddd_harness_engineering/ui_trace.py`

## Implementation Rule

Keep each starter state visible in both places:

1. UI shows not implemented.
2. Code clearly marks where participants continue.
