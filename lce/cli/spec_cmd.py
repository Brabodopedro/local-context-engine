from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from lce.generators.spec_generator import (
    generate_spec_context,
    render_acceptance_criteria,
    render_affected_context,
    render_local_llm_prompt,
    render_requirements,
    render_risks,
    render_spec,
    render_technical_plan,
    render_validation_checklist,
    spec_output_paths,
)
from lce.scanner.scan_config import SUPPORTED_PROFILES, load_project_profile, load_task_budget
from lce.store.context_store import ContextStore
from lce.utils.file_utils import write_json, write_text

console = Console()


def spec(
    spec_description: Annotated[
        str,
        typer.Argument(help="Implementation idea to convert into a technical specification."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Specification output folder."),
    ] = Path(".ai-context/specs"),
    target: Annotated[
        str,
        typer.Option("--target", help="Spec prompt target."),
    ] = "local-llm",
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Override project profile for this spec."),
    ] = None,
) -> None:
    """Generate a deterministic specification pack before implementation."""
    normalized_target = target.lower()
    if normalized_target != "local-llm":
        raise typer.BadParameter("Only `local-llm` is supported for spec prompts in this version.")

    context_dir = _context_dir_for_output(output)
    _ensure_context_ready(context_dir)

    project_profile = profile or load_project_profile(context_dir)
    if project_profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise typer.BadParameter(
            f"Unsupported profile '{project_profile}'. Supported profiles: {supported}"
        )

    store = ContextStore(context_dir)
    file_index = store.read_file_index()
    repo_map = store.read_repo_map()
    spec_context = generate_spec_context(
        file_index,
        spec_description,
        budget=load_task_budget(context_dir),
        profile=project_profile,
        repo_map=repo_map,
        agent_context_available=(context_dir / "agent-context.md").exists(),
    )
    paths = spec_output_paths(output, spec_context.slug)

    write_text(paths["spec.md"], render_spec(spec_context))
    write_text(paths["requirements.md"], render_requirements(spec_context))
    write_text(paths["technical-plan.md"], render_technical_plan(spec_context))
    write_json(paths["affected-context.json"], render_affected_context(spec_context))
    write_text(paths["acceptance-criteria.md"], render_acceptance_criteria(spec_context))
    write_text(paths["risks.md"], render_risks(spec_context))
    write_text(paths["validation-checklist.md"], render_validation_checklist())
    write_text(paths["agent-prompt-local-llm.md"], render_local_llm_prompt(spec_context))

    spec_dir = output / spec_context.slug
    console.print(f"[green]Generated specification:[/green] {spec_dir}")
    console.print(f"Project profile: [bold]{spec_context.project_profile}[/bold]")
    console.print(f"Primary files: [bold]{len(spec_context.task_context.primary_files)}[/bold]")
    console.print(f"Secondary files: [bold]{len(spec_context.task_context.secondary_files)}[/bold]")
    console.print(f"Context files: [bold]{len(spec_context.task_context.context_files)}[/bold]")
    console.print(f"Avoid files: [bold]{len(spec_context.task_context.avoid_files)}[/bold]")


def _context_dir_for_output(output: Path) -> Path:
    if output.name == "specs" and output.parent.name == ".ai-context":
        return output.parent
    return Path(".ai-context")


def _ensure_context_ready(context_dir: Path) -> None:
    required = [
        context_dir,
        context_dir / "agent-context.md",
        context_dir / "file-index.json",
        context_dir / "repo-map.json",
    ]
    if all(path.exists() for path in required):
        return
    raise typer.BadParameter(
        "Missing LCE context. Run:\n\n"
        "lce init\n"
        "lce scan ."
    )
