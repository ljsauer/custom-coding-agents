"""
Keyword — Pydantic Value Object

A keyword is a meaningful word extracted from source text that drives both
the wordcloud composition and the reference-image search.

Value objects are immutable and defined entirely by their value.
Two Keywords with the same text are equal regardless of object identity.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, validator


class Keyword(BaseModel):
    """A normalized keyword extracted from source text."""
    
    text: str = Field(..., description="The keyword text, normalized to lowercase")

    @validator('text')
    def normalize_and_validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError(
                "A keyword must contain at least one non-whitespace character."
            )
        # Normalize to lowercase so 'Apple' and 'apple' are the same keyword.
        return v.strip().lower()

    def __str__(self) -> str:
        return self.text
    
    def __hash__(self) -> int:
        return hash(self.text)

    class Config:
        frozen = True
