# Local Context Engine

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

## Main Workflow

```bash
lce init
lce scan .
lce task "add JWT authentication"
lce prompt --target cline
```

Then paste the generated prompt into your AI coding agent. The prompt tells the agent to read the persistent context first, inspect only relevant files initially, avoid unrelated changes, and report validation steps.

Future versions will add `lce update` for incremental refreshes.

## Install Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI Commands

### `lce init`

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

### `lce task "<task description>"`

Creates a deterministic task context pack:

```text
.ai-context/tasks/add-jwt-authentication/
├── task-context.md
├── relevant-files.json
├── risk-map.md
├── validation-checklist.md
└── agent-prompt.md
```

Task context generation uses deterministic relevance scoring in the MVP. It combines keyword matches with source-directory priority, file type weighting, and penalties for documentation, examples, and generated output. For example, auth-related tasks prioritize files containing terms like `auth`, `user`, `login`, `token`, `jwt`, `session`, `middleware`, and `security`. LLM-based semantic relevance will be added later.

### `lce prompt --target <target>`

Generates an agent prompt from the latest task folder.

Supported targets:

- `generic`
- `cline`
- `codex`
- `copilot`
- `cursor`
- `claude`

### `lce doctor`

Checks whether `.ai-context/` exists and includes expected scan outputs. Warnings are printed if no scan has been run or the context looks empty.

## Current MVP Features

- Python 3.12+ CLI built with Typer.
- Rich terminal output.
- Pydantic data models.
- Deterministic recursive repository scan.
- Default ignore rules for heavy and sensitive files.
- Extension-based language detection.
- Python AST analyzer for imports, functions, and classes.
- JavaScript and TypeScript regex analyzer for imports, functions, classes, and simple exports.
- Generic analyzer for structured metadata and tags.
- Repository map, file index, agent context, metadata, task context, risk map, validation checklist, and prompts.
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

- `lce update` for incremental rescans.
- `lce learn` for storing user-approved project notes.
- `lce pr-summary` for pull request context packs.
- Better framework detection.
- More analyzers for PHP, Go, Java, and C#.
- Optional embeddings.
- Optional Ollama integration.
- Optional OpenAI integration.
- Web dashboard.
- API server.
- Watch mode.

## Non-Goals For The MVP

This first implementation intentionally does not include OpenAI, Ollama, embeddings, vector databases, a web dashboard, an API server, or watch mode.
