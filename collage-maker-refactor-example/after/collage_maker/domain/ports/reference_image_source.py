"""
IReferenceImageSource — Enhanced Outbound Port

The domain needs a way to obtain raw image data for a given keyword so the
composition service can isolate subjects and place them on the canvas.

This enhanced version supports multiple image sources, quality filtering,
metadata collection, and rate limiting to provide a robust foundation
for image acquisition from various providers.

The interface is designed to be agnostic to the actual image source
(Google Images, Unsplash, Pixabay, etc.) while providing rich metadata
for quality assessment and legal compliance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from collage_maker.domain.model.keyword import Keyword


class ImageQuality(Enum):
    """
    Image quality levels for filtering and selection.

    Used to specify minimum quality requirements when fetching images.
    """

    LOW = "low"  # Accepts images as low as 200px
    MEDIUM = "medium"  # Requires at least 400px
    HIGH = "high"  # Requires at least 800px
    ANY = "any"  # No quality filtering


class ImageLicense(Enum):
    """
    Image license types for legal compliance.

    Enables filtering by usage rights to ensure proper legal compliance
    for different use cases (commercial, educational, etc.).
    """

    PUBLIC_DOMAIN = "public_domain"
    CREATIVE_COMMONS = "creative_commons"
    ROYALTY_FREE = "royalty_free"
    COMMERCIAL_USE = "commercial_use"
    ANY = "any"


@dataclass(frozen=True)
class ImageMetadata:
    """
    Metadata for fetched images to enable quality filtering and assessment.

    Provides comprehensive information about image characteristics,
    licensing, and quality metrics to support intelligent image selection.
    """

    url: str
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    format: str = "unknown"
    license: ImageLicense = ImageLicense.ANY
    source: str = "unknown"
    alt_text: str = ""
    blur_score: float = 0.0  # Higher = more blurry (0.0 = sharp)

    @property
    def resolution(self) -> int:
        """Get the maximum dimension (width or height) for quality assessment."""
        return max(self.width, self.height)

    @property
    def aspect_ratio(self) -> float:
        """Get width/height ratio, or 1.0 if dimensions are unknown."""
        return self.width / self.height if self.height > 0 else 1.0

    @property
    def megapixels(self) -> float:
        """Calculate image size in megapixels."""
        return (
            (self.width * self.height) / 1_000_000
            if self.width > 0 and self.height > 0
            else 0.0
        )

    def is_high_quality(self) -> bool:
        """
        Determine if image meets high quality criteria.

        Returns:
            True if image has good resolution, sharpness, and format
        """
        return (
            self.resolution >= 512
            and self.blur_score < 100.0  # Not too blurry
            and self.format.lower() in {"jpg", "jpeg", "png", "webp"}
            and self.file_size_bytes > 10_000  # Not too small
        )

    def is_landscape(self) -> bool:
        """Check if image is in landscape orientation."""
        return self.aspect_ratio > 1.2

    def is_portrait(self) -> bool:
        """Check if image is in portrait orientation."""
        return self.aspect_ratio < 0.8

    def is_square(self) -> bool:
        """Check if image is approximately square."""
        return 0.8 <= self.aspect_ratio <= 1.2


@dataclass(frozen=True)
class ImageResult:
    """
    Container for image data and its metadata.

    Combines the raw image bytes with rich metadata to enable
    intelligent processing and quality assessment downstream.
    """

    data: bytes
    metadata: ImageMetadata

    @property
    def size_mb(self) -> float:
        """Get image size in megabytes."""
        return len(self.data) / 1_048_576

    def is_valid(self) -> bool:
        """Check if image result contains valid data."""
        return (
            len(self.data) > 1000  # Minimum size
            and self.metadata.url
            and self.metadata.format != "unknown"
        )


class IReferenceImageSource(ABC):
    """
    Enhanced interface for fetching reference images with quality controls.

    Provides a clean abstraction for obtaining images from various sources
    while supporting quality filtering, licensing compliance, and rate limiting.
    """

    @abstractmethod
    def fetch_for_keyword(
        self,
        keyword: Keyword,
        min_quality: ImageQuality = ImageQuality.MEDIUM,
        required_license: ImageLicense = ImageLicense.ANY,
        max_results: int | None = None,
    ) -> list[ImageResult]:
        """
        Fetch images for the given keyword with quality and license filtering.

        Args:
            keyword: The keyword to search for images
            min_quality: Minimum image quality level to accept
            required_license: Required license type for legal compliance
            max_results: Maximum number of results (None = use source default)

        Returns:
            List of ImageResult objects with data and metadata, ordered by quality

        Raises:
            ImageSourceError: If the image source is unavailable or fails
            RateLimitError: If rate limits are exceeded
        """

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Return human-readable name of this image source.

        Returns:
            String identifier like "Google Images", "Unsplash", etc.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this image source is currently available and configured.

        Should perform a lightweight connectivity check without consuming
        significant API quotas or time.

        Returns:
            True if source is ready to use, False otherwise
        """

    @abstractmethod
    def get_rate_limit_info(self) -> dict[str, int]:
        """
        Get rate limiting information for this source.

        Provides information about current usage and limits to enable
        intelligent request scheduling and user feedback.

        Returns:
            Dict with keys like 'requests_per_hour', 'requests_remaining',
            'reset_time', 'daily_quota_remaining', etc.
        """

    def get_supported_qualities(self) -> list[ImageQuality]:
        """
        Get list of quality levels supported by this source.

        Default implementation supports all quality levels.
        Sources can override to indicate their capabilities.

        Returns:
            List of supported ImageQuality enum values
        """
        return list(ImageQuality)

    def get_supported_licenses(self) -> list[ImageLicense]:
        """
        Get list of license types supported by this source.

        Default implementation supports any license (no filtering).
        Sources can override to indicate their license filtering capabilities.

        Returns:
            List of supported ImageLicense enum values
        """
        return [ImageLicense.ANY]

    def estimate_fetch_time(self, keyword: Keyword, max_results: int) -> float:
        """
        Estimate time required to fetch images for a keyword.

        Default implementation provides a conservative estimate.
        Sources can override with more accurate estimates based on their
        performance characteristics.

        Args:
            keyword: Keyword to fetch images for
            max_results: Number of results requested

        Returns:
            Estimated time in seconds
        """
        return max_results * 2.0  # Conservative 2 seconds per image
