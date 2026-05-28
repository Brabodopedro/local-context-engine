from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from lce.utils.file_utils import read_json

console = Console()

REQUIRED_FILES = [
    "config.yml",
    "agent-context.md",
    "file-index.json",
    "repo-map.json",
    "metadata.json",
]

SAFE_SCAN_COUNTERS = [
    "skipped_large_files",
    "ignored_sensitive_files",
    "ignored_binary_files",
    "lceignore_detected",
    "config_source",
]


def doctor(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Context folder."),
    ] = Path(".ai-context"),
) -> None:
    """Check whether .ai-context is healthy."""
    table = Table(title="Local Context Engine Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    if not output.exists():
        table.add_row(".ai-context exists", "[red]missing[/red]", str(output))
        console.print(table)
        raise typer.Exit(code=1)

    table.add_row(".ai-context exists", "[green]ok[/green]", str(output))
    lceignore_path = Path(".lceignore")
    table.add_row(
        ".lceignore",
        "[green]present[/green]" if lceignore_path.exists() else "[yellow]missing[/yellow]",
        str(lceignore_path),
    )
    missing = []
    for name in REQUIRED_FILES:
        exists = (output / name).exists()
        if not exists:
            missing.append(name)
        table.add_row(name, "[green]ok[/green]" if exists else "[yellow]missing[/yellow]", "")

    tasks_dir = output / "tasks"
    task_count = (
        len([path for path in tasks_dir.iterdir() if path.is_dir()])
        if tasks_dir.exists()
        else 0
    )
    table.add_row(
        "task folders",
        "[green]ok[/green]" if task_count else "[yellow]none[/yellow]",
        str(task_count),
    )

    warnings = []
    metadata_path = output / "metadata.json"
    file_index_path = output / "file-index.json"
    if "metadata.json" in missing or "file-index.json" in missing:
        warnings.append("No scan has been run or scan output is incomplete.")
    elif metadata_path.exists() and file_index_path.exists():
        metadata = read_json(metadata_path)
        file_index = read_json(file_index_path)
        skipped_large = metadata.get("skipped_large_files", 0)
        ignored_sensitive = metadata.get("ignored_sensitive_files", 0)
        ignored_binary = metadata.get("ignored_binary_files", 0)
        table.add_row("skipped large files", "[green]ok[/green]", str(skipped_large))
        table.add_row("ignored sensitive files", "[green]ok[/green]", str(ignored_sensitive))
        table.add_row("ignored binary files", "[green]ok[/green]", str(ignored_binary))

        if metadata.get("indexed_files", 0) == 0 or not file_index.get("files"):
            warnings.append("Context looks empty.")
        if not file_index.get("files"):
            warnings.append("file-index.json has zero files.")
        missing_counters = [key for key in SAFE_SCAN_COUNTERS if key not in metadata]
        if missing_counters:
            warnings.append(
                "metadata.json is missing safe scan counters: "
                + ", ".join(missing_counters)
            )
        if not lceignore_path.exists() and ignored_binary > 0:
            warnings.append(
                ".lceignore is missing while heavy/binary files were detected. "
                "Consider adding project-specific exclusions."
            )

    console.print(table)
    for warning in warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")

    if missing:
        raise typer.Exit(code=1)
