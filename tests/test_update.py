from __future__ import annotations

from pathlib import Path

from lce.cli.init_cmd import init
from lce.cli.scan_cmd import scan
from lce.cli.update_cmd import update
from lce.utils.file_utils import read_json


def initialize_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init()
    scan(Path("."))


def test_update_detects_added_file(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    initialize_context(tmp_path, monkeypatch)
    (tmp_path / "auth.py").write_text("def login():\n    return True\n", encoding="utf-8")

    update()

    data = read_json(tmp_path / ".ai-context" / "last-update.json")
    assert data["added_files"] == ["auth.py"]
    assert data["modified_files"] == []
    assert data["removed_files"] == []


def test_update_detects_modified_file_and_unchanged_count(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    (tmp_path / "stable.py").write_text("VALUE = 1\n", encoding="utf-8")
    initialize_context(tmp_path, monkeypatch)
    (tmp_path / "app.py").write_text("def run():\n    return False\n", encoding="utf-8")

    update()

    data = read_json(tmp_path / ".ai-context" / "last-update.json")
    assert data["modified_files"] == ["app.py"]
    assert data["unchanged_files_count"] == 1


def test_update_detects_removed_file(tmp_path: Path, monkeypatch) -> None:
    removed = tmp_path / "old.py"
    removed.write_text("def old():\n    return True\n", encoding="utf-8")
    initialize_context(tmp_path, monkeypatch)
    removed.unlink()

    update()

    data = read_json(tmp_path / ".ai-context" / "last-update.json")
    assert data["removed_files"] == ["old.py"]


def test_update_generates_reports_and_updates_metadata(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    initialize_context(tmp_path, monkeypatch)
    (tmp_path / "new.py").write_text("def new():\n    return True\n", encoding="utf-8")
    (tmp_path / "clip.mp4").write_bytes(b"video")

    update()

    context_dir = tmp_path / ".ai-context"
    metadata = read_json(context_dir / "metadata.json")
    update_data = read_json(context_dir / "last-update.json")
    assert (context_dir / "last-update.md").exists()
    assert (context_dir / "last-update.json").exists()
    assert "updated_at" in metadata
    assert metadata["last_update_added_files"] == ["new.py"]
    assert metadata["last_update_modified_files"] == []
    assert metadata["last_update_removed_files"] == []
    assert metadata["ignored_binary_files"] == 1
    assert update_data["ignored_binary_files"] == 1
    assert update_data["lceignore_detected"] is False


def test_update_command_is_registered() -> None:
    from lce.main import app

    command_names = {command.name for command in app.registered_commands}
    assert "update" in command_names
