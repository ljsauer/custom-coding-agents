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

## Architecture

```
src/pyagent/
├── __main__.py     # CLI entrypoint (typer + rich)
├── agent.py        # Core orchestration loop
├── config.py       # Pydantic settings
├── context.py      # Codebase ingestion & AST parsing
├── logging.py      # Structured logger factory
├── memory.py       # Conversation state management
├── prompts.py      # Prompt templates per capability
├── rag.py          # Documentation retrieval
└── tools/
    ├── base.py       # Tool protocol
    ├── reviewer.py   # Code review tool
    ├── refactor.py   # Refactoring tool
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
