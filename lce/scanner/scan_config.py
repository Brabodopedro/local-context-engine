from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_FILE_SIZE_KB = 500
DEFAULT_MAX_PRIMARY_FILES = 5
DEFAULT_MAX_SECONDARY_FILES = 8
DEFAULT_MAX_CONTEXT_FILES = 10
DEFAULT_MAX_AVOID_FILES = 20


@dataclass(frozen=True)
class ScanConfig:
    max_file_size_kb: int = DEFAULT_MAX_FILE_SIZE_KB
    config_source: str = "default"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_kb * 1024


@dataclass(frozen=True)
class TaskBudget:
    max_primary_files: int = DEFAULT_MAX_PRIMARY_FILES
    max_secondary_files: int = DEFAULT_MAX_SECONDARY_FILES
    max_context_files: int = DEFAULT_MAX_CONTEXT_FILES
    max_avoid_files: int = DEFAULT_MAX_AVOID_FILES


def load_scan_config(output_path: Path | None = None) -> ScanConfig:
    if output_path is None:
        return ScanConfig()
    config_path = output_path / "config.yml"
    if not config_path.exists():
        return ScanConfig()

    max_size = _read_nested_int(config_path, "scan", "max_file_size_kb")
    if max_size is None:
        return ScanConfig(config_source=str(config_path))
    return ScanConfig(max_file_size_kb=max_size, config_source=str(config_path))


def load_task_budget(output_path: Path | None = None) -> TaskBudget:
    if output_path is None:
        return TaskBudget()
    config_path = output_path / "config.yml"
    if not config_path.exists():
        return TaskBudget()

    return TaskBudget(
        max_primary_files=_read_nested_int(config_path, "task", "max_primary_files")
        or DEFAULT_MAX_PRIMARY_FILES,
        max_secondary_files=_read_nested_int(config_path, "task", "max_secondary_files")
        or DEFAULT_MAX_SECONDARY_FILES,
        max_context_files=_read_nested_int(config_path, "task", "max_context_files")
        or DEFAULT_MAX_CONTEXT_FILES,
        max_avoid_files=_read_nested_int(config_path, "task", "max_avoid_files")
        or DEFAULT_MAX_AVOID_FILES,
    )


def _read_nested_int(path: Path, section: str, key: str) -> int | None:
    current_section: str | None = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith((" ", "\t")) and stripped.endswith(":"):
            current_section = stripped[:-1]
            continue
        if current_section == section and stripped.startswith(f"{key}:"):
            _, value = stripped.split(":", 1)
            try:
                parsed = int(value.strip())
            except ValueError:
                return None
            return parsed if parsed > 0 else None
    return None
