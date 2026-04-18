# custom-coding-agents

A [uv](https://docs.astral.sh/uv/) workspace containing two independently-packaged coding agents:

- **[pyagent](agents/fluent-pythonista/)** — an opinionated Python code reviewer, refactorer, and explainer. Named patterns from a built-in playbook, whole-codebase two-phase refactor flow, and RAG over a local documentation set.
- **[archagent](agents/software-architect/)** — a conversational software-architecture advisor grounded in DDD, Clean, Hexagonal, and Onion Architecture. Tracks decisions per project and can propose (and, with opt-in, apply) file edits.

Each agent is its own package with its own `pyproject.toml` and script entry point. A single `uv.lock` at the root covers the whole workspace.

## Quickstart

```bash
# Install uv if you don't have it.
curl -LsSf https://astral.sh/uv/install.sh | sh

# From the repo root:
uv sync --extra dev          # resolves both agents' dependencies into one venv

# Set your API key (both agents read ANTHROPIC_API_KEY).
cp .env.example .env
# edit .env

# Run either agent from the root — no `cd` needed.
uv run pyagent --help
uv run pyagent refactor path/to/project/          # full two-phase codebase refactor
uv run pyagent refactor path/to/file.py           # single-file refactor

uv run archagent                                  # interactive architecture advisor
```

## Running tests

```bash
uv run pytest agents/fluent-pythonista/test_core.py -v
uv run pytest agents/software-architect/test_archagent.py -v
```

## Repo layout

```
custom-coding-agents/
├── pyproject.toml              # workspace root
├── uv.lock                     # single lock for the whole workspace
├── agents/
│   ├── pythonista-agent/       # pyagent package
│   │   ├── pyproject.toml
│   │   ├── src/pyagent/
│   │   ├── test_core.py
│   │   └── README.md
│   └── software-architect/     # archagent package
│       ├── pyproject.toml
│       ├── src/archagent/
│       └── test_archagent.py
├── docs/
│   ├── architecture/           # consumed by archagent's RAG index
│   └── python/                 # consumed by pyagent's RAG index
└── collage-maker-refactor-example/   # sample codebase used to exercise pyagent
```

Each agent can also be used standalone from its own directory (`cd agents/pythonista-agent && uv run pyagent …`) — workspace membership is additive, not exclusive.

## Configuration

Both agents read `ANTHROPIC_API_KEY` from the environment or a local `.env` file. archagent additionally reads an optional `AGENT_WORKSPACE` variable — set it to a directory path to enable archagent's `write_file` / `edit_file` tools, scoped to that directory. Without it, those tools refuse to run.

See each agent's own README for command-level detail:

- [pyagent README](agents/fluent-pythonista/README.md)
