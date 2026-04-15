# PyAgent

An opinionated Python code review, refactoring, and explanation agent powered by Claude.

## Quickstart

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
cd pyagent
uv sync

# Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run a code review
uv run pyagent review path/to/file.py

# Refactor a single file
uv run pyagent refactor path/to/file.py

# Refactor an entire codebase (full two-phase: plan, then batched execute)
uv run pyagent refactor path/to/project/

# Narrow refactor focused on a specific concern (single context-packed pass)
uv run pyagent refactor path/to/project/ -i "modernize type hints"

# Explain a file
uv run pyagent explain path/to/file.py

# Start an interactive chat session
uv run pyagent chat --path path/to/project/
```

## Commands

| Command | Description |
|---------|-------------|
| `review <path>` | Review code for correctness, style, and best practices |
| `refactor <path>` | Apply named refactoring patterns from the playbook |
| `explain <path>` | Explain code structure, patterns, and design decisions |
| `chat` | Interactive conversation about a codebase |
| `info` | Show configuration and knowledge base stats |

All commands accept `--instructions` / `-i` (or `--question` / `-q` for explain) for additional guidance, and `--model` / `-m` to override the default model.  `review`, `refactor`, and `explain` all auto-detect file vs directory paths — no mode flag required.

### Refactor modes

`refactor` picks its mode implicitly from the path and whether you supplied `-i`:

| Path | `-i` instructions | Mode |
|------|-------------------|------|
| file | n/a | single file, refactored in place with surrounding package context |
| directory | _(none)_ | **full** codebase refactor in two phases (plan → batched execution) |
| directory | focused instructions | **partial** refactor — a single context-packed pass over the highest-priority files matching your instructions |

The intuition: a bare `refactor ./proj` means "refactor the whole project", so every file gets a turn. A `refactor ./proj -i "modernize the auth module"` is narrow and focused, so only the files relevant to the instructions are touched — faster and cheaper.

Two flags override the heuristic when needed:

| Flag | Description |
|------|-------------|
| `--full` | Force the two-phase codebase refactor (directory only) |
| `--partial` | Force the context-packed single-pass refactor (directory only) |
| `--dry-run` | Show proposed changes without writing any files |
| `--no-confirm` / `-y` | Apply changes without a confirmation prompt |
| `--no-backup` | Skip creating backup files before writing |

The full mode works in two phases:

1. **Planning** — The LLM receives the full structural summary of the codebase and produces a named, actionable refactoring strategy (themes, order of operations, file-specific notes). The plan is persisted to `.pyagent/last_plan.json` and `last_plan.md`.
2. **Execution** — All source files are grouped into token-budget-constrained batches. Each batch is refactored with the overall plan as context. Per-batch output is persisted to `.pyagent/batches/batch_NNN.md` for audit, and a plan-adherence check flags any batch that ignored the strategy (and retries it once).

The same diff-review → confirm → backup → write workflow applies in every mode — you see every proposed change before anything is written to disk.

```bash
# Full refactor of the whole project (implicit — directory, no -i)
uv run pyagent refactor ./my_project

# Narrow refactor with a focus (implicit — directory + -i)
uv run pyagent refactor ./my_project -i "modernize type hints and remove legacy patterns"

# Force the full mode even when -i is narrow
uv run pyagent refactor ./my_project -i "clean up the models" --full

# Preview without writing
uv run pyagent refactor ./my_project --dry-run
```

## Architecture

```
src/pyagent/
├── __main__.py     # CLI entrypoint (typer + rich)
├── agent.py        # Core orchestration loop
├── config.py       # Pydantic settings
├── context.py      # Codebase ingestion, AST parsing & file batching
├── logging.py      # Structured logger factory
├── memory.py       # Conversation state management
├── prompts.py      # Prompt templates per capability
├── rag.py          # Documentation retrieval
└── tools/
    ├── base.py       # Tool protocol
    ├── reviewer.py   # Code review tool
    ├── refactor.py   # Refactoring tool (single-file + batch)
    └── explainer.py  # Explanation tool
```

## Knowledge Base

The agent's opinions are codified in six documents under `docs/`:

| Document | Purpose |
|----------|---------|
| `python_standards.md` | Language-level style, idioms, and conventions |
| `tech_stack.md` | Preferred tools and libraries with rationale |
| `anti_patterns.md` | Code smells and mistakes to flag |
| `refactoring_playbook.md` | Named patterns with before/after examples |
| `architecture_patterns.md` | Module design, DI, and structural best practices |
| `review_rubric.md` | Severity levels, scoring dimensions, output format |

These docs are retrieved via RAG at runtime, meaning you can edit them to tune the agent's behavior without touching code.

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
```
