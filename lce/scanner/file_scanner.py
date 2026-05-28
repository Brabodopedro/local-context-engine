from __future__ import annotations

from dataclasses import dataclass
from os import walk
from pathlib import Path

from lce.analyzers.generic_analyzer import analyze_generic
from lce.analyzers.javascript_analyzer import analyze_javascript
from lce.analyzers.python_analyzer import analyze_python
from lce.models.context_models import FileInfo
from lce.scanner.ignore_rules import IgnoreReason, IgnoreRules, classify_ignore, load_ignore_rules
from lce.scanner.language_detector import detect_language, is_supported_file
from lce.scanner.scan_config import ScanConfig, load_scan_config


@dataclass(frozen=True)
class ScanResult:
    root: Path
    files: list[FileInfo]
    ignored_files: int
    total_files: int
    skipped_large_files: int
    ignored_sensitive_files: int
    ignored_binary_files: int
    lceignore_detected: bool
    config_source: str


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


def scan_repository(
    root: Path,
    ignore_rules: IgnoreRules | None = None,
    config: ScanConfig | None = None,
) -> ScanResult:
    root = root.resolve()
    rules = ignore_rules or load_ignore_rules(root)
    scan_config = config or load_scan_config()
    files: list[FileInfo] = []
    ignored_files = 0
    skipped_large_files = 0
    ignored_sensitive_files = 0
    ignored_binary_files = 0
    total_files = 0

    for current_root, dirnames, filenames in walk(root):
        current_path = Path(current_root)
        dirnames.sort()
        filenames.sort()
        for dirname in list(dirnames):
            directory_path = current_path / dirname
            ignore_reason = classify_ignore(directory_path, root, rules)
            if ignore_reason is not None:
                ignored_files += 1
                dirnames.remove(dirname)

        for filename in filenames:
            path = current_path / filename
            total_files += 1
            ignore_reason = classify_ignore(path, root, rules)
            if ignore_reason is not None:
                ignored_files += 1
                if ignore_reason == IgnoreReason.SENSITIVE:
                    ignored_sensitive_files += 1
                elif ignore_reason == IgnoreReason.BINARY:
                    ignored_binary_files += 1
                continue
            if path.stat().st_size > scan_config.max_file_size_bytes:
                ignored_files += 1
                skipped_large_files += 1
                continue
            if not is_supported_file(path):
                continue
            info = analyze_file(path, root)
            if info is not None:
                files.append(info)

    return ScanResult(
        root=root,
        files=files,
        ignored_files=ignored_files,
        total_files=total_files,
        skipped_large_files=skipped_large_files,
        ignored_sensitive_files=ignored_sensitive_files,
        ignored_binary_files=ignored_binary_files,
        lceignore_detected=rules.lceignore_detected,
        config_source=scan_config.config_source,
    )
