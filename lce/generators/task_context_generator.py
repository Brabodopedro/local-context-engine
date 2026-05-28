from __future__ import annotations

from pathlib import Path

from lce.models.context_models import FileIndex, TaskContext, TaskRelevantFile
from lce.utils.file_utils import slugify

TASK_KEYWORDS = {
    ("auth", "login", "jwt", "token"): [
        "auth",
        "user",
        "login",
        "token",
        "jwt",
        "session",
        "middleware",
        "security",
    ],
    ("docker",): ["Dockerfile", "docker-compose", "compose", "nginx", "env", "deployment"],
    ("upload",): ["upload", "file", "storage", "s3", "minio", "media"],
    ("render",): ["render", "worker", "ffmpeg", "video", "output"],
}

DEFAULT_VALIDATION_CHECKLIST = [
    "Run the relevant test suite.",
    "Run the project formatter or linter if available.",
    "Verify the changed workflow manually when practical.",
    "Confirm unrelated files were not modified.",
    "Update documentation if public behavior changed.",
]


def keywords_for_task(task: str) -> list[str]:
    lowered = task.lower()
    keywords: list[str] = []
    for triggers, matches in TASK_KEYWORDS.items():
        if any(trigger in lowered for trigger in triggers):
            keywords.extend(matches)
    if not keywords:
        keywords.extend(part for part in lowered.replace("-", " ").split() if len(part) >= 4)
    return sorted(set(keywords), key=str.lower)


def score_file(path: str, tags: list[str], keywords: list[str]) -> tuple[int, list[str]]:
    haystack = f"{path} {' '.join(tags)}".lower()
    matched = [keyword for keyword in keywords if keyword.lower() in haystack]
    return len(matched), matched


def find_relevant_files(
    file_index: FileIndex,
    task: str,
    limit: int = 12,
) -> list[TaskRelevantFile]:
    keywords = keywords_for_task(task)
    scored: list[tuple[int, str, TaskRelevantFile]] = []
    for file in file_index.files:
        score, matched = score_file(file.path, file.tags, keywords)
        if score == 0:
            continue
        confidence = min(0.95, 0.45 + score * 0.15)
        reason = f"Matched task keywords: {', '.join(matched)}"
        scored.append(
            (
                score,
                file.path,
                TaskRelevantFile(path=file.path, reason=reason, confidence=confidence),
            )
        )
    return [item for _, _, item in sorted(scored, key=lambda row: (-row[0], row[1]))[:limit]]


def files_to_avoid() -> list[str]:
    return [
        ".env* files unless explicitly requested",
        "database migrations unless explicitly requested",
        "generated build artifacts",
        "vendored dependencies",
    ]


def generate_task_context(file_index: FileIndex, task: str) -> TaskContext:
    slug = slugify(task)
    generated_files = [
        f".ai-context/tasks/{slug}/task-context.md",
        f".ai-context/tasks/{slug}/relevant-files.json",
        f".ai-context/tasks/{slug}/risk-map.md",
        f".ai-context/tasks/{slug}/validation-checklist.md",
        f".ai-context/tasks/{slug}/agent-prompt.md",
    ]
    return TaskContext(
        task=task,
        slug=slug,
        relevant_files=find_relevant_files(file_index, task),
        generated_files=generated_files,
        validation_checklist=DEFAULT_VALIDATION_CHECKLIST,
    )


def render_task_context(context: TaskContext) -> str:
    lines = [
        "# Task Context",
        "",
        "## Task Goal",
        "",
        context.task,
        "",
        "## Probable Relevant Files",
        "",
    ]
    if context.relevant_files:
        lines.extend(
            f"- `{file.path}` ({file.confidence:.2f}): {file.reason}"
            for file in context.relevant_files
        )
    else:
        lines.append("- No deterministic matches found. Start from `file-index.json`.")
    lines.extend(
        [
            "",
            "## Suggested Implementation Approach",
            "",
            "1. Read `.ai-context/agent-context.md`.",
            "2. Inspect the probable relevant files before broadening the search.",
            "3. Make the smallest change that satisfies the task.",
            "4. Add or update tests for changed behavior.",
            "5. Document public behavior changes.",
            "",
            "## Files To Avoid Unless Necessary",
            "",
            *[f"- {item}" for item in files_to_avoid()],
            "",
            "## Validation Checklist",
            "",
            *[f"- [ ] {item}" for item in context.validation_checklist],
            "",
            "## Final Prompt For An AI Coding Agent",
            "",
            render_agent_prompt(context, "generic"),
            "",
        ]
    )
    return "\n".join(lines)


def render_risk_map(context: TaskContext) -> str:
    lines = [
        "# Risk Map",
        "",
        "- Keep changes scoped to files related to the task.",
        "- Avoid environment files and migrations unless the user explicitly requests them.",
        "- Prefer adding tests near changed code.",
        "",
        "## Relevant File Risks",
        "",
    ]
    if context.relevant_files:
        lines.extend(
            f"- `{file.path}`: verify behavior covered by this area."
            for file in context.relevant_files
        )
    else:
        lines.append("- No relevant files were selected deterministically.")
    return "\n".join(lines) + "\n"


def render_validation_checklist(context: TaskContext) -> str:
    return "# Validation Checklist\n\n" + "\n".join(
        f"- [ ] {item}" for item in context.validation_checklist
    ) + "\n"


def render_agent_prompt(context: TaskContext, target: str) -> str:
    relevant = (
        "\n".join(f"- `{file.path}`" for file in context.relevant_files)
        or "- No files preselected"
    )
    target_note = {
        "cline": "Use Cline's planning and file editing tools carefully.",
        "codex": "Use Codex to inspect, edit, and validate the local repository.",
        "copilot": "Use Copilot chat with the listed files as the starting context.",
        "cursor": "Use Cursor with the listed files attached or opened first.",
        "claude": "Use Claude Code with the listed files as initial context.",
        "generic": "Use your coding-agent tools with a narrow initial context.",
    }.get(target, "Use your coding-agent tools with a narrow initial context.")
    return (
        f"You are working on this task: {context.task}\n\n"
        "Before changing code:\n"
        "1. Read `.ai-context/agent-context.md`.\n"
        f"2. Read `.ai-context/tasks/{context.slug}/task-context.md`.\n"
        "3. Inspect only the relevant files first:\n"
        f"{relevant}\n\n"
        "Implementation rules:\n"
        "- Avoid unrelated changes and broad refactors.\n"
        "- Do not modify environment files or migrations unless explicitly requested.\n"
        "- Update tests when behavior changes.\n"
        "- Explain changed files after implementation.\n"
        "- Provide validation steps and any commands run.\n\n"
        f"Target guidance: {target_note}"
    )


def latest_task_dir(output_path: Path) -> Path | None:
    tasks_path = output_path / "tasks"
    if not tasks_path.exists():
        return None
    task_dirs = [path for path in tasks_path.iterdir() if path.is_dir()]
    if not task_dirs:
        return None
    return max(task_dirs, key=lambda path: path.stat().st_mtime)
