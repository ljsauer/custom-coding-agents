"""
SQLAlchemy engine and session factory with modern configuration.

This module is the only place in the entire codebase where SQLAlchemy is
configured. It is called once from main.py (the composition root) and the
resulting engine is injected into SqliteCollageRepository.

Nothing in the domain or application layers imports from this module,
maintaining clean separation of concerns and testability.

The configuration includes SQLite-specific optimizations and modern
SQLAlchemy patterns for reliability and performance.
"""

from __future__ import annotations

import logging
from pathlib import Path
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """
    Shared declarative base for all ORM models.

    This provides the foundation for SQLAlchemy model classes
    and ensures consistent metadata handling across the application.
    """

    pass


def init_db(database_path: str) -> Engine:
    """
    Create (or open) the SQLite database at database_path and return the engine.

    Performs complete database initialization including:
    - Directory creation if needed
    - Engine configuration with SQLite optimizations
    - Table creation via metadata
    - Connection validation

    Args:
        database_path: File system path to SQLite database file

    Returns:
        Configured SQLAlchemy Engine ready for use

    Raises:
        SQLAlchemyError: If database initialization fails
        OSError: If directory creation fails
    """
    try:
        # Ensure parent directory exists
        db_path = Path(database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Database directory ensured: %s", db_path.parent)

        # Create engine with SQLite-specific optimizations
        url = f"sqlite:///{database_path}"
        engine = create_engine(
            url,
            echo=False,  # Set to True for SQL debugging
            # SQLite-specific optimizations
            connect_args={
                "check_same_thread": False,  # Allow multi-threading
                "timeout": 30,  # 30 second timeout for locked databases
            },
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections every hour
            # Connection pool configuration for better concurrency
            pool_size=10,
            max_overflow=20,
        )

        # Register SQLite configuration event handler
        _configure_sqlite_connection(engine)

        # Create all tables defined in metadata
        Base.metadata.create_all(engine)
        logger.info("Database initialized successfully: %s", database_path)

        return engine

    except SQLAlchemyError as e:
        logger.error("SQLAlchemy error during database initialization: %s", e)
        raise
    except OSError as e:
        logger.error("File system error during database initialization: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during database initialization: %s", e)
        raise SQLAlchemyError(f"Database initialization failed: {e}") from e


def _configure_sqlite_connection(engine: Engine) -> None:
    """
    Configure SQLite-specific settings for optimal performance and reliability.

    This event handler is called for every new connection to ensure
    consistent SQLite configuration across the application lifetime.

    Args:
        engine: SQLAlchemy Engine to configure
    """

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        """Configure SQLite pragmas for performance and reliability."""
        try:
            cursor = dbapi_connection.cursor()

            # Enable foreign key constraints (critical for data integrity)
            cursor.execute("PRAGMA foreign_keys=ON")

            # Enable WAL mode for better concurrency and crash recovery
            cursor.execute("PRAGMA journal_mode=WAL")

            # Performance optimizations
            cursor.execute("PRAGMA synchronous=NORMAL")  # Balance safety/performance
            cursor.execute("PRAGMA cache_size=10000")  # 10MB cache
            cursor.execute("PRAGMA temp_store=memory")  # Use RAM for temp tables
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping

            # Improve query performance
            cursor.execute("PRAGMA optimize")
            cursor.execute("PRAGMA analysis_limit=1000")

            # Set reasonable timeouts
            cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds

            cursor.close()
            logger.info("SQLite pragmas configured successfully")

        except Exception as e:
            logger.error("Failed to configure SQLite pragmas: %s", e)
            # Don't re-raise as this would prevent app startup
            # The database will still work, just potentially less optimally


def make_session(engine: Engine) -> Session:
    """
    Create a new SQLAlchemy Session bound to the given engine.

    The session is configured for optimal usage patterns in this application,
    with appropriate defaults for transaction handling and object lifecycle.

    Args:
        engine: SQLAlchemy Engine to bind the session to

    Returns:
        Configured Session instance ready for database operations

    Note:
        Sessions should be managed carefully - typically one session per
        request/operation, with proper cleanup via try/finally or context managers.
    """
    try:
        factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,  # Keep objects usable after commit
            autoflush=True,  # Auto-flush before queries
            autocommit=False,  # Explicit transaction control
        )
        session = factory()
        logger.info("Database session created successfully")
        return session

    except SQLAlchemyError as e:
        logger.error("Failed to create database session: %s", e)
        raise


def close_engine(engine: Engine) -> None:
    """
    Properly close an engine and clean up its connection pool.

    This should be called during application shutdown to ensure
    clean resource cleanup and proper database disconnection.

    Args:
        engine: SQLAlchemy Engine to close
    """
    try:
        engine.dispose()
        logger.info("Database engine closed successfully")
    except Exception as e:
        logger.error("Error closing database engine: %s", e)
        # Don't raise during shutdown
