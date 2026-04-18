"""
Dependency Injection — FastAPI Dependencies

Provides callable dependency providers for use with FastAPI's Depends().
set_dependencies() is called once at startup from the composition root;
the get_* functions are used by route handlers to resolve dependencies.

This follows the Service Locator pattern for FastAPI dependency injection,
isolating use case construction from route handlers.
"""

from __future__ import annotations

from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.domain.ports.collage_storage import ICollageStorage

# Module-level dependency store
_create_uc: CreateCollageUseCase | None = None
_rename_uc: RenameCollageUseCase | None = None
_delete_uc: DeleteCollageUseCase | None = None
_list_uc: ListCollagesUseCase | None = None
_storage: ICollageStorage | None = None

# Application constants
THUMBNAIL_SIZE = 300


def set_dependencies(
    *,
    create_uc: CreateCollageUseCase,
    rename_uc: RenameCollageUseCase,
    delete_uc: DeleteCollageUseCase,
    list_uc: ListCollagesUseCase,
    storage: ICollageStorage,
) -> None:
    """
    Store use-case instances for later injection into route handlers.

    This is called once during application startup from main.py.
    All parameters are required and must be fully constructed instances.

    Args:
        create_uc: Use case for creating new collages
        rename_uc: Use case for renaming existing collages
        delete_uc: Use case for deleting collages
        list_uc: Use case for listing all collages
        storage: Storage adapter for collage images
    """
    global _create_uc, _rename_uc, _delete_uc, _list_uc, _storage
    _create_uc = create_uc
    _rename_uc = rename_uc
    _delete_uc = delete_uc
    _list_uc = list_uc
    _storage = storage


def get_create_use_case() -> CreateCollageUseCase:
    """Dependency provider for create collage use case."""
    if _create_uc is None:
        raise RuntimeError(
            "Dependencies not initialized - call set_dependencies() first"
        )
    return _create_uc


def get_rename_use_case() -> RenameCollageUseCase:
    """Dependency provider for rename collage use case."""
    if _rename_uc is None:
        raise RuntimeError(
            "Dependencies not initialized - call set_dependencies() first"
        )
    return _rename_uc


def get_delete_use_case() -> DeleteCollageUseCase:
    """Dependency provider for delete collage use case."""
    if _delete_uc is None:
        raise RuntimeError(
            "Dependencies not initialized - call set_dependencies() first"
        )
    return _delete_uc


def get_list_use_case() -> ListCollagesUseCase:
    """Dependency provider for list collages use case."""
    if _list_uc is None:
        raise RuntimeError(
            "Dependencies not initialized - call set_dependencies() first"
        )
    return _list_uc


def get_storage() -> ICollageStorage:
    """Dependency provider for collage storage adapter."""
    if _storage is None:
        raise RuntimeError(
            "Dependencies not initialized - call set_dependencies() first"
        )
    return _storage


def get_thumbnail_size() -> int:
    """Dependency provider for thumbnail size configuration."""
    return THUMBNAIL_SIZE
