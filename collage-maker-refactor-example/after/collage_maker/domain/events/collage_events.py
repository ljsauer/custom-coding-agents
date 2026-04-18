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

from datetime import datetime as dt
from pydantic import BaseModel, Field

from collage_maker.domain.model.keyword import Keyword


class DomainEvent(BaseModel):
    """Base class for all domain events with common timestamp behavior."""
    
    occurred_at: dt = Field(
        default_factory=lambda: dt.now(dt.UTC),
        description="When the event occurred",
        frozen=True
    )

    class Config:
        frozen = True


class CollageCreated(DomainEvent):
    """Event raised when a new collage is successfully created."""
    
    collage_id: str = Field(..., description="Unique identifier for the collage")
    name: str = Field(..., description="Human-readable name of the collage")
    keywords: list[Keyword] = Field(..., description="Keywords extracted from source text")
    image_count: int = Field(..., description="Number of images composed in the collage", ge=0)
    processing_time_seconds: float = Field(
        default=0.0, 
        description="Time taken to create the collage",
        ge=0.0
    )


class CollageRenamed(DomainEvent):
    """Event raised when a collage is renamed."""
    
    collage_id: str = Field(..., description="Unique identifier for the collage")
    old_name: str = Field(..., description="Previous name")
    new_name: str = Field(..., description="New name")


class CollageDeleted(DomainEvent):
    """Event raised when a collage is deleted."""
    
    collage_id: str = Field(..., description="Unique identifier for the deleted collage")
    name: str = Field(..., description="Name of the deleted collage for audit purposes")


class CollageProcessingStarted(DomainEvent):
    """Event raised when collage processing begins."""
    
    collage_id: str = Field(..., description="Unique identifier for the collage being processed")
    keyword_count: int = Field(..., description="Number of keywords to process", ge=1)
    estimated_duration_seconds: float = Field(
        default=30.0,
        description="Estimated processing time",
        ge=1.0
    )


class CollageProcessingFailed(DomainEvent):
    """Event raised when collage processing fails."""
    
    collage_id: str = Field(..., description="Unique identifier for the failed collage")
    error_type: str = Field(..., description="Type of error that occurred")
    error_message: str = Field(..., description="Detailed error message")
    keywords_processed: int = Field(default=0, description="Number of keywords processed before failure", ge=0)
