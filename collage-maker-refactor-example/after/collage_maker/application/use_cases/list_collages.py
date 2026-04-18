"""
ListCollagesUseCase — Application Service

Returns all persisted Collages for display on the index page.
The simplest use case: a single repository read, no mutation.

Classification: Application Service
  - A pure query — no domain rules to enforce, no state to change.
"""

from __future__ import annotations

from collage_maker.domain.model.collage import Collage
from collage_maker.domain.ports.collage_repository import ICollageRepository


class ListCollagesUseCase:
    def __init__(self, repository: ICollageRepository) -> None:
        self._repository = repository

    def execute(self) -> list[Collage]:
        """Return all Collages ordered by creation date, most recent first."""
        return self._repository.find_all()
