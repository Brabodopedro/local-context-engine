from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lce.generators.task_context_generator import (
    detect_task_intents,
    files_to_avoid,
    generate_task_context,
)
from lce.models.context_models import FileIndex, RepoMap, TaskContext, TaskRelevantFile
from lce.scanner.scan_config import TaskBudget
from lce.utils.file_utils import slugify

SPEC_FILENAMES = [
    "spec.md",
    "requirements.md",
    "technical-plan.md",
    "affected-context.json",
    "acceptance-criteria.md",
    "risks.md",
    "validation-checklist.md",
    "agent-prompt-local-llm.md",
]


@dataclass(frozen=True)
class SpecContext:
    description: str
    slug: str
    project_profile: str
    task_context: TaskContext
    repo_map: RepoMap | None = None
    agent_context_available: bool = False


def generate_spec_context(
    file_index: FileIndex,
    description: str,
    *,
    budget: TaskBudget,
    profile: str,
    repo_map: RepoMap | None = None,
    agent_context_available: bool = False,
) -> SpecContext:
    task_context = generate_task_context(
        file_index,
        description,
        budget=budget,
        profile=profile,
    )
    return SpecContext(
        description=description,
        slug=slugify(description),
        project_profile=task_context.project_profile,
        task_context=task_context,
        repo_map=repo_map,
        agent_context_available=agent_context_available,
    )


def render_spec(spec: SpecContext) -> str:
    open_questions = _open_questions(spec.description)
    lines = [
        "# Specification",
        "",
        "## Title",
        "",
        _title_from_description(spec.description),
        "",
        "## Goal",
        "",
        f"Create a plan-ready technical specification for: {spec.description}.",
        "",
        "## Problem",
        "",
        (
            "The implementation idea needs to be clarified before source files are edited. "
            "This specification captures the current context, likely affected areas, risks, "
            "and validation steps so an agent can plan first."
        ),
        "",
        "## Non-goals",
        "",
        "- Do not implement the feature as part of spec generation.",
        "- Do not add new external LLM, embedding, vector database, or API-server dependencies.",
        (
            "- Do not change avoid files unless the reviewed implementation plan explicitly "
            "requires it."
        ),
        "",
        "## Project Profile",
        "",
        spec.project_profile,
        "",
        "## Current Context",
        "",
        *_current_context_lines(spec),
        "",
        "## Affected Areas",
        "",
        *_affected_area_lines(spec.task_context),
        "",
        "## Proposed Design",
        "",
        "- Start from the generated context and inspect primary files before implementation.",
        "- Keep the first implementation pass small and reversible.",
        "- TODO: confirm API contract",
        "- TODO: confirm persistence strategy",
        "- TODO: confirm credential strategy",
        "",
        "## Implementation Plan",
        "",
        *_implementation_steps(spec.task_context),
        "",
        "## Acceptance Criteria",
        "",
        *_acceptance_criteria(spec.description),
        "",
        "## Risks",
        "",
        *_risk_lines(spec.task_context),
        "",
        "## Validation Plan",
        "",
        *_validation_checklist(),
        "",
        "## Agent Instructions",
        "",
        "- Read this specification before inspecting source files.",
        "- Read `technical-plan.md` next.",
        "- Return a concise implementation plan before editing.",
        "- Ask for approval before reading or editing source files.",
        "- Do not modify avoid files unless explicitly required.",
        "- Keep the first implementation pass small.",
        "",
        "## Open Questions",
        "",
        *[f"- {question}" for question in open_questions],
        "",
    ]
    return "\n".join(lines)


def render_requirements(spec: SpecContext) -> str:
    lines = [
        "# Requirements",
        "",
        "## Functional Requirements",
        "",
        f"- Define the expected implementation approach for: {spec.description}.",
        "- Identify candidate files and affected areas before coding.",
        "- Preserve a plan-first workflow for local coding agents.",
        "",
        "## Non-functional Requirements",
        "",
        "- Keep the implementation deterministic and testable.",
        "- Avoid unnecessary new dependencies.",
        "- Keep changes scoped to the approved plan.",
        "",
        "## Constraints",
        "",
        "- Use existing repository context from `.ai-context/`.",
        "- Do not rely on OpenAI, Ollama, embeddings, vector databases, or external LLM calls.",
        (
            "- Do not modify generated context files as part of implementation unless "
            "regenerating LCE output."
        ),
        "",
        "## Out of Scope",
        "",
        "- Full implementation during spec generation.",
        "- Broad refactors unrelated to the approved plan.",
        "- Schema migrations unless schema changes are explicitly approved.",
        "",
        "## Open Questions",
        "",
        *[f"- {question}" for question in _open_questions(spec.description)],
        "",
    ]
    return "\n".join(lines)


def render_technical_plan(spec: SpecContext) -> str:
    context = spec.task_context
    lines = [
        "# Technical Plan",
        "",
        "## Suggested Approach",
        "",
        "- Review `spec.md` and confirm the open questions before implementation.",
        "- Inspect primary files first and expand only when needed.",
        "- Prefer small, testable changes over broad rewrites.",
        "",
        "## Candidate Files",
        "",
        *_render_files([*context.primary_files, *context.secondary_files, *context.context_files]),
        "",
        "## Implementation Steps",
        "",
        *_implementation_steps(context),
        "",
        "## Data/State Changes",
        "",
        "- TODO: confirm persistence strategy",
        "- Avoid migrations unless schema changes are explicitly required.",
        "",
        "## API Changes",
        "",
        "- TODO: confirm API contract",
        "- Document any new public command, endpoint, or callable behavior before implementation.",
        "",
        "## Worker/Pipeline Changes",
        "",
        "- TODO: confirm whether this affects background jobs, render workers, or post-processing.",
        "- Keep worker changes isolated and covered by validation when applicable.",
        "",
        "## Validation Steps",
        "",
        *_validation_checklist(),
        "",
    ]
    return "\n".join(lines)


def render_affected_context(spec: SpecContext) -> dict[str, object]:
    context = spec.task_context
    return {
        "spec": spec.description,
        "slug": spec.slug,
        "project_profile": spec.project_profile,
        "detected_intents": context.detected_intents or detect_task_intents(spec.description),
        "candidate_files": [
            file.model_dump()
            for file in [*context.primary_files, *context.secondary_files, *context.context_files]
        ],
        "primary_files": [file.model_dump() for file in context.primary_files],
        "secondary_files": [file.model_dump() for file in context.secondary_files],
        "context_files": [file.model_dump() for file in context.context_files],
        "avoid_files": [file.model_dump() for file in context.avoid_files],
        "open_questions": _open_questions(spec.description),
    }


def render_acceptance_criteria(spec: SpecContext) -> str:
    return "# Acceptance Criteria\n\n" + "\n".join(_acceptance_criteria(spec.description)) + "\n"


def render_risks(spec: SpecContext) -> str:
    lines = [
        "# Risks",
        "",
        "## Technical Risks",
        "",
        "- The implementation may require files outside the primary candidates.",
        "- TODO: confirm API contract before changing public behavior.",
        "",
        "## Integration Risks",
        "",
        "- Integration boundaries may be unclear until primary files are inspected.",
        "- TODO: confirm credential strategy for external integrations.",
        "",
        "## Data/Schema Risks",
        "",
        "- Persistence needs may require schema changes that are not yet confirmed.",
        "- Do not modify migrations unless schema changes are explicitly required.",
        "",
        "## Local LLM Execution Risks",
        "",
        "- Local LLMs may over-read files or start editing before a plan is approved.",
        "- Keep the first implementation pass small and inspect primary files first.",
        "",
        "## Files To Avoid Unless Explicitly Required",
        "",
        *_render_files(spec.task_context.avoid_files, fallback=files_to_avoid()),
        "",
    ]
    return "\n".join(lines)


def render_validation_checklist() -> str:
    return "# Validation Checklist\n\n" + "\n".join(_validation_checklist()) + "\n"


def render_local_llm_prompt(spec: SpecContext) -> str:
    return "\n".join(
        [
            "# Local LLM Spec Prompt",
            "",
            f"You are working from a specification for: {spec.description}",
            "",
            "You are working from a specification, not implementing immediately.",
            "",
            "Rules:",
            f"- Read `.ai-context/specs/{spec.slug}/spec.md` first.",
            f"- Read `.ai-context/specs/{spec.slug}/technical-plan.md`.",
            "- Do not edit files yet.",
            "- Return a concise implementation plan.",
            "- List the first files you would inspect and why.",
            "- Ask for approval before reading/editing source files.",
            "- Do not modify avoid files.",
            "- Do not modify migrations unless schema changes are explicitly required.",
            "- Keep the first implementation pass small.",
            "",
            "First files to consider:",
            *_render_files(spec.task_context.primary_files),
            "",
        ]
    )


def spec_output_paths(base_output: Path, slug: str) -> dict[str, Path]:
    spec_dir = base_output / slug
    return {filename: spec_dir / filename for filename in SPEC_FILENAMES}


def _title_from_description(description: str) -> str:
    words = description.strip().split()
    return " ".join(word[:1].upper() + word[1:] for word in words) if words else "Untitled Spec"


def _current_context_lines(spec: SpecContext) -> list[str]:
    lines = [
        f"- Agent context available: {'yes' if spec.agent_context_available else 'no'}",
        f"- Indexed files considered: {len(spec.task_context.relevant_files)} relevant candidates",
    ]
    if spec.repo_map is not None:
        lines.append(f"- Project name: {spec.repo_map.project.name}")
        detected_stack = ", ".join(spec.repo_map.project.detected_stack) or "None"
        lines.append(f"- Detected stack: {detected_stack}")
        lines.append(f"- Indexed files: {spec.repo_map.summary.indexed_files}")
    return lines


def _affected_area_lines(context: TaskContext) -> list[str]:
    return [
        "- Primary files:",
        *_render_files(context.primary_files),
        "- Secondary files:",
        *_render_files(context.secondary_files),
        "- Context files:",
        *_render_files(context.context_files),
        "- Avoid files:",
        *_render_files(context.avoid_files, fallback=files_to_avoid()),
    ]


def _implementation_steps(context: TaskContext) -> list[str]:
    first_file = (
        context.primary_files[0].path if context.primary_files else "TODO: identify first file"
    )
    return [
        "1. Review the generated specification and open questions.",
        f"2. Inspect `{first_file}` first and confirm it is the right entry point.",
        "3. Inspect additional primary files only as needed.",
        "4. Draft the smallest implementation plan that satisfies the accepted criteria.",
        "5. Ask for approval before editing files.",
        "6. Implement, test, and regenerate LCE context after changes.",
    ]


def _acceptance_criteria(description: str) -> list[str]:
    return [
        f"- [ ] The approved implementation addresses: {description}.",
        "- [ ] Primary and secondary affected files have been reviewed before editing.",
        "- [ ] Open questions have been answered or explicitly deferred.",
        "- [ ] Tests or manual validation steps cover the changed behavior.",
        "- [ ] `lce update` has been run after implementation changes.",
        "- [ ] Avoid files were not modified unless explicitly required.",
    ]


def _risk_lines(context: TaskContext) -> list[str]:
    return [
        "- Technical risk: the initial candidate files may be incomplete.",
        "- Integration risk: external services or pipeline boundaries may need confirmation.",
        "- Data/schema risk: persistence requirements are not confirmed.",
        "- Local LLM risk: the agent may edit too broadly without an approved plan.",
        "- Files to avoid unless explicitly required:",
        *_render_files(context.avoid_files, fallback=files_to_avoid()),
    ]


def _validation_checklist() -> list[str]:
    return [
        "- [ ] Run tests.",
        "- [ ] Run `lce update` after changes.",
        "- [ ] Verify generated context still works.",
        "- [ ] Verify no sensitive files were indexed.",
        "- [ ] Verify avoid files were not modified unless required.",
    ]


def _open_questions(description: str) -> list[str]:
    lowered = description.lower()
    questions = [
        "What is the smallest useful implementation slice?",
        "What API contract or user-facing behavior should be preserved?",
        "What validation command should be considered authoritative?",
    ]
    if any(term in lowered for term in ("upload", "youtube", "credential", "oauth")):
        questions.extend(
            [
                "Which credential strategy should be used?",
                "Should uploads be automatic or manually triggered?",
                "Should upload failures affect render success?",
                "Should upload status be persisted?",
            ]
        )
    if any(term in lowered for term in ("render", "worker", "pipeline")):
        questions.append("Where should the post-render pipeline boundary live?")
    return questions


def _render_files(files: list[TaskRelevantFile], fallback: list[str] | None = None) -> list[str]:
    if not files:
        return [f"- {item}" for item in fallback] if fallback else ["- None"]
    return [
        f"- `{file.path}` ({file.role}, confidence {file.confidence:.2f}): {file.reason}"
        for file in files
    ]
