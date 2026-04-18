"""
GoogleImageFetcher — Infrastructure Adapter

Implements IReferenceImageSource by scraping Google Images for a keyword
and returning the results as ImageResult objects with metadata.

This is the only place in the codebase where requests, BeautifulSoup, and
the Google Images URL are mentioned. Swapping the image source (e.g. to
Bing, Unsplash, or a local fixture directory) requires only implementing
IReferenceImageSource and changing the binding in main.py.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.reference_image_source import (
    IReferenceImageSource,
    ImageQuality,
    ImageLicense,
    ImageResult,
    ImageMetadata,
)

logger = logging.getLogger(__name__)

_GOOGLE_IMAGE_SEARCH_BASE_URL = "https://www.google.com/search"
_REQUEST_TIMEOUT_SECONDS = 10
_MAX_RETRIES = 3


class GoogleImageFetcher(IReferenceImageSource):
    """Google Images scraper with enhanced metadata support."""

    def __init__(self, images_per_keyword: int = 4) -> None:
        self._images_per_keyword = images_per_keyword
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def fetch_for_keyword(
        self,
        keyword: Keyword,
        min_quality: ImageQuality = ImageQuality.MEDIUM,
        required_license: ImageLicense = ImageLicense.ANY,
        max_results: int | None = None,
    ) -> list[ImageResult]:
        """
        Fetch images for the given keyword with quality and license filtering.
        """
        max_results = max_results or self._images_per_keyword

        try:
            # Use keyword variants for better results
            search_terms = keyword.get_search_variants()[:3]  # Limit API calls
            logger.info(
                f"Trying search terms: {search_terms} for keyword '{keyword.text}'"
            )
            all_results = []

            for search_term in search_terms:
                if len(all_results) >= max_results:
                    break

                results = self._scrape_images(
                    search_term, min_quality, required_license
                )
                all_results.extend(results)

            # Remove duplicates by URL and return limited results
            seen_urls = set()
            unique_results = []
            for result in all_results:
                if result.metadata.url not in seen_urls:
                    seen_urls.add(result.metadata.url)
                    unique_results.append(result)
                    if len(unique_results) >= max_results:
                        break

            logger.info(
                f"Fetched {len(unique_results)} images for keyword '{keyword.text}'",
            )
            return unique_results

        except Exception as e:
            logger.error(
                f"Failed to fetch images for keyword '{keyword.text}': {e}",
            )
            return []

    def get_source_name(self) -> str:
        """Return human-readable name of this image source."""
        return "Google Images"

    def is_available(self) -> bool:
        """Check if this image source is currently available."""
        try:
            response = self._session.get("https://www.google.com/", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_rate_limit_info(self) -> dict[str, int]:
        """Get rate limiting information for this source."""
        # Google Images doesn't provide official rate limits for scraping
        # These are conservative estimates based on typical usage
        return {
            "requests_per_hour": 100,
            "requests_remaining": 100,  # Unknown, assume full
            "reset_time": 3600,  # 1 hour in seconds
        }

    def _scrape_images(
        self,
        search_term: str,
        min_quality: ImageQuality,
        required_license: ImageLicense,
    ) -> list[ImageResult]:
        """Scrape images from Google Images for a search term."""
        search_params = {
            "q": search_term,
            "tbm": "isch",  # Image search
            "hl": "en",
            "safe": "active",
            "as_st": "y",
        }

        # Add license filtering if specified
        if required_license != ImageLicense.ANY:
            license_map = {
                ImageLicense.PUBLIC_DOMAIN: "fmc",
                ImageLicense.CREATIVE_COMMONS: "fc",
                ImageLicense.ROYALTY_FREE: "f",
                ImageLicense.COMMERCIAL_USE: "fmc",
            }
            if required_license in license_map:
                search_params["as_rights"] = license_map[required_license]

        url = f"{_GOOGLE_IMAGE_SEARCH_BASE_URL}?{urlencode(search_params)}"
        logger.info(f"Searching URL: {url}")

        try:
            response = self._session.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            return self._extract_images(soup, min_quality)

        except Exception as e:
            logger.warning(
                f"Failed to scrape images for '{search_term}': {e}",
            )
            return []

    def _extract_images(
        self, soup: BeautifulSoup, min_quality: ImageQuality
    ) -> list[ImageResult]:
        """Extract image results from parsed HTML."""
        results = []

        for img_tag in soup.find_all("img"):
            if len(results) >= self._images_per_keyword:
                logger.info("Too many results")
                break

            src = img_tag.get("src", "")
            if not src or src.startswith("data:"):
                logger.info("Skipping image")
                continue

            # Skip GIFs and other formats we don't want
            if any(ext in src.lower() for ext in [".gif", ".svg"]):
                continue

            try:
                image_data = self._fetch_image(src)
                if not image_data:
                    continue

                metadata = self._create_metadata(src, img_tag)

                # Quality filtering
                if not self._meets_quality_requirements(metadata, min_quality):
                    continue

                result = ImageResult(data=image_data, metadata=metadata)
                results.append(result)

            except Exception as e:
                logger.info("Failed to process image %s: %s", src, e)
                continue

        return results

    def _fetch_image(self, url: str) -> bytes | None:
        """Fetch image data from URL."""
        try:
            response = self._session.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            # Basic validation
            if len(response.content) < 1024:  # Too small
                logger.info("Image is too small")
                return None

            return response.content

        except Exception:
            logger.info(f"Failed to fetch image from url: {url}")
            return None

    def _create_metadata(self, url: str, img_tag) -> ImageMetadata:
        """Create metadata from image tag and URL."""
        # Extract basic metadata from HTML attributes
        width = 0
        height = 0
        alt_text = img_tag.get("alt", "")

        # Try to get dimensions from attributes
        try:
            if img_tag.get("width"):
                width = int(img_tag.get("width"))
            if img_tag.get("height"):
                height = int(img_tag.get("height"))
        except ValueError, TypeError:
            pass

        # Determine format from URL
        format_ext = "unknown"
        if "." in url:
            format_ext = url.split(".")[-1].split("?")[0].lower()

        return ImageMetadata(
            url=url,
            width=width,
            height=height,
            format=format_ext,
            alt_text=alt_text,
            source="Google Images",
            license=ImageLicense.ANY,  # Can't determine license from scraping
        )

    def _meets_quality_requirements(
        self, metadata: ImageMetadata, min_quality: ImageQuality
    ) -> bool:
        """Check if image meets quality requirements."""
        if min_quality == ImageQuality.ANY:
            return True

        # Define quality thresholds
        quality_thresholds = {
            ImageQuality.LOW: 200,
            ImageQuality.MEDIUM: 400,
            ImageQuality.HIGH: 800,
        }

        min_resolution = quality_thresholds.get(min_quality, 0)

        # Check resolution if available
        if metadata.width > 0 and metadata.height > 0:
            return metadata.resolution >= min_resolution

        # If no dimension info, accept it for low/medium quality
        return min_quality in (ImageQuality.LOW, ImageQuality.MEDIUM)
