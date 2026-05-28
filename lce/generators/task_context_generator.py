from __future__ import annotations

import re
from dataclasses import dataclass
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
    ("upload",): ["upload", "storage", "s3", "minio", "media"],
    ("render",): ["render", "worker", "ffmpeg", "video", "output"],
}

TASK_STOPWORDS = {
    "file",
    "files",
    "source",
    "code",
    "module",
    "project",
    "app",
    "system",
    "data",
    "logic",
    "implementation",
    "add",
    "after",
    "before",
    "create",
    "update",
    "change",
    "improve",
}

INTENT_KEYWORDS = {
    "auth": {"auth", "login", "jwt", "token", "session", "user"},
    "render": {"render", "ffmpeg", "video", "output", "worker"},
    "upload/storage": {"upload", "storage", "s3", "minio", "file", "media"},
    "docker/deploy": {"docker", "compose", "container", "image", "deploy"},
    "database": {"database", "migration", "schema", "table", "column", "alembic", "model"},
    "frontend": {"frontend", "page", "component", "ui", "react", "vue", "screen"},
    "api": {"api", "endpoint", "route", "controller"},
}

DEFAULT_VALIDATION_CHECKLIST = [
    "Run the relevant test suite.",
    "Run the project formatter or linter if available.",
    "Verify the changed workflow manually when practical.",
    "Confirm unrelated files were not modified.",
    "Update documentation if public behavior changes.",
]

SOURCE_DIRS = ("lce", "src", "app", "apps", "backend", "frontend", "server", "api")
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
    "last-update.md",
    "last-update.json",
}
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".php", ".go", ".java", ".cs"}
CONFIG_EXTENSIONS = {".json", ".yml", ".yaml", ".toml", ".ini"}
CONFIG_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "pyproject.toml",
    "package.json",
}
MIN_RELEVANCE_SCORE = 0.20


@dataclass(frozen=True)
class RelevanceCandidate:
    file: TaskRelevantFile
    category: str
    score: float


def keywords_for_task(task: str) -> list[str]:
    task_terms = _tokenize(task)
    keywords: list[str] = [term for term in task_terms if term not in TASK_STOPWORDS]
    lowered = task.lower()
    for triggers, matches in TASK_KEYWORDS.items():
        if any(trigger in lowered for trigger in triggers):
            keywords.extend(matches)
    return sorted({keyword for keyword in keywords if keyword.lower() not in TASK_STOPWORDS})


def detect_task_intents(task: str) -> list[str]:
    task_terms = set(_tokenize(task))
    lowered = task.lower()
    intents = [
        intent
        for intent, keywords in INTENT_KEYWORDS.items()
        if task_terms & keywords or any(keyword in lowered for keyword in keywords)
    ]
    return sorted(intents)


def classify_path_role(file_info: FileInfo | str) -> str:
    path = normalize_index_path(file_info.path if isinstance(file_info, FileInfo) else file_info)
    path_obj = Path(path)
    parts = path.split("/")
    filename = path_obj.name
    suffix = path_obj.suffix.lower()

    if path.startswith(".ai-context/") or path == ".ai-context" or filename in GENERATED_NAMES:
        return "generated"
    if "migrations" in parts:
        return "migration"
    if filename == "__init__.py":
        return "package_init"
    if parts and parts[0] in {"tests", "test"}:
        return "test"
    if parts and parts[0] == "examples":
        return "example"
    if parts and parts[0] in {"docs", "documentation"}:
        return "documentation"
    if suffix == ".md":
        return "documentation"
    if filename in CONFIG_FILENAMES or suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix in SOURCE_EXTENSIONS and any(part in SOURCE_DIRS for part in parts[:-1]):
        return "source"
    return "unknown"


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
    candidate = _score_file(file_info, task_description)
    return candidate.score, [candidate.file.reason]


def find_relevant_files(
    file_index: FileIndex,
    task: str,
    limit: int = 10,
) -> list[TaskRelevantFile]:
    return generate_task_context(file_index, task, limit=limit).relevant_files


def generate_task_context(file_index: FileIndex, task: str, limit: int = 10) -> TaskContext:
    slug = slugify(task)
    candidates = _rank_candidates(file_index, task)
    primary = _take_category(candidates, "primary", limit)
    secondary = _take_category(candidates, "secondary", limit)
    context_files = _take_category(candidates, "context", limit)
    avoid = _take_category(candidates, "avoid", limit)
    flattened = [*primary, *secondary, *context_files]
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
        detected_intents=detect_task_intents(task),
        primary_files=primary,
        secondary_files=secondary,
        context_files=context_files,
        avoid_files=avoid,
        relevant_files=flattened[:limit],
        generated_files=generated_files,
        validation_checklist=DEFAULT_VALIDATION_CHECKLIST,
    )


def files_to_avoid() -> list[str]:
    return [
        ".env* files unless explicitly requested",
        "database migrations unless explicitly requested",
        "Dockerfile unless dependency or container changes are required",
        "generated build artifacts",
        "vendored dependencies",
    ]


def render_task_context(context: TaskContext) -> str:
    lines = [
        "# Task Context",
        "",
        "## Goal",
        "",
        context.task,
        "",
        "## Detected Intents",
        "",
        *(_render_plain_list(context.detected_intents) if context.detected_intents else ["- None"]),
        "",
        "## Primary Files To Inspect First",
        "",
        *_render_relevant_files(context.primary_files),
        "",
        "## Secondary Files",
        "",
        *_render_relevant_files(context.secondary_files),
        "",
        "## Context Files",
        "",
        *_render_relevant_files(context.context_files),
        "",
        "## Files To Avoid Unless Explicitly Needed",
        "",
        *_render_relevant_files(context.avoid_files, fallback=files_to_avoid()),
        "",
        "## Suggested Implementation Approach",
        "",
        "1. Read `.ai-context/agent-context.md`.",
        "2. Inspect primary files first.",
        "3. Inspect secondary files only if needed.",
        "4. Avoid migrations unless the task requires schema changes.",
        "5. Avoid Dockerfile unless the task requires dependency or container changes.",
        "6. Make the smallest change that satisfies the task.",
        "7. Add or update tests for changed behavior.",
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
    return "\n".join(lines)


def render_risk_map(context: TaskContext) -> str:
    lines = [
        "# Risk Map",
        "",
        "- Keep changes scoped to primary files unless investigation requires more context.",
        "- Avoid environment files and migrations unless the task explicitly requires them.",
        "- Avoid Dockerfile unless dependency or container changes are required.",
        "- Prefer adding tests near changed code.",
        "",
        "## Avoid Files",
        "",
        *_render_relevant_files(context.avoid_files, fallback=files_to_avoid()),
    ]
    return "\n".join(lines) + "\n"


def render_validation_checklist(context: TaskContext) -> str:
    return "# Validation Checklist\n\n" + "\n".join(
        f"- [ ] {item}" for item in context.validation_checklist
    ) + "\n"


def render_agent_prompt(context: TaskContext, target: str) -> str:
    primary = _render_prompt_file_list(context.primary_files)
    secondary = _render_prompt_file_list(context.secondary_files)
    avoid = _render_prompt_file_list(context.avoid_files)
    target_note = {
        "cline": "Use Cline's planning and file editing tools carefully.",
        "codex": "Use Codex to inspect, edit, and validate the local repository.",
        "copilot": "Use Copilot chat with the listed primary files as the starting context.",
        "cursor": "Use Cursor with the primary files attached or opened first.",
        "claude": "Use Claude Code with the primary files as initial context.",
        "generic": "Use your coding-agent tools with a narrow initial context.",
    }.get(target, "Use your coding-agent tools with a narrow initial context.")
    return (
        f"You are working on this task: {context.task}\n\n"
        "Before changing code:\n"
        "1. Read `.ai-context/agent-context.md`.\n"
        f"2. Read `.ai-context/tasks/{context.slug}/task-context.md`.\n"
        "3. Inspect primary files first:\n"
        f"{primary}\n"
        "4. Inspect secondary files only if needed:\n"
        f"{secondary}\n\n"
        "Implementation rules:\n"
        "- Do not modify avoid files unless explicitly required:\n"
        f"{avoid}\n"
        "- Do not modify migrations unless the task requires schema changes.\n"
        "- Do not modify Dockerfile unless the task requires dependency/container changes.\n"
        "- Explain any decision to edit files outside primary_files.\n"
        "- Avoid unrelated changes and broad refactors.\n"
        "- Update tests when behavior changes.\n"
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


def _rank_candidates(file_index: FileIndex, task: str) -> list[RelevanceCandidate]:
    candidates: list[RelevanceCandidate] = []
    for file in file_index.files:
        candidate = _score_file(file, task)
        has_keyword_match = "Matched task keywords" in candidate.file.reason
        if (
            candidate.category == "avoid"
            or candidate.score >= MIN_RELEVANCE_SCORE
            or (candidate.category == "context" and has_keyword_match and candidate.score > 0.05)
        ):
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: (-item.score, item.file.path))


def _score_file(file_info: FileInfo, task: str) -> RelevanceCandidate:
    path = normalize_index_path(file_info.path)
    role = classify_path_role(file_info)
    intents = set(detect_task_intents(task))
    keywords = keywords_for_task(task)
    path_obj = Path(path)
    filename = path_obj.name
    suffix = path_obj.suffix.lower()
    lower_path = path.lower()
    lower_filename = filename.lower()
    lower_tags = " ".join(file_info.tags).lower()
    lower_summary = file_info.summary.lower()
    score = 0.0
    matched_keywords: list[str] = []
    reasons: list[str] = []

    if role == "generated":
        return _candidate(path, role, "avoid", 0.0, ["Generated context or sample output."])

    for keyword in keywords:
        lowered = keyword.lower()
        matched = False
        if lowered in lower_path:
            score += 0.18
            matched = True
        if lowered in lower_filename:
            score += 0.16
            matched = True
        if lowered in lower_tags:
            score += 0.12
            matched = True
        if lowered in lower_summary:
            score += 0.06
            matched = True
        if matched:
            matched_keywords.append(keyword)

    if not matched_keywords:
        category = "avoid" if role in {"migration", "generated"} else "context"
        return _candidate(path, role, category, 0.0, ["No actionable task keyword match."])

    reasons.append(f"Matched task keywords '{', '.join(sorted(set(matched_keywords)))}'.")
    if intents:
        reasons.append(f"Task intent includes {', '.join(sorted(intents))}.")
    if role == "source":
        source_dir = next((part for part in path.split("/")[:-1] if part in SOURCE_DIRS), None)
        if source_dir:
            reasons.append(f"Located in source directory '{source_dir}/'.")

    score = _apply_role_and_intent_score(score, role, suffix, filename, intents, task, reasons)
    category = _category_for(role, score, intents, task)
    if is_generated_context_path(path):
        score = max(0.0, score - 0.80)
        category = "avoid"
        reasons.append("Penalized generated context or sample output path.")
    return _candidate(path, role, category, score, reasons)


def _apply_role_and_intent_score(
    score: float,
    role: str,
    suffix: str,
    filename: str,
    intents: set[str],
    task: str,
    reasons: list[str],
) -> float:
    if role == "source":
        score += 0.28
        reasons.append("Located in source directory; role source.")
    elif role == "test":
        if "test" in _tokenize(task) or "tests" in _tokenize(task):
            score += 0.18
            reasons.append("Task explicitly mentions tests.")
        else:
            score -= 0.02
            reasons.append("Role test; inspect after primary files.")
    elif role == "config":
        if _has_config_intent(intents, task):
            score += 0.22
            reasons.append("Config file matches dependency/container/config intent.")
        else:
            score -= 0.20
            reasons.append("Config file is lower priority without config or deploy intent.")
    elif role == "migration":
        if "database" in intents:
            score += 0.12
            reasons.append("Migration matches database intent.")
        else:
            score -= 0.55
            reasons.append("Migration penalized because task has no database intent.")
    elif role == "package_init":
        if _mentions_package_surface(task):
            score += 0.08
            reasons.append("Package init may matter for exports/imports.")
        else:
            score -= 0.15
            reasons.append("__init__.py is usually not an actionable implementation file.")
    elif role == "documentation":
        score -= 0.22
        reasons.append("Documentation is low priority for implementation tasks.")
    elif role == "example":
        score -= 0.45
        reasons.append("Example files are heavily penalized.")

    if suffix in SOURCE_EXTENSIONS:
        score += 0.16
    elif suffix in CONFIG_EXTENSIONS or filename in CONFIG_FILENAMES:
        score += 0.06 if _has_config_intent(intents, task) else 0.0
    elif suffix == ".md":
        score -= 0.12

    if filename == "Dockerfile" and not _has_config_intent(intents, task):
        score -= 0.45
        reasons.append("Dockerfile is not primary without docker/deploy/dependency intent.")

    return max(0.0, min(score, 0.99))


def _category_for(role: str, score: float, intents: set[str], task: str) -> str:
    if role == "migration" and "database" not in intents:
        return "avoid"
    if role == "generated":
        return "avoid"
    if role == "example":
        return "avoid"
    if role == "package_init" and not _mentions_package_surface(task):
        return "context"
    if role == "config" and not _has_config_intent(intents, task):
        return "context"
    if role == "documentation":
        return "context"
    if role == "test":
        return "secondary"
    if role == "source" and score >= 0.45:
        return "primary"
    if score >= 0.35:
        return "secondary"
    return "context"


def _candidate(
    path: str,
    role: str,
    category: str,
    score: float,
    reasons: list[str],
) -> RelevanceCandidate:
    return RelevanceCandidate(
        file=TaskRelevantFile(
            path=path,
            role=role,
            reason=" ".join(reasons),
            confidence=round(score, 2),
        ),
        category=category,
        score=score,
    )


def _take_category(
    candidates: list[RelevanceCandidate],
    category: str,
    limit: int,
) -> list[TaskRelevantFile]:
    return [candidate.file for candidate in candidates if candidate.category == category][:limit]


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 2]


def _has_config_intent(intents: set[str], task: str) -> bool:
    task_terms = set(_tokenize(task))
    return bool(
        {"docker/deploy"} & intents
        or task_terms & {"config", "env", "dependency", "dependencies", "docker", "deploy"}
    )


def _mentions_package_surface(task: str) -> bool:
    return bool(set(_tokenize(task)) & {"export", "exports", "package", "import", "imports"})


def _render_relevant_files(
    files: list[TaskRelevantFile],
    fallback: list[str] | None = None,
) -> list[str]:
    if not files:
        return [f"- {item}" for item in fallback] if fallback else ["- None"]
    return [
        f"- `{file.path}` ({file.role}, {file.confidence:.2f}): {file.reason}"
        for file in files
    ]


def _render_plain_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _render_prompt_file_list(files: list[TaskRelevantFile]) -> str:
    if not files:
        return "- None"
    return "\n".join(f"- `{file.path}` ({file.role})" for file in files)
