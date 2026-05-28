from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectInfo(BaseModel):
    name: str
    root: str
    detected_stack: list[str] = Field(default_factory=list)


class RepoSummary(BaseModel):
    total_files: int
    indexed_files: int
    ignored_files: int


class DirectoryInfo(BaseModel):
    path: str
    purpose: str


class RepoMap(BaseModel):
    project: ProjectInfo
    summary: RepoSummary
    directories: list[DirectoryInfo] = Field(default_factory=list)


class FileInfo(BaseModel):
    path: str
    language: str
    size_lines: int
    content_hash: str = ""
    imports: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    summary: str
    tags: list[str] = Field(default_factory=list)


class FileIndex(BaseModel):
    files: list[FileInfo] = Field(default_factory=list)


class FileFingerprint(BaseModel):
    path: str
    size_lines: int
    content_hash: str


class UpdateSummary(BaseModel):
    updated_at: str
    added_files: list[str] = Field(default_factory=list)
    modified_files: list[str] = Field(default_factory=list)
    removed_files: list[str] = Field(default_factory=list)
    unchanged_files_count: int
    indexed_files: int
    ignored_files: int
    skipped_large_files: int = 0
    ignored_sensitive_files: int = 0
    ignored_binary_files: int = 0
    lceignore_detected: bool = False


class TaskRelevantFile(BaseModel):
    path: str
    role: str = "unknown"
    module_role: str | None = None
    reason: str
    confidence: float


class TaskContext(BaseModel):
    task: str
    slug: str
    project_profile: str = "generic"
    max_primary_files: int = 5
    max_secondary_files: int = 8
    max_context_files: int = 10
    max_avoid_files: int = 20
    detected_intents: list[str] = Field(default_factory=list)
    detected_pipeline_phases: list[str] = Field(default_factory=list)
    primary_files: list[TaskRelevantFile] = Field(default_factory=list)
    secondary_files: list[TaskRelevantFile] = Field(default_factory=list)
    context_files: list[TaskRelevantFile] = Field(default_factory=list)
    avoid_files: list[TaskRelevantFile] = Field(default_factory=list)
    relevant_files: list[TaskRelevantFile] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
    validation_checklist: list[str] = Field(default_factory=list)
