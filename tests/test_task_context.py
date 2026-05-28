from __future__ import annotations

from lce.generators.task_context_generator import (
    calculate_relevance_score,
    generate_task_context,
    keywords_for_task,
)
from lce.models.context_models import FileIndex, FileInfo


def make_file(path: str, tags: list[str], summary: str | None = None) -> FileInfo:
    return FileInfo(
        path=path,
        language="Python",
        size_lines=10,
        summary=summary or f"File {path}",
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


def test_ai_context_files_are_excluded_from_task_relevance() -> None:
    index = FileIndex(
        files=[
            make_file(".ai-context/tasks/add-jwt-auth/task-context.md", ["auth", "jwt"]),
            make_file("app/auth.py", ["auth", "jwt"]),
        ]
    )

    context = generate_task_context(index, "add JWT authentication")

    paths = [file.path for file in context.relevant_files]
    assert ".ai-context/tasks/add-jwt-auth/task-context.md" not in paths
    assert "app/auth.py" in paths


def test_sample_output_files_are_penalized_below_source_files() -> None:
    source = make_file("lce/cli/task_cmd.py", ["task"], "Generates task context files")
    sample = make_file(
        "examples/sample-output/tasks/add-jwt-auth/task-context.md",
        ["task", "auth", "jwt"],
    )

    source_score, source_reasons = calculate_relevance_score(source, "task context")
    sample_score, sample_reasons = calculate_relevance_score(sample, "task context")

    assert source_score > sample_score
    assert any("source directory 'lce/'" in reason for reason in source_reasons)
    assert any("sample output" in reason for reason in sample_reasons)


def test_source_files_are_prioritized_over_markdown_examples() -> None:
    index = FileIndex(
        files=[
            make_file(
                "examples/sample-output/tasks/add-jwt-auth/agent-prompt.md",
                ["auth", "jwt"],
            ),
            make_file("lce/auth/token.py", ["auth", "token", "jwt"]),
            make_file("docs/auth.md", ["auth"]),
        ]
    )

    context = generate_task_context(index, "add JWT authentication")

    assert context.relevant_files[0].path == "lce/auth/token.py"
    assert "examples/sample-output/tasks/add-jwt-auth/agent-prompt.md" not in [
        file.path for file in context.relevant_files
    ]


def test_only_sample_output_matches_are_not_selected() -> None:
    index = FileIndex(
        files=[
            make_file(
                "examples/sample-output/tasks/add-jwt-auth/relevant-files.json",
                ["auth", "jwt"],
            )
        ]
    )

    context = generate_task_context(index, "add JWT authentication")

    assert context.relevant_files == []


def test_relevant_files_are_sorted_by_confidence() -> None:
    index = FileIndex(
        files=[
            make_file("tests/test_login.py", ["login"]),
            make_file("lce/auth/middleware.py", ["auth", "jwt", "middleware"]),
            make_file("README.md", ["auth"]),
        ]
    )

    context = generate_task_context(index, "add JWT authentication")
    confidences = [file.confidence for file in context.relevant_files]

    assert confidences == sorted(confidences, reverse=True)
    assert context.relevant_files[0].path == "lce/auth/middleware.py"
