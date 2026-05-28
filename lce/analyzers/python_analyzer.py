from __future__ import annotations

import ast
from pathlib import Path

from lce.analyzers.generic_analyzer import analyze_generic
from lce.models.context_models import FileInfo
from lce.utils.file_utils import read_text


def analyze_python(path: Path, relative_path: Path) -> FileInfo:
    info = analyze_generic(path, relative_path, "Python")
    content = read_text(path)
    try:
        tree = ast.parse(content)
    except SyntaxError:
        info.summary = f"Python file at {relative_path}; syntax could not be parsed"
        return info

    imports: set[str] = set()
    functions: list[str] = []
    classes: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)

    info.imports = sorted(import_name for import_name in imports if import_name)
    info.functions = sorted(functions)
    info.classes = sorted(classes)
    details = []
    if info.classes:
        details.append(f"{len(info.classes)} classes")
    if info.functions:
        details.append(f"{len(info.functions)} functions")
    info.summary = f"Python file at {relative_path}"
    if details:
        info.summary += f" with {', '.join(details)}"
    return info
