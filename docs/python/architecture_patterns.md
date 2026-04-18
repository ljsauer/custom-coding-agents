# Architecture Patterns

This document defines the structural and architectural standards for Python
projects. It covers module design, dependency management, packaging, and
application-level patterns.

Note: Do not apply these concepts literally or without clear need. Respect the existing structure of the code base and fit these concepts into it logically, without disruption the organization structure more than necessary. 

---

## 1. Project Layout

### 1.1 The `src` Layout

All projects use the `src/` layout:

```
project-name/
├── pyproject.toml
├── src/
│   └── package_name/
│       ├── __init__.py
│       └── ...
├── tests/
│   ├── conftest.py
│   └── ...
├── docs/
├── .env.example
├── .gitignore
├── .python-version
└── README.md
```

**Rationale:** The `src/` layout prevents accidental imports of the package
from the project root during development. It forces you to install the package
(even in editable mode), which catches packaging issues early.

### 1.2 `pyproject.toml` as Single Source of Truth

All project metadata, dependencies, tool configuration, and build settings live
in `pyproject.toml`. No `setup.py`, `setup.cfg`, `requirements.txt`,
`MANIFEST.in`, or scattered tool config files.

**Recommended structure:**
```toml
[project]
name = "package-name"
version = "0.1.0"
description = "What this project does"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.100",
    "pydantic>=2.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.8",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## 2. Module Design

### 2.1 One Concept Per Module

A module should have a single, clear responsibility. If a module's docstring
requires "and" to describe what it does, it should be split.

**Good module boundaries:**
```
package/
├── models.py        # Domain data models
├── exceptions.py    # Custom exception hierarchy
├── config.py        # Application configuration
├── service.py       # Business logic
├── repository.py    # Data access
└── api.py           # HTTP route handlers
```

**Bad module boundaries:**
```
package/
├── utils.py         # "Everything that doesn't fit elsewhere"
├── helpers.py       # Same problem, different name
├── core.py          # "The important stuff" (all of it)
└── misc.py          # Giving up on organization
```

### 2.2 Public API via `__init__.py`

A package's `__init__.py` defines its public API. It should re-export the names
that external consumers need and nothing else:

```python
"""User management package."""

from package.models import User, UserCreate, UserUpdate
from package.exceptions import UserNotFoundError, DuplicateUserError
from package.service import UserService

__all__ = [
    "User",
    "UserCreate",
    "UserUpdate",
    "UserNotFoundError",
    "DuplicateUserError",
    "UserService",
]
```

**Rules:**
- `__init__.py` contains imports and `__all__`. No logic.
- `__all__` is always defined and matches the imports.
- Internal modules not in `__all__` are private by convention.

### 2.3 Module-Level Code

Modules should be safe to import without side effects. No module-level code
should:
- Make network calls
- Open files (except for reading configuration at import time via Pydantic)
- Start threads or processes
- Print output

Side effects belong in explicitly called functions or application entry points.

---

## 3. Dependency Management

### 3.1 Dependency Direction

Dependencies flow inward. Outer layers depend on inner layers, never the
reverse:

```
HTTP/CLI (outer) → Service (middle) → Repository/Models (inner)
```

- **Models and exceptions** depend on nothing (or only the standard library
  and Pydantic).
- **Services** depend on models, exceptions, and repository interfaces
  (protocols).
- **API/CLI layers** depend on services.
- **Repositories** implement protocols defined by the service layer.

### 3.2 Dependency Injection

Use constructor injection for dependencies. Do not import and instantiate
dependencies inside business logic:

**Before (tight coupling):**
```python
class OrderService:
    def __init__(self) -> None:
        self._db = PostgresDatabase("postgresql://...")
        self._mailer = SmtpMailer("smtp://...")
```

**After (dependency injection):**
```python
class OrderService:
    def __init__(self, db: Database, mailer: Mailer) -> None:
        self._db = db
        self._mailer = mailer
```

Where `Database` and `Mailer` are protocols:
```python
class Database(Protocol):
    async def execute(self, query: str, params: dict[str, Any]) -> list[Row]: ...

class Mailer(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...
```

### 3.3 Composition Root

Dependencies are wired together at the application's entry point — the "composition root."
This is typically `main.py` or an application factory:

```python
def create_app() -> FastAPI:
    settings = Settings()
    db = PostgresDatabase(settings.database_url)
    mailer = SmtpMailer(settings.smtp_url)
    order_service = OrderService(db=db, mailer=mailer)

    app = FastAPI(lifespan=lifespan)
    app.include_router(create_order_router(order_service))
    return app
```

---

## 4. Application Patterns

### 4.1 Configuration

- **Single configuration object** using Pydantic `BaseSettings`.
- **Loaded once** at application startup.
- **Passed explicitly** to components that need it — never accessed as a
  global.
- **Environment-specific** values come from environment variables or `.env`
  files, never from code.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
    )

    debug: bool = False
    database_url: str
    redis_url: str = "redis://localhost:6379"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
```

### 4.2 Application Entry Point

The entry point is thin. It wires dependencies, configures logging, and starts
the application:

```python
"""Application entry point."""

from pyagent import logging
import sys

from package.config import Settings
from package.app import create_app
from package.logging import configure_logging


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level)
    app = create_app(settings)
    # Start the application (e.g., uvicorn.run for FastAPI)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 4.3 Service Layer

Business logic lives in service classes or functions, not in route handlers or CLI commands.
The service layer:

- Accepts and returns domain models (Pydantic models).
- Raises domain exceptions for error conditions.
- Has no knowledge of HTTP, CLI, or transport concerns.
- Receives its dependencies via constructor injection.

```python
class UserService:
    def __init__(self, repo: UserRepository, hasher: PasswordHasher) -> None:
        self._repo = repo
        self._hasher = hasher

    async def create_user(self, data: UserCreate) -> User:
        existing = await self._repo.find_by_email(data.email)
        if existing:
            raise DuplicateUserError(data.email)

        hashed_password = self._hasher.hash(data.password)
        user = User(
            id=generate_id(),
            name=data.name,
            email=data.email,
            password_hash=hashed_password,
        )
        await self._repo.save(user)
        return user
```

### 4.4 Repository Pattern

Data access is abstracted behind repository protocols. This allows:
- Swapping storage backends without changing business logic.
- Testing services with in-memory repositories.
- Clear separation between domain logic and persistence.

```python
class UserRepository(Protocol):
    async def find_by_id(self, user_id: str) -> User | None: ...
    async def find_by_email(self, email: str) -> User | None: ...
    async def save(self, user: User) -> None: ...
    async def delete(self, user_id: str) -> None: ...
```

---

## 5. Error Handling Architecture

### 5.1 Exception Hierarchy

Define a base exception for the application and derive domain exceptions from
it. Place all exceptions in a dedicated `exceptions.py`:

```python
class AppError(Exception):
    """Base exception for the application."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ConflictError(AppError):
    """Raised when an operation conflicts with existing state."""


class ValidationError(AppError):
    """Raised when input validation fails."""
```

### 5.2 Error Translation at Boundaries

Transport layers (HTTP, CLI) translate domain exceptions into transport-appropriate responses:

```python
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})

@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": str(exc)})
```

---

## 6. Testing Architecture

### 6.1 Test Organization

Mirror the source layout:

```
tests/
├── conftest.py              # Shared fixtures
├── test_models.py           # Unit tests for models
├── test_service.py          # Unit tests for services
├── test_repository.py       # Integration tests for repositories
└── test_api.py              # Integration tests for HTTP endpoints
```

### 6.2 Test Fixtures and Factories

Use factory functions for test data:

```python
def make_user(**overrides: Any) -> User:
    defaults = {
        "id": "user-001",
        "name": "Test User",
        "email": "test@example.com",
        "role": UserRole.MEMBER,
    }
    return User(**(defaults | overrides))
```

Use fixtures for dependencies:

```python
@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()

@pytest.fixture
def user_service(user_repo: InMemoryUserRepository) -> UserService:
    return UserService(repo=user_repo, hasher=FakeHasher())
```

### 6.3 Test Boundaries

- **Unit tests** test services and models in isolation with fake dependencies.
- **Integration tests** test repositories against real (or containerized)
  databases and HTTP endpoints via `TestClient`.
- **Never mock what you own.** Use fake implementations of your own protocols
  instead. Mocks test interaction patterns; fakes test behavior.

---

## 7. Async Architecture

### 7.1 Structured Concurrency

Use `asyncio.TaskGroup` (Python 3.11+) for managing concurrent operations:

```python
async def fetch_user_data(user_id: str) -> UserProfile:
    async with asyncio.TaskGroup() as tg:
        user_task = tg.create_task(repo.get_user(user_id))
        prefs_task = tg.create_task(repo.get_preferences(user_id))
        history_task = tg.create_task(repo.get_history(user_id))

    return UserProfile(
        user=user_task.result(),
        preferences=prefs_task.result(),
        history=history_task.result(),
    )
```

### 7.2 Async Lifecycle

Use FastAPI's `lifespan` for async resource management:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    pool = await create_pool(settings.database_url)
    app.state.db = pool
    yield
    # Shutdown
    await pool.close()

app = FastAPI(lifespan=lifespan)
```
