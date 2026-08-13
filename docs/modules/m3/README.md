# M3 Assignment README

## Goal

Implement module 3 from red to green:

1. Human approval gate for mutating actions
2. Approve/edit/reject decisions
3. Resume flow and approval trace visibility

M3 builds on M2.

## Red Starter State

M3 should start as not implemented in both places:

1. Module status should indicate M3 not completed.
2. Approval flow code should include explicit scaffold comments/TODO blocks.

Code placement for M3:

1. ddd_harness_engineering/agent.py (interrupt_on + decision helpers)
2. ddd_harness_engineering/ui_chat.py (approval dialog)
3. ddd_harness_engineering/main.py (pause/resume orchestration)
4. ddd_harness_engineering/ui_trace.py (approval event visibility)

## Files To Edit (Exact)

1. ddd_harness_engineering/agent.py
- Approval gate map: `_INTERRUPT_ON`.
- Decision helpers: `approval_resume(...)`, `approve(...)`, `edit(...)`, `reject(...)`.

2. ddd_harness_engineering/ui_chat.py
- Approval dialog flow: `approval_dialog(...)`.

3. ddd_harness_engineering/main.py
- Pause/resume integration in `_continue_turn(...)` and `main()` decision branch.

4. ddd_harness_engineering/ui_trace.py
- Ensure approval category events remain visible in Activity rendering.

## Files To Add (Usually None)

1. No new files are required for core M3 completion.
- Focus on wiring and flow completion in existing files.

## Step By Step (Red -> Green)

1. Add gating for mutating tool calls.
2. Implement approve/edit/reject decision generation.
3. Implement resume flow after decisions.
4. Ensure approval decisions are shown in Activity trace.
5. Run checks and verify module status updates.

## Suggested Verification

1. uv run pytest tests/test_approvals.py tests/test_agent.py -q
2. uv run pytest tests/test_execution_events.py -q

## Notes

1. Keep normal chat working while approvals are stubbed.
2. Keep scaffold comments visible so participants know exactly where to continue.
3. Preserve trace legibility.
