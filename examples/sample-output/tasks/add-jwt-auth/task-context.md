# Task Context

## Goal

add JWT auth

## Detected Intents

- auth

## Context Budget

- Primary file limit: 5
- Secondary file limit: 8
- Context file limit: 10
- This context pack intentionally limits primary files to 5 to reduce context usage for AI coding agents.

## Primary Files To Inspect First

- `app/auth.py` (source, 0.82): Matched task keywords 'auth, jwt'. Task intent includes auth. Located in source directory 'app/'.

## Secondary Files

- `tests/test_auth.py` (test, 0.44): Matched task keywords 'auth'. Task intent includes auth. Role test; inspect after primary files.

## Context Files

- None

## Files To Avoid Unless Explicitly Needed

- `app/migrations/001_add_auth_table.py` (migration, 0.00): Migration penalized because task has no database intent.

## Suggested Implementation Approach

1. Read `.ai-context/agent-context.md`.
2. Inspect primary files first.
3. Inspect secondary files only if needed.
4. Keep the first implementation pass focused on primary files.
5. Avoid migrations unless the task requires schema changes.
6. Avoid Dockerfile unless the task requires dependency or container changes.
7. Make the smallest change that satisfies the task.
8. Add or update tests for changed behavior.

## Validation Checklist

- [ ] Run the relevant test suite.
- [ ] Run the project formatter or linter if available.
- [ ] Verify the changed workflow manually when practical.
- [ ] Confirm unrelated files were not modified.
- [ ] Update documentation if public behavior changed.
