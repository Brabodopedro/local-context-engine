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


class TaskRelevantFile(BaseModel):
    path: str
    reason: str
    confidence: float


class TaskContext(BaseModel):
    task: str
    slug: str
    relevant_files: list[TaskRelevantFile] = Field(default_factory=list)
    generated_files: list[str] = Field(default_factory=list)
    validation_checklist: list[str] = Field(default_factory=list)
