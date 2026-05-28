from __future__ import annotations

from pathlib import Path

from lce.cli.init_cmd import init
from lce.cli.prompt_cmd import prompt
from lce.cli.scan_cmd import scan
from lce.cli.task_cmd import task
from lce.utils.file_utils import read_json, write_json


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


def test_prompt_does_not_fallback_when_primary_files_is_empty(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    task_dir = tmp_path / ".ai-context" / "tasks" / "empty-primary"
    task_dir.mkdir(parents=True)
    write_json(
        task_dir / "relevant-files.json",
        {
            "task": "add YouTube private upload after render",
            "slug": "empty-primary",
            "primary_files": [],
            "secondary_files": [
                {
                    "path": "apps/workers/aethel_workers/ffmpeg.py",
                    "role": "source",
                    "reason": "Secondary helper.",
                    "confidence": 0.5,
                }
            ],
            "context_files": [],
            "avoid_files": [],
            "files": [
                {
                    "path": "apps/workers/aethel_workers/ffmpeg.py",
                    "role": "source",
                    "reason": "Compatibility list.",
                    "confidence": 0.5,
                }
            ],
        },
    )

    prompt(target="cline")

    output = capsys.readouterr().out
    assert "Inspect primary files first" in output
    assert "- None" in output
    assert "Inspect secondary files only if needed" in output


def test_ai_video_relevant_files_json_includes_module_role(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    init(profile="ai-video")
    worker_dir = tmp_path / "apps" / "workers" / "aethel_workers"
    api_dir = tmp_path / "apps" / "api" / "aethel_api"
    shared_dir = tmp_path / "packages" / "shared" / "aethel_shared"
    worker_dir.mkdir(parents=True)
    api_dir.mkdir(parents=True)
    shared_dir.mkdir(parents=True)
    (worker_dir / "rendering.py").write_text("def render():\n    pass\n", encoding="utf-8")
    (worker_dir / "worker.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (api_dir / "outputs_api.py").write_text("def output_status():\n    pass\n", encoding="utf-8")
    (shared_dir / "models.py").write_text("class VideoOutput:\n    pass\n", encoding="utf-8")
    scan(Path("."))

    task("add YouTube private upload after render")

    data = read_json(
        tmp_path
        / ".ai-context"
        / "tasks"
        / "add-youtube-private-upload-after-render"
        / "relevant-files.json"
    )
    module_roles = {file["path"]: file["module_role"] for file in data["primary_files"]}
    assert data["project_profile"] == "ai-video"
    assert {"render", "post-render", "storage/upload"} <= set(data["detected_pipeline_phases"])
    assert module_roles["apps/workers/aethel_workers/rendering.py"] == "render_orchestrator"
    assert module_roles["apps/workers/aethel_workers/worker.py"] == "worker_entrypoint"
    assert module_roles["apps/api/aethel_api/outputs_api.py"] == "output_api"
    assert module_roles["packages/shared/aethel_shared/models.py"] == "shared_models"


def test_local_llm_and_compact_prompts_are_written(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    init(profile="ai-video")
    worker_dir = tmp_path / "apps" / "workers" / "aethel_workers"
    worker_dir.mkdir(parents=True)
    (worker_dir / "rendering.py").write_text("def render():\n    pass\n", encoding="utf-8")
    scan(Path("."))
    task("add YouTube private upload after render")

    prompt(target="local-llm")
    prompt(target="cline", compact=True)

    task_dir = tmp_path / ".ai-context" / "tasks" / "add-youtube-private-upload-after-render"
    assert (task_dir / "agent-prompt-local-llm.md").exists()
    assert (task_dir / "agent-prompt-cline-compact.md").exists()
    compact_prompt = (task_dir / "agent-prompt-local-llm.md").read_text(encoding="utf-8")
    assert "First return a concise implementation plan before editing." in compact_prompt
    assert "Do not open all files upfront." in compact_prompt
