from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from lce.generators.task_context_generator import (
    generate_task_context,
    render_agent_prompt,
    render_risk_map,
    render_task_context,
    render_validation_checklist,
)
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
    context = generate_task_context(file_index, task_description)
    task_dir = output / "tasks" / context.slug
    write_text(task_dir / "task-context.md", render_task_context(context))
    write_json(
        task_dir / "relevant-files.json",
        {
            "task": context.task,
            "slug": context.slug,
            "files": [file.model_dump() for file in context.relevant_files],
        },
    )
    write_text(task_dir / "risk-map.md", render_risk_map(context))
    write_text(task_dir / "validation-checklist.md", render_validation_checklist(context))
    write_text(task_dir / "agent-prompt.md", render_agent_prompt(context, "generic"))

    console.print(f"[green]Generated task context:[/green] {task_dir}")
    console.print(f"Relevant files: [bold]{len(context.relevant_files)}[/bold]")
