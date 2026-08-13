# M2 Assignment README

## Goal

Implement module 2 from red to green:

1. Filesystem duplicate analysis
2. File move/copy/delete tools
3. Web search tool integration

M2 builds on M1.

## Red Starter State

M2 should start as not implemented in both places:

1. Harness UI should indicate Harness S2 not completed.
2. Tool code should have explicit scaffold comments/TODO blocks for missing logic.

Code placement for M2:

1. ddd_harness_engineering/tools/filesystem.py
2. ddd_harness_engineering/tools/file_ops.py
3. ddd_harness_engineering/tools/web.py
4. ddd_harness_engineering/agent.py (tool wiring)

## Files To Edit (Exact)

1. ddd_harness_engineering/tools/filesystem.py
- Implement `find_duplicate_files(...)` behavior.

2. ddd_harness_engineering/tools/file_ops.py
- Implement `move_file(...)` behavior.
- Implement `copy_file(...)` behavior.
- Implement `delete_file(...)` behavior.

3. ddd_harness_engineering/tools/web.py
- Implement `web_search(...)` behavior.

4. ddd_harness_engineering/agent.py
- Ensure module tools are wired in `main_tools()`.

5. ddd_harness_engineering/sandbox.py
- Do not replace boundary logic; only adjust if starter branch intentionally stubbed it.

## Files To Add (Usually None)

1. No new files are required for core M2 completion.
- Keep implementation inside existing tool modules unless your facilitator asks for extension work.

## Step By Step (Red -> Green)

1. Implement duplicate detection behavior.
2. Implement safe move/copy/delete behavior with sandbox boundaries.
3. Implement web search behavior and defensive framing.
4. Wire tools in the intended registration points.
5. Run checks and verify harness status updates.

## Suggested Verification

1. uv run pytest tests/test_duplicate_files.py tests/test_file_ops.py tests/test_web_search.py -q
2. uv run pytest tests/test_sandbox_boundary.py tests/test_guardrails.py -q

## Notes

1. Keep signatures and wiring visible in starter code.
2. Prefer explicit TODO scaffold comments over hidden omissions.
3. Keep boundary checks strict.
