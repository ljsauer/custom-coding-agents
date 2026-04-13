# Anti-Patterns

This document catalogs Python anti-patterns, code smells, and common mistakes
that this agent should flag during code review. Each entry includes: what the
problem is, why it matters, and what to do instead.

---

## 1. Structural Anti-Patterns

### 1.1 God Module

**Symptom:** A single file exceeds ~400 lines or handles multiple unrelated
concerns.

**Why it matters:** Large modules are hard to navigate, hard to test in
isolation, and create merge conflicts. They violate "one concept per module."

**Fix:** Split by responsibility. A module named `utils.py` that has grown to
500 lines is begging to become a `utils/` package with focused submodules.

---

### 1.2 God Class

**Symptom:** A class with more than ~10 public methods or that mixes multiple
responsibilities (e.g., data access, business logic, and formatting).

**Why it matters:** Same as God Module, but at the class level. Classes should
have a single axis of change.

**Fix:** Extract cohesive method groups into collaborator classes. Use
composition and dependency injection.

---

### 1.3 Circular Imports

**Symptom:** `ImportError` at runtime, or imports buried inside functions to
avoid import-time failures.

**Why it matters:** Circular imports indicate tangled dependencies. They make
the codebase fragile and hard to reason about.

**Fix:** Restructure modules to break the cycle. Common strategies:
- Extract shared types/interfaces into a separate module.
- Use `TYPE_CHECKING` for imports only needed by type annotations:
  ```python
  from __future__ import annotations
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from other_module import SomeClass
  ```
- Invert the dependency with a protocol/interface.

---

### 1.4 Flat Project Layout

**Symptom:** All Python files in a single directory with no package structure.

**Why it matters:** Flat layouts do not scale. They make imports ambiguous,
testing harder, and packaging impossible.

**Fix:** Use `src/` layout with a proper package and `pyproject.toml` from
day one.

---

## 2. Typing Anti-Patterns

### 2.1 Untyped Functions

**Symptom:** Functions with no type annotations on parameters or return values.

**Why it matters:** Without type annotations, static analysis tools are blind,
IDE support degrades, and documentation is lost.

**Fix:** Annotate all function signatures. Use `ty` to verify.

---

### 2.2 Overuse of `Any`

**Symptom:** `Any` scattered through the codebase, especially in function
parameters and return types.

**Why it matters:** `Any` disables type checking wherever it appears. It is
a virus — it propagates through assignments and return values.

**Fix:** Replace with specific types. If the type is genuinely unknown, use
`object` (which is type-safe, unlike `Any`). If interfacing with untyped
third-party code, isolate the `Any` to a thin adapter layer and document it.

---

### 2.3 Legacy Type Syntax

**Symptom:** `Optional[X]`, `List[str]`, `Dict[str, int]`, `Union[X, Y]`
in projects targeting Python 3.10+.

**Why it matters:** Modern syntax (`X | None`, `list[str]`, `dict[str, int]`)
is more readable and is the standard going forward.

**Fix:** Use `pyupgrade` (via ruff's `UP` rules) to auto-migrate.

---

### 2.4 Stringly-Typed Code

**Symptom:** Using raw strings where enums, constants, or types should be used:
```python
if user.role == "admin":  # Magic string
    ...
```

**Why it matters:** Typos become silent bugs. No autocompletion, no refactoring
support.

**Fix:** Use `StrEnum` or constants:
```python
class UserRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"

if user.role == UserRole.ADMIN:
    ...
```

---

## 3. Function Anti-Patterns

### 3.1 Mutable Default Arguments

**Symptom:**
```python
def process(items: list[str] = []) -> list[str]:
    items.append("new")
    return items
```

**Why it matters:** The default list is shared across all calls. This is one of
Python's most infamous footguns.

**Fix:** Use `None` sentinel:
```python
def process(items: list[str] | None = None) -> list[str]:
    items = items if items is not None else []
    ...
```

---

### 3.2 Boolean Trap

**Symptom:** Functions with boolean parameters that change behavior:
```python
def render(data, verbose=False, include_header=True, raw=False):
    ...
```

**Why it matters:** Call sites become unreadable — `render(data, True, False, True)`
tells the reader nothing.

**Fix:** Use keyword-only arguments or, for complex cases, an enum or config
object:
```python
def render(data: Data, *, verbose: bool = False, include_header: bool = True) -> str:
    ...
```

---

### 3.3 Deep Nesting

**Symptom:** More than two or three levels of indentation inside a function.

**Why it matters:** Deep nesting makes control flow hard to follow and hides
bugs in rarely-reached branches.

**Fix:** Use guard clauses (early returns), extract helper functions, or
restructure logic.

---

### 3.4 Returning Multiple Types

**Symptom:** A function that returns different types depending on conditions:
```python
def find_user(user_id: int) -> User | dict | None:
    ...
```

**Why it matters:** Callers must handle multiple shapes, leading to brittle
`isinstance` checks. The function's contract is unclear.

**Fix:** Return a single type. Use exceptions for error cases, `None` only
when "not found" is a normal condition, and never return a dict as a degraded
form of a proper model.

---

## 4. Data Anti-Patterns

### 4.1 Primitive Obsession

**Symptom:** Using raw strings, ints, or dicts to represent domain concepts:
```python
def create_order(user_id: str, product_id: str, quantity: int, price: float):
    ...
```

**Why it matters:** Nothing prevents passing `product_id` where `user_id` is
expected. The types carry no semantic meaning.

**Fix:** Use `NewType` for lightweight type-level distinction, or full
Pydantic models for validated domain objects.

---

### 4.2 Dictionary-Driven Development

**Symptom:** Passing `dict[str, Any]` between functions as the primary data
structure:
```python
def process(data: dict[str, Any]) -> dict[str, Any]:
    ...
```

**Why it matters:** No validation, no autocompletion, no documentation, no
type safety. Every consumer must know the dict's implicit schema.

**Fix:** Define a Pydantic model or dataclass. Known-shape data should always
be modeled.

---

### 4.3 Stringly-Typed Errors

**Symptom:** Returning error strings instead of raising exceptions:
```python
def validate(input: str) -> str:
    if not input:
        return "Error: input is empty"
    return input
```

**Why it matters:** Callers must check return values for magic error strings.
The type system cannot distinguish success from failure.

**Fix:** Raise specific exceptions for failures. Reserve return values for
success.

---

## 5. Style Anti-Patterns

### 5.1 Print-Driven Development

**Symptom:** Using `print()` for debugging, status updates, or error reporting
in application code.

**Why it matters:** `print()` has no log levels, no filtering, no routing,
and no structured context. It writes to stdout unconditionally and cannot be
silenced in tests or production.

**Fix:** Use the `logging` module. See `tech_stack.md`, Section 7.

---

### 5.2 Commented-Out Code

**Symptom:** Blocks of code commented out with `#`, left in the file.

**Why it matters:** Dead code is noise. It confuses readers, clutters diffs,
and decays as the surrounding code evolves. Version control preserves history.

**Fix:** Delete it. If it might be needed, it is in git history.

---

### 5.3 Wildcard Imports

**Symptom:** `from module import *`

**Why it matters:** Pollutes the namespace, makes dependency tracking
impossible, and can cause silent name collisions.

**Fix:** Import specific names. Always.

---

### 5.4 Bare `except`

**Symptom:**
```python
try:
    ...
except:
    ...
```

**Why it matters:** Catches `SystemExit`, `KeyboardInterrupt`, and
`GeneratorExit` — things that should almost never be caught. Even
`except Exception` is too broad in most contexts.

**Fix:** Catch specific exceptions.

---

### 5.5 Magic Numbers and Strings

**Symptom:** Numeric or string literals embedded in logic without explanation:
```python
if retry_count > 3:
    ...
time.sleep(0.5)
```

**Why it matters:** The reader cannot know why `3` or `0.5` was chosen.
Changes require finding every occurrence.

**Fix:** Extract to named constants:
```python
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5
```

---

### 5.6 Using `os.path` Instead of `pathlib`

**Symptom:**
```python
import os
path = os.path.join(base_dir, "data", filename)
```

**Why it matters:** `os.path` is a string-manipulation API disguised as path
handling. It is error-prone, verbose, and lacks the composability of `pathlib`.

**Fix:**
```python
from pathlib import Path
path = Path(base_dir) / "data" / filename
```

---

## 6. Async Anti-Patterns

### 6.1 Sync in Async

**Symptom:** Calling blocking I/O (file reads, `requests.get`, `time.sleep`)
inside an `async` function.

**Why it matters:** Blocks the entire event loop, negating the benefits of
async. Other coroutines cannot run during the blocking call.

**Fix:** Use async equivalents (`aiofiles`, `httpx.AsyncClient`,
`asyncio.sleep`). For unavoidable sync calls, use `asyncio.to_thread`.

---

### 6.2 Fire-and-Forget Tasks

**Symptom:** `asyncio.create_task(coro())` without storing or awaiting the
task reference.

**Why it matters:** The task can be garbage collected before completing.
Exceptions are silently swallowed.

**Fix:** Use `asyncio.TaskGroup` (3.11+) for structured concurrency, or store
task references and handle exceptions:
```python
async with asyncio.TaskGroup() as tg:
    tg.create_task(some_work())
    tg.create_task(other_work())
```

---

### 6.3 Mixing Sync and Async I/O

**Symptom:** An async application that uses `requests` alongside `httpx` async
client, or mixes `open()` with `aiofiles`.

**Why it matters:** Sync I/O in an async context blocks the event loop. Mixed
usage signals an incomplete async migration.

**Fix:** Go fully async. Replace all sync I/O with async equivalents.

---

## 7. Security Anti-Patterns

### 7.1 Hardcoded Secrets

**Symptom:** API keys, passwords, or tokens in source code.

**Why it matters:** Secrets in code end up in version control, logs, and error
reports.

**Fix:** Use environment variables loaded via Pydantic `BaseSettings`.

---

### 7.2 Unvalidated Input

**Symptom:** Using user input directly without validation:
```python
query = f"SELECT * FROM users WHERE name = '{name}'"
```

**Why it matters:** Injection attacks. This applies to SQL, shell commands,
file paths, and template rendering.

**Fix:** Use parameterized queries, Pydantic validation, and `shlex.quote`
for shell arguments. Never interpolate user input into executable strings.

---

### 7.3 Overly Broad File Permissions

**Symptom:** Writing files with default permissions in security-sensitive
contexts.

**Why it matters:** Sensitive files (configs with secrets, key files) should
not be world-readable.

**Fix:** Use `Path.chmod()` or `os.open` with explicit mode bits.
