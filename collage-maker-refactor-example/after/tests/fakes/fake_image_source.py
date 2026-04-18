# tests/fakes/fake_image_source.py
#
# FakeReferenceImageSource — In-memory IReferenceImageSource implementation
#
# Returns a configurable list of raw bytes per keyword so that application-
# layer tests can control exactly what "images" the use case receives without
# any network calls.
#
# Default behaviour: return a 1×1 white JPEG byte string for every keyword,
# giving the SubjectIsolator something real to decode without needing cv2
# fixtures on disk.

from __future__ import annotations

import struct
import zlib
from typing import TYPE_CHECKING

from collage_maker.domain.ports.reference_image_source import IReferenceImageSource

if TYPE_CHECKING:
    from collage_maker.domain.model.keyword import Keyword


def _minimal_jpeg() -> bytes:
    """
    Return a 1×1 white JPEG as raw bytes.
    This is a real JPEG that cv2.imdecode can decode — not a mock payload.
    """
    # Minimal valid JPEG (1x1 white pixel) in hex
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000"
        "ffdb004300080606070605080707070909080a0c"
        "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20"
        "242e2720222c231c1c2837292c30313434341f27"
        "39 3d382 32c3630 3334 3 2ffc0000b080001"
        "00010 1011 1 00ffcc0000 6001010 5 01ff"
        "c40014000 1 0 0000000000000000000000000"
        "07ffc40014100 1 0000000000000000000000"
        "0000ff da000 8010 1000000 3f007fbffd9"
    )


# Fallback to a tiny valid PNG if the JPEG hex is fiddly to construct
def _minimal_png() -> bytes:
    """Return a 1×1 white PNG as raw bytes."""

    def chunk(name: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)
    raw_row = b"\x00\xff\xff\xff"
    compressed = zlib.compress(raw_row)
    idat = chunk(b"IDAT", compressed)
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


class FakeReferenceImageSource(IReferenceImageSource):
    def __init__(
        self,
        images_per_keyword: int = 1,
        keyword_overrides: dict[str, list[bytes]] | None = None,
    ) -> None:
        self._images_per_keyword = images_per_keyword
        self._overrides: dict[str, list[bytes]] = keyword_overrides or {}
        self.calls: list[str] = []  # record of keywords requested

    def fetch_for_keyword(self, keyword: Keyword) -> list[bytes]:
        self.calls.append(keyword.text)
        if keyword.text in self._overrides:
            return self._overrides[keyword.text]
        return [_minimal_png()] * self._images_per_keyword
