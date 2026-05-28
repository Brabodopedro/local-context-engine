from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from lce.models.context_models import FileIndex, FileInfo, TaskContext, TaskRelevantFile
from lce.scanner.scan_config import DEFAULT_PROFILE, SUPPORTED_PROFILES, TaskBudget
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
BROAD_ARCHITECTURE_KEYWORDS = {
    "worker",
    "api",
    "service",
    "app",
    "module",
    "core",
    "common",
    "utils",
    "helper",
}
HELPER_MODULE_STEMS = {"utils", "helpers", "ffmpeg", "client", "adapter", "config"}
FFMPEG_PRIMARY_TERMS = {"ffmpeg", "filter", "codec", "command", "subtitle", "crop", "transcode"}
AI_VIDEO_PROFILE = "ai-video"
AI_VIDEO_MODULE_ROLES = {
    "rendering.py": "render_orchestrator",
    "worker.py": "worker_entrypoint",
    "ffmpeg.py": "render_helper",
    "outputs_api.py": "output_api",
    "videos_api.py": "video_api",
    "jobs.py": "job_helpers",
    "planning.py": "planning_agent",
    "quality.py": "quality_agent",
    "metadata.py": "metadata_agent",
    "highlights.py": "highlight_agent",
    "transcription.py": "transcription_agent",
    "watcher.py": "watcher",
    "storage.py": "storage_service",
    "upload.py": "upload_service",
    "youtube.py": "upload_service",
}
AI_VIDEO_POST_RENDER_PRIMARY = {
    "render_orchestrator": 0.97,
    "worker_entrypoint": 0.94,
    "output_api": 0.93,
    "upload_service": 0.92,
    "storage_service": 0.90,
    "shared_models": 0.88,
    "video_api": 0.86,
}
AI_VIDEO_POST_RENDER_SECONDARY = {
    "render_helper": 0.76,
    "job_helpers": 0.72,
    "shared_enums": 0.70,
    "metadata_agent": 0.68,
}
AI_VIDEO_BACKGROUND_CONTEXT = {
    "planning_agent",
    "quality_agent",
    "highlight_agent",
    "transcription_agent",
    "watcher",
}


@dataclass(frozen=True)
class RelevanceCandidate:
    file: TaskRelevantFile
    category: str
    score: float
    actionable_score: float = 0.0
    strong_match_count: int = 0


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


def detect_pipeline_phases(task: str, profile: str = DEFAULT_PROFILE) -> list[str]:
    if _normalize_profile(profile) != AI_VIDEO_PROFILE:
        return []
    task_terms = set(_tokenize(task))
    lowered = task.lower()
    phases: set[str] = set()

    if task_terms & {"analysis", "transcription", "whisper", "detect", "vision"}:
        phases.add("analysis")
    if task_terms & {"planning", "planner", "edl", "plan"}:
        phases.add("planning")
    if task_terms & {"render", "rendering", "ffmpeg", "output"} or "final.mp4" in lowered:
        phases.add("render")
    if (
        "after render" in lowered
        or task_terms & {"upload", "publish", "youtube", "metadata"}
        or "output status" in lowered
    ):
        phases.add("post-render")
    if task_terms & {"quality", "validation", "check"}:
        phases.add("quality")
    if task_terms & {"storage", "s3", "minio", "artifact", "upload", "youtube"}:
        phases.add("storage/upload")
    if task_terms & {"highlight", "highlights"}:
        phases.add("highlight")

    return sorted(phases)


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


def classify_module_role(file_info: FileInfo | str, profile: str = DEFAULT_PROFILE) -> str | None:
    if _normalize_profile(profile) != AI_VIDEO_PROFILE:
        return None
    path = normalize_index_path(file_info.path if isinstance(file_info, FileInfo) else file_info)
    parts = path.split("/")
    filename = Path(path).name

    if filename == "models.py" and _is_under_shared_package(parts):
        return "shared_models"
    if filename == "enums.py" and _is_under_shared_package(parts):
        return "shared_enums"
    if filename.startswith("youtube") or filename.startswith("upload"):
        return "upload_service"
    return AI_VIDEO_MODULE_ROLES.get(filename)


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
    candidate = _score_file(file_info, task_description, DEFAULT_PROFILE)
    return candidate.score, [candidate.file.reason]


def find_relevant_files(
    file_index: FileIndex,
    task: str,
    limit: int = 10,
) -> list[TaskRelevantFile]:
    return generate_task_context(file_index, task, limit=limit).relevant_files


def generate_task_context(
    file_index: FileIndex,
    task: str,
    limit: int = 10,
    budget: TaskBudget | None = None,
    profile: str = DEFAULT_PROFILE,
) -> TaskContext:
    task_budget = budget or TaskBudget()
    project_profile = _normalize_profile(profile)
    slug = slugify(task)
    candidates = _rank_candidates(file_index, task, project_profile)
    primary, secondary, context_files, avoid = _rebalance_candidates(candidates, task_budget)
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
        project_profile=project_profile,
        max_primary_files=task_budget.max_primary_files,
        max_secondary_files=task_budget.max_secondary_files,
        max_context_files=task_budget.max_context_files,
        max_avoid_files=task_budget.max_avoid_files,
        detected_intents=detect_task_intents(task),
        detected_pipeline_phases=detect_pipeline_phases(task, project_profile),
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
        "## Project Profile",
        "",
        context.project_profile,
        "",
        "## Detected Intents",
        "",
        *(_render_plain_list(context.detected_intents) if context.detected_intents else ["- None"]),
        "",
        "## Detected Pipeline Phases",
        "",
        *(
            _render_plain_list(context.detected_pipeline_phases)
            if context.detected_pipeline_phases
            else ["- None"]
        ),
        "",
        "## Module Roles",
        "",
        *_render_module_roles(context),
        "",
        "## Context Budget",
        "",
        f"- Primary file limit: {context.max_primary_files}",
        f"- Secondary file limit: {context.max_secondary_files}",
        f"- Context file limit: {context.max_context_files}",
        (
            "- This context pack intentionally limits primary files to "
            f"{context.max_primary_files} to reduce context usage for AI coding agents."
        ),
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
        "4. Keep the first implementation pass focused on primary files.",
        "5. Avoid migrations unless the task requires schema changes.",
        "6. Avoid Dockerfile unless the task requires dependency or container changes.",
        "7. Make the smallest change that satisfies the task.",
        "8. Add or update tests for changed behavior.",
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
        f"This context pack was generated using the `{context.project_profile}` profile.\n"
        f"{_profile_prompt_note(context)}\n\n"
        "Before changing code:\n"
        "1. Read `.ai-context/agent-context.md`.\n"
        f"2. Read `.ai-context/tasks/{context.slug}/task-context.md`.\n"
        "3. Primary files are intentionally limited to reduce context.\n"
        "4. Inspect primary files first and do not open all secondary/context files upfront:\n"
        f"{primary}\n"
        "5. Inspect secondary files only if needed, when primary files are insufficient:\n"
        f"{secondary}\n\n"
        "Implementation rules:\n"
        "- For local LLMs, keep the first implementation pass focused on primary_files.\n"
        "- Do not modify avoid files unless explicitly required:\n"
        f"{avoid}\n"
        "- Do not modify migrations unless the task requires schema changes.\n"
        "- Do not modify Dockerfile unless the task requires dependency/container changes.\n"
        "- Explain before editing files outside primary_files.\n"
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


def _rank_candidates(
    file_index: FileIndex,
    task: str,
    profile: str,
) -> list[RelevanceCandidate]:
    candidates: list[RelevanceCandidate] = []
    for file in file_index.files:
        candidate = _score_file(file, task, profile)
        has_keyword_match = "Matched task keywords" in candidate.file.reason
        if (
            candidate.category == "avoid"
            or candidate.score >= MIN_RELEVANCE_SCORE
            or (candidate.category == "context" and has_keyword_match and candidate.score > 0.05)
        ):
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: (-item.score, item.file.path))


def _rebalance_candidates(
    candidates: list[RelevanceCandidate],
    budget: TaskBudget,
) -> tuple[
    list[TaskRelevantFile],
    list[TaskRelevantFile],
    list[TaskRelevantFile],
    list[TaskRelevantFile],
]:
    primary_candidates = [candidate for candidate in candidates if candidate.category == "primary"]
    primary = primary_candidates[: budget.max_primary_files]
    overflow_primary = primary_candidates[budget.max_primary_files :]

    secondary_candidates = [
        *overflow_primary,
        *[candidate for candidate in candidates if candidate.category == "secondary"],
    ]
    secondary = secondary_candidates[: budget.max_secondary_files]
    overflow_secondary = secondary_candidates[budget.max_secondary_files :]

    context_candidates = [
        *overflow_secondary,
        *[candidate for candidate in candidates if candidate.category == "context"],
    ]
    context_files = context_candidates[: budget.max_context_files]
    avoid = [
        candidate
        for candidate in candidates
        if candidate.category == "avoid"
        and candidate.file.role in {"migration", "generated", "example"}
    ][: budget.max_avoid_files]

    return (
        [candidate.file for candidate in primary],
        [candidate.file for candidate in secondary],
        [candidate.file for candidate in context_files],
        [candidate.file for candidate in avoid],
    )


def _score_file(file_info: FileInfo, task: str, profile: str) -> RelevanceCandidate:
    path = normalize_index_path(file_info.path)
    role = classify_path_role(file_info)
    module_role = classify_module_role(file_info, profile)
    intents = set(detect_task_intents(task))
    phases = set(detect_pipeline_phases(task, profile))
    keywords = keywords_for_task(task)
    path_obj = Path(path)
    filename = path_obj.name
    stem = path_obj.stem.lower()
    suffix = path_obj.suffix.lower()
    lower_filename = filename.lower()
    lower_tags = " ".join(file_info.tags).lower()
    lower_summary = file_info.summary.lower()
    parent_parts = [part.lower() for part in path.split("/")[:-1]]
    symbol_names = [
        *file_info.functions,
        *file_info.classes,
        *file_info.exports,
    ]
    lower_symbols = " ".join(symbol_names).lower()
    score = 0.0
    actionable_score = 0.0
    strong_match_count = 0
    matched_keywords: list[str] = []
    reasons: list[str] = []

    if role == "generated":
        return _candidate(
            path,
            role,
            module_role,
            "avoid",
            0.0,
            ["Generated context or sample output."],
        )

    for keyword in keywords:
        lowered = keyword.lower()
        matched = False
        broad_keyword = lowered in BROAD_ARCHITECTURE_KEYWORDS
        if lowered == stem:
            score += 0.30
            actionable_score += 0.30
            strong_match_count += 0 if broad_keyword else 1
            matched = True
        elif lowered in stem or lowered in lower_filename:
            score += 0.22
            actionable_score += 0.22
            strong_match_count += 0 if broad_keyword else 1
            matched = True
        if lowered in lower_symbols:
            score += 0.24
            actionable_score += 0.24
            strong_match_count += 0 if broad_keyword else 1
            matched = True
        if lowered in lower_tags:
            score += 0.20
            actionable_score += 0.14
            strong_match_count += 0 if broad_keyword else 1
            matched = True
        if lowered in lower_summary:
            score += 0.14
            actionable_score += 0.10
            strong_match_count += 0 if broad_keyword else 1
            matched = True
        if parent_parts and lowered in parent_parts[-1]:
            score += 0.08
            if not broad_keyword:
                actionable_score += 0.03
            matched = True
        elif any(lowered in part for part in parent_parts):
            score += 0.03
            matched = True
        if matched:
            matched_keywords.append(keyword)

    if not matched_keywords:
        category = "avoid" if role in {"migration", "generated"} else "context"
        if profile == AI_VIDEO_PROFILE and module_role:
            category, score, reasons = _apply_ai_video_profile_rules(
                role=role,
                module_role=module_role,
                phases=phases,
                task=task,
                score=0.0,
                category=category,
                reasons=["No actionable task keyword match."],
            )
            return _candidate(path, role, module_role, category, score, reasons)
        return _candidate(
            path,
            role,
            module_role,
            category,
            0.0,
            ["No actionable task keyword match."],
        )

    reasons.append(f"Matched task keywords '{', '.join(sorted(set(matched_keywords)))}'.")
    if intents:
        reasons.append(f"Task intent includes {', '.join(sorted(intents))}.")
    if role == "source":
        source_dir = next((part for part in path.split("/")[:-1] if part in SOURCE_DIRS), None)
        if source_dir:
            reasons.append(f"Located in source directory '{source_dir}/'.")

    score = _apply_role_and_intent_score(score, role, suffix, filename, intents, task, reasons)
    category = _category_for(
        role,
        score,
        intents,
        task,
        actionable_score,
        strong_match_count,
        stem,
    )
    if is_generated_context_path(path):
        score = max(0.0, score - 0.80)
        category = "avoid"
        reasons.append("Penalized generated context or sample output path.")
    if profile == AI_VIDEO_PROFILE and module_role:
        category, score, reasons = _apply_ai_video_profile_rules(
            role=role,
            module_role=module_role,
            phases=phases,
            task=task,
            score=score,
            category=category,
            reasons=reasons,
        )
    return _candidate(
        path,
        role,
        module_role,
        category,
        score,
        reasons,
        actionable_score,
        strong_match_count,
    )


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
        score += 0.12
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
        score += 0.08
    elif suffix in CONFIG_EXTENSIONS or filename in CONFIG_FILENAMES:
        score += 0.06 if _has_config_intent(intents, task) else 0.0
    elif suffix == ".md":
        score -= 0.12

    if filename == "Dockerfile" and not _has_config_intent(intents, task):
        score -= 0.45
        reasons.append("Dockerfile is not primary without docker/deploy/dependency intent.")

    stem = Path(filename).stem.lower()
    task_terms = set(_tokenize(task))
    if stem in HELPER_MODULE_STEMS and stem not in task_terms:
        if not (stem == "ffmpeg" and task_terms & FFMPEG_PRIMARY_TERMS):
            score -= 0.18
            reasons.append("Helper/module filename has secondary bias unless directly requested.")

    return max(0.0, min(score, 0.99))


def _category_for(
    role: str,
    score: float,
    intents: set[str],
    task: str,
    actionable_score: float,
    strong_match_count: int,
    stem: str,
) -> str:
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
    if role == "source" and _should_be_primary(
        score,
        actionable_score,
        strong_match_count,
        stem,
        task,
    ):
        return "primary"
    if score >= 0.35:
        return "secondary"
    return "context"


def _should_be_primary(
    score: float,
    actionable_score: float,
    strong_match_count: int,
    stem: str,
    task: str,
) -> bool:
    task_terms = set(_tokenize(task))
    if stem == "ffmpeg" and not task_terms & FFMPEG_PRIMARY_TERMS:
        return False
    if stem in HELPER_MODULE_STEMS and stem not in task_terms:
        return False
    return score >= 0.40 and actionable_score >= 0.20 and strong_match_count > 0


def _candidate(
    path: str,
    role: str,
    module_role: str | None,
    category: str,
    score: float,
    reasons: list[str],
    actionable_score: float = 0.0,
    strong_match_count: int = 0,
) -> RelevanceCandidate:
    return RelevanceCandidate(
        file=TaskRelevantFile(
            path=path,
            role=role,
            module_role=module_role,
            reason=" ".join(reasons),
            confidence=round(score, 2),
        ),
        category=category,
        score=score,
        actionable_score=actionable_score,
        strong_match_count=strong_match_count,
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


def _apply_ai_video_profile_rules(
    role: str,
    module_role: str,
    phases: set[str],
    task: str,
    score: float,
    category: str,
    reasons: list[str],
) -> tuple[str, float, list[str]]:
    if role in {"migration", "generated", "example", "package_init"}:
        return category, score, reasons

    task_terms = set(_tokenize(task))
    post_render_task = bool(phases & {"post-render", "storage/upload"})

    if module_role == "render_helper" and task_terms & FFMPEG_PRIMARY_TERMS:
        reasons.append(
            "AI-video profile promotes render_helper for explicit ffmpeg/render command work."
        )
        return "primary", max(score, 0.95), reasons
    if module_role == "planning_agent" and "planning" in phases:
        reasons.append("AI-video profile promotes planning_agent for planning phase work.")
        return "primary", max(score, 0.94), reasons
    if module_role == "quality_agent" and "quality" in phases:
        reasons.append("AI-video profile promotes quality_agent for quality phase work.")
        return "primary", max(score, 0.94), reasons
    if module_role == "highlight_agent" and "highlight" in phases:
        reasons.append("AI-video profile promotes highlight_agent for highlight phase work.")
        return "primary", max(score, 0.94), reasons

    if post_render_task:
        if module_role in AI_VIDEO_POST_RENDER_PRIMARY:
            reasons.append(
                "AI-video profile promotes this module for post-render/upload flow."
            )
            return "primary", max(score, AI_VIDEO_POST_RENDER_PRIMARY[module_role]), reasons
        if module_role in AI_VIDEO_POST_RENDER_SECONDARY:
            reasons.append(
                "AI-video profile marks this module secondary for post-render/upload flow."
            )
            return "secondary", max(score, AI_VIDEO_POST_RENDER_SECONDARY[module_role]), reasons
        if module_role in AI_VIDEO_BACKGROUND_CONTEXT:
            reasons.append(
                "AI-video profile keeps this phase-specific module as background context."
            )
            return "context", min(max(score, 0.25), 0.34), reasons

    if "render" in phases and module_role == "render_orchestrator":
        reasons.append("AI-video profile promotes render_orchestrator for render phase work.")
        return "primary", max(score, 0.92), reasons
    if "render" in phases and module_role == "render_helper":
        reasons.append("AI-video profile keeps render_helper secondary unless ffmpeg is explicit.")
        return "secondary", max(score, 0.70), reasons

    return category, score, reasons


def _normalize_profile(profile: str) -> str:
    return profile if profile in SUPPORTED_PROFILES else DEFAULT_PROFILE


def _is_under_shared_package(parts: list[str]) -> bool:
    return "packages" in parts and "shared" in parts


def _render_relevant_files(
    files: list[TaskRelevantFile],
    fallback: list[str] | None = None,
) -> list[str]:
    if not files:
        return [f"- {item}" for item in fallback] if fallback else ["- None"]
    return [
        f"- `{file.path}` ({_display_role(file)}, {file.confidence:.2f}): {file.reason}"
        for file in files
    ]


def _render_module_roles(context: TaskContext) -> list[str]:
    files = [
        *context.primary_files,
        *context.secondary_files,
        *context.context_files,
        *context.avoid_files,
    ]
    role_lines = [
        f"- {Path(file.path).name}: {file.module_role}"
        for file in files
        if file.module_role
    ]
    return role_lines or ["- None"]


def _render_plain_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _render_prompt_file_list(files: list[TaskRelevantFile]) -> str:
    if not files:
        return "- None"
    return "\n".join(f"- `{file.path}` ({_display_role(file)})" for file in files)


def _display_role(file: TaskRelevantFile) -> str:
    if file.module_role:
        return f"{file.role}, {file.module_role}"
    return file.role


def _profile_prompt_note(context: TaskContext) -> str:
    if context.project_profile != AI_VIDEO_PROFILE:
        return "Primary files are selected using the generic deterministic relevance profile."
    return (
        "Primary files are selected based on AI/video pipeline roles. "
        "Do not inspect planning/quality/highlight modules unless the task requires those phases."
    )
