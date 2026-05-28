from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from lce import __version__
from lce.generators.agent_context_generator import generate_agent_context
from lce.generators.file_index_generator import generate_file_index
from lce.generators.repo_map_generator import generate_repo_map
from lce.generators.update_generator import compare_file_indexes, render_last_update
from lce.models.context_models import UpdateSummary
from lce.scanner.file_scanner import scan_repository
from lce.scanner.scan_config import load_scan_config
from lce.store.context_store import ContextStore

console = Console()


def update(
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Repository root to update."),
    ] = Path("."),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output context folder."),
    ] = Path(".ai-context"),
) -> None:
    """Refresh .ai-context after files are added, modified, or removed."""
    if not output.exists():
        raise typer.BadParameter("Missing .ai-context/. Run `lce init` and `lce scan .` first.")
    if not (output / "file-index.json").exists():
        raise typer.BadParameter("Missing .ai-context/file-index.json. Run `lce scan .` first.")

    store = ContextStore(output)
    previous_index = store.read_file_index()
    scan_config = load_scan_config(output)
    result = scan_repository(path, config=scan_config)
    current_index = generate_file_index(result.files)
    repo_map = generate_repo_map(result)
    updated_at = datetime.now(UTC).isoformat()
    summary = compare_file_indexes(
        previous_index=previous_index,
        current_index=current_index,
        updated_at=updated_at,
        ignored_files=result.ignored_files,
        skipped_large_files=result.skipped_large_files,
        ignored_sensitive_files=result.ignored_sensitive_files,
        ignored_binary_files=result.ignored_binary_files,
        lceignore_detected=result.lceignore_detected,
    )
    metadata = {
        "generated_at": updated_at,
        "updated_at": updated_at,
        "lce_version": __version__,
        "root_path": str(result.root),
        "output_path": str(output.resolve()),
        "indexed_files": len(result.files),
        "ignored_files": result.ignored_files,
        "skipped_large_files": result.skipped_large_files,
        "ignored_sensitive_files": result.ignored_sensitive_files,
        "ignored_binary_files": result.ignored_binary_files,
        "lceignore_detected": result.lceignore_detected,
        "config_source": result.config_source,
        "last_update_added_files": summary.added_files,
        "last_update_modified_files": summary.modified_files,
        "last_update_removed_files": summary.removed_files,
    }

    store.write_json("repo-map.json", repo_map)
    store.write_json("file-index.json", current_index)
    store.write_text("agent-context.md", generate_agent_context(repo_map, current_index))
    store.write_json("metadata.json", metadata)
    store.write_json("last-update.json", summary)
    store.write_text("last-update.md", render_last_update(summary))

    _print_update_summary(summary)


def _print_update_summary(summary: UpdateSummary) -> None:
    table = Table(title="Local Context Engine Update")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Added files", str(len(summary.added_files)))
    table.add_row("Modified files", str(len(summary.modified_files)))
    table.add_row("Removed files", str(len(summary.removed_files)))
    table.add_row("Indexed files", str(summary.indexed_files))
    table.add_row("Ignored files", str(summary.ignored_files))
    table.add_row("Skipped large files", str(summary.skipped_large_files))
    table.add_row("Ignored sensitive files", str(summary.ignored_sensitive_files))
    table.add_row("Ignored binary files", str(summary.ignored_binary_files))
    table.add_row(".lceignore detected", "yes" if summary.lceignore_detected else "no")
    console.print(table)

    changed_files = summary.added_files + summary.modified_files + summary.removed_files
    if not changed_files:
        console.print("[green]No indexed file changes detected.[/green]")
    elif len(changed_files) <= 20:
        console.print("[bold]Changed files:[/bold]")
        for path in summary.added_files:
            console.print(f"[green]+[/green] {path}")
        for path in summary.modified_files:
            console.print(f"[yellow]~[/yellow] {path}")
        for path in summary.removed_files:
            console.print(f"[red]-[/red] {path}")
    else:
        console.print(
            f"[yellow]{len(changed_files)} changed files. "
            "See .ai-context/last-update.md.[/yellow]"
        )
