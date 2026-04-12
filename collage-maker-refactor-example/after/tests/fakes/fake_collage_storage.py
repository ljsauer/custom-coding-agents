# tests/fakes/fake_collage_storage.py
#
# FakeCollageStorage — In-memory ICollageStorage implementation
#
# Stores image bytes in a plain dict keyed by collage_id. Allows application-
# layer tests to assert that the correct bytes were persisted without touching
# the filesystem.

from __future__ import annotations

from typing import Dict

from collage_maker.domain.ports.collage_storage import ICollageStorage


class FakeCollageStorage(ICollageStorage):
    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}

    def save(self, collage_id: str, image_bytes: bytes) -> str:
        self._store[collage_id] = image_bytes
        return self.public_path(collage_id)

    def delete(self, collage_id: str) -> None:
        self._store.pop(collage_id, None)

    def public_path(self, collage_id: str) -> str:
        return f"{collage_id}.jpg"

    # ------------------------------------------------------------------
    # Test helpers (not part of the port contract)
    # ------------------------------------------------------------------

    def has(self, collage_id: str) -> bool:
        return collage_id in self._store

    def get(self, collage_id: str) -> bytes | None:
        return self._store.get(collage_id)

    def count(self) -> int:
        return len(self._store)
