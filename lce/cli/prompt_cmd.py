from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from lce.generators.prompt_generator import SUPPORTED_TARGETS, generate_prompt
from lce.generators.task_context_generator import latest_task_dir
from lce.models.context_models import TaskContext
from lce.utils.file_utils import read_json, write_text

console = Console()


def prompt(
    target: Annotated[
        str,
        typer.Option("--target", "-t", help="AI coding agent target."),
    ] = "generic",
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Context folder."),
    ] = Path(".ai-context"),
) -> None:
    """Generate a prompt for an AI coding agent from the latest task folder."""
    task_dir = latest_task_dir(output)
    if task_dir is None:
        raise typer.BadParameter("No task context found. Run `lce task \"...\"` first.")

    relevant_path = task_dir / "relevant-files.json"
    if not relevant_path.exists():
        raise typer.BadParameter(f"Missing relevant-files.json in {task_dir}")

    try:
        data = read_json(relevant_path)
        compatibility_files = data.get("files", [])
        primary_files = (
            data["primary_files"] if "primary_files" in data else compatibility_files
        )
        context = TaskContext(
            task=data["task"],
            slug=data["slug"],
            detected_intents=data.get("detected_intents", []),
            primary_files=primary_files,
            secondary_files=data.get("secondary_files", []),
            context_files=data.get("context_files", []),
            avoid_files=data.get("avoid_files", []),
            relevant_files=compatibility_files,
            generated_files=[],
            validation_checklist=[],
        )
        content = generate_prompt(context, target)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error

    prompt_path = task_dir / f"agent-prompt-{target.lower()}.md"
    write_text(prompt_path, content)
    console.print(content)
    console.print("")
    console.print(f"[green]Wrote prompt:[/green] {prompt_path}")
    console.print(f"Supported targets: {', '.join(sorted(SUPPORTED_TARGETS))}")
