from __future__ import annotations

from lce.models.context_models import FileIndex, FileInfo


def generate_file_index(files: list[FileInfo]) -> FileIndex:
    return FileIndex(files=sorted(files, key=lambda file: file.path))
