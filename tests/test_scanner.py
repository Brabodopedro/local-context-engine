from __future__ import annotations

from pathlib import Path

from lce.scanner.file_scanner import scan_repository


def test_scan_repository_extracts_python_metadata(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "class App:\n"
        "    pass\n\n"
        "def run():\n"
        "    return Path(os.getcwd())\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.ignored_files == 1
    assert len(result.files) == 1
    info = result.files[0]
    assert info.path == "app.py"
    assert info.language == "Python"
    assert "os" in info.imports
    assert "App" in info.classes
    assert "run" in info.functions


def test_scan_repository_ignores_node_modules(tmp_path: Path) -> None:
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    (nested / "index.js").write_text("export const value = 1\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.files == []
    assert result.ignored_files == 1


def test_scan_repository_ignores_ai_context(tmp_path: Path) -> None:
    generated = tmp_path / ".ai-context"
    generated.mkdir()
    (generated / "agent-context.md").write_text("# Agent Context\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [file.path for file in result.files] == ["app.py"]
    assert result.ignored_files == 1
