"""
SqliteCollageRepository — Enhanced Infrastructure Adapter

Implements ICollageRepository using SQLAlchemy + SQLite with enhanced
query capabilities and better error handling.

This class is the translator between the domain world (Collage aggregates,
Keyword value objects) and the relational world (CollageRow ORM records).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import Engine, func, or_
from sqlalchemy.exc import SQLAlchemyError

from collage_maker.domain.common.utils import utcnow
from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.collage_repository import ICollageRepository
from collage_maker.infrastructure.persistence.database import make_session
from collage_maker.infrastructure.persistence.orm_models import CollageRow

logger = logging.getLogger(__name__)


class SqliteCollageRepository(ICollageRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Core ICollageRepository implementation
    # ------------------------------------------------------------------

    def save(self, collage: Collage) -> None:
        """Persist a new or updated Collage aggregate."""
        try:
            with make_session(self._engine) as session:
                row = session.get(CollageRow, collage.id)
                if row is None:
                    row = CollageRow(
                        id=collage.id,
                        name=collage.name,
                        keywords_csv=self._keywords_to_csv(collage.keywords),
                        created_at=collage.created_at,
                        updated_at=collage.updated_at,
                    )
                    session.add(row)
                    logger.info("Creating new collage: %s", collage.id)
                else:
                    row.name = collage.name
                    row.keywords_csv = self._keywords_to_csv(collage.keywords)
                    row.updated_at = collage.updated_at
                    logger.info("Updating collage: %s", collage.id)
                session.commit()
        except SQLAlchemyError as e:
            logger.error("Failed to save collage %s: %s", collage.id, e)
            raise

    def find_by_id(self, collage_id: str) -> Collage | None:
        """Return the Collage with the given id, or None if not found."""
        try:
            with make_session(self._engine) as session:
                row = session.get(CollageRow, collage_id)
                return self._to_domain(row) if row else None
        except SQLAlchemyError as e:
            logger.error("Failed to find collage by id %s: %s", collage_id, e)
            return None

    def find_all(self) -> list[Collage]:
        """Return all persisted Collages, ordered by creation date descending."""
        try:
            with make_session(self._engine) as session:
                rows = (
                    session.query(CollageRow)
                    .order_by(CollageRow.created_at.desc())
                    .all()
                )
                return [self._to_domain(row) for row in rows]
        except SQLAlchemyError as e:
            logger.error("Failed to find all collages: %s", e)
            return []

    def delete(self, collage_id: str) -> bool:
        """
        Remove the Collage with the given id from the store.
        Returns True if a collage was deleted, False if none existed.
        """
        try:
            with make_session(self._engine) as session:
                row = session.get(CollageRow, collage_id)
                if row:
                    session.delete(row)
                    session.commit()
                    logger.info("Deleted collage: %s", collage_id)
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error("Failed to delete collage %s: %s", collage_id, e)
            raise

    # ------------------------------------------------------------------
    # Enhanced query methods
    # ------------------------------------------------------------------

    def find_by_name_pattern(self, pattern: str) -> list[Collage]:
        """Find collages whose names match the given pattern (case-insensitive)."""
        try:
            with make_session(self._engine) as session:
                search_pattern = f"%{pattern}%"
                rows = (
                    session.query(CollageRow)
                    .filter(CollageRow.name.ilike(search_pattern))
                    .order_by(CollageRow.created_at.desc())
                    .all()
                )
                return [self._to_domain(row) for row in rows]
        except SQLAlchemyError as e:
            logger.error("Failed to find collages by name pattern '%s': %s", pattern, e)
            return []

    def find_recent(self, hours: int = 24) -> list[Collage]:
        """Find collages created within the specified number of hours."""
        try:
            cutoff_time = utcnow() - timedelta(hours=hours)
            with make_session(self._engine) as session:
                rows = (
                    session.query(CollageRow)
                    .filter(CollageRow.created_at >= cutoff_time)
                    .order_by(CollageRow.created_at.desc())
                    .all()
                )
                return [self._to_domain(row) for row in rows]
        except SQLAlchemyError as e:
            logger.error("Failed to find recent collages: %s", e)
            return []

    def find_by_keyword(self, keyword_text: str) -> list[Collage]:
        """Find collages that contain the specified keyword."""
        try:
            with make_session(self._engine) as session:
                search_pattern = f"%{keyword_text.lower()}%"
                rows = (
                    session.query(CollageRow)
                    .filter(CollageRow.keywords_csv.ilike(search_pattern))
                    .order_by(CollageRow.created_at.desc())
                    .all()
                )
                # Additional filtering to ensure exact keyword match
                collages = []
                for row in rows:
                    collage = self._to_domain(row)
                    if any(kw.text == keyword_text.lower() for kw in collage.keywords):
                        collages.append(collage)
                return collages
        except SQLAlchemyError as e:
            logger.error("Failed to find collages by keyword '%s': %s", keyword_text, e)
            return []

    def count_all(self) -> int:
        """Return the total number of stored collages."""
        try:
            with make_session(self._engine) as session:
                return session.query(func.count(CollageRow.id)).scalar() or 0
        except SQLAlchemyError as e:
            logger.error("Failed to count collages: %s", e)
            return 0

    def exists(self, collage_id: str) -> bool:
        """Check if a collage with the given ID exists."""
        try:
            with make_session(self._engine) as session:
                return session.query(
                    session.query(CollageRow).filter_by(id=collage_id).exists()
                ).scalar()
        except SQLAlchemyError as e:
            logger.error("Failed to check existence of collage %s: %s", collage_id, e)
            return False

    # ------------------------------------------------------------------
    # Private mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: CollageRow) -> Collage:
        """Convert ORM row to domain aggregate."""
        try:
            keywords = [
                Keyword(text=word.strip()) 
                for word in row.keywords_csv.split(",") 
                if word.strip()
            ]
            return Collage(
                id=row.id,
                name=row.name,
                keywords=keywords,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        except Exception as e:
            logger.error("Failed to convert row to domain object: %s", e)
            # Create a minimal valid Collage as fallback
            return Collage(
                id=row.id,
                name=row.name or "Unnamed Collage",
                keywords=[Keyword(text="unknown")],
                created_at=row.created_at or utcnow(),
                updated_at=row.updated_at or utcnow(),
            )

    @staticmethod
    def _keywords_to_csv(keywords: list[Keyword]) -> str:
        """Convert keywords to CSV string for storage."""
        return ",".join(kw.text for kw in keywords)
