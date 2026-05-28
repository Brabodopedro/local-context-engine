from __future__ import annotations

from pathlib import Path

import pytest
import typer

from lce.cli.init_cmd import init
from lce.cli.scan_cmd import scan
from lce.cli.spec_cmd import spec
from lce.utils.file_utils import read_json

SPEC_FILES = {
    "spec.md",
    "requirements.md",
    "technical-plan.md",
    "affected-context.json",
    "acceptance-criteria.md",
    "risks.md",
    "validation-checklist.md",
    "agent-prompt-local-llm.md",
}


def test_spec_generates_spec_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    init(profile="ai-video")
    worker_dir = tmp_path / "apps" / "workers" / "aethel_workers"
    worker_dir.mkdir(parents=True)
    (worker_dir / "rendering.py").write_text("def render():\n    pass\n", encoding="utf-8")
    (worker_dir / "youtube_upload.py").write_text(
        "def upload_private():\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "apps" / "workers" / "Dockerfile").write_text(
        "FROM python:3.12\n",
        encoding="utf-8",
    )
    scan(Path("."))

    spec("prepare YouTube upload integration skeleton after render")

    spec_dir = (
        tmp_path
        / ".ai-context"
        / "specs"
        / "prepare-youtube-upload-integration-skeleton-after-render"
    )
    assert spec_dir.exists()
    assert SPEC_FILES == {path.name for path in spec_dir.iterdir() if path.is_file()}

    spec_md = (spec_dir / "spec.md").read_text(encoding="utf-8")
    requirements_md = (spec_dir / "requirements.md").read_text(encoding="utf-8")
    technical_plan = (spec_dir / "technical-plan.md").read_text(encoding="utf-8")
    local_prompt = (spec_dir / "agent-prompt-local-llm.md").read_text(encoding="utf-8")
    affected_context = read_json(spec_dir / "affected-context.json")

    assert "## Project Profile" in spec_md
    assert "ai-video" in spec_md
    assert "# Requirements" in requirements_md
    assert "# Technical Plan" in technical_plan
    assert affected_context["slug"] == "prepare-youtube-upload-integration-skeleton-after-render"
    assert {"primary_files", "secondary_files", "context_files", "avoid_files"} <= set(
        affected_context
    )
    assert "Do not edit files yet." in local_prompt
    assert "Ask for approval before reading/editing source files." in local_prompt


def test_spec_fails_clearly_without_ai_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(typer.BadParameter) as error:
        spec("prepare YouTube upload integration skeleton after render")

    message = str(error.value)
    assert "Missing LCE context" in message
    assert "lce init" in message
    assert "lce scan ." in message
