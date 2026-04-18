"""
Domain Events using Pydantic

A domain event is a record that something meaningful happened within the
domain. Events are named in the past tense and carry only the data that
describes what changed.

These are Pydantic models with validation and serialization support.
If an event bus or async queue is introduced, these models can be easily
serialized to JSON or other formats.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from collage_maker.domain.common.utils import utcnow
from collage_maker.domain.model.keyword import Keyword


class CollageCreated(BaseModel):
    """Event raised when a new collage is successfully created."""
    
    collage_id: str = Field(..., description="Unique identifier for the collage")
    name: str = Field(..., description="Human-readable name of the collage")
    keywords: list[Keyword] = Field(..., description="Keywords extracted from source text")
    occurred_at: datetime = Field(default_factory=utcnow, description="When the event occurred")

    class Config:
        frozen = True


class CollageRenamed(BaseModel):
    """Event raised when a collage is renamed."""
    
    collage_id: str = Field(..., description="Unique identifier for the collage")
    old_name: str = Field(..., description="Previous name")
    new_name: str = Field(..., description="New name")
    occurred_at: datetime = Field(default_factory=utcnow, description="When the event occurred")

    class Config:
        frozen = True


class CollageDeleted(BaseModel):
    """Event raised when a collage is deleted."""
    
    collage_id: str = Field(..., description="Unique identifier for the deleted collage")
    occurred_at: datetime = Field(default_factory=utcnow, description="When the event occurred")

    class Config:
        frozen = True
