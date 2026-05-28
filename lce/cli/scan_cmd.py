from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from lce import __version__
from lce.generators.agent_context_generator import generate_agent_context
from lce.generators.file_index_generator import generate_file_index
from lce.generators.repo_map_generator import generate_repo_map
from lce.scanner.file_scanner import scan_repository
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

    result = scan_repository(path)
    file_index = generate_file_index(result.files)
    repo_map = generate_repo_map(result)
    store = ContextStore(output)
    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "lce_version": __version__,
        "root_path": str(result.root),
        "output_path": str(output.resolve()),
        "indexed_files": len(result.files),
        "ignored_files": result.ignored_files,
    }

    store.write_json("repo-map.json", repo_map)
    store.write_json("file-index.json", file_index)
    store.write_text("agent-context.md", generate_agent_context(repo_map, file_index))
    store.write_json("metadata.json", metadata)

    console.print(f"[green]Scanned {result.root}[/green]")
    console.print(f"Indexed files: [bold]{len(result.files)}[/bold]")
    console.print(f"Ignored files: [bold]{result.ignored_files}[/bold]")
    console.print(f"Output: [bold]{output}[/bold]")
