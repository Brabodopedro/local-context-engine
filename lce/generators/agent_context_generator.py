from __future__ import annotations

from lce.models.context_models import FileIndex, RepoMap

AGENT_RULES = """# Agent Rules

- Read `.ai-context/agent-context.md` before making changes.
- Use `.ai-context/file-index.json` to locate relevant files.
- Do not modify environment files unless explicitly requested.
- Do not modify migrations unless explicitly requested.
- Prefer small, focused changes.
- Update tests when behavior changes.
- Update documentation when public behavior changes.
"""


def generate_agent_context(repo_map: RepoMap, file_index: FileIndex) -> str:
    important_files = file_index.files[:12]
    directories = repo_map.directories[:20]
    stack = repo_map.project.detected_stack or ["Unknown"]

    lines = [
        "# Agent Context",
        "",
        "## Project Overview",
        "",
        f"- Project: {repo_map.project.name}",
        f"- Root: {repo_map.project.root}",
        "",
        "## Detected Stack",
        "",
        *[f"- {item}" for item in stack],
        "",
        "## Repository Summary",
        "",
        f"- Total files seen: {repo_map.summary.total_files}",
        f"- Indexed files: {repo_map.summary.indexed_files}",
        f"- Ignored files: {repo_map.summary.ignored_files}",
        "",
        "## Main Directories",
        "",
    ]
    lines.extend(f"- `{directory.path}`: {directory.purpose}" for directory in directories)
    lines.extend(
        [
            "",
            "## Important Files",
            "",
        ]
    )
    lines.extend(
        f"- `{file.path}` ({file.language}, {file.size_lines} lines): {file.summary}"
        for file in important_files
    )
    lines.extend(
        [
            "",
            "## Agent Rules",
            "",
            "- Read `.ai-context/agent-context.md` before making changes.",
            "- Use `.ai-context/file-index.json` to locate relevant files.",
            "- Do not modify environment files unless explicitly requested.",
            "- Do not modify migrations unless explicitly requested.",
            "- Prefer small, focused changes.",
            "- Update tests when behavior changes.",
            "- Update documentation when public behavior changes.",
            "",
            "## Recommended Workflow For AI Agents",
            "",
            "1. Read this file first.",
            "2. Use `file-index.json` to locate relevant files.",
            "3. For a specific task, read the generated task context.",
            "4. Open only relevant source files before expanding the search.",
            "5. Avoid unrelated refactors.",
            "6. Update tests and documentation when behavior changes.",
            "",
        ]
    )
    return "\n".join(lines)
