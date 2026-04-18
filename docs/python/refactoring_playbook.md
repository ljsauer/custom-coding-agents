# Refactoring Playbook

This document defines named refactoring patterns with concrete before/after
examples. The agent uses these patterns when suggesting or performing
refactoring operations. Each pattern includes: the trigger (what signals this
refactoring is needed), the transformation, and any caveats.

---

## 1. Extract Function

**Trigger:** A block of code inside a function that performs a distinct
sub-task, especially if it is repeated, deeply nested, or preceded by a
comment explaining what it does.

**Before:**
```python
def process_order(order: Order) -> Invoice:
    # Validate inventory
    for item in order.items:
        stock = inventory.get(item.sku)
        if stock is None:
            raise ItemNotFoundError(item.sku)
        if stock.quantity < item.quantity:
            raise InsufficientStockError(item.sku, stock.quantity, item.quantity)

    # Calculate totals
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * order.tax_rate
    total = subtotal + tax

    return Invoice(order_id=order.id, subtotal=subtotal, tax=tax, total=total)
```

**After:**
```python
def process_order(order: Order) -> Invoice:
    _validate_inventory(order.items)
    return _build_invoice(order)


def _validate_inventory(items: list[OrderItem]) -> None:
    for item in items:
        stock = inventory.get(item.sku)
        if stock is None:
            raise ItemNotFoundError(item.sku)
        if stock.quantity < item.quantity:
            raise InsufficientStockError(item.sku, stock.quantity, item.quantity)


def _build_invoice(order: Order) -> Invoice:
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * order.tax_rate
    return Invoice(order_id=order.id, subtotal=subtotal, tax=tax, total=subtotal + tax)
```

**Caveat:** Do not extract single-line operations or trivial logic. The
extracted function must be meaningful enough to justify the indirection.

---

## 2. Replace Magic Values with Constants

**Trigger:** Numeric or string literals in logic whose meaning is not
self-evident from context.

**Before:**
```python
if response.status_code == 429:
    time.sleep(2.5)
    return retry(request, max_attempts=3)
```

**After:**
```python
HTTP_TOO_MANY_REQUESTS = 429
RETRY_DELAY_SECONDS = 2.5
MAX_RETRY_ATTEMPTS = 3

if response.status_code == HTTP_TOO_MANY_REQUESTS:
    time.sleep(RETRY_DELAY_SECONDS)
    return retry(request, max_attempts=MAX_RETRY_ATTEMPTS)
```

**Caveat:** HTTP status codes from `http.HTTPStatus` are preferable to custom
constants when available. The example above uses a custom constant for clarity,
but prefer:
```python
from http import HTTPStatus

if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
    ...
```

---

## 3. Replace Dict with Model

**Trigger:** A `dict[str, Any]` (or similar) is passed between functions, and
its keys are known and stable.

**Before:**
```python
def create_user(data: dict[str, Any]) -> dict[str, Any]:
    user = {
        "id": generate_id(),
        "name": data["name"],
        "email": data["email"],
        "role": data.get("role", "member"),
        "created_at": datetime.now(UTC),
    }
    db.insert(user)
    return user
```

**After:**
```python
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: UserRole = UserRole.MEMBER


class User(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: UserRole
    created_at: datetime


def create_user(data: UserCreate) -> User:
    user = User(
        id=generate_id(),
        created_at=datetime.now(UTC),
        **data.model_dump(),
    )
    db.insert(user.model_dump())
    return user
```

**Caveat:** Do not model truly dynamic key-value data. If the keys are
determined at runtime (e.g., user-defined metadata), a dict is correct.

---

## 4. Flatten Nested Conditionals (Guard Clauses)

**Trigger:** Functions with deeply nested `if`/`else` blocks, especially
when outer conditions are error checks or preconditions.

**Before:**
```python
def get_discount(user: User, order: Order) -> float:
    if user is not None:
        if user.is_active:
            if order.total > 100:
                if user.tier == "premium":
                    return 0.20
                else:
                    return 0.10
            else:
                return 0.0
        else:
            raise InactiveUserError(user.id)
    else:
        raise ValueError("User is required")
```

**After:**
```python
def get_discount(user: User, order: Order) -> float:
    if user is None:
        raise ValueError("User is required")

    if not user.is_active:
        raise InactiveUserError(user.id)

    if order.total <= 100:
        return 0.0

    if user.tier == UserTier.PREMIUM:
        return 0.20

    return 0.10
```

---

## 5. Replace Loop with Comprehension

**Trigger:** A `for` loop that builds a list, dict, or set via `.append()`, indexing, or `.add()`, where the logic is a simple transformation or filter.

**Before:**
```python
active_emails = []
for user in users:
    if user.is_active:
        active_emails.append(user.email.lower())
```

**After:**
```python
active_emails = [user.email.lower() for user in users if user.is_active]
```

**Caveat:** If the loop body exceeds one or two operations, keep the loop.
Comprehensions should be readable in a single visual scan. If you need to squint, use a loop.

---

## 6. Replace String Formatting with f-strings

**Trigger:** Any use of `str.format()`, `%` formatting, or string concatenation for interpolation.

**Before:**
```python
message = "User {} ({}) logged in at {}".format(user.name, user.email, timestamp)
path = base_dir + "/" + subdir + "/" + filename
```

**After:**
```python
message = f"User {user.name} ({user.email}) logged in at {timestamp}"
path = Path(base_dir) / subdir / filename
```

---

## 7. Replace os.path with pathlib

**Trigger:** Any use of `os.path.join`, `os.path.exists`, `os.path.basename`,
`os.path.dirname`, `os.path.splitext`, or similar.

**Before:**
```python
import os

config_path = os.path.join(os.path.dirname(__file__), "config", "settings.yaml")
if os.path.exists(config_path):
    with open(config_path) as f:
        ...
name, ext = os.path.splitext(filename)
```

**After:**
```python
from pathlib import Path

config_path = Path(__file__).parent / "config" / "settings.yaml"
if config_path.exists():
    with config_path.open() as f:
        ...
name = Path(filename).stem
ext = Path(filename).suffix
```

---

## 8. Introduce Early Return

**Trigger:** A function where the main logic is wrapped in a large `if` block
with a small `else` at the end (or vice versa).

**Before:**
```python
def parse_response(response: Response) -> ParsedData:
    if response.status_code == 200:
        data = response.json()
        validated = schema.validate(data)
        transformed = transform(validated)
        return ParsedData(content=transformed)
    else:
        logger.error("Request failed: %s", response.status_code)
        raise RequestError(response.status_code)
```

**After:**
```python
def parse_response(response: Response) -> ParsedData:
    if response.status_code != 200:
        logger.error("Request failed: %s", response.status_code)
        raise RequestError(response.status_code)

    data = response.json()
    validated = schema.validate(data)
    transformed = transform(validated)
    return ParsedData(content=transformed)
```

---

## 9. Replace Print with Logging

**Trigger:** Any `print()` call in application code (not in a one-off script
or CLI output function).

**Before:**
```python
def sync_data(source: DataSource) -> None:
    print(f"Starting sync from {source.name}")
    try:
        records = source.fetch()
        print(f"Fetched {len(records)} records")
        db.upsert_many(records)
        print("Sync complete")
    except Exception as e:
        print(f"Error: {e}")
```

**After:**
```python
logger = get_logger(__name__)


def sync_data(source: DataSource) -> None:
    logger.info("Starting sync from %s", source.name)
    try:
        records = source.fetch()
        logger.info("Fetched %d records", len(records))
        db.upsert_many(records)
        logger.info("Sync complete")
    except Exception:
        logger.exception("Sync failed for source %s", source.name)
        raise
```

**Note:** `logger.exception` logs the full traceback automatically. Re-raising
preserves the error for callers.

---

## 10. Replace Raw Exception with Custom Exception

**Trigger:** Raising `ValueError`, `TypeError`, or `RuntimeError` with domain-specific messages, especially when multiple call sites raise the same generic exception.

**Before:**
```python
def withdraw(account: Account, amount: Decimal) -> None:
    if amount <= 0:
        raise ValueError("Withdrawal amount must be positive")
    if amount > account.balance:
        raise ValueError("Insufficient funds")
    account.balance -= amount
```

**After:**
```python
class InvalidAmountError(AppError):
    """Raised when a transaction amount is not valid."""

class InsufficientFundsError(AppError):
    """Raised when an account lacks sufficient balance."""


def withdraw(account: Account, amount: Decimal) -> None:
    if amount <= 0:
        raise InvalidAmountError(f"Amount must be positive, got {amount}")
    if amount > account.balance:
        raise InsufficientFundsError(
            f"Cannot withdraw {amount} from balance of {account.balance}"
        )
    account.balance -= amount
```

---

## 11. Modernize Type Annotations

**Trigger:** Legacy typing syntax in a project targeting Python 3.10+.

**Before:**
```python
from typing import Optional, List, Dict, Tuple, Union

def process(
    items: List[str],
    config: Optional[Dict[str, Any]] = None,
    result: Union[str, int] = "",
) -> Tuple[bool, List[str]]:
    ...
```

**After:**
```python
def process(
    items: list[str],
    config: dict[str, Any] | None = None,
    result: str | int = "",
) -> tuple[bool, list[str]]:
    ...
```

**Automation:** `ruff` with rule `UP` (pyupgrade) handles this automatically.

---

## 12. Extract Configuration to Pydantic Settings

**Trigger:** Environment variables accessed via `os.environ` or `os.getenv`
scattered throughout the codebase.

**Before:**
```python
import os

db_url = os.environ["DATABASE_URL"]
api_key = os.getenv("API_KEY", "default-key")
debug = os.getenv("DEBUG", "false").lower() == "true"
max_workers = int(os.getenv("MAX_WORKERS", "4"))
```

**After:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    api_key: str = "default-key"
    debug: bool = False
    max_workers: int = 4


settings = Settings()
```

---

## 13. Replace Inheritance with Composition

**Trigger:** A class hierarchy deeper than two levels, or a subclass that
overrides most of the parent's methods, or a "mixin" that introduces state.

**Before:**
```python
class BaseProcessor:
    def validate(self, data): ...
    def transform(self, data): ...
    def save(self, data): ...
    def process(self, data):
        validated = self.validate(data)
        transformed = self.transform(validated)
        self.save(transformed)

class CSVProcessor(BaseProcessor):
    def validate(self, data): ...
    def transform(self, data): ...
    def save(self, data): ...

class JSONProcessor(BaseProcessor):
    def validate(self, data): ...
    def transform(self, data): ...
    def save(self, data): ...
```

**After:**
```python
class Validator(Protocol):
    def validate(self, data: RawData) -> ValidData: ...

class Transformer(Protocol):
    def transform(self, data: ValidData) -> TransformedData: ...

class Saver(Protocol):
    def save(self, data: TransformedData) -> None: ...


class Processor:
    def __init__(
        self,
        validator: Validator,
        transformer: Transformer,
        saver: Saver,
    ) -> None:
        self._validator = validator
        self._transformer = transformer
        self._saver = saver

    def process(self, data: RawData) -> None:
        validated = self._validator.validate(data)
        transformed = self._transformer.transform(validated)
        self._saver.save(transformed)
```

---

## Application Guidelines

When applying refactoring patterns, the agent should:

1. **Identify the pattern by name** in its output so the user can learn the
   vocabulary.
2. **Show the minimal diff** — do not refactor unrelated code in the same pass.
3. **Explain the tradeoff** — every refactoring has a cost (indirection,
   abstraction, migration effort). Name it.
4. **Preserve behavior** — refactoring changes structure, not behavior. If the
   proposed change alters semantics, it is not a refactoring; it is a
   modification and must be called out.
5. **Respect scope** — if the user asked for a review, suggest refactorings but
   do not apply them unless asked. If the user asked for a refactoring, apply
   it and explain what changed.
