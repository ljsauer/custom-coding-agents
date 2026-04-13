# Python Standards

> *"Readability counts." — The Zen of Python*

This document defines the Python coding standards enforced by this agent. It is
opinionated by design. These are not suggestions — they are the baseline
expectations for any Python code this agent reviews, refactors, or produces.

The standards draw from three authoritative sources:

- [The Python Language Reference](https://docs.python.org/3/reference/index.html)
- [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/)
- *Fluent Python* by Luciano Ramalho

---

## 1. The Zen of Python as Operating Philosophy

The Zen of Python is not decoration. It is the decision framework when style questions arise. 
The most operationally important koans are:

- **Explicit is better than implicit.** Never rely on side effects, magic
  globals, or implicit type coercion when an explicit alternative exists.
- **Simple is better than complex. Complex is better than complicated.** Choose
  the simplest construct that fully expresses the intent. A list comprehension
  is simpler than a manual loop with `.append()`. A generator expression is
  simpler than building a full list you only iterate once.
- **Flat is better than nested.** If a function has more than two levels of
  indentation, it likely needs extraction or early returns.
- **There should be one — and preferably only one — obvious way to do it.**
  When the standard library provides a tool, use it. Do not reinvent
  `itertools`, `functools`, `collections`, or `pathlib`.
- **If the implementation is hard to explain, it's a bad idea.** Code that
  requires a paragraph of comments to justify its structure should be
  restructured, not annotated.
- **Namespaces are one honking great idea.** Use modules and packages to
  organize code. Avoid polluting the global namespace. Never use wildcard
  imports (`from module import *`).

---

## 2. Naming Conventions

Naming is not cosmetic. Names are the primary documentation layer.

### 2.1 General Rules

- **Variables and functions**: `snake_case`. No exceptions.
- **Classes**: `PascalCase`. No exceptions.
- **Constants**: `UPPER_SNAKE_CASE`. Defined at module level.
- **Private attributes/methods**: Single leading underscore (`_internal`).
  This is a *convention*, not enforcement — but the agent treats violations as
  intentional API exposure.
- **Name mangling**: Double leading underscore (`__mangled`) is reserved for
  avoiding name collisions in inheritance hierarchies. Do not use it as a
  "more private" marker.
- **Dunder methods**: `__init__`, `__repr__`, etc. Never invent custom dunder
  names. The dunder namespace belongs to the language.

### 2.2 Naming Intent

- **Booleans** should read as predicates: `is_valid`, `has_permission`,
  `should_retry`. Never `valid`, `permission`, `retry` for boolean values.
- **Functions** should be verbs or verb phrases: `calculate_total`,
  `parse_response`, `validate_input`. If a function returns a boolean, it
  should read as a question: `is_expired()`, `has_children()`.
- **Variables** should be nouns or noun phrases that describe what they hold,
  not how they were computed: `user_count` not `len_result`.
- **Avoid abbreviations** unless they are universally understood in context
  (`url`, `http`, `db`, `config`). Never `usr`, `mgr`, `ctx` unless the domain
  demands it (e.g., `ctx` in click/typer CLIs is idiomatic).
- **Avoid generic names**: `data`, `info`, `result`, `temp`, `val`, `item`.
  These are placeholders, not names. Every variable should answer: "what *is*
  this?"

### 2.3 Module and Package Names

- Short, lowercase, no underscores if possible: `utils`, `models`, `config`.
- If a module name requires an underscore, it may indicate the module is doing
  too much and should be split.

---

## 3. Type Annotations

Python is a dynamically typed language that supports optional static typing.
This agent treats type annotations as **mandatory**, not optional.

### 3.1 Rules

- **All function signatures must be fully annotated** — parameters and return
  types. No exceptions.
- **Use modern syntax** (Python 3.10+):
  - `X | None` instead of `Optional[X]`
  - `list[str]` instead of `List[str]`
  - `dict[str, int]` instead of `Dict[str, int]`
  - `tuple[int, ...]` instead of `Tuple[int, ...]`
- **Use `Self`** (from `typing`) for methods that return their own class.
- **Avoid `Any`** unless interfacing with genuinely untyped external code, and
  document why.
- **Use `TypeAlias`** for complex type expressions that appear more than once:
  ```python
  type UserId = int
  type UserMap = dict[UserId, User]
  ```
- **Use `Protocol`** over abstract base classes when you only need structural
  subtyping (duck typing with type safety).
- **Use `TypeVar` and `Generic`** correctly for container types and polymorphic
  functions. Prefer the new `[T]` syntax (PEP 695) where supported.

### 3.2 What Not to Annotate

- **Local variables** where the type is obvious from assignment:
  ```python
  # Unnecessary — the type is obvious
  name: str = "Alice"

  # Useful — the type clarifies intent
  connections: dict[str, list[Connection]] = {}
  ```
- **`self` and `cls`** — these are implicit and should not be annotated.

---

## 4. Imports

### 4.1 Structure

Imports appear at the top of the file, organized into three groups separated by
blank lines (per PEP 8):

1. Standard library imports
2. Third-party imports
3. Local/project imports

Within each group, imports are sorted alphabetically. Use `ruff` (specifically
`isort`-compatible rules) to enforce this automatically.

### 4.2 Rules

- **Absolute imports only.** Relative imports (`from . import x`) are
  acceptable only within a package's internal modules and should be used
  sparingly.
- **Never use wildcard imports** (`from x import *`). They pollute the
  namespace and make dependency tracking impossible.
- **Import modules, not objects**, when the module name adds clarity:
  ```python
  # Prefer this when the module name adds context
  import os.path

  # Prefer this when the object name is self-explanatory
  from pathlib import Path
  from collections import defaultdict
  ```
- **Do not import from inside functions** unless there is a genuine reason
  (circular import resolution, optional heavy dependency). Document every
  exception with a comment explaining why.
- **One import per line** for `from` imports with more than three names:
  ```python
  from module import (
      ClassA,
      ClassB,
      function_c,
  )
  ```

---

## 5. Functions and Methods

### 5.1 Design Principles

- **Single responsibility.** A function does one thing. If the name requires
  "and" to describe it, split it.
- **Small surface area.** Fewer parameters is better. More than three positional
  parameters is a code smell. Use keyword-only arguments (`*`) or a config
  object (Pydantic model) for complex signatures.
- **Pure functions where possible.** Functions that take inputs and return
  outputs without side effects are easier to test, compose, and reason about.
- **Early returns over deep nesting.** Guard clauses at the top, happy path at
  the bottom:
  ```python
  def process(item: Item) -> Result:
      if not item.is_valid:
          raise InvalidItemError(item.id)

      if item.is_cached:
          return item.cached_result

      return _compute_result(item)
  ```

### 5.2 Signatures

- **Use keyword-only arguments** for any parameter that isn't self-evident from
  position:
  ```python
  def connect(host: str, port: int, *, timeout: float = 30.0, retries: int = 3) -> Connection:
      ...
  ```
- **Use positional-only parameters** (`/`) for functions where parameter names
  are implementation details:
  ```python
  def distance(x1: float, y1: float, x2: float, y2: float, /) -> float:
      ...
  ```
- **Never use mutable default arguments.** Use `None` and initialize inside:
  ```python
  def process(items: list[str] | None = None) -> list[str]:
      items = items or []
      ...
  ```

### 5.3 Docstrings

- **All public functions, classes, and modules must have docstrings.**
- Use Google-style docstrings for consistency:
  ```python
  def calculate_score(responses: list[Response], *, weights: dict[str, float] | None = None) -> float:
      """Calculate a weighted score from survey responses.

      Applies the provided weights to each response category. If no weights
      are given, all categories are weighted equally.

      Args:
          responses: Survey response objects to score.
          weights: Optional mapping of category names to weight multipliers.

      Returns:
          The calculated score as a float between 0.0 and 1.0.

      Raises:
          ValueError: If responses is empty.
          KeyError: If weights reference a category not in responses.
      """
  ```
- **Docstrings describe *what* and *why*, not *how*.** The code shows how.

---

## 6. Classes

### 6.1 When to Use Classes

- When you need **state + behavior together**. If a class has no methods beyond
  `__init__`, it should probably be a `dataclass`, `NamedTuple`, or Pydantic
  model.
- When you need to implement a **protocol or interface**.
- When **identity matters** — i.e., two instances with the same data are not
  interchangeable.

### 6.2 When Not to Use Classes

- **Bags of functions** — if a class is just a namespace for static methods, use
  a module instead.
- **Single-method classes** — if a class has only `__init__` and one other
  method, it should be a function (possibly a closure).
- **Data containers without behavior** — use Pydantic `BaseModel`, `dataclass`,
  or `NamedTuple`.

### 6.3 Class Design Rules

- **Always define `__repr__`** for debuggability. `__str__` is optional and
  should only differ from `__repr__` when a human-friendly format is needed.
- **Use `__slots__`** on classes that will be instantiated frequently, unless
  you need dynamic attribute assignment.
- **Prefer composition over inheritance.** Inheritance creates coupling.
  Composition via protocols and dependency injection creates flexibility.
- **Limit inheritance depth to two levels** (base → concrete). If you need
  more, you need a different design.
- **Use `@classmethod` for alternative constructors** (`from_json`,
  `from_config`, etc.).
- **Use `@staticmethod` sparingly** — if a method doesn't use the class or
  instance, ask whether it belongs on the class at all.
- **Use `@property`** for computed attributes that should look like attribute
  access. Never use it for expensive operations — the caller has no signal
  that a property is costly.

---

## 7. Data Modeling

### 7.1 Decision Framework

| Need | Use |
|------|-----|
| Immutable record with few fields | `NamedTuple` |
| Mutable record with defaults | `dataclass` |
| Validation, serialization, config | Pydantic `BaseModel` |
| API request/response models | Pydantic `BaseModel` |
| Simple enum of choices | `enum.Enum` or `enum.StrEnum` |
| Type-safe dictionary | `TypedDict` |

### 7.2 Rules

- **Never use raw dictionaries** as primary data structures for domain objects.
  Dictionaries are for truly dynamic key-value data. Known-shape data gets a
  model.
- **Prefer immutability.** Use `frozen=True` on dataclasses or Pydantic's
  `model_config = ConfigDict(frozen=True)` unless mutation is required.
- **Use `StrEnum`** for string-valued enums (Python 3.11+). They serialize
  naturally and work in match statements.

---

## 8. Error Handling

### 8.1 Principles

- **Be specific.** Catch specific exceptions, never bare `except:` or
  `except Exception:` unless you are at a top-level boundary (CLI entry point,
  request handler) where you log and re-raise or translate.
- **Fail fast.** Validate inputs at the boundary. Do not let invalid data
  propagate through layers.
- **Use custom exceptions** for domain-specific error conditions. Group them in
  a dedicated `exceptions.py` module:
  ```python
  class AppError(Exception):
      """Base exception for the application."""

  class ValidationError(AppError):
      """Raised when input validation fails."""

  class NotFoundError(AppError):
      """Raised when a requested resource does not exist."""
  ```
- **Never silence exceptions** without logging:
  ```python
  # Never
  try:
      do_something()
  except SomeError:
      pass

  # Acceptable, with justification
  try:
      do_something()
  except SomeError:
      logger.debug("Ignoring expected SomeError during cleanup")
  ```

### 8.2 Context Managers

- **Use `contextlib.suppress`** for intentionally ignored exceptions (one-liners
  only):
  ```python
  with suppress(FileNotFoundError):
      path.unlink()
  ```
- **Write custom context managers** for resource management (`__enter__` /
  `__exit__` or `@contextmanager`).

---

## 9. Comprehensions, Generators, and Iteration

### 9.1 Comprehensions

- **Use comprehensions** when they are clearer than the loop equivalent. If a
  comprehension exceeds one line comfortably, use a loop or extract a function.
- **Never nest more than two levels** of comprehension.
- **Use dict comprehensions** over `dict(zip(...))` when building dictionaries
  from parallel iterables.

### 9.2 Generators

- **Use generator expressions** (`(x for x in ...)`) when you only need to
  iterate once and don't need the full list in memory.
- **Use `yield`-based generators** for complex lazy sequences.
- **Use `itertools`** before writing custom iteration logic: `chain`,
  `islice`, `groupby`, `product`, `combinations`, `starmap`.

### 9.3 Unpacking and Iteration Patterns

- **Use tuple unpacking** in loops:
  ```python
  for name, score in results.items():
      ...
  ```
- **Use `enumerate`** instead of manual index tracking.
- **Use `zip`** (with `strict=True` on Python 3.10+) for parallel iteration.
- **Use the walrus operator (`:=`)** when it eliminates redundant computation in
  conditions, but not when it harms readability.

---

## 10. String Handling

- **Use f-strings** for all string interpolation. No `.format()`, no `%`
  formatting.
- **Use triple-quoted strings** for multi-line content. Avoid string
  concatenation with `+` across lines.
- **Use `pathlib.Path`** for all filesystem path construction. Never use string
  concatenation or `os.path.join`.

---

## 11. Concurrency

### 11.1 Decision Framework

| Workload | Use |
|----------|-----|
| I/O-bound (HTTP, file, DB) | `asyncio` |
| CPU-bound (computation) | `multiprocessing` or `concurrent.futures.ProcessPoolExecutor` |
| Simple parallelism | `concurrent.futures.ThreadPoolExecutor` (I/O) or `ProcessPoolExecutor` (CPU) |

### 11.2 Async Rules

- **If the project uses async, go fully async.** Do not mix sync and async
  I/O in the same call chain. Use `asyncio.to_thread` for unavoidable sync
  calls from async contexts.
- **Use `async with` and `async for`** for async context managers and iterators.
- **Use `asyncio.TaskGroup`** (Python 3.11+) over `asyncio.gather` for
  structured concurrency and better error handling.
- **Never use `asyncio.sleep(0)` as a yield point** — if you need to yield
  control, you likely have a design issue.

---

## 12. Testing

- **Use `pytest`** as the test framework. No `unittest` subclassing.
- **Name tests descriptively**: `test_parse_response_raises_on_empty_body`.
- **Use fixtures** for setup/teardown. Prefer factory fixtures over complex
  fixture chains.
- **Use parametrize** for testing multiple inputs against the same logic.
- **Test behavior, not implementation.** Tests should survive refactoring.
- **Aim for high coverage on domain logic, not on glue code.**

---

## 13. Logging

- **Use the `logging` module.** Never use `print()` for any form of output in
  production code.
- **Create a structured logger** that is reusable across the application:
  ```python

from pyagent import logging

  def get_logger(name: str) -> logging.Logger:
      logger = logging.getLogger(name)
      if not logger.handlers:
          handler = logging.StreamHandler()
          formatter = logging.Formatter(
              "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
          )
          handler.setFormatter(formatter)
          logger.addHandler(handler)
          logger.setLevel(logging.DEBUG)
      return logger
  ```
- **Use appropriate log levels**: `DEBUG` for diagnostic detail, `INFO` for
  operational events, `WARNING` for recoverable issues, `ERROR` for failures,
  `CRITICAL` for fatal conditions.
- **Use lazy formatting** in log calls:
  ```python
  logger.info("Processing user %s with %d items", user_id, item_count)
  ```

---

## 14. Code Organization

### 14.1 Module Structure

A well-organized module follows this order:

1. Module docstring
2. `__all__` (if applicable)
3. Imports (standard library → third-party → local)
4. Constants
5. Type aliases
6. Exceptions
7. Classes
8. Functions
9. `if __name__ == "__main__":` block (scripts only)

### 14.2 Package Structure

- **One concept per module.** A module named `models.py` should contain data
  models, not also utility functions and exception classes.
- **Use `__init__.py` to define the package's public API.** Re-export only
  what external consumers need.
- **Keep `__init__.py` thin.** It should contain imports and `__all__`, not
  logic.

---

## 15. Formatting and Linting

- **Use `ruff`** for both formatting and linting. It replaces `black`, `isort`,
  `flake8`, and `pylint` in a single tool.
- **Use `ty`** for static type checking.
- **Line length: 88 characters** (ruff default, matching black).
- **Trailing commas** on multi-line structures — they minimize diffs and prevent
  syntax errors:
  ```python
  config = Config(
      host="localhost",
      port=8080,
      debug=True,
  )
  ```
- **No commented-out code.** Version control exists. Dead code is noise.
