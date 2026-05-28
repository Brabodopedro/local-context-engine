from __future__ import annotations

from pathlib import Path

from lce.models.context_models import FileIndex, FileInfo, TaskContext, TaskRelevantFile
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

SOURCE_DIRS = ("lce", "src", "app", "backend", "frontend", "server", "api")
MEDIUM_DIRS = ("tests", "test", "config")
LOW_PRIORITY_DIRS = ("docs", "examples")
VERY_LOW_PRIORITY_PREFIXES = ("examples/sample-output", ".ai-context")
GENERATED_NAMES = {
    "agent-context.md",
    "task-context.md",
    "agent-prompt.md",
    "relevant-files.json",
    "risk-map.md",
    "validation-checklist.md",
    "repo-map.json",
    "file-index.json",
    "metadata.json",
}
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".php", ".go", ".java", ".cs"}
CONFIG_EXTENSIONS = {".json", ".yml", ".yaml", ".toml"}
CONFIG_FILENAMES = {"pyproject.toml", "package.json", "docker-compose.yml", "docker-compose.yaml"}
MIN_RELEVANCE_SCORE = 0.20


def keywords_for_task(task: str) -> list[str]:
    lowered = task.lower()
    keywords: list[str] = []
    for triggers, matches in TASK_KEYWORDS.items():
        if any(trigger in lowered for trigger in triggers):
            keywords.extend(matches)
    if not keywords:
        keywords.extend(part for part in lowered.replace("-", " ").split() if len(part) >= 4)
    return sorted(set(keywords), key=str.lower)


def normalize_index_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        return normalized[2:]
    return normalized


def is_generated_context_path(path: str) -> bool:
    normalized = normalize_index_path(path)
    parts = normalized.split("/")
    return (
        normalized.startswith(VERY_LOW_PRIORITY_PREFIXES)
        or any(part == ".ai-context" for part in parts)
        or Path(normalized).name in GENERATED_NAMES
    )


def calculate_relevance_score(
    file_info: FileInfo,
    task_description: str,
) -> tuple[float, list[str]]:
    path = file_info.path
    tags = list(file_info.tags)
    summary = file_info.summary
    normalized_path = normalize_index_path(path)
    path_obj = Path(normalized_path)
    filename = path_obj.name
    suffix = path_obj.suffix.lower()
    parts = normalized_path.split("/")
    top_dir = parts[0] if parts else ""
    keywords = keywords_for_task(task_description)
    score = 0.0
    reasons: list[str] = []
    matched_keywords: set[str] = set()

    if normalized_path.startswith(".ai-context") or ".ai-context" in parts:
        return 0.0, ["Excluded generated `.ai-context/` output."]

    lower_path = normalized_path.lower()
    lower_filename = filename.lower()
    lower_tags = " ".join(tags).lower()
    lower_summary = summary.lower()

    for keyword in keywords:
        lowered = keyword.lower()
        if lowered in lower_path:
            score += 0.24
            matched_keywords.add(keyword)
            reasons.append(f"Matched task keyword '{keyword}' in path.")
        if lowered in lower_filename:
            score += 0.18
            matched_keywords.add(keyword)
            reasons.append(f"Matched task keyword '{keyword}' in filename.")
        if lowered in lower_tags:
            score += 0.14
            matched_keywords.add(keyword)
            reasons.append(f"Matched task keyword '{keyword}' in tags.")
        if lowered in lower_summary:
            score += 0.08
            matched_keywords.add(keyword)
            reasons.append(f"Matched task keyword '{keyword}' in summary.")

    if not matched_keywords:
        return 0.0, ["No task keyword match."]

    if top_dir in SOURCE_DIRS:
        score += 0.28
        reasons.append(f"Located in source directory '{top_dir}/'.")
    elif top_dir in MEDIUM_DIRS or filename in CONFIG_FILENAMES:
        score += 0.12
        reasons.append("Located in tests or configuration area.")
    elif top_dir in LOW_PRIORITY_DIRS or filename.lower() == "readme.md":
        score -= 0.16
        reasons.append("Located in low-priority documentation or examples area.")

    if suffix in SOURCE_EXTENSIONS:
        score += 0.22
        reasons.append(f"Source file extension '{suffix}'.")
    elif suffix in CONFIG_EXTENSIONS or filename in CONFIG_FILENAMES:
        score += 0.10
        reasons.append(f"Configuration file extension '{suffix}'.")
    elif suffix == ".md":
        score -= 0.18
        reasons.append("Markdown file is lower priority for implementation tasks.")

    if is_generated_context_path(normalized_path):
        score -= 0.85
        reasons.append("Penalized generated context or sample output path.")

    return max(0.0, min(score, 0.99)), reasons


def find_relevant_files(
    file_index: FileIndex,
    task: str,
    limit: int = 10,
) -> list[TaskRelevantFile]:
    scored: list[tuple[float, str, TaskRelevantFile]] = []
    for file in file_index.files:
        score, reasons = calculate_relevance_score(file, task)
        if score < MIN_RELEVANCE_SCORE:
            continue
        reason = " ".join(reasons)
        scored.append(
            (
                score,
                file.path,
                TaskRelevantFile(path=file.path, reason=reason, confidence=round(score, 2)),
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
