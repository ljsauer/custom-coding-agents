"""
IReferenceImageSource — Outbound Port

The domain needs a way to obtain raw image data for a given keyword so the
composition service can isolate subjects and place them on the canvas.

The domain does not care whether images come from Google, Bing, a local
fixture directory, or an in-memory fake. That decision belongs entirely to
the infrastructure layer.

Images are returned as raw bytes so the domain and application layers remain
free of any cv2 / numpy dependency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from collage_maker.domain.model.keyword import Keyword


class IReferenceImageSource(ABC):
    @abstractmethod
    def fetch_for_keyword(self, keyword: Keyword) -> list[bytes]:
        """
        Return a list of raw image byte strings (JPEG or PNG) for the given
        keyword. Returns an empty list when no images could be obtained.
        The caller is responsible for deciding how many images are needed;
        implementations should return at most *images_per_keyword* items as
        configured at construction time.
        """
