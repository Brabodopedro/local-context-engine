from __future__ import annotations

from lce.generators.task_context_generator import generate_task_context, keywords_for_task
from lce.models.context_models import FileIndex, FileInfo


def make_file(path: str, tags: list[str]) -> FileInfo:
    return FileInfo(
        path=path,
        language="Python",
        size_lines=10,
        summary=f"File {path}",
        tags=tags,
    )


def test_auth_task_prioritizes_auth_related_files() -> None:
    index = FileIndex(
        files=[
            make_file("app/auth/middleware.py", ["auth", "middleware"]),
            make_file("app/billing/invoice.py", ["billing"]),
            make_file("tests/test_login.py", ["test", "login"]),
        ]
    )

    context = generate_task_context(index, "add JWT authentication")

    paths = [file.path for file in context.relevant_files]
    assert "app/auth/middleware.py" in paths
    assert "tests/test_login.py" in paths
    assert "app/billing/invoice.py" not in paths


def test_task_keywords_have_domain_defaults() -> None:
    assert "jwt" in keywords_for_task("add auth")
    assert "Dockerfile" in keywords_for_task("fix docker build")
