# M1 Assignment README

## Goal

Implement module 1 from red to green:

1. System prompt
2. Project context tool
3. Optional skill extension

Branch naming for progression:

1. m1
2. m2
3. m3

## Red Starter State

M1 should start as not implemented in both places:

1. Module status should indicate M1 not completed.
2. Code should contain explicit scaffold comments/TODO blocks where implementation is expected.

Code placement for M1:

1. ddd_harness_engineering/agent.py
2. _SYSTEM_PROMPT
3. get_current_project_context

## Files To Edit (Exact)

1. ddd_harness_engineering/agent.py
- Update `_SYSTEM_PROMPT` content.
- Update `get_current_project_context()` implementation.
- Keep the `MODULE M1 STARTER PLACEHOLDER` comments so participants can find this section quickly.

## Files To Add (Optional)

1. agent_home/skills/file-triage/SKILL.md
- Optional bonus only for M1.
- If extended, keep M1 completion independent from skill completion.

## Step By Step (Red -> Green)

1. Replace placeholder prompt with a useful, sectioned system prompt.
2. Implement get_current_project_context with meaningful project context.
3. Keep optional skill work as bonus only.
4. Run checks and verify module status updates.

## Suggested Verification

1. uv run pytest tests/test_prompt.py -q
2. uv run pytest tests/test_skills.py -q

## Notes

1. Keep the prompt practical for participant use case.
2. Keep context concise and useful for planning.
3. Do not remove scaffold comments; they are teaching signposts.
