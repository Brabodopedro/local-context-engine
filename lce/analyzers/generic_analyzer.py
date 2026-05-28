from __future__ import annotations

from pathlib import Path

from lce.models.context_models import FileInfo
from lce.utils.file_utils import content_hash, read_text


def build_tags(path: Path) -> list[str]:
    parts = [part.lower() for part in path.parts]
    name = path.stem.lower()
    tags = set(parts + [name])
    for keyword in (
        "test",
        "auth",
        "user",
        "api",
        "cli",
        "config",
        "docker",
        "database",
        "migration",
        "middleware",
        "service",
        "model",
    ):
        if keyword in str(path).lower():
            tags.add(keyword)
    return sorted(tag for tag in tags if tag)


def analyze_generic(path: Path, relative_path: Path, language: str) -> FileInfo:
    content = read_text(path)
    lines = content.splitlines()
    summary = f"{language} file at {relative_path}"
    return FileInfo(
        path=relative_path.as_posix(),
        language=language,
        size_lines=len(lines),
        content_hash=content_hash(path),
        summary=summary,
        tags=build_tags(relative_path),
    )
