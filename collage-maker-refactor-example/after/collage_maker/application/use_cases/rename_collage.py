"""
RenameCollageUseCase — Application Service

Loads a Collage aggregate by id, delegates the rename to the aggregate
(where the invariant "name must not be blank" is enforced), and persists
the updated state.

Classification: Application Service
  - Orchestrates: load → mutate → save.
  - The "must not be blank" rule lives on Collage.rename(), not here.
"""

from __future__ import annotations

from collage_maker.domain.exceptions import CollageNotFoundError
from collage_maker.domain.model.collage import Collage
from collage_maker.domain.ports.collage_repository import ICollageRepository


class RenameCollageUseCase:
    def __init__(self, repository: ICollageRepository) -> None:
        self._repository = repository

    def execute(self, collage_id: str, new_name: str) -> Collage:
        """
        Rename the Collage identified by *collage_id*.
        Raises InvalidCollageNameError (from the aggregate) if *new_name* is blank.
        Raises CollageNotFoundError if no Collage with that id exists.
        """
        collage = self._repository.find_by_id(collage_id)
        if collage is None:
            raise CollageNotFoundError(f"No collage found with id={collage_id!r}.")

        collage.rename(new_name)
        self._repository.save(collage)
        return collage
