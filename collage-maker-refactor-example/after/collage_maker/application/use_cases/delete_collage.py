"""
DeleteCollageUseCase — Application Service

Removes both the Collage aggregate from the repository and its rendered
image from storage. The order matters: we delete the aggregate record first
so a crash between the two steps leaves an orphaned image file rather than
a dangling DB record pointing at a missing file.

Classification: Application Service
  - Orchestrates two infrastructure operations through their ports.
  - Contains no business logic — "what deletion means" is not a rule here.
"""

from __future__ import annotations

from collage_maker.domain.exceptions import CollageNotFoundError
from collage_maker.domain.ports.collage_repository import ICollageRepository
from collage_maker.domain.ports.collage_storage import ICollageStorage


class DeleteCollageUseCase:
    def __init__(
        self,
        repository: ICollageRepository,
        storage: ICollageStorage,
    ) -> None:
        self._repository = repository
        self._storage = storage

    def execute(self, collage_id: str) -> None:
        """
        Delete the Collage and its rendered image.
        Raises CollageNotFoundError if no Collage with that id exists.
        """
        collage = self._repository.find_by_id(collage_id)
        if collage is None:
            raise CollageNotFoundError(f"No collage found with id={collage_id!r}.")

        self._repository.delete(collage_id)
        self._storage.delete(collage_id)
