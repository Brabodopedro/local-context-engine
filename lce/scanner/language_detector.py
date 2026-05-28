from __future__ import annotations

from pathlib import Path

SUPPORTED_FILENAMES = {
    "Dockerfile": "Dockerfile",
    "docker-compose.yml": "YAML",
    "docker-compose.yaml": "YAML",
}

SUPPORTED_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript JSX",
    ".ts": "TypeScript",
    ".tsx": "TypeScript TSX",
    ".php": "PHP",
    ".go": "Go",
    ".java": "Java",
    ".cs": "C#",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".md": "Markdown",
    ".toml": "TOML",
    ".ini": "INI",
    ".dockerfile": "Dockerfile",
}


def detect_language(path: Path | str) -> str | None:
    file_path = Path(path)
    if file_path.name in SUPPORTED_FILENAMES:
        return SUPPORTED_FILENAMES[file_path.name]
    return SUPPORTED_EXTENSIONS.get(file_path.suffix.lower())


def is_supported_file(path: Path | str) -> bool:
    return detect_language(path) is not None
