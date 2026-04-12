# tests/fakes/fake_collage_repository.py
#
# FakeCollageRepository — In-memory ICollageRepository implementation
#
# A first-class fake: a real implementation of the port contract backed by a
# plain dict. Used in unit and application-layer tests so those tests have
# zero I/O and zero dependency on SQLAlchemy or SQLite.
#
# Fakes are preferred over mocks here because they exercise the port contract
# (save → find_by_id round-trips correctly) rather than just recording calls.

from __future__ import annotations

from typing import Dict, List, Optional

from collage_maker.domain.model.collage import Collage
from collage_maker.domain.ports.collage_repository import ICollageRepository


class FakeCollageRepository(ICollageRepository):
    def __init__(self) -> None:
        self._store: Dict[str, Collage] = {}

    def save(self, collage: Collage) -> None:
        self._store[collage.id] = collage

    def find_by_id(self, collage_id: str) -> Optional[Collage]:
        return self._store.get(collage_id)

    def find_all(self) -> List[Collage]:
        return sorted(
            self._store.values(),
            key=lambda c: c.created_at,
            reverse=True,
        )

    def delete(self, collage_id: str) -> None:
        self._store.pop(collage_id, None)

    # ------------------------------------------------------------------
    # Test helpers (not part of the port contract)
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._store)

    def all_ids(self) -> List[str]:
        return list(self._store.keys())
