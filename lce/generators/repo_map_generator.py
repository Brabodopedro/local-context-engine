from __future__ import annotations

from collections import Counter
from pathlib import Path

from lce.models.context_models import (
    DirectoryInfo,
    ProjectInfo,
    RepoMap,
    RepoSummary,
)
from lce.scanner.file_scanner import ScanResult

STACK_MARKERS = {
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "package.json": "Node.js",
    "composer.json": "PHP",
    "go.mod": "Go",
    "pom.xml": "Java",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
}


def detect_stack(root: Path, files: list[str]) -> list[str]:
    detected = {stack for marker, stack in STACK_MARKERS.items() if (root / marker).exists()}
    languages = Counter(path.rsplit(".", 1)[-1] for path in files if "." in path)
    if languages.get("py"):
        detected.add("Python")
    if languages.get("ts") or languages.get("tsx"):
        detected.add("TypeScript")
    if languages.get("js") or languages.get("jsx"):
        detected.add("JavaScript")
    return sorted(detected)


def describe_directory(path: str) -> str:
    name = Path(path).name.lower()
    if name in {"tests", "test", "__tests__"}:
        return "Test suite"
    if name in {"docs", "documentation"}:
        return "Documentation"
    if name in {"src", "app", "lib"}:
        return "Application source"
    if name in {"cli", "commands"}:
        return "Command-line interface code"
    if name in {"models", "schemas"}:
        return "Data models and schemas"
    if name in {"config", "settings"}:
        return "Configuration"
    return "Repository directory"


def generate_repo_map(scan: ScanResult) -> RepoMap:
    file_paths = [file.path for file in scan.files]
    directory_paths = sorted(
        {str(Path(path).parent) for path in file_paths if str(Path(path).parent) != "."}
    )
    return RepoMap(
        project=ProjectInfo(
            name=scan.root.name,
            root=str(scan.root),
            detected_stack=detect_stack(scan.root, file_paths),
        ),
        summary=RepoSummary(
            total_files=scan.total_files,
            indexed_files=len(scan.files),
            ignored_files=scan.ignored_files,
        ),
        directories=[
            DirectoryInfo(path=directory, purpose=describe_directory(directory))
            for directory in directory_paths
        ],
    )
