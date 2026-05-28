from __future__ import annotations

import re
from pathlib import Path

from lce.analyzers.generic_analyzer import analyze_generic
from lce.models.context_models import FileInfo
from lce.utils.file_utils import read_text

IMPORT_RE = re.compile(r"^\s*import\s+(?:.+?\s+from\s+)?[\"']([^\"']+)[\"']", re.MULTILINE)
REQUIRE_RE = re.compile(r"require\([\"']([^\"']+)[\"']\)")
FUNCTION_RE = re.compile(
    r"(?:function\s+([A-Za-z_$][\w$]*)|const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(|"
    r"export\s+function\s+([A-Za-z_$][\w$]*))"
)
CLASS_RE = re.compile(r"(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")
EXPORT_RE = re.compile(
    r"export\s+(?:default\s+)?(?:class|function|const|let|var)\s+([A-Za-z_$][\w$]*)|"
    r"export\s*\{([^}]+)\}"
)


def analyze_javascript(path: Path, relative_path: Path, language: str) -> FileInfo:
    info = analyze_generic(path, relative_path, language)
    content = read_text(path)

    imports = set(IMPORT_RE.findall(content))
    imports.update(REQUIRE_RE.findall(content))

    functions: list[str] = []
    for match in FUNCTION_RE.findall(content):
        functions.extend(name for name in match if name)

    classes = CLASS_RE.findall(content)
    exports: list[str] = []
    for direct, grouped in EXPORT_RE.findall(content):
        if direct:
            exports.append(direct)
        if grouped:
            exports.extend(item.strip().split(" as ")[0].strip() for item in grouped.split(","))

    info.imports = sorted(imports)
    info.functions = sorted(set(functions))
    info.classes = sorted(set(classes))
    info.exports = sorted(export for export in set(exports) if export)
    info.summary = f"{language} file at {relative_path}"
    return info
