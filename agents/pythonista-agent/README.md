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

# Run a refactoring pass
uv run pyagent refactor path/to/file.py

# Refactor an entire codebase (all files, two-phase)
uv run pyagent refactor path/to/project/ --all-files

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

All commands accept `--instructions` / `-i` (or `--question` / `-q` for explain) for additional guidance, and `--model` / `-m` to override the default model.

### Refactor options

| Flag | Description |
|------|-------------|
| `--all-files` | Refactor every file in the codebase (see below) |
| `--dry-run` | Show proposed changes without writing any files |
| `--no-confirm` / `-y` | Apply changes without a confirmation prompt |
| `--no-backup` | Skip creating backup files before writing |

### Whole-codebase refactoring (`--all-files`)

By default, `refactor` uses a single LLM call with a token-budget-limited context window — meaning only the highest-priority files are included. Pass `--all-files` with a directory path to refactor **every** source file in two phases:

1. **Planning** — The LLM receives the full structural summary of the codebase and produces a named, actionable refactoring strategy (themes, order of operations, file-specific notes).
2. **Execution** — All source files are grouped into token-budget-constrained batches. Each batch is refactored with the overall plan as context, ensuring consistent changes across files. Results from all batches are merged into a single plan.

The same diff-review → confirm → backup → write workflow applies — you see every proposed change before anything is written to disk.

```bash
# Refactor everything
uv run pyagent refactor ./my_project --all-files

# With a specific focus
uv run pyagent refactor ./my_project --all-files -i "modernize type hints and remove legacy patterns"

# Preview without writing
uv run pyagent refactor ./my_project --all-files --dry-run
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
