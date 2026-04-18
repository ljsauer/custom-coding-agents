# Collage Maker — Refactored (`after/`)

This is the architecturally-refactored version of the Collage Maker application.
It is the direct counterpart to `before/` and is intended to be read alongside
the architectural review document at `../ARCHITECTURE_REVIEW.md`.

---

## What This Application Does

A user uploads a plain-text file (e.g. a novel, article, or essay). The
application:

1. Extracts the most significant keywords from the text by frequency.
2. Fetches reference images from Google Images for each keyword.
3. Isolates the foreground subject of each image using computer vision.
4. Composites the subjects onto a word-cloud background.
5. Saves the resulting JPEG collage and displays it in a gallery.

Collages can be renamed and deleted from the gallery.

---

## Architecture Overview

This project follows **Clean / Hexagonal Architecture** with a strict
inward-only dependency rule:

```
Presentation → Application → Domain ← Infrastructure
```

The domain layer imports from nothing outside itself. Infrastructure adapters
implement domain port interfaces and are named only in `main.py`.

### Layer Map

```
collage_maker/
├── domain/             # The centre. Pure Python. No I/O. No frameworks.
│   ├── model/          # Aggregate roots and value objects
│   ├── services/       # Domain services (stateless business logic)
│   ├── ports/          # Outbound port interfaces (ABCs)
│   └── events/         # Domain events (past-tense facts)
│
├── application/        # Use cases. Orchestration only. No business logic.
│   └── use_cases/
│
├── infrastructure/     # Adapters. Implement domain ports.
│   ├── persistence/    # SQLAlchemy + SQLite
│   ├── image_sourcing/ # Google Images scraper
│   ├── storage/        # Local disk JPEG storage
│   └── rendering/      # OpenCV + WordCloud compositor
│
└── presentation/       # Flask. Thin HTTP translation layer.
    ├── app.py          # Application factory (create_app)
    └── routes/         # Blueprint — routes only, no logic
```

---

## Key Design Decisions

### 1. The Domain Has No External Dependencies

`collage_maker/domain/` imports only from the Python standard library and
`nltk` (a pure computation library). It has zero knowledge of Flask,
SQLAlchemy, OpenCV, or Google Images.

**Why:** The domain is the most important and most frequently changed part of
the system. Keeping it free of infrastructure dependencies means it can be
understood, tested, and evolved without any framework setup.

### 2. Ports — The Domain Declares What It Needs

Three interface classes (Python ABCs) in `domain/ports/` define what the domain
requires from the outside world:

| Port | Purpose |
|---|---|
| `ICollageRepository` | Save, find, and delete Collage aggregates |
| `IReferenceImageSource` | Fetch raw images for a given keyword |
| `ICollageStorage` | Persist and delete rendered collage image bytes |

Infrastructure implements these. The domain never names the implementation.
Swapping SQLite for Postgres, or Google Images for Bing, requires only a new
adapter class and a one-line change in `main.py`.

### 3. `Collage` Is a Real Domain Object, Not an ORM Entity

`domain/model/collage.py` is a plain Python dataclass with behaviour:
- `Collage.create()` — named constructor that enforces the "must have keywords"
  invariant and assigns a UUID identity.
- `collage.rename()` — enforces the "name must not be blank" invariant and
  stamps `updated_at`.

The ORM mapping (`infrastructure/persistence/orm_models.py`) is a completely
separate class. `SqliteCollageRepository` translates between them.
They are never the same object.

### 4. The God Service Is Gone

`before/`'s `CollageGenerator` was simultaneously a domain service, an
application service, and an infrastructure service. It has been decomposed:

| Class | Layer | Responsibility |
|---|---|---|
| `KeywordExtractor` | Domain Service | Tokenise, clean, rank keywords from text |
| `SubjectIsolator` | Domain Service | Edge-detect + GrabCut a single image array |
| `CompositionService` | Domain Service | Collision-free layout + alpha blending |
| `CreateCollageUseCase` | Application Service | Orchestrates the full pipeline |
| `GoogleImageFetcher` | Infrastructure Adapter | Fetches images from Google |
| `LocalDiskStorage` | Infrastructure Adapter | Writes JPEG files to disk |

### 5. `config.py` Has Zero Side Effects

`before/`'s `Settings` class called `os.mkdir()` at class-body parse time —
every import triggered filesystem operations. `config.py` is a frozen
dataclass of plain values. `os.makedirs()` is called once, explicitly, in
`main.py`.

### 6. `main.py` Is the Composition Root

The only file in the project that imports concrete infrastructure classes by
name. It constructs every adapter, injects them into use cases through their
port interfaces, and hands the wired use cases to the Flask factory. Nothing
else is allowed to do this.

### 7. Tests Are Stratified

| Layer | Location | I/O |
|---|---|---|
| Domain unit tests | `tests/unit/domain/` | None |
| Application unit tests | `tests/unit/application/` | None (fakes only) |
| Infrastructure integration tests | `tests/integration/` | Real in-memory SQLite |

**Fakes** (`tests/fakes/`) are first-class in-memory implementations of domain
ports — not mocks. They are reusable across the entire test suite and exercise
the port contract rather than just recording calls.

---

## Project Structure (Full)

```
after/
├── collage_maker/
│   ├── domain/
│   │   ├── model/
│   │   │   ├── collage.py          # Collage — Aggregate Root
│   │   │   ├── keyword.py          # Keyword — Value Object
│   │   │   └── canvas.py           # Canvas + Rectangle — Value Objects
│   │   ├── services/
│   │   │   ├── keyword_extraction.py   # Domain Service
│   │   │   ├── subject_isolation.py    # Domain Service
│   │   │   └── composition.py          # Domain Service
│   │   ├── ports/
│   │   │   ├── collage_repository.py       # ICollageRepository
│   │   │   ├── reference_image_source.py   # IReferenceImageSource
│   │   │   └── collage_storage.py          # ICollageStorage
│   │   └── events/
│   │       └── collage_events.py
│   ├── application/
│   │   └── use_cases/
│   │       ├── create_collage.py
│   │       ├── rename_collage.py
│   │       ├── delete_collage.py
│   │       └── list_collages.py
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── database.py
│   │   │   ├── orm_models.py
│   │   │   └── sqlite_collage_repository.py
│   │   ├── image_sourcing/
│   │   │   └── google_image_fetcher.py
│   │   ├── storage/
│   │   │   └── local_disk_storage.py
│   │   └── rendering/
│   │       └── opencv_renderer.py
│   └── presentation/
│       ├── app.py
│       ├── routes/
│       │   └── collage_routes.py
│       └── templates/
│           ├── index.html
│           └── image.html
├── tests/
│   ├── fakes/
│   │   ├── fake_collage_repository.py
│   │   ├── fake_image_source.py
│   │   └── fake_collage_storage.py
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_collage.py
│   │   │   ├── test_keyword_extraction.py
│   │   │   └── test_composition.py
│   │   └── application/
│   │       └── test_create_collage.py
│   └── integration/
│       └── test_sqlite_repository.py
├── config.py
├── main.py
├── requirements.txt
└── README.md
```

---

## Getting Started

### Install dependencies

```bash
pip install -r requirements.txt
```

### Download NLTK data (first run only)

```python
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
nltk.download('wordnet')
```

### Run the application

```bash
python main.py
```

Open `http://127.0.0.1:8080` in your browser.

### Run the tests

```bash
# All tests
pytest

# Unit tests only (no I/O — fast)
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=collage_maker --cov-report=term-missing
```

---

## Before vs. After: Quick Reference

| Concern | `before/` | `after/` |
|---|---|---|
| Domain model | PonyORM `db.Entity` subclass | Plain Python dataclass |
| Persistence interface | None — ORM used directly everywhere | `ICollageRepository` ABC |
| Persistence implementation | Inline `Collage.select()` in routes | `SqliteCollageRepository` adapter |
| Business logic location | `main.py` + `CollageGenerator` (mixed) | `domain/services/` exclusively |
| Image fetching boundary | Direct instantiation inside logic class | `IReferenceImageSource` port |
| Config side effects | `Settings` creates dirs at import time | `config.py` is pure data |
| Application orchestration | Flask route handlers | Dedicated use-case classes |
| Testability | Requires real DB + disk + network | Domain: zero I/O · App: fakes only |
| Antipatterns present | Anemic model, God Service, Leaky Layers, No Repository, UL Drift | None |
