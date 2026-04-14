"""
GoogleImageFetcher — Infrastructure Adapter

Implements IReferenceImageSource by scraping Google Images for a keyword
and returning the results as raw bytes.

This is the only place in the codebase where requests, BeautifulSoup, and
the Google Images URL are mentioned. Swapping the image source (e.g. to
Bing, Unsplash, or a local fixture directory) requires only implementing
IReferenceImageSource and changing the binding in main.py.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.reference_image_source import IReferenceImageSource

_GOOGLE_IMAGE_SEARCH_URL = (
    "https://www.google.com/search"
    "?as_st=y&tbm=isch&hl=en&as_q={keyword}"
    "&as_epq=&as_oq=&as_eq=&cr=&as_sitesearch=&safe=active"
)

_REQUEST_TIMEOUT_SECONDS = 10


class GoogleImageFetcher(IReferenceImageSource):
    def __init__(self, images_per_keyword: int = 4) -> None:
        self._images_per_keyword = images_per_keyword

    # ------------------------------------------------------------------
    # IReferenceImageSource implementation
    # ------------------------------------------------------------------

    def fetch_for_keyword(self, keyword: Keyword) -> list[bytes]:
        """
        Fetch up to *images_per_keyword* raw image byte strings from Google
        Images for the given keyword. Returns an empty list on any network
        or parsing failure so the caller can continue gracefully.
        """
        try:
            return self._scrape(keyword.text)
        except Exception:
            # Network errors, HTML parsing failures, and timeouts must not
            # propagate to the application layer.
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _scrape(self, keyword: str) -> list[bytes]:
        url = _GOOGLE_IMAGE_SEARCH_URL.format(keyword=keyword)
        response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[bytes] = []

        for img_tag in soup.find_all("img"):
            if len(results) >= self._images_per_keyword:
                break
            src = img_tag.get("src", "")
            if not src or src.endswith(".gif"):
                continue
            try:
                img_response = requests.get(src, timeout=_REQUEST_TIMEOUT_SECONDS)
                img_response.raise_for_status()
                results.append(img_response.content)
            except Exception:
                continue

        return results
