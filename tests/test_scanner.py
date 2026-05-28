from __future__ import annotations

from pathlib import Path

from lce.scanner.file_scanner import scan_repository
from lce.scanner.scan_config import ScanConfig


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


def test_lceignore_ignores_custom_directory(tmp_path: Path) -> None:
    ignored_dir = tmp_path / "outputs"
    ignored_dir.mkdir()
    (ignored_dir / "generated.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".lceignore").write_text("outputs/\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.files == []
    assert result.ignored_files == 1
    assert result.lceignore_detected


def test_lceignore_ignores_wildcard_extension(tmp_path: Path) -> None:
    (tmp_path / "debug.log").write_text("log line\n", encoding="utf-8")
    (tmp_path / ".lceignore").write_text("*.log\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.files == []
    assert result.ignored_files == 1


def test_lceignore_ignores_nested_path(tmp_path: Path) -> None:
    nested = tmp_path / "frontend" / "generated"
    nested.mkdir(parents=True)
    (nested / "bundle.js").write_text("export const value = 1\n", encoding="utf-8")
    (tmp_path / ".lceignore").write_text("frontend/generated/\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.files == []
    assert result.ignored_files == 1


def test_lceignore_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "drop.tmp").write_text("temporary\n", encoding="utf-8")
    (tmp_path / ".lceignore").write_text("# comment\n\n*.tmp\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [file.path for file in result.files] == ["keep.py"]
    assert result.ignored_files == 1


def test_sensitive_and_binary_files_are_ignored_by_default(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / "clip.mp4").write_bytes(b"video")
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert [file.path for file in result.files] == ["app.py"]
    assert result.ignored_sensitive_files == 1
    assert result.ignored_binary_files == 1
    assert result.ignored_files == 2


def test_large_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "large.py").write_text("x = '" + ("a" * 2048) + "'\n", encoding="utf-8")

    result = scan_repository(tmp_path, config=ScanConfig(max_file_size_kb=1))

    assert result.files == []
    assert result.skipped_large_files == 1
    assert result.ignored_files == 1
