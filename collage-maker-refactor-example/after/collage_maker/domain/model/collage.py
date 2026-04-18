# domain/model/collage.py
#
# Collage — Aggregate Root
#
# The central concept of the domain. A Collage is created from source text,
# carries the keywords that shaped it, and has a human-readable name.
#
# This class is pure Python. It knows nothing about:
#   - databases or ORMs
#   - file paths or storage locations
#   - Flask, HTTP, or any framework
#
# Persistence mapping is the exclusive responsibility of SqliteCollageRepository.
# Storage of the rendered image is the responsibility of ICollageStorage.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from collage_maker.domain.model.keyword import Keyword


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Collage:
    """
    Aggregate root.

    Identity is carried by *id* (a UUID string). Callers must use
    ICollageRepository to obtain and persist instances; they must never
    construct a Collage and assume it is already stored.
    """

    id: str
    keywords: List[Keyword]
    name: str
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, keywords: List[Keyword], name: Optional[str] = None) -> Collage:
        """
        Named constructor — the canonical way to bring a new Collage into
        existence. Assigns a fresh identity and a default name derived from
        that identity if none is supplied.
        """
        if not keywords:
            raise ValueError("A collage must be based on at least one keyword.")
        collage_id = str(uuid.uuid4())
        return cls(
            id=collage_id,
            keywords=keywords,
            name=name or f"collage-{collage_id[:8]}",
        )

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------

    def rename(self, new_name: str) -> None:
        """
        Apply a user-chosen name. Invariant: the name must not be blank.
        Stamps updated_at so callers can detect that the aggregate changed.
        """
        if not new_name or not new_name.strip():
            raise ValueError("Collage name must not be blank.")
        self.name = new_name.strip()
        self.updated_at = _utcnow()

    # ------------------------------------------------------------------
    # Convenience accessors (for templates and serialisers)
    # ------------------------------------------------------------------

    def keyword_texts(self) -> List[str]:
        return [kw.text for kw in self.keywords]

    def __repr__(self) -> str:
        return f"<Collage id={self.id!r} name={self.name!r}>"
