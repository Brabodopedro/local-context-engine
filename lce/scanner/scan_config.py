from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_FILE_SIZE_KB = 500


@dataclass(frozen=True)
class ScanConfig:
    max_file_size_kb: int = DEFAULT_MAX_FILE_SIZE_KB
    config_source: str = "default"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_kb * 1024


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
