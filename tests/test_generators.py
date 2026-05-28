from __future__ import annotations

from pathlib import Path

from lce.generators.agent_context_generator import generate_agent_context
from lce.generators.file_index_generator import generate_file_index
from lce.generators.repo_map_generator import generate_repo_map
from lce.scanner.file_scanner import scan_repository


def test_generators_create_repo_map_and_agent_context(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")

    scan = scan_repository(tmp_path)
    repo_map = generate_repo_map(scan)
    file_index = generate_file_index(scan.files)
    context = generate_agent_context(repo_map, file_index)

    assert repo_map.project.name == tmp_path.name
    assert "Python" in repo_map.project.detected_stack
    assert file_index.files[0].path == "main.py"
    assert "# Agent Context" in context
    assert "## Recommended Workflow For AI Agents" in context
