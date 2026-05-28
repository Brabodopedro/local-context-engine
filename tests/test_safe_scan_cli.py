from __future__ import annotations

from pathlib import Path

from lce.cli.doctor_cmd import doctor
from lce.cli.init_cmd import init
from lce.cli.scan_cmd import scan
from lce.scanner.scan_config import load_project_profile
from lce.utils.file_utils import read_json


def test_scan_metadata_includes_safe_scan_counters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init()
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / "video.mp4").write_bytes(b"video")
    (tmp_path / ".lceignore").write_text("outputs/\n", encoding="utf-8")
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "generated.py").write_text("VALUE = 1\n", encoding="utf-8")

    scan(Path("."))

    metadata = read_json(tmp_path / ".ai-context" / "metadata.json")
    assert metadata["indexed_files"] == 1
    assert metadata["ignored_files"] == 4
    assert metadata["ignored_sensitive_files"] == 1
    assert metadata["ignored_binary_files"] == 1
    assert metadata["skipped_large_files"] == 0
    assert metadata["lceignore_detected"] is True
    assert metadata["config_source"] == ".ai-context/config.yml"


def test_scan_respects_max_file_size_from_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init()
    config_path = tmp_path / ".ai-context" / "config.yml"
    config_path.write_text(
        "version: 1\n"
        "context_dir: .ai-context\n"
        "default_output: .ai-context\n"
        "scan:\n"
        "  max_file_size_kb: 1\n",
        encoding="utf-8",
    )
    (tmp_path / "large.py").write_text("x = '" + ("a" * 2048) + "'\n", encoding="utf-8")

    scan(Path("."))

    metadata = read_json(tmp_path / ".ai-context" / "metadata.json")
    assert metadata["indexed_files"] == 0
    assert metadata["skipped_large_files"] == 1


def test_doctor_reports_lceignore_status(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    init()
    (tmp_path / ".lceignore").write_text("outputs/\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    scan(Path("."))

    doctor()

    output = capsys.readouterr().out
    assert ".lceignore" in output
    assert "present" in output


def test_init_writes_selected_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    init(profile="ai-video")

    config = (tmp_path / ".ai-context" / "config.yml").read_text(encoding="utf-8")
    assert "profile: ai-video" in config
    assert load_project_profile(tmp_path / ".ai-context") == "ai-video"


def test_missing_profile_falls_back_to_generic(tmp_path: Path) -> None:
    context_dir = tmp_path / ".ai-context"
    context_dir.mkdir()
    (context_dir / "config.yml").write_text("version: 1\n", encoding="utf-8")

    assert load_project_profile(context_dir) == "generic"


def test_invalid_profile_falls_back_to_generic(tmp_path: Path) -> None:
    context_dir = tmp_path / ".ai-context"
    context_dir.mkdir()
    (context_dir / "config.yml").write_text("profile: strange\n", encoding="utf-8")

    assert load_project_profile(context_dir) == "generic"
