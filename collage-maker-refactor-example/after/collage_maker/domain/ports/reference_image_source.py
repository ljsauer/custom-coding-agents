"""
IReferenceImageSource — Enhanced Outbound Port

The domain needs a way to obtain raw image data for a given keyword so the
composition service can isolate subjects and place them on the canvas.

This enhanced version supports multiple image sources, quality filtering,
and metadata for better image selection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from collage_maker.domain.model.keyword import Keyword


class ImageQuality(Enum):
    """Image quality levels for filtering."""
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    ANY = "any"


class ImageLicense(Enum):
    """Image license types for legal compliance."""
    PUBLIC_DOMAIN = "public_domain"
    CREATIVE_COMMONS = "creative_commons"
    ROYALTY_FREE = "royalty_free"
    COMMERCIAL_USE = "commercial_use"
    ANY = "any"


@dataclass(frozen=True)
class ImageMetadata:
    """Metadata for fetched images to enable quality filtering."""
    
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
        """Get the maximum dimension (width or height)."""
        return max(self.width, self.height)

    @property
    def aspect_ratio(self) -> float:
        """Get width/height ratio, or 1.0 if dimensions unknown."""
        return self.width / self.height if self.height > 0 else 1.0

    def is_high_quality(self) -> bool:
        """Determine if image meets high quality criteria."""
        return (
            self.resolution >= 512 and
            self.blur_score < 100.0 and  # Not too blurry
            self.format.lower() in {'jpg', 'jpeg', 'png', 'webp'}
        )


@dataclass(frozen=True) 
class ImageResult:
    """Container for image data and its metadata."""
    
    data: bytes
    metadata: ImageMetadata


class IReferenceImageSource(ABC):
    """Enhanced interface for fetching reference images with quality controls."""

    @abstractmethod
    def fetch_for_keyword(
        self, 
        keyword: Keyword,
        min_quality: ImageQuality = ImageQuality.MEDIUM,
        required_license: ImageLicense = ImageLicense.ANY,
        max_results: int | None = None
    ) -> list[ImageResult]:
        """
        Fetch images for the given keyword with quality and license filtering.
        
        Args:
            keyword: The keyword to search for
            min_quality: Minimum image quality level
            required_license: Required license type for legal use
            max_results: Maximum number of results (None = use default)
            
        Returns:
            List of ImageResult objects with data and metadata
        """

    @abstractmethod
    def get_source_name(self) -> str:
        """Return human-readable name of this image source."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this image source is currently available/configured."""

    @abstractmethod
    def get_rate_limit_info(self) -> dict[str, int]:
        """
        Get rate limiting information for this source.
        
        Returns:
            Dict with keys like 'requests_per_hour', 'requests_remaining', etc.
        """
