from __future__ import annotations

from lce.models.context_models import FileFingerprint, FileIndex, UpdateSummary


def compare_file_indexes(
    previous_index: FileIndex,
    current_index: FileIndex,
    updated_at: str,
    ignored_files: int,
    skipped_large_files: int = 0,
    ignored_sensitive_files: int = 0,
    ignored_binary_files: int = 0,
    lceignore_detected: bool = False,
) -> UpdateSummary:
    previous_by_path = _fingerprints_by_path(previous_index)
    current_by_path = _fingerprints_by_path(current_index)

    previous_paths = set(previous_by_path)
    current_paths = set(current_by_path)
    added_files = sorted(current_paths - previous_paths)
    removed_files = sorted(previous_paths - current_paths)
    shared_paths = previous_paths & current_paths

    modified_files = sorted(
        path
        for path in shared_paths
        if previous_by_path[path].content_hash != current_by_path[path].content_hash
    )
    unchanged_files_count = len(shared_paths) - len(modified_files)

    return UpdateSummary(
        updated_at=updated_at,
        added_files=added_files,
        modified_files=modified_files,
        removed_files=removed_files,
        unchanged_files_count=unchanged_files_count,
        indexed_files=len(current_index.files),
        ignored_files=ignored_files,
        skipped_large_files=skipped_large_files,
        ignored_sensitive_files=ignored_sensitive_files,
        ignored_binary_files=ignored_binary_files,
        lceignore_detected=lceignore_detected,
    )


def _fingerprints_by_path(file_index: FileIndex) -> dict[str, FileFingerprint]:
    return {
        file.path: FileFingerprint(
            path=file.path,
            size_lines=file.size_lines,
            content_hash=file.content_hash,
        )
        for file in file_index.files
    }


def render_last_update(summary: UpdateSummary) -> str:
    return "\n".join(
        [
            "# Last Context Update",
            "",
            f"Updated at: {summary.updated_at}",
            "",
            "## Added Files",
            "",
            *_render_file_list(summary.added_files),
            "",
            "## Modified Files",
            "",
            *_render_file_list(summary.modified_files),
            "",
            "## Removed Files",
            "",
            *_render_file_list(summary.removed_files),
            "",
            "## Summary",
            "",
            f"- Added files: {len(summary.added_files)}",
            f"- Modified files: {len(summary.modified_files)}",
            f"- Removed files: {len(summary.removed_files)}",
            f"- Unchanged files: {summary.unchanged_files_count}",
            f"- Indexed files: {summary.indexed_files}",
            f"- Ignored files: {summary.ignored_files}",
            f"- Skipped large files: {summary.skipped_large_files}",
            f"- Ignored sensitive files: {summary.ignored_sensitive_files}",
            f"- Ignored binary files: {summary.ignored_binary_files}",
            f"- `.lceignore` detected: {'yes' if summary.lceignore_detected else 'no'}",
            "",
        ]
    )


def _render_file_list(files: list[str]) -> list[str]:
    if not files:
        return ["- None"]
    return [f"- `{path}`" for path in files]
