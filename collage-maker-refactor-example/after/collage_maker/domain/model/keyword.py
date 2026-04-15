"""
Keyword — Enhanced Pydantic Value Object

A keyword is a meaningful word extracted from source text that drives both
the wordcloud composition and the reference-image search. This version includes
enhanced validation, normalization, and semantic capabilities.
"""

from __future__ import annotations
import re
from pydantic import BaseModel, Field, field_validator


class Keyword(BaseModel):
    """A normalized, validated keyword extracted from source text."""

    text: str = Field(..., description="The keyword text, normalized to lowercase")
    frequency: int = Field(
        default=1, description="Frequency of this keyword in source text", ge=1
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score for keyword relevance",
        ge=0.0,
        le=1.0,
    )

    @field_validator("text")
    @classmethod
    def normalize_and_validate_text(cls, v: str) -> str:
        """Enhanced normalization and validation."""
        if not v or not v.strip():
            raise ValueError(
                "A keyword must contain at least one non-whitespace character."
            )

        # Initial cleanup
        cleaned = v.strip().lower()

        # Remove problematic characters but preserve meaningful punctuation
        cleaned = re.sub(r"[^\w\s\-\']", "", cleaned)

        # Handle contractions and hyphenated words appropriately
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Length validation
        if len(cleaned) < 2:
            raise ValueError("Keywords must be at least 2 characters long.")
        if len(cleaned) > 50:
            raise ValueError("Keywords cannot exceed 50 characters.")

        # Pattern-based validation
        if cleaned.isdigit():
            raise ValueError("Keywords cannot be purely numeric.")

        # Check for minimum alphabetic content
        alpha_chars = sum(1 for c in cleaned if c.isalpha())
        if alpha_chars < 2:
            raise ValueError("Keywords must contain at least 2 alphabetic characters.")

        return cleaned

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: int) -> int:
        """Ensure frequency is reasonable."""
        if v > 10000:  # Sanity check for very large texts
            return 10000
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is within valid range."""
        return max(0.0, min(1.0, v))

    def is_high_quality(self) -> bool:
        """Determine if this is a high-quality keyword."""
        return (
            len(self.text) >= 3
            and self.frequency >= 2
            and self.confidence >= 0.4
            and not self._is_common_noise_word()
        )

    def _is_common_noise_word(self) -> bool:
        """Check if keyword is likely a noise word despite filtering."""
        noise_patterns = {
            "chapter",
            "section",
            "page",
            "line",
            "paragraph",
            "figure",
            "table",
            "image",
            "photo",
            "picture",
            "first",
            "second",
            "third",
            "last",
            "next",
            "previous",
            "example",
            "instance",
            "case",
            "situation",
        }
        return self.text in noise_patterns

    def similarity_score(self, other: "Keyword") -> float:
        """
        Calculate semantic similarity with another keyword using simple heuristics.
        Returns score between 0.0 (no similarity) and 1.0 (identical).
        """
        if not isinstance(other, Keyword):
            return 0.0

        if self.text == other.text:
            return 1.0

        # Simple character-based similarity
        text1, text2 = self.text, other.text

        # Check for substring relationships
        if text1 in text2 or text2 in text1:
            return 0.8

        # Check for common prefixes/suffixes (stemming-like)
        if len(text1) > 4 and len(text2) > 4:
            if text1[:4] == text2[:4] or text1[-4:] == text2[-4:]:
                return 0.6

        # Character overlap ratio
        chars1, chars2 = set(text1), set(text2)
        overlap = len(chars1 & chars2)
        union = len(chars1 | chars2)
        if union > 0:
            return overlap / union * 0.5

        return 0.0

    def get_search_variants(self) -> list[str]:
        """
        Generate search term variants for better image retrieval.
        Returns alternative forms that might yield better results.
        """
        variants = [self.text]

        # Add plural/singular variants using simple heuristics
        if (
            self.text.endswith("s")
            and not self.text.endswith("ous")
            and len(self.text) > 3
        ):
            # Try singular
            singular = self.text[:-1]
            if singular not in variants:
                variants.append(singular)
        elif not self.text.endswith("s"):
            # Try plural
            if self.text.endswith("y"):
                plural = self.text[:-1] + "ies"
            elif self.text.endswith(("ch", "sh", "x", "z")):
                plural = self.text + "es"
            else:
                plural = self.text + "s"
            if plural not in variants:
                variants.append(plural)

        # Add related terms for common categories
        category_expansions = {
            "car": ["automobile", "vehicle"],
            "house": ["home", "building"],
            "dog": ["puppy", "canine"],
            "cat": ["kitten", "feline"],
            "tree": ["forest", "nature"],
            "ocean": ["sea", "water"],
            "mountain": ["peak", "landscape"],
        }

        if self.text in category_expansions:
            variants.extend(category_expansions[self.text])

        return variants[:5]  # Limit to prevent too many API calls

    def __str__(self) -> str:
        return self.text

    def __hash__(self) -> int:
        return hash(self.text)

    def __lt__(self, other: "Keyword") -> bool:
        """Enable sorting by frequency (descending) then confidence (descending)."""
        if not isinstance(other, Keyword):
            return NotImplemented
        return (self.frequency, self.confidence) > (other.frequency, other.confidence)

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }
