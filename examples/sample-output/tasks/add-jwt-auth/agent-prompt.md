You are working on this task: add JWT auth

Before changing code:
1. Read `.ai-context/agent-context.md`.
2. Read `.ai-context/tasks/add-jwt-auth/task-context.md`.
3. Primary files are intentionally limited to reduce context.
4. Inspect primary files first and do not open all secondary/context files upfront:
- `app/auth.py` (source)
5. Inspect secondary files only if needed, when primary files are insufficient:
- `tests/test_auth.py` (test)

Implementation rules:
- For local LLMs, keep the first implementation pass focused on primary_files.
- Do not modify avoid files unless explicitly required:
- `app/migrations/001_add_auth_table.py` (migration)
- Do not modify migrations unless the task requires schema changes.
- Do not modify Dockerfile unless the task requires dependency/container changes.
- Explain before editing files outside primary_files.
- Avoid unrelated changes and broad refactors.
- Update tests when behavior changes.
- Provide validation steps and any commands run.

Target guidance: Use your coding-agent tools with a narrow initial context.
