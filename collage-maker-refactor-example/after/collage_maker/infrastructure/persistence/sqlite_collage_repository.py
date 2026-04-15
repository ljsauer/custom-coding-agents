"""
SqliteCollageRepository — Enhanced Infrastructure Adapter

Implements ICollageRepository using SQLAlchemy + SQLite with enhanced
query capabilities and better error handling.

This class is the translator between the domain world (Collage aggregates,
Keyword value objects) and the relational world (CollageRow ORM records).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import Engine, func, desc
from sqlalchemy.exc import SQLAlchemyError

from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.collage_repository import ICollageRepository
from collage_maker.infrastructure.persistence.database import make_session
from collage_maker.infrastructure.persistence.orm_models import CollageRow

logger = logging.getLogger(__name__)


class SqliteCollageRepository(ICollageRepository):
    """SQLite-backed repository for Collage aggregates with enhanced querying."""

    def __init__(self, engine: Engine) -> None:
        """
        Initialize repository with SQLAlchemy engine.

        Args:
            engine: SQLAlchemy engine configured for SQLite
        """
        self._engine = engine
        logger.info("SqliteCollageRepository initialized")

    # ------------------------------------------------------------------
    # Core ICollageRepository implementation
    # ------------------------------------------------------------------

    def save(self, collage: Collage) -> None:
        """
        Persist a new or updated Collage aggregate.

        Args:
            collage: Domain aggregate to persist

        Raises:
            SQLAlchemyError: If database operation fails
        """
        if not collage.id:
            raise ValueError("Collage ID cannot be empty")

        try:
            with make_session(self._engine) as session:
                row = session.get(CollageRow, collage.id)

                if row is None:
                    # Create new record
                    row = CollageRow(
                        id=collage.id,
                        name=collage.name,
                        keywords_csv=self._keywords_to_csv(collage.keywords),
                        created_at=collage.created_at or datetime.now(timezone.utc),
                        updated_at=collage.updated_at or datetime.now(timezone.utc),
                    )
                    session.add(row)
                    logger.info("Creating new collage: %s", collage.id)
                else:
                    # Update existing record
                    row.name = collage.name
                    row.keywords_csv = self._keywords_to_csv(collage.keywords)
                    row.updated_at = collage.updated_at or datetime.now(timezone.utc)
                    logger.info("Updating existing collage: %s", collage.id)

                session.commit()
                logger.debug("Successfully saved collage: %s", collage.id)

        except SQLAlchemyError as e:
            logger.error("Failed to save collage %s: %s", collage.id, e)
            raise SQLAlchemyError(f"Failed to save collage {collage.id}") from e
        except Exception as e:
            logger.error("Unexpected error saving collage %s: %s", collage.id, e)
            raise

    def find_by_id(self, collage_id: str) -> Collage | None:
        """
        Return the Collage with the given id, or None if not found.

        Args:
            collage_id: Unique identifier for the collage

        Returns:
            Collage domain object or None if not found
        """
        if not collage_id:
            return None

        try:
            with make_session(self._engine) as session:
                row = session.get(CollageRow, collage_id)
                if row:
                    logger.debug("Found collage by id: %s", collage_id)
                    return self._to_domain(row)
                else:
                    logger.debug("Collage not found: %s", collage_id)
                    return None
        except SQLAlchemyError as e:
            logger.error("Failed to find collage by id %s: %s", collage_id, e)
            return None
        except Exception as e:
            logger.error("Unexpected error finding collage %s: %s", collage_id, e)
            return None

    def find_all(self) -> list[Collage]:
        """
        Return all persisted Collages, ordered by creation date descending.

        Returns:
            List of all Collage domain objects, newest first
        """
        try:
            with make_session(self._engine) as session:
                rows = (
                    session.query(CollageRow)
                    .order_by(desc(CollageRow.created_at))
                    .all()
                )
                collages = [self._to_domain(row) for row in rows]
                logger.debug("Found %d collages", len(collages))
                return collages
        except SQLAlchemyError as e:
            logger.error("Failed to find all collages: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected error finding all collages: %s", e)
            return []

    def delete(self, collage_id: str) -> bool:
        """
        Remove the Collage with the given id from the store.

        Args:
            collage_id: Unique identifier for the collage

        Returns:
            True if a collage was deleted, False if none existed

        Raises:
            SQLAlchemyError: If database operation fails
        """
        if not collage_id:
            return False

        try:
            with make_session(self._engine) as session:
                row = session.get(CollageRow, collage_id)
                if row:
                    session.delete(row)
                    session.commit()
                    logger.info("Deleted collage: %s", collage_id)
                    return True
                else:
                    logger.debug("Collage not found for deletion: %s", collage_id)
                    return False
        except SQLAlchemyError as e:
            logger.error("Failed to delete collage %s: %s", collage_id, e)
            raise SQLAlchemyError(f"Failed to delete collage {collage_id}") from e
        except Exception as e:
            logger.error("Unexpected error deleting collage %s: %s", collage_id, e)
            raise

    # ------------------------------------------------------------------
    # Enhanced query methods
    # ------------------------------------------------------------------

    def find_by_name_pattern(self, pattern: str) -> list[Collage]:
        """
        Find collages whose names match the given pattern (case-insensitive).

        Args:
            pattern: Text pattern to search for in collage names

        Returns:
            List of matching Collage domain objects, newest first
        """
        if not pattern:
            return []

        try:
            with make_session(self._engine) as session:
                search_pattern = f"%{pattern.strip()}%"
                rows = (
                    session.query(CollageRow)
                    .filter(CollageRow.name.ilike(search_pattern))
                    .order_by(desc(CollageRow.created_at))
                    .all()
                )
                collages = [self._to_domain(row) for row in rows]
                logger.debug(
                    "Found %d collages matching pattern '%s'", len(collages), pattern
                )
                return collages
        except SQLAlchemyError as e:
            logger.error("Failed to find collages by name pattern '%s': %s", pattern, e)
            return []
        except Exception as e:
            logger.error(
                "Unexpected error finding collages by pattern '%s': %s", pattern, e
            )
            return []

    def find_recent(self, hours: int = 24) -> list[Collage]:
        """
        Find collages created within the specified number of hours.

        Args:
            hours: Number of hours to look back (default: 24)

        Returns:
            List of recent Collage domain objects, newest first
        """
        if hours <= 0:
            return []

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            with make_session(self._engine) as session:
                rows = (
                    session.query(CollageRow)
                    .filter(CollageRow.created_at >= cutoff_time)
                    .order_by(desc(CollageRow.created_at))
                    .all()
                )
                collages = [self._to_domain(row) for row in rows]
                logger.debug(
                    "Found %d recent collages (last %d hours)", len(collages), hours
                )
                return collages
        except SQLAlchemyError as e:
            logger.error("Failed to find recent collages: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected error finding recent collages: %s", e)
            return []

    def find_by_keyword(self, keyword_text: str) -> list[Collage]:
        """
        Find collages that contain the specified keyword.

        Args:
            keyword_text: Keyword to search for

        Returns:
            List of matching Collage domain objects, newest first
        """
        if not keyword_text:
            return []

        try:
            with make_session(self._engine) as session:
                # Use ilike for case-insensitive search
                search_pattern = f"%{keyword_text.lower().strip()}%"
                rows = (
                    session.query(CollageRow)
                    .filter(CollageRow.keywords_csv.ilike(search_pattern))
                    .order_by(desc(CollageRow.created_at))
                    .all()
                )

                # Additional filtering to ensure exact keyword match
                # This handles cases where a search for "cat" shouldn't match "category"
                collages = []
                for row in rows:
                    try:
                        collage = self._to_domain(row)
                        if any(
                            kw.text.lower() == keyword_text.lower()
                            for kw in collage.keywords
                        ):
                            collages.append(collage)
                    except Exception as e:
                        logger.warning(
                            "Failed to process collage row during keyword search: %s", e
                        )
                        continue

                logger.debug(
                    "Found %d collages with keyword '%s'", len(collages), keyword_text
                )
                return collages

        except SQLAlchemyError as e:
            logger.error("Failed to find collages by keyword '%s': %s", keyword_text, e)
            return []
        except Exception as e:
            logger.error(
                "Unexpected error finding collages by keyword '%s': %s", keyword_text, e
            )
            return []

    def count_all(self) -> int:
        """
        Return the total number of stored collages.

        Returns:
            Total count of collages in the repository
        """
        try:
            with make_session(self._engine) as session:
                count = session.query(func.count(CollageRow.id)).scalar() or 0
                logger.debug("Total collage count: %d", count)
                return count
        except SQLAlchemyError as e:
            logger.error("Failed to count collages: %s", e)
            return 0
        except Exception as e:
            logger.error("Unexpected error counting collages: %s", e)
            return 0

    def exists(self, collage_id: str) -> bool:
        """
        Check if a collage with the given ID exists.

        Args:
            collage_id: Unique identifier for the collage

        Returns:
            True if collage exists, False otherwise
        """
        if not collage_id:
            return False

        try:
            with make_session(self._engine) as session:
                exists = session.query(
                    session.query(CollageRow).filter_by(id=collage_id).exists()
                ).scalar()
                logger.debug("Collage exists check for %s: %s", collage_id, exists)
                return bool(exists)
        except SQLAlchemyError as e:
            logger.error("Failed to check existence of collage %s: %s", collage_id, e)
            return False
        except Exception as e:
            logger.error(
                "Unexpected error checking collage existence %s: %s", collage_id, e
            )
            return False

    # ------------------------------------------------------------------
    # Private mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: CollageRow) -> Collage:
        """
        Convert ORM row to domain aggregate.

        Args:
            row: SQLAlchemy ORM row

        Returns:
            Collage domain object

        Note:
            Includes fallback logic for corrupted data
        """
        try:
            # Parse keywords with better error handling
            keywords = []
            if row.keywords_csv:
                for word in row.keywords_csv.split(","):
                    word = word.strip()
                    if word:  # Skip empty strings
                        try:
                            keywords.append(Keyword(text=word))
                        except Exception as e:
                            logger.warning(
                                "Failed to create keyword from '%s': %s", word, e
                            )
                            continue

            # Ensure we have at least one keyword
            if not keywords:
                logger.warning(
                    "No valid keywords found for collage %s, adding default", row.id
                )
                keywords = [Keyword(text="unknown")]

            # Handle timezone-naive datetimes
            created_at = row.created_at
            if created_at and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            elif created_at is None:
                created_at = datetime.now(timezone.utc)

            updated_at = row.updated_at
            if updated_at and updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            elif updated_at is None:
                updated_at = created_at

            return Collage(
                id=row.id,
                name=row.name or "Unnamed Collage",
                keywords=keywords,
                created_at=created_at,
                updated_at=updated_at,
            )

        except Exception as e:
            logger.error(
                "Failed to convert row to domain object for collage %s: %s", row.id, e
            )
            # Create a minimal valid Collage as fallback
            return Collage(
                id=row.id,
                name=row.name or "Corrupted Collage",
                keywords=[Keyword(text="error")],
                created_at=row.created_at or datetime.now(timezone.utc),
                updated_at=row.updated_at or datetime.now(timezone.utc),
            )

    @staticmethod
    def _keywords_to_csv(keywords: list[Keyword]) -> str:
        """
        Convert keywords to CSV string for storage.

        Args:
            keywords: List of Keyword domain objects

        Returns:
            Comma-separated string representation
        """
        if not keywords:
            return ""

        try:
            # Filter out empty or invalid keywords
            valid_texts = []
            for kw in keywords:
                if hasattr(kw, "text") and kw.text and kw.text.strip():
                    # Escape commas in keyword text
                    text = kw.text.strip().replace(",", "&#44;")
                    valid_texts.append(text)

            return ",".join(valid_texts)
        except Exception as e:
            logger.warning("Failed to convert keywords to CSV: %s", e)
            return "error"
