from __future__ import annotations

from pathlib import Path

DEFAULT_IGNORED_NAMES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "venv",
    ".venv",
    "__pycache__",
    "coverage",
    "vendor",
    "storage",
    ".next",
    ".turbo",
    ".cache",
    ".ai-context",
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}


def should_ignore(path: Path, root: Path, ignored_names: set[str] | None = None) -> bool:
    ignored = ignored_names or DEFAULT_IGNORED_NAMES
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part in ignored for part in relative.parts)
