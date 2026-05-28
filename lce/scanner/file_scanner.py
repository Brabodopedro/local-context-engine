from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lce.analyzers.generic_analyzer import analyze_generic
from lce.analyzers.javascript_analyzer import analyze_javascript
from lce.analyzers.python_analyzer import analyze_python
from lce.models.context_models import FileInfo
from lce.scanner.ignore_rules import DEFAULT_IGNORED_NAMES, should_ignore
from lce.scanner.language_detector import detect_language, is_supported_file


@dataclass(frozen=True)
class ScanResult:
    root: Path
    files: list[FileInfo]
    ignored_files: int
    total_files: int


def analyze_file(path: Path, root: Path) -> FileInfo | None:
    language = detect_language(path)
    if language is None:
        return None
    relative_path = path.relative_to(root)
    if language == "Python":
        return analyze_python(path, relative_path)
    if language.startswith(("JavaScript", "TypeScript")):
        return analyze_javascript(path, relative_path, language)
    return analyze_generic(path, relative_path, language)


def scan_repository(root: Path, ignored_names: set[str] | None = None) -> ScanResult:
    root = root.resolve()
    ignored = ignored_names or DEFAULT_IGNORED_NAMES
    files: list[FileInfo] = []
    ignored_files = 0
    total_files = 0

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        total_files += 1
        if should_ignore(path, root, ignored):
            ignored_files += 1
            continue
        if not is_supported_file(path):
            continue
        info = analyze_file(path, root)
        if info is not None:
            files.append(info)

    return ScanResult(root=root, files=files, ignored_files=ignored_files, total_files=total_files)
