# Local Context Engine

Version: 1.2.0

Local Context Engine is a local context agent for AI coding workflows. It scans repositories, builds persistent local memory, and generates task-specific context packs so AI coding agents can work with less context, fewer mistakes, and better architectural awareness.

## Why This Exists

AI coding agents often spend their first minutes rediscovering the same repository facts: where the source code lives, which files matter, what stack is present, where tests are located, and which files should not be touched casually. That burns context and increases the chance of unrelated changes.

Local Context Engine creates a deterministic `.ai-context/` folder that can be read by tools like Cline, Codex, Claude Code, Copilot, Cursor, or local agents before they start editing.

The first version does not call an LLM. It uses filesystem scanning, extension-based language detection, lightweight analyzers, and keyword-based task relevance.

## How `.ai-context/` Works

After initialization and scanning, your repository gets:

- `.ai-context/agent-context.md`: human-readable context for AI agents.
- `.ai-context/file-index.json`: structured file metadata, languages, tags, functions, classes, and imports where supported.
- `.ai-context/repo-map.json`: project summary and directory map.
- `.ai-context/metadata.json`: generation metadata.
- `.ai-context/tasks/<task>/`: task-specific relevant files, risk map, checklist, and agent prompt.
- `.ai-context/specs/<spec>/`: specification packs for plan-first implementation.

## Main Workflow

```bash
lce init
lce scan .
lce task "add JWT authentication"
lce prompt --target cline
lce spec "prepare YouTube upload integration skeleton after render"
lce update
```

Then paste the generated prompt into your AI coding agent. The prompt tells the agent to read the persistent context first, inspect only relevant files initially, avoid unrelated changes, and report validation steps.

Run `lce update` after code changes to refresh `.ai-context/` and record added, modified, removed, and unchanged indexed files.

## Install Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI Commands

### `lce init`

You can initialize with the default generic profile:

```bash
lce init --profile generic
```

For AI/video/rendering repositories, use:

```bash
lce init --profile ai-video
```

Creates:

```text
.ai-context/
├── config.yml
├── agent-rules.md
└── README.md
```

### `lce scan <path> --output .ai-context`

Scans a repository and generates:

- `repo-map.json`
- `file-index.json`
- `agent-context.md`
- `metadata.json`

The scanner ignores common heavy or sensitive paths such as `.git`, `node_modules`, build folders, virtual environments, caches, storage folders, and `.env` files.

## Safe scanning with `.lceignore`

LCE ignores common heavy and sensitive files by default, including local environment files, keys, certificates, local databases, archives, videos, images, caches, build outputs, and `.ai-context/` itself. `.ai-context/` is generated output and is ignored as source input.

Each repository can add a `.lceignore` file at the repository root for project-specific exclusions. The MVP supports simple gitignore-like patterns: directory patterns ending with `/`, exact file names, wildcard extensions, nested paths, comments starting with `#`, and blank lines.

For video, AI, and media-heavy projects, ignore videos, generated outputs, model files, logs, and local storage. Example for AETHEL-like projects:

```gitignore
.ai-context/
storage/
outputs/
videos/
models/
logs/
tmp/
*.mp4
*.mov
*.mkv
*.pt
*.onnx
*.safetensors
.env
.env.*
```

By default, files larger than 500 KB are skipped. You can override this in `.ai-context/config.yml`:

```yaml
scan:
  max_file_size_kb: 500
```

### `lce update`

Refreshes an existing `.ai-context/` folder after files are added, modified, or removed.

The update command reuses the scanner, regenerates the base context files, compares the previous and current file indexes using SHA-256 content hashes, and writes:

- `last-update.md`
- `last-update.json`

It also updates `metadata.json` with the latest added, modified, and removed files.

### `lce task "<task description>"`

Creates a deterministic task context pack:

```text
.ai-context/tasks/add-jwt-authentication/
├── task-context.md
├── relevant-files.json
├── compact-context.md
├── risk-map.md
├── validation-checklist.md
└── agent-prompt.md
```

Task context generation uses deterministic relevance scoring in the MVP. It combines keyword matches with source-directory priority, file type weighting, and penalties for documentation, examples, and generated output. For example, auth-related tasks prioritize files containing terms like `auth`, `user`, `login`, `token`, `jwt`, `session`, `middleware`, and `security`. LLM-based semantic relevance will be added later.

Project profiles can refine deterministic task relevance. The `generic` profile is the default. The `ai-video` profile adds AI/video pipeline phases and module roles for render, worker, output, shared model, storage, upload, planning, quality, highlight, transcription, and ffmpeg workflows.

## Spec Engine

Spec Engine converts an implementation idea into a structured technical specification before coding.

```bash
lce spec "prepare YouTube upload integration skeleton after render"
```

This creates a deterministic specification folder:

```text
.ai-context/specs/prepare-youtube-upload-integration-skeleton-after-render/
├── spec.md
├── requirements.md
├── technical-plan.md
├── affected-context.json
├── acceptance-criteria.md
├── risks.md
├── validation-checklist.md
└── agent-prompt-local-llm.md
```

Workflow:

1. Generate context with LCE.
2. Generate a spec with `lce spec`.
3. Review the spec.
4. Send the spec-aware local LLM prompt to Cline/Qwen.
5. Approve the plan.
6. Only then allow implementation.

Spec generation is deterministic. It reuses `.ai-context/agent-context.md`, `.ai-context/file-index.json`, `.ai-context/repo-map.json`, project profiles, and task relevance logic where useful. It does not call OpenAI, Ollama, embeddings, vector databases, or external LLMs.

### `lce prompt --target <target>`

Generates an agent prompt from the latest task folder.

Supported targets:

- `generic`
- `cline`
- `codex`
- `copilot`
- `cursor`
- `claude`
- `local-llm`

## Local LLM workflow

Local coding models can struggle when too many source files are opened at once. `lce prompt --target local-llm` generates a plan-first compact prompt for workflows such as Cline with Qwen, DeepSeek Coder, CodeLlama, or other local models.

```bash
lce task "add YouTube private upload after render"
lce prompt --target local-llm
```

Then paste `agent-prompt-local-llm.md` into the coding agent. The prompt tells the model to read `compact-context.md` first, avoid opening source files initially, return a concise plan, choose the first single source file it would inspect, and wait for approval before reading or editing source files.

For compact prompts with another target:

```bash
lce prompt --target cline --compact
```

### `lce doctor`

Checks whether `.ai-context/` exists and includes expected scan outputs. Warnings are printed if no scan has been run or the context looks empty.

## Current MVP Features

- Python 3.12+ CLI built with Typer.
- Rich terminal output.
- Pydantic data models.
- Deterministic recursive repository scan.
- Default ignore rules for heavy and sensitive files.
- `.lceignore` support for repository-specific safe scanning.
- Large file skipping with metadata counters.
- Extension-based language detection.
- Python AST analyzer for imports, functions, and classes.
- JavaScript and TypeScript regex analyzer for imports, functions, classes, and simple exports.
- Generic analyzer for structured metadata and tags.
- Repository map, file index, agent context, metadata, task context, risk map, validation checklist, prompts, spec packs, and update summaries.
- Pytest coverage for core scanner and generator behavior.
- Ruff configuration for linting and formatting.

## Supported Files

The MVP indexes:

- `.py`
- `.js`
- `.jsx`
- `.ts`
- `.tsx`
- `.php`
- `.go`
- `.java`
- `.cs`
- `.json`
- `.yml`
- `.yaml`
- `.md`
- `.toml`
- `.ini`
- `.dockerfile`
- `Dockerfile`
- `docker-compose.yml`
- `docker-compose.yaml`

## Development

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Smoke test the CLI:

```bash
python -m lce.main --help
```

## Roadmap

- Skills Registry.
- Code Intelligence Map.
- `detailed-context.json`.
- Function and line-range mapping.
- `lce learn` for storing user-approved project notes.
- `lce pr-summary` for pull request context packs.
- Better framework detection.
- More analyzers for PHP, Go, Java, and C#.

## Non-Goals For The MVP

This implementation intentionally does not include OpenAI, Ollama, embeddings, vector databases, a web dashboard, an API server, or watch mode.
