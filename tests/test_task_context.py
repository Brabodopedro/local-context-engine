from __future__ import annotations

from lce.generators.task_context_generator import (
    calculate_relevance_score,
    classify_module_role,
    classify_path_role,
    detect_pipeline_phases,
    detect_task_intents,
    generate_task_context,
    keywords_for_task,
    render_agent_prompt,
    render_compact_agent_prompt,
    render_compact_context,
    render_task_context,
)
from lce.models.context_models import FileIndex, FileInfo, TaskContext, TaskRelevantFile
from lce.scanner.scan_config import TaskBudget


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


def test_stopwords_do_not_influence_task_keywords() -> None:
    keywords = keywords_for_task("add YouTube private upload after render file")

    assert {"youtube", "private", "upload", "render"} <= set(keywords)
    assert "add" not in keywords
    assert "after" not in keywords
    assert "file" not in keywords


def test_file_does_not_boost_dockerfile_relevance() -> None:
    dockerfile = make_file("apps/workers/Dockerfile", ["docker", "file"])

    score, reasons = calculate_relevance_score(
        dockerfile,
        "add YouTube private upload after render",
    )

    assert score < 0.20
    assert any("Dockerfile is not primary" in reason for reason in reasons)


def test_migrations_are_avoid_without_database_intent() -> None:
    index = FileIndex(
        files=[
            make_file("apps/api/migrations/001_add_upload_table.py", ["upload", "migration"]),
            make_file("apps/workers/aethel_workers/upload.py", ["upload", "render"]),
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")

    assert context.primary_files[0].path == "apps/workers/aethel_workers/upload.py"
    assert context.avoid_files[0].role == "migration"


def test_migration_can_be_primary_with_database_intent() -> None:
    index = FileIndex(
        files=[
            make_file("apps/api/migrations/001_add_upload_table.py", ["upload", "migration"]),
        ]
    )

    context = generate_task_context(index, "add database migration for upload table")

    assert "database" in context.detected_intents
    assert context.secondary_files or context.primary_files
    assert not context.avoid_files


def test_dockerfile_is_not_primary_unless_docker_intent_is_detected() -> None:
    index = FileIndex(files=[make_file("apps/workers/Dockerfile", ["docker"])])

    upload_context = generate_task_context(index, "add YouTube private upload after render")
    docker_context = generate_task_context(index, "update docker image for worker")

    assert upload_context.primary_files == []
    assert docker_context.primary_files or docker_context.secondary_files


def test_package_init_is_low_priority() -> None:
    init_file = make_file("apps/workers/aethel_workers/__init__.py", ["upload"])

    assert classify_path_role(init_file) == "package_init"
    context = generate_task_context(FileIndex(files=[init_file]), "add upload")

    assert context.primary_files == []
    assert context.context_files[0].role == "package_init"


def test_source_render_upload_files_rank_as_primary() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/rendering.py", ["render", "worker"]),
            make_file("apps/workers/aethel_workers/youtube_upload.py", ["youtube", "upload"]),
            make_file("apps/workers/Dockerfile", ["docker", "file"]),
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")
    primary_paths = [file.path for file in context.primary_files]

    assert detect_task_intents("add YouTube private upload after render") == [
        "render",
        "upload/storage",
    ]
    assert "apps/workers/aethel_workers/youtube_upload.py" in primary_paths
    assert "apps/workers/aethel_workers/rendering.py" in primary_paths
    assert "apps/workers/Dockerfile" not in primary_paths


def test_output_api_ranks_as_primary_for_post_render_upload_task() -> None:
    index = FileIndex(
        files=[
            make_file("apps/api/outputs_api.py", ["output", "api"]),
            make_file("apps/workers/aethel_workers/highlights.py", ["worker"]),
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")

    assert context.primary_files[0].path == "apps/api/outputs_api.py"


def test_task_context_contains_categorized_sections() -> None:
    context = generate_task_context(
        FileIndex(files=[make_file("apps/workers/aethel_workers/upload.py", ["upload"])]),
        "add YouTube private upload after render",
    )
    rendered = render_task_context(context)

    assert "## Primary Files To Inspect First" in rendered
    assert "## Secondary Files" in rendered
    assert "## Context Files" in rendered
    assert "## Files To Avoid Unless Explicitly Needed" in rendered


def test_prompt_instructs_agent_to_inspect_primary_files_first() -> None:
    context = generate_task_context(
        FileIndex(files=[make_file("apps/workers/aethel_workers/upload.py", ["upload"])]),
        "add YouTube private upload after render",
    )
    prompt = render_agent_prompt(context, "cline")

    assert "Inspect primary files first" in prompt
    assert "Inspect secondary files only if needed" in prompt
    assert "Do not modify migrations unless the task requires schema changes" in prompt


def test_primary_files_are_capped_by_default_budget() -> None:
    index = FileIndex(
        files=[
            make_file(f"apps/workers/aethel_workers/upload_{number}.py", ["upload", "youtube"])
            for number in range(8)
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")

    assert len(context.primary_files) == 5
    assert len(context.secondary_files) == 3


def test_broad_worker_directory_does_not_promote_unrelated_modules_to_primary() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/highlights.py", ["worker"]),
            make_file("apps/workers/aethel_workers/planning.py", ["worker"]),
            make_file("apps/workers/aethel_workers/quality.py", ["worker"]),
            make_file("apps/workers/aethel_workers/youtube_upload.py", ["youtube", "upload"]),
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")
    primary_paths = {file.path for file in context.primary_files}

    assert "apps/workers/aethel_workers/youtube_upload.py" in primary_paths
    assert "apps/workers/aethel_workers/highlights.py" not in primary_paths
    assert "apps/workers/aethel_workers/planning.py" not in primary_paths
    assert "apps/workers/aethel_workers/quality.py" not in primary_paths


def test_rendering_ranks_above_ffmpeg_for_after_render_task() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/ffmpeg.py", ["ffmpeg", "render"]),
            make_file("apps/workers/aethel_workers/rendering.py", ["render"]),
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")

    assert context.primary_files[0].path == "apps/workers/aethel_workers/rendering.py"
    assert context.secondary_files[0].path == "apps/workers/aethel_workers/ffmpeg.py"


def test_ffmpeg_becomes_primary_when_task_mentions_ffmpeg_explicitly() -> None:
    index = FileIndex(files=[make_file("apps/workers/aethel_workers/ffmpeg.py", ["ffmpeg"])])

    context = generate_task_context(index, "change ffmpeg render command")

    assert context.primary_files[0].path == "apps/workers/aethel_workers/ffmpeg.py"


def test_secondary_files_receive_relevant_less_actionable_files() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/youtube_upload.py", ["youtube", "upload"]),
            make_file("apps/workers/aethel_workers/ffmpeg.py", ["ffmpeg", "render"]),
        ]
    )

    context = generate_task_context(index, "add YouTube private upload after render")

    assert context.primary_files[0].path == "apps/workers/aethel_workers/youtube_upload.py"
    assert context.secondary_files[0].path == "apps/workers/aethel_workers/ffmpeg.py"


def test_task_budget_can_be_overridden() -> None:
    index = FileIndex(
        files=[
            make_file(f"apps/workers/aethel_workers/upload_{number}.py", ["upload", "youtube"])
            for number in range(4)
        ]
    )

    context = generate_task_context(
        index,
        "add YouTube private upload after render",
        budget=TaskBudget(max_primary_files=2, max_secondary_files=1),
    )

    assert len(context.primary_files) == 2
    assert len(context.secondary_files) == 1


def test_prompt_mentions_compact_primary_context() -> None:
    context = generate_task_context(
        FileIndex(files=[make_file("apps/workers/aethel_workers/upload.py", ["upload"])]),
        "add YouTube private upload after render",
    )
    prompt = render_agent_prompt(context, "cline")

    assert "Primary files are intentionally limited to reduce context" in prompt
    assert "For local LLMs" in prompt
    assert "Explain before editing files outside primary_files" in prompt


def test_task_context_includes_context_budget_section() -> None:
    context = generate_task_context(
        FileIndex(files=[make_file("apps/workers/aethel_workers/upload.py", ["upload"])]),
        "add YouTube private upload after render",
    )
    rendered = render_task_context(context)

    assert "## Context Budget" in rendered
    assert "Primary file limit: 5" in rendered
    assert "intentionally limits primary files to 5" in rendered


def test_ai_video_classifies_known_module_roles() -> None:
    assert classify_module_role("apps/workers/aethel_workers/rendering.py", "ai-video") == (
        "render_orchestrator"
    )
    assert classify_module_role("apps/workers/aethel_workers/worker.py", "ai-video") == (
        "worker_entrypoint"
    )
    assert classify_module_role("apps/workers/aethel_workers/ffmpeg.py", "ai-video") == (
        "render_helper"
    )
    assert classify_module_role("apps/workers/aethel_workers/planning.py", "ai-video") == (
        "planning_agent"
    )


def test_ai_video_detects_post_render_upload_phases() -> None:
    phases = detect_pipeline_phases("add YouTube private upload after render", "ai-video")

    assert {"render", "post-render", "storage/upload"} <= set(phases)


def test_ai_video_post_render_upload_expected_ranking() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/rendering.py", ["render"]),
            make_file("apps/workers/aethel_workers/worker.py", ["worker"]),
            make_file("apps/api/aethel_api/outputs_api.py", ["output", "api"]),
            make_file("packages/shared/aethel_shared/models.py", ["model"]),
            make_file("apps/api/aethel_api/videos_api.py", ["video", "api"]),
            make_file("apps/workers/aethel_workers/ffmpeg.py", ["ffmpeg", "render"]),
            make_file("apps/workers/aethel_workers/jobs.py", ["job"]),
            make_file("packages/shared/aethel_shared/enums.py", ["enum"]),
            make_file("apps/workers/aethel_workers/metadata.py", ["metadata"]),
            make_file("apps/workers/aethel_workers/planning.py", ["planning"]),
            make_file("apps/workers/aethel_workers/quality.py", ["quality"]),
            make_file("apps/workers/aethel_workers/highlights.py", ["highlight"]),
            make_file("apps/workers/aethel_workers/transcription.py", ["transcription"]),
            make_file("apps/workers/aethel_workers/watcher.py", ["watcher"]),
            make_file("apps/api/aethel_api/migrations/001_upload.py", ["upload"]),
        ]
    )

    context = generate_task_context(
        index,
        "add YouTube private upload after render",
        profile="ai-video",
    )

    assert [file.path for file in context.primary_files] == [
        "apps/workers/aethel_workers/rendering.py",
        "apps/workers/aethel_workers/worker.py",
        "apps/api/aethel_api/outputs_api.py",
        "packages/shared/aethel_shared/models.py",
        "apps/api/aethel_api/videos_api.py",
    ]
    assert [file.path for file in context.secondary_files[:4]] == [
        "apps/workers/aethel_workers/ffmpeg.py",
        "apps/workers/aethel_workers/jobs.py",
        "packages/shared/aethel_shared/enums.py",
        "apps/workers/aethel_workers/metadata.py",
    ]
    assert {
        "apps/workers/aethel_workers/planning.py",
        "apps/workers/aethel_workers/quality.py",
        "apps/workers/aethel_workers/highlights.py",
    } <= {file.path for file in context.context_files}
    assert context.avoid_files[0].role == "migration"


def test_ai_video_ffmpeg_task_promotes_render_helper() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/rendering.py", ["render"]),
            make_file("apps/workers/aethel_workers/ffmpeg.py", ["ffmpeg"]),
        ]
    )

    context = generate_task_context(index, "change ffmpeg render command", profile="ai-video")

    assert context.primary_files[0].path == "apps/workers/aethel_workers/ffmpeg.py"
    assert context.primary_files[0].module_role == "render_helper"


def test_ai_video_planning_task_promotes_planning_agent() -> None:
    index = FileIndex(
        files=[
            make_file("apps/workers/aethel_workers/rendering.py", ["render"]),
            make_file("apps/workers/aethel_workers/planning.py", ["planning"]),
        ]
    )

    context = generate_task_context(index, "update planning edl flow", profile="ai-video")

    assert context.primary_files[0].path == "apps/workers/aethel_workers/planning.py"
    assert context.primary_files[0].module_role == "planning_agent"


def test_ai_video_task_context_includes_profile_phase_and_module_sections() -> None:
    context = generate_task_context(
        FileIndex(files=[make_file("apps/workers/aethel_workers/rendering.py", ["render"])]),
        "add YouTube private upload after render",
        profile="ai-video",
    )
    rendered = render_task_context(context)

    assert "## Project Profile" in rendered
    assert "ai-video" in rendered
    assert "## Detected Pipeline Phases" in rendered
    assert "## Module Roles" in rendered
    assert "rendering.py: render_orchestrator" in rendered


def test_ai_video_prompt_mentions_profile_guidance() -> None:
    context = generate_task_context(
        FileIndex(files=[make_file("apps/workers/aethel_workers/rendering.py", ["render"])]),
        "add YouTube private upload after render",
        profile="ai-video",
    )
    prompt = render_agent_prompt(context, "cline")

    assert "generated using the `ai-video` profile" in prompt
    assert "AI/video pipeline roles" in prompt
    assert "Do not inspect planning/quality/highlight modules" in prompt


def test_ai_video_frontend_file_not_promoted_without_frontend_intent() -> None:
    index = FileIndex(
        files=[
            make_file("apps/dashboard/src/main.tsx", ["dashboard", "react"]),
            make_file("apps/workers/aethel_workers/rendering.py", ["render"]),
        ]
    )

    context = generate_task_context(
        index,
        "add YouTube private upload after render",
        profile="ai-video",
    )

    assert "apps/dashboard/src/main.tsx" not in [file.path for file in context.primary_files]
    assert "apps/dashboard/src/main.tsx" not in [file.path for file in context.secondary_files]


def test_ai_video_frontend_file_promoted_with_frontend_intent() -> None:
    index = FileIndex(files=[make_file("apps/dashboard/src/main.tsx", ["dashboard", "react"])])

    context = generate_task_context(index, "add dashboard UI button", profile="ai-video")

    assert context.primary_files[0].path == "apps/dashboard/src/main.tsx"
    assert context.primary_files[0].module_role == "frontend_app"


def test_ai_video_loot_detection_context_unless_requested() -> None:
    index = FileIndex(
        files=[make_file("apps/workers/aethel_workers/loot_detection.py", ["detection"])]
    )

    unrelated = generate_task_context(
        index,
        "add YouTube private upload after render",
        profile="ai-video",
    )
    requested = generate_task_context(index, "improve loot detection", profile="ai-video")

    assert unrelated.context_files[0].module_role == "loot_detection_agent"
    assert requested.primary_files[0].module_role == "loot_detection_agent"


def test_ai_video_thumbnail_context_unless_requested() -> None:
    index = FileIndex(files=[make_file("apps/workers/aethel_workers/thumbnail.py", ["thumbnail"])])

    unrelated = generate_task_context(
        index,
        "add YouTube private upload after render",
        profile="ai-video",
    )
    requested = generate_task_context(index, "generate thumbnail preview image", profile="ai-video")

    assert unrelated.context_files[0].module_role == "thumbnail_agent"
    assert requested.primary_files[0].module_role == "thumbnail_agent"


def test_compact_prompt_includes_primary_files_and_summarizes_avoid_files() -> None:
    context = TaskContext(
        task="add YouTube private upload after render",
        slug="add-youtube-private-upload-after-render",
        project_profile="ai-video",
        detected_pipeline_phases=["render", "post-render", "storage/upload"],
        primary_files=[
            TaskRelevantFile(
                path="apps/workers/aethel_workers/rendering.py",
                role="source",
                module_role="render_orchestrator",
                reason="primary",
                confidence=0.97,
            )
        ],
        avoid_files=[
            TaskRelevantFile(
                path=f"apps/api/migrations/{number}.py",
                role="migration",
                module_role=None,
                reason="avoid",
                confidence=0.0,
            )
            for number in range(5)
        ],
    )

    prompt = render_compact_agent_prompt(context, "local-llm")

    assert ".ai-context/tasks/add-youtube-private-upload-after-render/compact-context.md" in prompt
    assert "Do not open source files yet." in prompt
    assert "First return a concise plan based only on compact context." in prompt
    assert "Wait for approval before reading/editing source files." in prompt
    assert "Do not open all files upfront." in prompt


def test_compact_context_includes_primary_file_summaries() -> None:
    file_info = FileInfo(
        path="apps/workers/aethel_workers/rendering.py",
        language="Python",
        size_lines=120,
        imports=["pathlib", "subprocess"],
        functions=["render_video"],
        classes=[],
        summary="Python file at apps/workers/aethel_workers/rendering.py",
        tags=["render", "worker"],
    )
    context = generate_task_context(
        FileIndex(files=[file_info]),
        "add YouTube private upload after render",
        profile="ai-video",
    )

    compact = render_compact_context(context, FileIndex(files=[file_info]))

    assert "# Compact Context" in compact
    assert "## Project Profile" in compact
    assert "ai-video" in compact
    assert "## Detected Pipeline Phases" in compact
    assert "## Suggested First Pass" in compact
    assert "apps/workers/aethel_workers/rendering.py" in compact
    assert "Render orchestration module" in compact
    assert "Functions: render_video" in compact
    assert "Likely inspection purpose" in compact
