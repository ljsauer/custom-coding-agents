"""
Pydantic request models for the collage API.

These models define the structure and validation rules for incoming
API requests, ensuring data quality and providing clear error messages
for validation failures.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RenameCollageRequest(BaseModel):
    """Request model for renaming a collage via JSON API."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="New name for the collage",
        examples=["My Beautiful Landscape", "Abstract Art Collection"],
    )

    model_config = {
        "str_strip_whitespace": True,  # Automatically strip whitespace
        "validate_assignment": True,  # Validate on field assignment
    }
