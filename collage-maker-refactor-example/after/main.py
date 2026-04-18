"""
main.py — Composition Root

This is the ONLY file in the codebase that:
  - Names concrete infrastructure adapter classes
  - Constructs those adapters
  - Injects them into use cases through domain port interfaces
  - Hands the wired use cases to the FastAPI presentation layer

Nothing else in the codebase imports GoogleImageFetcher, SqliteCollageRepository,
or LocalDiskStorage by name. That isolation is what makes every other module
independently testable.

Startup sequence:
  1. Ensure required filesystem directories exist (side effects belong here).
  2. Initialise the database engine.
  3. Construct infrastructure adapters.
  4. Construct domain services (configuration-driven).
  5. Construct application use cases, injecting adapters through ports.
  6. Build the FastAPI app, injecting use cases.
  7. Run with uvicorn.
"""

import os
import uvicorn

from config import default_config as cfg

# -- Infrastructure ----------------------------------------------------------
from collage_maker.infrastructure.persistence.database import init_db
from collage_maker.infrastructure.persistence.sqlite_collage_repository import (
    SqliteCollageRepository,
)
from collage_maker.infrastructure.image_sourcing.google_image_fetcher import (
    GoogleImageFetcher,
)
from collage_maker.infrastructure.storage.local_disk_storage import LocalDiskStorage
from collage_maker.infrastructure.rendering.opencv_renderer import OpenCVRenderer

# -- Domain services ---------------------------------------------------------
from collage_maker.domain.services.keyword_extraction import KeywordExtractor

# -- Application use cases ---------------------------------------------------
from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase

# -- Presentation ------------------------------------------------------------
from collage_maker.presentation.app import create_app


def bootstrap() -> None:
    """Bootstrap and run the application."""
    # 1. Filesystem bootstrap (the only os.makedirs call in the project)
    for directory in (cfg.collage_dir, cfg.download_dir):
        os.makedirs(directory, exist_ok=True)

    # 2. Database
    engine = init_db(cfg.database_path)

    # 3. Infrastructure adapters
    repository = SqliteCollageRepository(engine)
    image_source = GoogleImageFetcher(
        images_per_keyword=cfg.images_per_keyword,
    )
    storage = LocalDiskStorage(collage_dir=cfg.collage_dir)
    renderer = OpenCVRenderer(
        canvas_width=cfg.canvas_width,
        canvas_height=cfg.canvas_height,
        max_word_font_size=cfg.max_word_font_size,
        colormaps=cfg.colormaps,
    )

    # 4. Domain services
    keyword_extractor = KeywordExtractor(
        n_keywords=cfg.n_keywords,
        extra_stopwords=cfg.extra_stopwords,
    )

    # 5. Application use cases
    create_uc = CreateCollageUseCase(
        image_source=image_source,
        composition_service=renderer.composition_service,
        storage=storage,
        repository=repository,
        keyword_extractor=keyword_extractor,
    )
    rename_uc = RenameCollageUseCase(repository=repository)
    delete_uc = DeleteCollageUseCase(repository=repository, storage=storage)
    list_uc = ListCollagesUseCase(repository=repository)

    # 6. FastAPI application
    app = create_app(
        create_uc=create_uc,
        rename_uc=rename_uc,
        delete_uc=delete_uc,
        list_uc=list_uc,
        storage=storage,
        static_dir=cfg.collage_dir,
    )

    # 7. Run with uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080,
        log_level="info",
        reload=True,  # Enable auto-reload for development
    )


if __name__ == "__main__":
    bootstrap()
