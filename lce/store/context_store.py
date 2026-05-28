from __future__ import annotations

from pathlib import Path

from lce.models.context_models import FileIndex, RepoMap
from lce.utils.file_utils import ensure_dir, read_json, write_json, write_text


class ContextStore:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        ensure_dir(self.output_path)

    def path(self, *parts: str) -> Path:
        return self.output_path.joinpath(*parts)

    def write_json(self, name: str, data: object) -> None:
        if hasattr(data, "model_dump"):
            data = data.model_dump()
        write_json(self.path(name), data)

    def write_text(self, name: str, content: str) -> None:
        write_text(self.path(name), content)

    def read_file_index(self) -> FileIndex:
        return FileIndex.model_validate(read_json(self.path("file-index.json")))

    def read_repo_map(self) -> RepoMap:
        return RepoMap.model_validate(read_json(self.path("repo-map.json")))
