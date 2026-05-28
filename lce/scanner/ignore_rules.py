from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path


class IgnoreReason(StrEnum):
    DEFAULT = "default"
    SENSITIVE = "sensitive"
    BINARY = "binary"
    LCEIGNORE = "lceignore"


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".ai-context",
    "node_modules",
    "dist",
    "build",
    "venv",
    ".venv",
    "__pycache__",
    "coverage",
    "vendor",
    "storage",
    "tmp",
    "logs",
    ".next",
    ".turbo",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

DEFAULT_SENSITIVE_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "secrets.yml",
    "secrets.yaml",
}

DEFAULT_BINARY_PATTERNS = {
    "*.mp4",
    "*.mov",
    "*.avi",
    "*.mkv",
    "*.mp3",
    "*.wav",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.webp",
    "*.gif",
    "*.pdf",
    "*.sqlite",
    "*.db",
}


@dataclass(frozen=True)
class IgnoreRules:
    ignored_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_IGNORED_DIRS))
    sensitive_patterns: set[str] = field(default_factory=lambda: set(DEFAULT_SENSITIVE_PATTERNS))
    binary_patterns: set[str] = field(default_factory=lambda: set(DEFAULT_BINARY_PATTERNS))
    lceignore_patterns: list[str] = field(default_factory=list)
    lceignore_detected: bool = False


def load_ignore_rules(root: Path) -> IgnoreRules:
    lceignore_path = root / ".lceignore"
    patterns = _load_lceignore_patterns(lceignore_path)
    return IgnoreRules(
        lceignore_patterns=patterns,
        lceignore_detected=lceignore_path.exists(),
    )


def classify_ignore(path: Path, root: Path, rules: IgnoreRules) -> IgnoreReason | None:
    relative_path = _relative_posix(path, root)
    parts = relative_path.split("/")
    name = path.name

    if any(part in rules.ignored_dirs for part in parts):
        return IgnoreReason.DEFAULT
    if _matches_any(relative_path, name, rules.sensitive_patterns):
        return IgnoreReason.SENSITIVE
    if _matches_any(relative_path, name, rules.binary_patterns):
        return IgnoreReason.BINARY
    if _matches_any(relative_path, name, rules.lceignore_patterns):
        return IgnoreReason.LCEIGNORE
    return None


def should_ignore(path: Path, root: Path, rules: IgnoreRules | None = None) -> bool:
    return classify_ignore(path, root, rules or load_ignore_rules(root)) is not None


def _load_lceignore_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def _matches_any(relative_path: str, name: str, patterns: set[str] | list[str]) -> bool:
    return any(_matches_pattern(relative_path, name, pattern) for pattern in patterns)


def _matches_pattern(relative_path: str, name: str, pattern: str) -> bool:
    normalized = pattern.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized:
        return False

    if normalized.endswith("/"):
        directory = normalized.rstrip("/")
        if "/" in directory:
            return relative_path == directory or relative_path.startswith(f"{directory}/")
        return directory in relative_path.split("/")

    if any(char in normalized for char in "*?[]"):
        return fnmatch(name, normalized) or fnmatch(relative_path, normalized)

    if "/" in normalized:
        return relative_path == normalized

    return name == normalized or normalized in relative_path.split("/")


def _relative_posix(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return relative.as_posix()
