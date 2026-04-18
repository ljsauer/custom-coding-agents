# infrastructure/storage/local_disk_storage.py
#
# LocalDiskStorage — Infrastructure Adapter
#
# Implements ICollageStorage by writing JPEG files to a local directory.
#
# The public_path returned is a filename relative to the Flask static folder
# so that url_for('static', filename=path) works without modification.
#
# This is the only place in the codebase where os.path and file I/O for
# collage images appear. Swapping to S3 or any other object store requires
# only a new ICollageStorage implementation and a change in main.py.

from __future__ import annotations

import os

from collage_maker.domain.ports.collage_storage import ICollageStorage

_EXTENSION = ".jpg"


class LocalDiskStorage(ICollageStorage):
    def __init__(self, collage_dir: str) -> None:
        self._collage_dir = collage_dir

    # ------------------------------------------------------------------
    # ICollageStorage implementation
    # ------------------------------------------------------------------

    def save(self, collage_id: str, image_bytes: bytes) -> str:
        path = self._full_path(collage_id)
        with open(path, "wb") as f:
            f.write(image_bytes)
        return self.public_path(collage_id)

    def delete(self, collage_id: str) -> None:
        path = self._full_path(collage_id)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # Nothing to delete — treat as success

    def public_path(self, collage_id: str) -> str:
        """Return the filename relative to the static folder."""
        return f"{collage_id}{_EXTENSION}"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _full_path(self, collage_id: str) -> str:
        return os.path.join(self._collage_dir, f"{collage_id}{_EXTENSION}")
