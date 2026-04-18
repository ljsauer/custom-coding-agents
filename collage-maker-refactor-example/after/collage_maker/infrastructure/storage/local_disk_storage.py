"""
LocalDiskStorage — Infrastructure Adapter

Implements ICollageStorage by writing JPEG files to a local directory.

The public_path returned is a filename relative to the static folder
for proper URL generation in web frameworks.

This is the only place in the codebase where file I/O for collage images
appears. Swapping to S3 or any other object store requires only a new
ICollageStorage implementation and a change in main.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from collage_maker.domain.ports.collage_storage import ICollageStorage

logger = logging.getLogger(__name__)

# Configuration constants
_EXTENSION: Final[str] = ".jpg"
_MAX_FILENAME_LENGTH: Final[int] = 255
_UNSAFE_CHARS: Final[set[str]] = {"/", "\\", ":", "*", "?", '"', "<", ">", "|", "\0"}


class LocalDiskStorage(ICollageStorage):
    """Local filesystem storage adapter for collage images."""

    def __init__(self, collage_dir: str | Path) -> None:
        """
        Initialize storage adapter with target directory.

        Args:
            collage_dir: Directory path for storing collage images

        Raises:
            OSError: If directory cannot be created
        """
        self._collage_dir = Path(collage_dir).resolve()
        self._ensure_directory_exists()

    def save(self, collage_id: str, image_bytes: bytes) -> str:
        """
        Save collage image to local filesystem.

        Args:
            collage_id: Unique identifier for the collage
            image_bytes: JPEG image data

        Returns:
            Public path for URL generation

        Raises:
            ValueError: If collage_id is invalid or image_bytes is empty
            OSError: If filesystem operation fails
        """
        self._validate_collage_id(collage_id)

        if not image_bytes:
            raise ValueError("Image bytes cannot be empty")

        path = self._full_path(collage_id)

        try:
            path.write_bytes(image_bytes)
            logger.info("Saved collage %s (%d bytes)", collage_id, len(image_bytes))
        except OSError as e:
            logger.error("Failed to save collage %s: %s", collage_id, e)
            raise OSError(f"Failed to save collage {collage_id} to {path}") from e

        return self.public_path(collage_id)

    def delete(self, collage_id: str) -> None:
        """
        Delete collage image from local filesystem.

        Args:
            collage_id: Unique identifier for the collage

        Note:
            This operation is idempotent - no error if file doesn't exist
        """
        self._validate_collage_id(collage_id)
        path = self._full_path(collage_id)

        try:
            path.unlink(missing_ok=True)
            logger.info("Deleted collage %s", collage_id)
        except OSError as e:
            logger.warning("Failed to delete collage %s: %s", collage_id, e)
            # Don't raise - treat as idempotent operation

    def public_path(self, collage_id: str) -> str:
        """
        Return the filename relative to the static folder.

        Args:
            collage_id: Unique identifier for the collage

        Returns:
            Relative path for URL generation (e.g., "collage123.jpg")
        """
        self._validate_collage_id(collage_id)
        return f"{collage_id}{_EXTENSION}"

    def exists(self, collage_id: str) -> bool:
        """
        Check if collage exists in storage.

        Args:
            collage_id: Unique identifier for the collage

        Returns:
            True if collage exists, False otherwise
        """
        self._validate_collage_id(collage_id)
        return self._full_path(collage_id).exists()

    def _full_path(self, collage_id: str) -> Path:
        """
        Get full filesystem path for collage.

        Args:
            collage_id: Unique identifier for the collage

        Returns:
            Full Path object for the collage file
        """
        return self._collage_dir / f"{collage_id}{_EXTENSION}"

    def _ensure_directory_exists(self) -> None:
        """
        Ensure the collage directory exists.

        Raises:
            OSError: If directory cannot be created
        """
        try:
            self._collage_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Ensured collage directory exists: %s", self._collage_dir)
        except OSError as e:
            raise OSError(f"Cannot create collage directory {self._collage_dir}") from e

    def _validate_collage_id(self, collage_id: str) -> None:
        """
        Validate collage ID for filesystem safety.

        Args:
            collage_id: ID to validate

        Raises:
            ValueError: If ID is invalid for filesystem use
        """
        if not collage_id:
            raise ValueError("Collage ID cannot be empty")

        if len(collage_id) > _MAX_FILENAME_LENGTH - len(_EXTENSION):
            raise ValueError(
                f"Collage ID too long (max {_MAX_FILENAME_LENGTH - len(_EXTENSION)} chars)"
            )

        # Check for filesystem-unsafe characters
        found_unsafe = _UNSAFE_CHARS & set(collage_id)
        if found_unsafe:
            raise ValueError(f"Collage ID contains unsafe characters: {found_unsafe}")

        # Prevent directory traversal
        if ".." in collage_id or collage_id.startswith("."):
            raise ValueError("Collage ID cannot contain '..' or start with '.'")
