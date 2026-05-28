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
from lce.scanner.file_scanner import scan_repository
from lce.scanner.scan_config import load_scan_config
from lce.store.context_store import ContextStore

console = Console()


def scan(
    path: Annotated[Path, typer.Argument(help="Repository path to scan.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output context folder."),
    ] = Path(".ai-context"),
) -> None:
    """Scan a repository and generate base context files."""
    if not path.exists():
        raise typer.BadParameter(f"Path does not exist: {path}")

    scan_config = load_scan_config(output)
    result = scan_repository(path, config=scan_config)
    file_index = generate_file_index(result.files)
    repo_map = generate_repo_map(result)
    store = ContextStore(output)
    generated_at = datetime.now(UTC).isoformat()
    metadata = {
        "generated_at": generated_at,
        "updated_at": generated_at,
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
    }

    store.write_json("repo-map.json", repo_map)
    store.write_json("file-index.json", file_index)
    store.write_text("agent-context.md", generate_agent_context(repo_map, file_index))
    store.write_json("metadata.json", metadata)

    table = Table(title="Local Context Engine Scan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Indexed files", str(len(result.files)))
    table.add_row("Ignored files", str(result.ignored_files))
    table.add_row("Skipped large files", str(result.skipped_large_files))
    table.add_row("Ignored sensitive files", str(result.ignored_sensitive_files))
    table.add_row("Ignored binary files", str(result.ignored_binary_files))
    table.add_row("Output path", str(output))
    table.add_row(".lceignore detected", "yes" if result.lceignore_detected else "no")
    console.print(table)
