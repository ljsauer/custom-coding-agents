"""
SQLAlchemy engine and session factory with modern configuration.

This module is the only place in the entire codebase where SQLAlchemy is
configured. It is called once from main.py (the composition root) and the
resulting engine is injected into SqliteCollageRepository.

Nothing in the domain or application layers imports from this module.
"""

from __future__ import annotations

from pathlib import Path
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def init_db(database_path: str) -> Engine:
    """
    Create (or open) the SQLite database at *database_path*, run
    create_all to ensure tables exist, and return the engine.
    """
    # Ensure parent directory exists
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    url = f"sqlite:///{database_path}"
    engine = create_engine(
        url, 
        echo=False,
        # SQLite-specific optimizations
        connect_args={
            "check_same_thread": False,  # Allow multi-threading
            "timeout": 30,  # 30 second timeout for locked databases
        },
        pool_pre_ping=True,  # Verify connections before use
    )
    
    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Optimize SQLite performance
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=memory")
        cursor.close()
    
    Base.metadata.create_all(engine)
    return engine


def make_session(engine: Engine) -> Session:
    """Return a new SQLAlchemy Session bound to *engine*."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory()
