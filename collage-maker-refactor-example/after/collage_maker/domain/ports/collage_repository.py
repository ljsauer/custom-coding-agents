"""
ICollageRepository — Enhanced Outbound Port

The domain declares WHAT it needs from persistence without knowing HOW it is
provided. This enhanced version includes additional query methods for better
functionality while maintaining clean architecture principles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collage_maker.domain.model.collage import Collage


class ICollageRepository(ABC):
    """Enhanced repository interface with modern query capabilities."""

    @abstractmethod
    def save(self, collage: Collage) -> None:
        """Persist a new or updated Collage aggregate."""

    @abstractmethod
    def find_by_id(self, collage_id: str) -> Collage | None:
        """Return the Collage with the given id, or None if not found."""

    @abstractmethod
    def find_all(self) -> list[Collage]:
        """Return all persisted Collages, ordered by creation date descending."""

    @abstractmethod
    def find_by_name_pattern(self, pattern: str) -> list[Collage]:
        """Find collages whose names match the given pattern (case-insensitive)."""

    @abstractmethod
    def find_recent(self, hours: int = 24) -> list[Collage]:
        """Find collages created within the specified number of hours."""

    @abstractmethod
    def find_by_keyword(self, keyword_text: str) -> list[Collage]:
        """Find collages that contain the specified keyword."""

    @abstractmethod
    def count_all(self) -> int:
        """Return the total number of stored collages."""

    @abstractmethod
    def delete(self, collage_id: str) -> bool:
        """
        Remove the Collage with the given id from the store.
        Returns True if a collage was deleted, False if none existed.
        """

    @abstractmethod
    def exists(self, collage_id: str) -> bool:
        """Check if a collage with the given ID exists."""
