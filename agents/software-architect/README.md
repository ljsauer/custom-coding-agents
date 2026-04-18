# archagent

A conversational software-architecture advisor grounded in Domain-Driven Design, Clean Architecture, Hexagonal Architecture, and Onion Architecture. Part of the [custom-coding-agents](../../README.md) workspace.

## Quickstart

```bash
# Install uv if you don't have it.
curl -LsSf https://astral.sh/uv/install.sh | sh

# From the workspace root — the workspace lockfile covers this package.
uv sync --extra dev

# Set your API key (the workspace .env at the repo root is read automatically).
cp ../../.env.example ../../.env
# Edit .env and add ANTHROPIC_API_KEY

# Start an interactive architecture review session.
uv run archagent chat

# Scope decisions and history to a named project.
uv run archagent chat --project my-service

# Enable file writes by setting AGENT_WORKSPACE first.
AGENT_WORKSPACE=/path/to/project uv run archagent chat -p my-service

# Resume a prior session (or list them first).
uv run archagent list-sessions
uv run archagent list-sessions --project my-service
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

`archagent --version` prints the installed version and exits. All other global options live on the subcommands.

### `chat` options

| Flag | Description |
|------|-------------|
| `--project` / `-p` | Project name used to scope persisted decisions and sessions (default: `default`) |
| `--resume` / `-r` | Session ID to resume instead of starting a new one |
| `--model` / `-m` | Override the default Claude model |

Inside the chat loop:
- `:decide <text>` logs an architectural decision against the current project. Decisions are surfaced automatically in subsequent sessions' system prompt.
- `:quit` exits and saves the session. `Ctrl-C` / `Ctrl-D` also save and exit.

Sessions and per-project decisions are persisted as JSON under `~/.arch_agent/` — one directory per project, one file per session.

## Tools

The agent drives Claude's tool-use API with four tools:

| Tool | Description |
|------|-------------|
| `read_file` | Read a source file for review. |
| `describe_project_structure` | List a directory tree (with `max_depth`) to understand layer structure. |
| `write_file` | Write/replace file contents. Disabled unless `AGENT_WORKSPACE` is set, and refuses paths outside it. |
| `edit_file` | Replace an exact `old_str` match with `new_str` in a file. Same workspace gating as `write_file`. |

Every write is confirmed interactively in the terminal before it lands on disk.

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
| `HF_TOKEN` | _unset_ | Optional Hugging Face token used when downloading the sentence-transformer embedding model on first run |

By default the agent can read files and describe project trees. The `write_file` and `edit_file` tools are off unless `AGENT_WORKSPACE` is set, and writes outside that directory are refused.

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
# Install with dev dependencies (from the workspace root).
uv sync --extra dev

# Run archagent's tests.
uv run pytest agents/software-architect/test_archagent.py -v

# Lint and format.
uv run ruff check agents/software-architect/
uv run ruff format agents/software-architect/
```

## Related

- [pyagent](../fluent-pythonista/) — the Python-focused reviewer/refactorer companion that lives in the same workspace.
