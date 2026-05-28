from __future__ import annotations

from lce.generators.task_context_generator import render_agent_prompt
from lce.models.context_models import TaskContext

SUPPORTED_TARGETS = {"generic", "cline", "codex", "copilot", "cursor", "claude"}


def generate_prompt(context: TaskContext, target: str) -> str:
    normalized_target = target.lower()
    if normalized_target not in SUPPORTED_TARGETS:
        supported = ", ".join(sorted(SUPPORTED_TARGETS))
        raise ValueError(f"Unsupported target '{target}'. Supported targets: {supported}")
    return render_agent_prompt(context, normalized_target)
