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
  1. Configure logging and validate environment
  2. Ensure required filesystem directories exist
  3. Initialize the database engine
  4. Construct infrastructure adapters with validation
  5. Construct domain services (configuration-driven)
  6. Construct application use cases, injecting adapters through ports
  7. Build the FastAPI app, injecting use cases
  8. Run with uvicorn with proper error handling
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import NoReturn

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
from collage_maker.infrastructure.rendering.composition_renderer import CompositionRendererAdapter

# -- Domain services ---------------------------------------------------------
from collage_maker.domain.services.keyword_extraction import KeywordExtractor

# -- Application use cases ---------------------------------------------------
from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase

# -- Presentation ------------------------------------------------------------
from collage_maker.presentation.app import create_app


def setup_logging(*, debug: bool = False) -> None:
    """Configure application logging with appropriate levels and formatting."""
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    if not debug:
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


def validate_configuration() -> None:
    """
    Validate critical configuration parameters before application startup.

    Raises:
        ValueError: If any configuration parameter is invalid
    """
    errors = []

    # Validate numeric constraints
    if cfg.canvas_width <= 0 or cfg.canvas_height <= 0:
        errors.append("Canvas dimensions must be positive")

    if cfg.images_per_keyword <= 0:
        errors.append("Images per keyword must be positive")

    if cfg.n_keywords <= 0:
        errors.append("Number of keywords must be positive")

    # Validate paths
    try:
        Path(cfg.database_path).parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        errors.append(f"Cannot create database directory: {e}")

    if errors:
        for error in errors:
            logging.error("Configuration error: %s", error)
        raise ValueError(f"Invalid configuration: {'; '.join(errors)}")


def bootstrap_filesystem() -> None:
    """
    Bootstrap required filesystem directories.

    Raises:
        OSError: If directory creation fails
    """
    directories = [
        ("collage_dir", cfg.collage_dir),
        ("download_dir", cfg.download_dir),
    ]

    for name, directory in directories:
        try:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            logging.info("Ensured directory exists: %s -> %s", name, path.resolve())
        except OSError as e:
            logging.error("Failed to create directory %s (%s): %s", name, directory, e)
            raise OSError(f"Failed to create {name} directory: {e}") from e


def create_infrastructure_adapters() -> tuple[
    SqliteCollageRepository,
    GoogleImageFetcher,
    LocalDiskStorage,
    CompositionRendererAdapters,
]:
    """
    Create and validate infrastructure adapters.

    Returns:
        Tuple of initialized infrastructure adapters

    Raises:
        RuntimeError: If any adapter initialization fails
    """
    logging.info("Initializing infrastructure adapters...")

    # Database
    try:
        engine = init_db(cfg.database_path)
        repository = SqliteCollageRepository(engine)
        logging.info("Database initialized: %s", cfg.database_path)
    except Exception as e:
        logging.error("Database initialization failed: %s", e)
        raise RuntimeError(f"Database initialization failed: {e}") from e

    # Image sourcing
    try:
        image_source = GoogleImageFetcher(
            images_per_keyword=cfg.images_per_keyword,
        )
        logging.info(
            "Image fetcher configured: %d images per keyword", cfg.images_per_keyword
        )
    except Exception as e:
        logging.error("Image fetcher initialization failed: %s", e)
        raise RuntimeError(f"Image fetcher initialization failed: {e}") from e

    # Storage
    try:
        storage = LocalDiskStorage(collage_dir=cfg.collage_dir)
        logging.info("Storage configured: %s", Path(cfg.collage_dir).resolve())
    except Exception as e:
        logging.error("Storage initialization failed: %s", e)
        raise RuntimeError(f"Storage initialization failed: {e}") from e

    # Rendering
    try:
        renderer = CompositionRendererAdapter(
            canvas_width=cfg.canvas_width,
            canvas_height=cfg.canvas_height,
            max_word_font_size=cfg.max_word_font_size,
            colormaps=cfg.colormaps,
        )
        logging.info(
            "Renderer configured: %dx%d canvas", cfg.canvas_width, cfg.canvas_height
        )
    except Exception as e:
        logging.error("Renderer initialization failed: %s", e)
        raise RuntimeError(f"Renderer initialization failed: {e}") from e

    return repository, image_source, storage, renderer


def create_domain_services() -> KeywordExtractor:
    """
    Create domain services with configuration-driven parameters.

    Returns:
        Configured KeywordExtractor instance

    Raises:
        RuntimeError: If service initialization fails
    """
    try:
        keyword_extractor = KeywordExtractor(
            n_keywords=cfg.n_keywords,
            extra_stopwords=cfg.extra_stopwords,
        )
        logging.info(f"{type(keyword_extractor)}")
        logging.info(
            f"Keyword extractor configured to use max {cfg.n_keywords} keywords"
        )
        return keyword_extractor
    except Exception as e:
        logging.error(f"Domain services initialization failed: {e}")
        raise RuntimeError(f"Domain services initialization failed: {e}") from e


def create_use_cases(
    repository: SqliteCollageRepository,
    image_source: GoogleImageFetcher,
    storage: LocalDiskStorage,
    renderer: OpenCVRenderer,
    keyword_extractor: KeywordExtractor,
) -> tuple[
    CreateCollageUseCase,
    RenameCollageUseCase,
    DeleteCollageUseCase,
    ListCollagesUseCase,
]:
    """
    Create application use cases with dependency injection.

    Returns:
        Tuple of configured use case instances

    Raises:
        RuntimeError: If use case initialization fails
    """
    try:
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

        logging.info("Application use cases initialized")
        return create_uc, rename_uc, delete_uc, list_uc
    except Exception as e:
        logging.error("Use case initialization failed: %s", e)
        raise RuntimeError(f"Use case initialization failed: {e}") from e


def bootstrap() -> None:
    """Bootstrap and run the application with comprehensive error handling."""
    # Determine if we're in debug mode
    debug = "--debug" in sys.argv or "--reload" in sys.argv

    try:
        # 1. Setup logging early
        setup_logging(debug=debug)
        logger = logging.getLogger(__name__)
        logger.info("Starting Collage Maker application...")

        # 2. Validate configuration
        validate_configuration()

        # 3. Bootstrap filesystem
        bootstrap_filesystem()

        # 4. Create infrastructure adapters
        repository, image_source, storage, renderer = create_infrastructure_adapters()

        # 5. Create domain services
        keyword_extractor = create_domain_services()

        # 6. Create use cases
        create_uc, rename_uc, delete_uc, list_uc = create_use_cases(
            repository, image_source, storage, renderer, keyword_extractor
        )

        # 7. Create FastAPI application
        app = create_app(
            create_uc=create_uc,
            rename_uc=rename_uc,
            delete_uc=delete_uc,
            list_uc=list_uc,
            storage=storage,
            static_dir=cfg.collage_dir,
            debug=debug,
            allowed_hosts=["127.0.0.1", "localhost"] if not debug else None,
            cors_origins=None,  # Use defaults from create_app
        )

        logger.info("Application bootstrap completed successfully")

        # 8. Run with uvicorn
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8080,
            log_level="debug" if debug else "info",
            reload=debug,
            access_log=debug,
        )

    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
    except Exception as e:
        logger.error("Application bootstrap failed: %s", e, exc_info=True)
        sys.exit(1)


def main() -> NoReturn:
    """Main entry point with proper error handling and exit codes."""
    try:
        bootstrap()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
