from __future__ import annotations

from pathlib import Path

from lce.cli.init_cmd import init
from lce.cli.scan_cmd import scan
from lce.cli.task_cmd import task
from lce.utils.file_utils import read_json


def test_task_writes_categorized_relevant_files_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init()
    worker_dir = tmp_path / "apps" / "workers" / "aethel_workers"
    worker_dir.mkdir(parents=True)
    (worker_dir / "rendering.py").write_text("def render_video():\n    pass\n", encoding="utf-8")
    (worker_dir / "youtube_upload.py").write_text(
        "def upload_private():\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "apps" / "workers" / "Dockerfile").write_text(
        "FROM python:3.12\n",
        encoding="utf-8",
    )
    scan(Path("."))

    task("add YouTube private upload after render")

    data = read_json(
        tmp_path
        / ".ai-context"
        / "tasks"
        / "add-youtube-private-upload-after-render"
        / "relevant-files.json"
    )
    expected_keys = {"primary_files", "secondary_files", "context_files", "avoid_files", "files"}
    assert expected_keys <= set(data)
    assert {file["path"] for file in data["primary_files"]} == {
        "apps/workers/aethel_workers/youtube_upload.py",
        "apps/workers/aethel_workers/rendering.py",
    }
    assert data["files"] == data["primary_files"]
