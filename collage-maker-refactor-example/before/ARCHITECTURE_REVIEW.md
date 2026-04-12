# Collage Maker — Architecture Review & Redesign

## How to Use This Document

This document was produced during an architectural review session and serves as
the canonical record of:

1. What is wrong with the `before/` project and why
2. The target architecture for the `after/` project
3. The decisions and tradeoffs behind every structural choice

When resuming work in a new session, share this document alongside the codebase
so the reviewer can pick up without re-deriving context from scratch.

**Suggested session opener:**
> "Please read `collage-maker-refactor-example/ARCHITECTURE_REVIEW.md` and the
> project structure under both `before/` and `after/`, then help me continue
> building out the `after/` project."

---

## Project Overview

**Domain:** A collage-making web application. A user uploads a plain-text file.
The application extracts the most significant words from that text, fetches
reference images for each word from Google Images, isolates the foreground
subject of each image using computer vision, and composites those subjects onto
a word-cloud background to produce a JPEG collage. Collages can be renamed and
deleted.

**Stack (before):** Python 3.9, Flask, PonyORM, OpenCV, NLTK, WordCloud,
BeautifulSoup, SQLite.

**Stack (after):** Same libraries, reorganised so they are hidden behind
interfaces and never imported by the domain or application layers.

---

## Part 1 — Review of `before/`

### Step 1 — Dependency Direction: CRITICAL VIOLATIONS

These are the highest-severity findings. Nothing else was evaluated until these
were named.

**Violation 1 — ORM entity handed directly to the presentation layer.**
`db/models/collage.py` defines `Collage` as a PonyORM `db.Entity` subclass.
`main.py` imports it and passes instances directly to Jinja2 templates.
Infrastructure bleeds into the presentation layer with zero mediation.

**Violation 2 — Database connection established as a module import side effect.**
`db/models/collage.py` calls `start_db()` and `db.generate_mapping()` at module
level. Importing the model creates a database connection. There is no dependency
injection and no way to substitute the database in tests without monkey-patching.

**Violation 3 — `CollageGenerator` imports `Settings` directly.**
`Settings` calls `os.getcwd()` and `os.mkdir()` at class-body parse time.
Infrastructure side effects are triggered by importing what is intended to be a
business-logic class.

**Violation 4 — `CollageGenerator` instantiates `ImageSearch` inline.**
`CollageGenerator._get_images()` constructs `ImageSearch` objects directly.
There is no port/adapter boundary. Business logic is fused to the HTTP scraping
mechanism with no seam for testing or substitution.

---

### Step 2 — Layer Responsibility: Misplaced Logic

| Logic | Where it lives in `before/` | Where it belongs |
|---|---|---|
| Collage naming convention (`collage-{id}`) | `main.py` route handler | Domain layer |
| File deletion (`os.remove`) | `main.py` route handler | Infrastructure layer |
| DB session management (`@db_session`, `commit()`) | `main.py` route handlers | Infrastructure / Application layer |
| Word extraction and frequency ranking | `app/NLP/` — reasonable placement, but coupled to `Settings` | Domain layer (clean) |
| Image layout and collision detection | `CollageGenerator` — reasonable logic, but tangled with I/O | Domain layer |
| Directory creation | `app/settings.py` at class-body execution time | Infrastructure bootstrap in `main.py` |
| Google image downloading | `app/web_scraper/` — correct layer, but has no port | Infrastructure layer (behind a port) |

The application layer **does not exist**. `main.py` is simultaneously
presentation, application, and infrastructure.

---

### Step 3 — Aggregate Integrity

The only aggregate candidate is `Collage`. Issues:

- `path` (a filesystem location) is embedded in the domain entity. The domain
  should not know where files are stored. This is an infrastructure concern.
- There is no aggregate root — `Collage` is a PonyORM entity, not a domain
  object.
- The `find()` method on the entity is a repository concern and does not belong
  on the aggregate.

The aggregate boundary is appropriately small, but its content is contaminated
by infrastructure.

---

### Step 4 — Ubiquitous Language Drift

| Current name | Problem | Proposed domain name |
|---|---|---|
| `CollageGenerator` | "Generator" is a technical/factory term | `CollageComposer` |
| `ImportantWords` | Vague — important by what measure? | `KeywordExtractor` |
| `EdgeDetector` | CV-technical jargon, not domain language | `SubjectIsolator` |
| `ImageSearch` | Describes mechanism, not intent | `ReferenceImageFetcher` |
| `start_db()` | Pure infrastructure jargon | Should not exist in domain |
| `find()` on `Collage` entity | Repository concern on an entity | Belongs on `ICollageRepository` |
| `NLP` (module name) | Technical acronym | `text_analysis` |
| `computer_vision` (module name) | Technical jargon | `composition` |
| `web_scraper` (module name) | Describes mechanism | `image_sourcing` |

---

### Step 5 — Repository Pattern: Absent

There is no repository. Persistence is handled in three places simultaneously:

- `Collage.find()` — a query method on the entity itself
- `Collage.select(lambda c: c)` — ORM query syntax in a route handler
- `Collage[collage_id].delete()` — ORM delete in a route handler

No repository interface exists in the domain. No repository implementation
exists in infrastructure. The ORM is the de facto repository, accessed from
everywhere.

---

### Step 6 — Service Classification: God Service

`CollageGenerator` is simultaneously:
- A **Domain Service** (collision detection, object placement, alpha blending)
- An **Application Service** (orchestrating the full collage creation pipeline)
- An **Infrastructure Service** (downloading images, reading/writing files,
  managing a temp directory)

This is the **God Service** antipattern.

`main.py` is equally a God Service: HTTP routing, session management, DB
queries, filesystem operations, and business rule application all coexist in the
same functions.

---

### Named Antipatterns in `before/`

| Antipattern | Evidence |
|---|---|
| **Anemic Domain Model** | `Collage` is a data bag; all behaviour lives in services |
| **Leaky Layers** | PonyORM types (`db.Entity`, `db_session`, `StrArray`) appear in domain objects; `os` calls appear in route handlers |
| **God Service** | `CollageGenerator` and `main.py` both qualify |
| **Ubiquitous Language Drift** | Technical module and class names throughout |
| **No Repository Pattern** | ORM used as a global data-access utility with no interface |
| **Big Ball of Mud** | No bounded context boundaries; everything imports everything |

---

## Part 2 — Target Architecture for `after/`

### Bounded Contexts

The domain decomposes into two bounded contexts:

1. **Collage Context** — the core domain. Creating, naming, storing, and
   managing collages.
2. **Content Sourcing Context** — a supporting subdomain. Given keywords, find
   and return reference images. Generic/supporting, not core.

### Dependency Rule

```
Presentation → Application → Domain ← Infrastructure (implements ports)
```

The domain imports from nothing outside itself. Infrastructure imports from the
domain (to implement its ports). The presentation and application layers import
from the domain (for types) and from each other (upward only).

---

### Target Directory Structure

```
collage-maker-example-project/after/
│
├── collage_maker/
│
│   ├── domain/                             # THE CENTRE. No imports from outer layers. Ever.
│   │   ├── model/
│   │   │   ├── collage.py                  # Collage — Aggregate Root (plain Python, no ORM)
│   │   │   ├── keyword.py                  # Keyword — Value Object
│   │   │   └── canvas.py                   # Canvas + Rectangle — Value Objects
│   │   │
│   │   ├── services/
│   │   │   ├── keyword_extraction.py       # Domain Service: extract + rank keywords from text
│   │   │   ├── composition.py              # Domain Service: layout, collision, alpha blending
│   │   │   └── subject_isolation.py        # Domain Service: isolate foreground from an image
│   │   │
│   │   ├── ports/                          # Interfaces (ABCs). Domain declares what it needs.
│   │   │   ├── collage_repository.py       # ICollageRepository
│   │   │   ├── reference_image_source.py   # IReferenceImageSource
│   │   │   └── collage_storage.py          # ICollageStorage
│   │   │
│   │   └── events/
│   │       └── collage_events.py           # CollageCreated, CollageRenamed, CollageDeleted
│   │
│   ├── application/                        # Orchestration only. No business logic. No framework.
│   │   └── use_cases/
│   │       ├── create_collage.py           # CreateCollageUseCase
│   │       ├── rename_collage.py           # RenameCollageUseCase
│   │       ├── delete_collage.py           # DeleteCollageUseCase
│   │       └── list_collages.py            # ListCollagesUseCase
│   │
│   ├── infrastructure/                     # Adapters. Implements domain ports.
│   │   ├── persistence/
│   │   │   ├── sqlite_collage_repository.py  # Implements ICollageRepository
│   │   │   ├── orm_models.py                 # SQLAlchemy ORM models (NOT the domain Collage)
│   │   │   └── database.py                   # Engine / session factory
│   │   │
│   │   ├── image_sourcing/
│   │   │   └── google_image_fetcher.py       # Implements IReferenceImageSource
│   │   │
│   │   ├── storage/
│   │   │   └── local_disk_storage.py         # Implements ICollageStorage
│   │   │
│   │   └── rendering/
│   │       └── opencv_renderer.py            # Wraps cv2 for wordcloud + compositing
│   │
│   └── presentation/                       # Flask. Thin. Translates HTTP ↔ use cases.
│       ├── app.py                          # Flask factory function (create_app)
│       └── routes/
│           └── collage_routes.py           # Blueprint. Routes only. No logic.
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_keyword_extraction.py  # No I/O. Pure domain tests.
│   │   │   ├── test_composition.py
│   │   │   └── test_collage.py
│   │   └── application/
│   │       └── test_create_collage.py      # Uses in-memory fakes, not mocks
│   │
│   ├── integration/
│   │   └── test_sqlite_repository.py       # Real adapter against real SQLite
│   │
│   └── fakes/                              # In-memory port implementations for testing
│       ├── fake_collage_repository.py
│       ├── fake_image_source.py
│       └── fake_collage_storage.py
│
├── config.py                               # Pure config values. No side effects at import time.
├── main.py                                 # Composition root: wires infrastructure → application
├── ARCHITECTURE_REVIEW.md                  # This file
└── requirements.txt
```

---

### Key Design Decisions

#### 1. Domain ports replace all direct infrastructure imports

The domain defines three interfaces (Python ABCs) that describe what it needs:

| Port | Purpose |
|---|---|
| `ICollageRepository` | Save, find, and delete Collage aggregates |
| `IReferenceImageSource` | Fetch raw images for a given keyword |
| `ICollageStorage` | Persist and delete rendered collage image bytes |

Infrastructure implements them. The domain never names the implementation.

#### 2. `Collage` is a plain Python object, not an ORM entity

`domain/model/collage.py` contains a pure Python dataclass with behaviour
(`rename()`, `create()` factory, invariant enforcement). The ORM mapping in
`infrastructure/persistence/orm_models.py` is a separate, parallel structure.
The repository translates between them. They are never the same class.

#### 3. `CollageGenerator` (God Service) is decomposed into three focused services

| Service | Type | Responsibility |
|---|---|---|
| `KeywordExtractor` | Domain Service | Pure NLP — tokenise, clean, rank by frequency |
| `CompositionService` | Domain Service | Layout, collision detection, alpha blending |
| `SubjectIsolator` | Domain Service | Edge detection + GrabCut on a single image array |

Each takes plain data in, returns plain data out. No I/O. Fully unit-testable.

#### 4. `Settings` becomes `config.py` with zero side effects

The `before/` `Settings` class creates directories at class-body parse time.
The `after/` `Config` is a frozen dataclass of plain values. `os.makedirs()`
is called once, explicitly, in `main.py` during bootstrap.

#### 5. Use-cases receive all dependencies via constructor injection

```python
class CreateCollageUseCase:
    def __init__(
        self,
        image_source: IReferenceImageSource,  # port — not GoogleImageFetcher
        renderer: OpenCVRenderer,
        storage: ICollageStorage,             # port — not LocalDiskStorage
        repository: ICollageRepository,       # port — not SqliteCollageRepository
        n_keywords: int,
        extra_stopwords: List[str],
    ): ...
```

The use-case names only domain ports. The concrete adapters are supplied by
`main.py` (the composition root) and nowhere else.

#### 6. Tests are stratified by what they test, not by what module they mirror

- **Unit tests** (`tests/unit/`) — test domain logic. Zero I/O. Milliseconds.
- **Integration tests** (`tests/integration/`) — test adapters against real
  infrastructure (real SQLite, real disk).
- **Fakes** (`tests/fakes/`) — first-class in-memory implementations of domain
  ports. Reused across all unit and application tests. Preferred over mocks
  because they exercise the port contract rather than just recording calls.

#### 7. `main.py` is the composition root

The only file in the entire codebase that imports concrete infrastructure
adapters by name. Every other module depends only on abstractions (ports) or
on things that are inward of it in the dependency ring.

---

### Before vs. After: Side-by-Side

| Concern | `before/` | `after/` |
|---|---|---|
| Domain model | PonyORM `db.Entity` subclass | Plain Python dataclass in `domain/model/` |
| Persistence interface | None — ORM used directly everywhere | `ICollageRepository` ABC in `domain/ports/` |
| Persistence implementation | Inline `Collage.select()` in route handlers | `SqliteCollageRepository` in `infrastructure/` |
| Business logic location | `main.py` + `CollageGenerator` (mixed) | `domain/services/` exclusively |
| Image fetching boundary | `CollageGenerator` instantiates `ImageSearch` directly | `IReferenceImageSource` port; `GoogleImageFetcher` adapter |
| Configuration side effects | `Settings` creates directories at import time | `config.py` is pure data; `main.py` bootstraps |
| Application orchestration | Flask route handlers | Dedicated use-case classes |
| Testability | Requires real DB, real disk