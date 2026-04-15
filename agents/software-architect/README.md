# archagent

A conversational software-architecture advisor grounded in Domain-Driven Design, Clean Architecture, Hexagonal Architecture, and Onion Architecture. Part of the [custom-coding-agents](../../README.md) workspace.

## Quickstart

```bash
# From the workspace root:
uv sync --extra dev

# Set your API key.
cp ../../.env.example ../../.env
# Edit .env and add ANTHROPIC_API_KEY

# Start an interactive architecture review session.
uv run archagent chat

# Resume a prior session (or list them first).
uv run archagent list-sessions
uv run archagent resume 20260415_153527

# Show resolved configuration and knowledge-base stats.
uv run archagent info
```

## Commands

| Command | Description |
|---------|-------------|
| `chat` | Start (or resume) an interactive architecture-review session |
| `list-sessions` | Show previously saved sessions, optionally filtered by project |
| `resume <id>` | Shortcut for `chat --resume <id>` |
| `info` | Show resolved configuration and loaded knowledge-base stats |

### `chat` options

| Flag | Description |
|------|-------------|
| `--project` / `-p` | Project name used to scope persisted decisions and sessions (default: `default`) |
| `--resume` / `-r` | Session ID to resume instead of starting a new one |
| `--model` / `-m` | Override the default Claude model |

Inside the chat loop:
- `:decide <text>` logs an architectural decision against the current project. Decisions are surfaced automatically in subsequent sessions' system prompt.
- `:quit` exits and saves the session.

## Configuration

Settings are read from environment variables (optionally via a `.env` file) and resolved by [`archagent.config.Settings`](src/archagent/config.py).

| Env var | Default | Purpose |
|---------|---------|---------|
| `ANTHROPIC_API_KEY` | _required_ | API key for Claude access |
| `ARCHAGENT_MODEL` | `claude-sonnet-4-6` | Model ID to use |
| `ARCHAGENT_MAX_TOKENS` | `4096` | Upper bound on model output tokens per turn |
| `ARCHAGENT_LOG_LEVEL` | `INFO` | Log level name |
| `ARCHAGENT_DOCS_PATH` | `<repo>/docs/architecture` | Directory of `.md` files indexed for RAG |
| `AGENT_WORKSPACE` | _unset_ | Directory the agent is allowed to write into (gates `write_file` / `edit_file`) |

By default the agent can read files and describe project trees. The `write_file` and `edit_file` tools are off unless `AGENT_WORKSPACE` is set, and writes outside that directory are refused. Every write is also confirmed interactively in the terminal before it lands on disk.

## Knowledge base

archagent's opinions are codified in the documents under [`docs/architecture/`](../../docs/architecture/):

| Document | Purpose |
|----------|---------|
| `design_influences.md` | Canonical references for DDD, Clean, Hexagonal, Onion |
| `foundational_patterns.md` | Aggregate, repository, service classification, layer rules |
| `general_rules.md` | Cross-cutting decision heuristics |

Documents are indexed with sentence-transformer embeddings (`all-MiniLM-L6-v2`) at agent startup and retrieved via similarity to the current user query.

## Architecture

```
src/archagent/
├── __main__.py      # Typer CLI (chat / list-sessions / resume / info)
├── agent.py         # ArchAgent — injects Settings, orchestrates tools + RAG + memory
├── config.py        # Pydantic Settings
├── logging.py       # namespaced logger factory
├── memory.py        # JSON-on-disk session + decision persistence under ~/.arch_agent
├── prompts.py       # SYSTEM_PROMPT with the mandatory evaluation procedure
├── rag.py           # ArchitectureKnowledgeBase — embedding-based retrieval
└── tools/
    ├── definitions.py  # Anthropic tool-use JSON schemas
    └── executor.py     # Dispatcher for read_file / describe_project_structure / write_file / edit_file
```

Mirrors [pyagent's layout](../fluent-pythonista/src/pyagent/) so that reading one package informs reading the other.

## Development

```bash
# Run archagent's tests.
uv run pytest agents/software-architect/test_archagent.py -v

# Lint.
uv run ruff check agents/software-architect/
```
