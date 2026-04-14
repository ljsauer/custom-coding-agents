"""
Collage — Aggregate Root using modern Python patterns

The central concept of the domain. A Collage is created from source text,
carries the keywords that shaped it, and has a human-readable name.

This class uses modern Python features including structural pattern matching
and enhanced type safety while remaining framework-agnostic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from collage_maker.domain.common.utils import utcnow
from collage_maker.domain.exceptions import (
    CollageCreationError,
    InvalidCollageNameError,
)
from collage_maker.domain.model.keyword import Keyword


@dataclass
class Collage:
    """
    Aggregate root with enhanced validation and modern Python features.

    Identity is carried by *id* (a UUID string). Callers must use
    ICollageRepository to obtain and persist instances; they must never
    construct a Collage and assume it is already stored.
    """

    id: str
    keywords: list[Keyword]
    name: str
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    # Additional metadata for enhanced functionality
    source_text_length: int = field(default=0)
    processing_time_seconds: float = field(default=0.0)
    image_count: int = field(default=0)

    def __post_init__(self):
        """Validate aggregate state after construction."""
        if not self.id:
            raise CollageCreationError("Collage ID cannot be empty")
        
        if not self.keywords:
            raise CollageCreationError("Collage must have at least one keyword")
        
        if not self.name or not self.name.strip():
            raise InvalidCollageNameError("Collage name cannot be blank")
        
        # Normalize the name
        object.__setattr__(self, 'name', self.name.strip())

    # ------------------------------------------------------------------
    # Factory Methods
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls, 
        keywords: list[Keyword], 
        name: str | None = None,
        source_text: str = "",
        processing_time: float = 0.0
    ) -> Collage:
        """
        Named constructor — the canonical way to bring a new Collage into
        existence. Uses modern Python features for enhanced validation.
        """
        if not keywords:
            raise CollageCreationError(
                "A collage must be based on at least one keyword."
            )
        
        # Validate keyword quality
        unique_keywords = list({kw.text: kw for kw in keywords}.values())
        if len(unique_keywords) < len(keywords):
            # Remove duplicates while preserving order
            keywords = unique_keywords
        
        collage_id = str(uuid.uuid4())
        default_name = cls._generate_smart_name(keywords, collage_id)
        
        return cls(
            id=collage_id,
            keywords=keywords,
            name=name or default_name,
            source_text_length=len(source_text),
            processing_time_seconds=processing_time,
        )

    @classmethod
    def _generate_smart_name(cls, keywords: list[Keyword], collage_id: str) -> str:
        """Generate a meaningful default name based on top keywords."""
        if not keywords:
            return f"collage-{collage_id[:8]}"
        
        # Use structural pattern matching for name generation
        match len(keywords):
            case 1:
                return f"{keywords[0].text}-collage"
            case 2:
                return f"{keywords[0].text}-{keywords[1].text}"
            case n if n >= 3:
                top_words = [kw.text for kw in keywords[:3]]
                return "-".join(top_words)
            case _:
                return f"collage-{collage_id[:8]}"

    # ------------------------------------------------------------------
    # Behavior Methods
    # ------------------------------------------------------------------

    def rename(self, new_name: str) -> None:
        """
        Apply a user-chosen name with enhanced validation.
        Stamps updated_at so callers can detect that the aggregate changed.
        """
        if not new_name or not new_name.strip():
            raise InvalidCollageNameError("Collage name must not be blank.")
        
        clean_name = new_name.strip()
        
        # Enhanced name validation
        if len(clean_name) > 100:
            raise InvalidCollageNameError(
                "Collage name too long. Maximum 100 characters allowed."
            )
        
        if len(clean_name) < 2:
            raise InvalidCollageNameError(
                "Collage name too short. Minimum 2 characters required."
            )
        
        # Check for problematic characters
        forbidden_chars = {'/', '\\', ':', '*', '?', '"', '<', '>', '|'}
        if any(char in clean_name for char in forbidden_chars):
            raise InvalidCollageNameError(
                f"Collage name contains forbidden characters: {forbidden_chars}"
            )
        
        self.name = clean_name
        self.updated_at = utcnow()

    def add_metadata(self, image_count: int, processing_time: float) -> None:
        """Add processing metadata after collage creation."""
        if image_count < 0:
            raise ValueError("Image count cannot be negative")
        if processing_time < 0:
            raise ValueError("Processing time cannot be negative")
        
        self.image_count = image_count
        self.processing_time_seconds = processing_time
        self.updated_at = utcnow()

    # ------------------------------------------------------------------
    # Query Methods (for templates and serializers)
    # ------------------------------------------------------------------

    def keyword_texts(self) -> list[str]:
        """Get list of keyword text strings."""
        return [kw.text for kw in self.keywords]

    def primary_keywords(self, count: int = 5) -> list[Keyword]:
        """Get the top N keywords (assumes keywords are already ranked)."""
        return self.keywords[:min(count, len(self.keywords))]

    def get_quality_score(self) -> float:
        """
        Calculate a quality score based on various factors.
        Returns a score between 0.0 and 1.0.
        """
        # Base score factors
        keyword_quality = min(len(self.keywords) / 25, 1.0)  # Optimal around 25 keywords
        text_quality = min(self.source_text_length / 5000, 1.0)  # Good text length
        processing_quality = 1.0 if self.processing_time_seconds > 0 else 0.5
        image_quality = min(self.image_count / 50, 1.0) if self.image_count > 0 else 0.5
        
        # Weighted average
        return (
            keyword_quality * 0.3 + 
            text_quality * 0.2 + 
            processing_quality * 0.2 + 
            image_quality * 0.3
        )

    def is_recent(self, hours: int = 24) -> bool:
        """Check if collage was created within the specified hours."""
        age = utcnow() - self.created_at
        return age.total_seconds() < (hours * 3600)

    # ------------------------------------------------------------------
    # Rich Comparison and Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        quality = self.get_quality_score()
        return f"<Collage id={self.id!r} name={self.name!r} quality={quality:.2f}>"

    def __str__(self) -> str:
        return f"Collage '{self.name}' ({len(self.keywords)} keywords, {self.image_count} images)"
