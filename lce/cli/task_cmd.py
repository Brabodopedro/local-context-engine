from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from lce.generators.task_context_generator import (
    generate_task_context,
    render_agent_prompt,
    render_compact_context,
    render_risk_map,
    render_task_context,
    render_validation_checklist,
)
from lce.scanner.scan_config import load_project_profile, load_task_budget
from lce.store.context_store import ContextStore
from lce.utils.file_utils import write_json, write_text

console = Console()


def task(
    task_description: Annotated[
        str,
        typer.Argument(help="Task description, for example: add JWT auth"),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Context folder."),
    ] = Path(".ai-context"),
) -> None:
    """Generate a deterministic task-specific context pack."""
    store = ContextStore(output)
    file_index_path = output / "file-index.json"
    if not file_index_path.exists():
        raise typer.BadParameter("Run `lce scan .` before generating a task context.")

    file_index = store.read_file_index()
    context = generate_task_context(
        file_index,
        task_description,
        budget=load_task_budget(output),
        profile=load_project_profile(output),
    )
    task_dir = output / "tasks" / context.slug
    write_text(task_dir / "task-context.md", render_task_context(context))
    write_text(task_dir / "compact-context.md", render_compact_context(context, file_index))
    write_json(
        task_dir / "relevant-files.json",
        {
            "task": context.task,
            "slug": context.slug,
            "project_profile": context.project_profile,
            "context_budget": {
                "max_primary_files": context.max_primary_files,
                "max_secondary_files": context.max_secondary_files,
                "max_context_files": context.max_context_files,
                "max_avoid_files": context.max_avoid_files,
            },
            "detected_intents": context.detected_intents,
            "detected_pipeline_phases": context.detected_pipeline_phases,
            "primary_files": [file.model_dump() for file in context.primary_files],
            "secondary_files": [file.model_dump() for file in context.secondary_files],
            "context_files": [file.model_dump() for file in context.context_files],
            "avoid_files": [file.model_dump() for file in context.avoid_files],
            "files": [file.model_dump() for file in context.relevant_files],
        },
    )
    write_text(task_dir / "risk-map.md", render_risk_map(context))
    write_text(task_dir / "validation-checklist.md", render_validation_checklist(context))
    write_text(task_dir / "agent-prompt.md", render_agent_prompt(context, "generic"))

    console.print(f"[green]Generated task context:[/green] {task_dir}")
    console.print(f"Primary files: [bold]{len(context.primary_files)}[/bold]")
    console.print(f"Secondary files: [bold]{len(context.secondary_files)}[/bold]")
    console.print(f"Context files: [bold]{len(context.context_files)}[/bold]")
    console.print(f"Avoid files: [bold]{len(context.avoid_files)}[/bold]")
