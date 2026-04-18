# domain/ports/collage_storage.py
#
# ICollageStorage — Outbound Port
#
# The domain needs a way to persist the rendered image bytes produced for a
# Collage and to remove them when the Collage is deleted.
#
# The domain does not care whether images are stored on local disk, in an S3
# bucket, or in an in-memory dict. That decision belongs to infrastructure.
#
# The storage key is the collage id — a stable, domain-owned identifier that
# has no coupling to filesystem paths or bucket structures.

from __future__ import annotations

from abc import ABC, abstractmethod


class ICollageStorage(ABC):
    @abstractmethod
    def save(self, collage_id: str, image_bytes: bytes) -> str:
        """
        Persist *image_bytes* under the given *collage_id*.
        Returns a URL path or filename that the presentation layer can use
        to serve the image (e.g. a relative URL for a static file route).
        """

    @abstractmethod
    def delete(self, collage_id: str) -> None:
        """
        Remove the stored image for *collage_id*.
        Silently succeeds if no image exists for that id.
        """

    @abstractmethod
    def public_path(self, collage_id: str) -> str:
        """
        Return the URL path or filename under which the image for
        *collage_id* is publicly accessible.
        """
