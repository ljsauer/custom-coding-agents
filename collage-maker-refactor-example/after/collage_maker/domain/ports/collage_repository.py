"""
ICollageRepository — Outbound Port

The domain declares WHAT it needs from persistence without knowing HOW it is
provided. Concrete implementations live in infrastructure/persistence/ and
must implement every method defined here.

Method names speak the domain language. There is no mention of SQL, sessions,
ORM concepts, or storage technology anywhere in this file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from collage_maker.domain.model.collage import Collage


class ICollageRepository(ABC):
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
    def delete(self, collage_id: str) -> None:
        """Remove the Collage with the given id from the store."""
