# infrastructure/persistence/database.py
#
# SQLAlchemy engine and session factory.
#
# This module is the only place in the entire codebase where SQLAlchemy is
# configured. It is called once from main.py (the composition root) and the
# resulting engine is injected into SqliteCollageRepository.
#
# Nothing in the domain or application layers imports from this module.

from __future__ import annotations

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


def init_db(database_path: str) -> Engine:
    """
    Create (or open) the SQLite database at *database_path*, run
    create_all to ensure tables exist, and return the engine.
    """
    url = f"sqlite:///{database_path}"
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def make_session(engine: Engine) -> Session:
    """Return a new SQLAlchemy Session bound to *engine*."""
    factory = sessionmaker(bind=engine)
    return factory()
