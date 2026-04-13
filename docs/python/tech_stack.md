# Tech Stack

This document defines the preferred tools, libraries, and frameworks for Python
projects reviewed or produced by this agent. Each choice includes its rationale
and known exceptions.

The format is: **Tool → Use Case → Rationale → Exceptions**.

---

## 1. Package Management: `uv`

**Use case:** Dependency resolution, virtual environment management, package
installation, project scaffolding.

**Rationale:** `uv` is a Rust-based drop-in replacement for `pip`, `pip-tools`,
`virtualenv`, and `pyenv` in a single binary. It is orders of magnitude faster
than pip for dependency resolution and installation, supports lockfiles natively,
and manages Python versions directly. It aligns with the principle of reducing
tool sprawl — one tool instead of four.

**Key commands:**
```bash
uv init                      # Scaffold a new project
uv add <package>             # Add a dependency
uv add --dev <package>       # Add a dev dependency
uv sync                      # Install from lockfile
uv run <command>             # Run a command in the project's venv
uv python install 3.12       # Install a Python version
```

**Exceptions:** None. If a project currently uses `poetry`, `pdm`, or bare `pip`
with `requirements.txt`, recommend migration to `uv` during refactoring.

---

## 2. Backend Framework: FastAPI

**Use case:** HTTP APIs, webhooks, backend services.

**Rationale:** FastAPI is async-native, uses Pydantic for request/response
validation by default, generates OpenAPI documentation automatically, and
enforces type annotations at the framework level. It aligns with the standards
in this codebase: type-first, explicit, and modern. Starlette underneath provides
a mature ASGI foundation.

**Key patterns:**
- Use dependency injection (`Depends`) for shared logic (auth, DB sessions).
- Use Pydantic models for all request/response bodies — never raw dicts.
- Use `APIRouter` to organize routes by domain.
- Use `lifespan` context manager for startup/shutdown logic.

**Exceptions:** For CLI tools, simple scripts, or non-HTTP services, FastAPI is
not relevant. Do not force an HTTP layer where one is not needed.

---

## 3. Data Modeling and Validation: Pydantic

**Use case:** Data classes, input validation, environment variable loading,
application configuration, serialization/deserialization.

**Rationale:** Pydantic provides runtime validation with a type-annotation-first
API. It replaces the need for manual validation logic, reduces boilerplate, and
integrates natively with FastAPI. Using Pydantic as the single data modeling
layer across an application (config, domain models, API schemas) creates
consistency and reduces cognitive overhead.

**Preferred over:**
- `dataclasses` — Pydantic provides validation, serialization, and schema
  generation that dataclasses do not. Use dataclasses only for simple internal
  data containers where validation is unnecessary and Pydantic would be
  over-engineering (e.g., grouping a few related values inside a function's
  private logic).
- `NamedTuple` — Use NamedTuple only for lightweight immutable records that
  need tuple semantics (unpacking, indexing).
- `TypedDict` — Use TypedDict only when interfacing with code that expects
  plain dicts (e.g., JSON payloads to third-party libraries that do not accept
  objects).
- `attrs` — Pydantic and attrs overlap significantly. Standardize on Pydantic
  for consistency.

**Key patterns:**
```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
    )

    debug: bool = False
    database_url: str
    api_key: str = Field(min_length=1)
    log_level: str = "INFO"


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[\w.-]+@[\w.-]+\.\w+$")
    role: UserRole = UserRole.MEMBER
```

**Exceptions:** Performance-critical inner loops where Pydantic's validation
overhead is measurable. Profile first — premature optimization is the root of
all evil.

---

## 4. Formatting and Linting: `ruff`

**Use case:** Code formatting, import sorting, linting, style enforcement.

**Rationale:** `ruff` is a single Rust-based tool that replaces `black`,
`isort`, `flake8`, `pylint`, and `pycodestyle`. It is fast enough to run on
save and on every commit without friction. It enforces PEP 8 and a wide range
of best-practice rules. Consolidating to one tool eliminates configuration
conflicts between separate linters and formatters.

**Recommended `pyproject.toml` configuration:**
```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # type-checking imports
    "RUF",  # ruff-specific rules
    "S",    # flake8-bandit (security)
    "C4",   # flake8-comprehensions
    "PTH",  # flake8-use-pathlib
    "RET",  # flake8-return
    "ARG",  # flake8-unused-arguments
]

[tool.ruff.lint.isort]
known-first-party = ["your_package"]
```

**Exceptions:** None. All Python projects should use `ruff`.

---

## 5. Static Type Checking: `ty`

**Use case:** Static analysis of type annotations.

**Rationale:** `ty` is Astral's (the makers of `ruff` and `uv`) type checker
for Python. It is designed to integrate naturally with the `ruff` + `uv`
toolchain. Using tools from the same ecosystem reduces friction and
configuration overhead.

**Exceptions:** Projects with complex type-level logic (heavy generics, plugin
systems, metaclass patterns) may still benefit from `mypy` or `pyright` for
their more mature handling of edge cases. Evaluate on a per-project basis.

---

## 6. Testing: `pytest`

**Use case:** All testing — unit, integration, functional.

**Rationale:** `pytest` is the de facto standard. It supports plain `assert`
statements, powerful fixtures, parametrize, and a rich plugin ecosystem.
`unittest`-style test classes with `setUp`/`tearDown` are needlessly verbose.

**Key patterns:**
- Use `conftest.py` for shared fixtures.
- Use `pytest-asyncio` for async test functions.
- Use `pytest-cov` for coverage reporting.
- Use `factory_boy` or simple fixture factories over complex fixture chains.

**Exceptions:** None.

---

## 7. ORM: SQLAlchemy

**Use case:** Database modeling, querying, and object-relational mapping.

**Rationale:** SQLAlchemy is the most mature and capable ORM in the Python
ecosystem. Its 2.0-style API embraces type annotations, supports both sync and
async engines, and provides fine-grained control over query generation without
sacrificing the convenience of mapped classes. It pairs naturally with Pydantic
for the data boundary: SQLAlchemy models own the persistence layer, Pydantic
models own the API/validation layer.

**Key patterns:**
- Use the 2.0-style `DeclarativeBase` with `Mapped` and `mapped_column` for
  all model definitions — never the legacy 1.x declarative style.
- Use `AsyncSession` with `create_async_engine` for async applications.
- Keep SQLAlchemy models in a dedicated `models/` or `db/models.py` module,
  separate from Pydantic schemas.
- Define relationships explicitly with `relationship()` and `Mapped[]`
  annotations.
- Use `sessionmaker` (or `async_sessionmaker`) bound at startup, injected
  into services via dependency injection — never create sessions ad hoc.
- Prefer `select()` statements over the legacy `Query` API.

**Example (2.0 style):**
```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    posts: Mapped[list["Post"]] = relationship(back_populates="author")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="posts")
```

**Preferred over:**
- `Django ORM` — tightly coupled to the Django framework. Not suitable for
  FastAPI or standalone applications.
- `Tortoise ORM` — less mature, smaller ecosystem, weaker type support.
- `Peewee` — simpler but lacks the power and flexibility needed for complex
  query patterns.
- Raw SQL everywhere — acceptable for simple scripts or performance-critical
  queries, but for applications with a domain model, an ORM provides
  structure, safety, and maintainability.

**Exceptions:** For read-heavy analytics or reporting queries where ORM
overhead is measurable, drop to raw SQL via `session.execute(text(...))` or
use SQLAlchemy Core (table-level, non-ORM) constructs. The ORM and Core
coexist cleanly.

---

## 8. Database Migrations: Alembic

**Use case:** Schema versioning, migration generation, and database evolution.

**Rationale:** Alembic is SQLAlchemy's official migration tool. It generates
migration scripts from model diffs, supports both upgrade and downgrade paths,
and integrates directly with SQLAlchemy's metadata. Using anything else with
SQLAlchemy is fighting the ecosystem.

**Key patterns:**
- Initialize with `alembic init --template async migrations` for async
  projects.
- Configure `target_metadata` in `env.py` to point to your `Base.metadata`
  so autogeneration works.
- Always review autogenerated migrations before applying — they are drafts,
  not final products.
- Write data migrations as separate scripts from schema migrations. Do not
  mix DDL and DML in the same migration.
- Name migration files descriptively: `add_user_email_index`, not
  `update_table`.
- Always include a `downgrade()` function — even if it is just
  `op.drop_table()`. Irreversible migrations should raise
  `NotImplementedError` in `downgrade()` with a comment explaining why.

**Key commands:**
```bash
alembic revision --autogenerate -m "add posts table"   # Generate migration
alembic upgrade head                                    # Apply all pending
alembic downgrade -1                                    # Rollback one step
alembic history                                         # View migration history
alembic current                                         # Show current revision
```

**Exceptions:** None. If the project uses SQLAlchemy, it uses Alembic for
migrations. Manual SQL migration scripts are not acceptable for applications.

---

## 9. Logging: `logging` (standard library)

**Use case:** All runtime output — diagnostics, operational events, errors.

**Rationale:** The `logging` module is built-in, configurable, and supports
structured output. `print()` statements have no level, no filtering, no routing,
and no structured context. They are unacceptable in production code.

**Key patterns:**
- Create a reusable logger factory (see `python_standards.md`, Section 13).
- Use `structlog` as an enhancement layer for structured JSON logging in
  production services, while keeping the standard `logging` module as the
  backend.
- Configure logging once at the application entry point, not in library modules.

**Exceptions:** `print()` is acceptable in:
- One-off scripts that will not be maintained.
- CLI output that is the program's *product* (e.g., `typer`/`click` output
  formatting). Even then, prefer `rich` or `typer.echo`.

---

## 10. CLI Framework: `typer` + `rich`

**Use case:** Command-line interfaces and terminal output formatting.

**Rationale:** `typer` builds on `click` with type-annotation-driven argument
parsing. It aligns with the type-first philosophy and integrates naturally with
Pydantic. It reduces boilerplate compared to raw `argparse` or `click`.

`rich` is the recommended companion for all terminal output beyond basic text.
It provides styled text, tables, progress bars, tracebacks, syntax
highlighting, panels, and tree views — all with minimal API surface. `typer`
has built-in `rich` integration via `rich_help_panel` and automatically renders
rich-formatted help text when `rich` is installed.

**Key patterns:**
- Use `rich.console.Console` for all styled output instead of `print()` or
  `typer.echo()`.
- Use `rich.table.Table` for tabular CLI output.
- Use `rich.progress` for long-running operations.
- Use `rich.traceback.install()` at the entry point for readable tracebacks
  during development.
- Use `rich.panel.Panel` and `rich.syntax.Syntax` for displaying code or
  structured information.

**Exceptions:** For extremely simple scripts with one or two arguments,
`argparse` from the standard library is fine. Do not over-engineer a CLI for a
script that takes a filename. `rich` is not needed for scripts with no
user-facing terminal output.

---

## 11. HTTP Client: `httpx`

**Use case:** Making HTTP requests (sync and async).

**Rationale:** `httpx` provides both sync and async interfaces, follows the
`requests` API closely, supports HTTP/2, and integrates well with `asyncio`. It
is the natural choice for async-first applications and a strict improvement over
`requests` for new code.

**Exceptions:** Projects already using `aiohttp` with no issues do not need to
migrate unless undergoing a broader refactor.

---

## 12. Import Discipline

**Rule:** All imports are at module level unless there is a documented,
necessary exception.

**Acceptable exceptions:**
- **Circular import resolution**: When two modules depend on each other and
  restructuring is not feasible in the current scope.
- **Optional heavy dependencies**: When a module conditionally uses a library
  that is expensive to import or not always installed.

**Documentation requirement:** Every in-function import must include a comment:
```python
def render_chart(data: ChartData) -> bytes:
    # Imported here: matplotlib is an optional heavy dependency
    # not required for non-chart code paths
    import matplotlib.pyplot as plt
    ...
```

---

## 13. Path Handling: `pathlib`

**Use case:** All filesystem path construction and manipulation.

**Rationale:** `pathlib.Path` provides an object-oriented, cross-platform API
for path operations. It is more readable and less error-prone than `os.path`
string manipulation.

**Exceptions:** None. `os.path` is legacy. Use `Path`.

---

## Summary Table

| Concern | Tool | Replaces |
|---------|------|----------|
| Package management | `uv` | pip, pip-tools, poetry, pyenv |
| Backend framework | FastAPI | Flask, Django REST |
| Data modeling | Pydantic | dataclasses, attrs, marshmallow |
| Formatting + linting | `ruff` | black, isort, flake8, pylint |
| Type checking | `ty` | mypy, pyright |
| Testing | `pytest` | unittest |
| ORM | SQLAlchemy (2.0) | Django ORM, Tortoise, Peewee |
| Database migrations | Alembic | manual SQL scripts, Django migrations |
| Logging | `logging` + `structlog` | print statements |
| CLI | `typer` + `rich` | argparse, click |
| HTTP client | `httpx` | requests, aiohttp |
| Path handling | `pathlib` | os.path |
