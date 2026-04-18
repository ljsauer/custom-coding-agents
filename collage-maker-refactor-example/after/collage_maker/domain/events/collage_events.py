"""
Domain Events using Pydantic

A domain event is a record that something meaningful happened within the
domain. Events are named in the past tense and carry only the data that
describes what changed.

These are Pydantic models with validation and serialization support.
If an event bus or async queue is introduced, these models can be easily
serialized to JSON or other formats for inter-service communication.

All events inherit from DomainEvent for consistent timestambing and behavior.
"""

from __future__ import annotations

from datetime import datetime as dt
from pydantic import BaseModel, Field

from collage_maker.domain.model.keyword import Keyword


class DomainEvent(BaseModel):
    """
    Base class for all domain events with common timestamp behavior.

    Provides automatic timestamping in UTC and enforces immutability
    to ensure events represent immutable facts about what happened.
    """

    occurred_at: dt = Field(
        default_factory=lambda: dt.now(dt.UTC),
        description="When the event occurred (UTC timezone)",
        frozen=True,
    )

    model_config = {
        "frozen": True,
        "validate_assignment": True,
    }


class CollageCreated(DomainEvent):
    """
    Event raised when a new collage is successfully created.

    This event signifies that a complete collage has been generated,
    including keyword extraction, image fetching, composition, and storage.
    """

    collage_id: str = Field(..., description="Unique identifier for the collage")
    name: str = Field(..., description="Human-readable name of the collage")
    keywords: list[Keyword] = Field(
        ..., description="Keywords extracted from source text"
    )
    image_count: int = Field(
        ..., description="Number of images composed in the collage", ge=0
    )
    processing_time_seconds: float = Field(
        default=0.0, description="Time taken to create the collage", ge=0.0
    )
    source_text_length: int = Field(
        default=0, description="Length of source text in characters", ge=0
    )
    quality_score: float = Field(
        default=0.0, description="Overall quality score of the collage", ge=0.0, le=1.0
    )


class CollageRenamed(DomainEvent):
    """
    Event raised when a collage is renamed by a user.

    Captures both old and new names for audit purposes and
    potential undo functionality.
    """

    collage_id: str = Field(..., description="Unique identifier for the collage")
    old_name: str = Field(..., description="Previous name before rename")
    new_name: str = Field(..., description="New name after rename")
    renamed_by: str | None = Field(
        default=None, description="User or system that performed the rename"
    )


class CollageDeleted(DomainEvent):
    """
    Event raised when a collage is deleted from the system.

    Records the deletion for audit trails and cleanup processes.
    The name is preserved for audit purposes since the collage no longer exists.
    """

    collage_id: str = Field(
        ..., description="Unique identifier for the deleted collage"
    )
    name: str = Field(..., description="Name of the deleted collage for audit purposes")
    keyword_count: int = Field(
        default=0, description="Number of keywords the collage contained", ge=0
    )
    deleted_by: str | None = Field(
        default=None, description="User or system that performed the deletion"
    )


class CollageProcessingStarted(DomainEvent):
    """
    Event raised when collage processing begins.

    Useful for tracking processing pipelines, user notifications,
    and performance monitoring.
    """

    collage_id: str = Field(
        ..., description="Unique identifier for the collage being processed"
    )
    keyword_count: int = Field(..., description="Number of keywords to process", ge=1)
    estimated_duration_seconds: float = Field(
        default=30.0, description="Estimated processing time", ge=1.0
    )
    source_text_preview: str = Field(
        default="", description="First 100 characters of source text", max_length=100
    )


class CollageProcessingFailed(DomainEvent):
    """
    Event raised when collage processing fails at any stage.

    Captures error details for debugging, monitoring, and user notification.
    Includes progress information to understand where the failure occurred.
    """

    collage_id: str = Field(..., description="Unique identifier for the failed collage")
    error_type: str = Field(..., description="Type of error that occurred")
    error_message: str = Field(..., description="Detailed error message")
    keywords_processed: int = Field(
        default=0, description="Number of keywords processed before failure", ge=0
    )
    images_fetched: int = Field(
        default=0, description="Number of images fetched before failure", ge=0
    )
    processing_stage: str = Field(
        default="unknown",
        description="Stage where processing failed (extraction, fetching, composition, storage)",
    )
    source_name: str | None = Field(
        default=None, description="Image source that failed"
    )
    retry_count: int = Field(default=0, description="Number of retries attempted", ge=0)


class ImageSourceError(DomainEvent):
    """
    Event raised when image source encounters errors.

    This provides detailed tracking of image source failures to help
    diagnose and monitor external service issues.
    """

    source_name: str = Field(..., description="Name of the image source that failed")
    keyword_text: str = Field(
        ..., description="Keyword being searched when error occurred"
    )
    error_type: str = Field(
        ..., description="Type of error (network, rate_limit, parsing)"
    )
    error_message: str = Field(..., description="Detailed error message")
    http_status: int | None = Field(
        default=None, description="HTTP status code if applicable"
    )
    retry_after: int | None = Field(
        default=None, description="Seconds to wait before retry if provided"
    )
    images_fetched_before_error: int = Field(
        default=0, description="Images successfully fetched before error", ge=0
    )


class ImageQualityFiltered(DomainEvent):
    """
    Event raised when images are filtered due to quality issues.

    Helps track image quality patterns and tune filtering parameters.
    """

    keyword_text: str = Field(..., description="Keyword the images were for")
    images_filtered: int = Field(..., description="Number of images filtered out", ge=0)
    filter_reasons: list[str] = Field(
        ..., description="Reasons images were filtered (blur, size, format, etc.)"
    )
    source_name: str = Field(..., description="Image source name")


class CollageImageUpdated(DomainEvent):
    """
    Event raised when a collage's rendered image is updated.

    This might occur during reprocessing, quality improvements,
    or format conversions.
    """

    collage_id: str = Field(..., description="Unique identifier for the collage")
    old_image_size_bytes: int = Field(
        default=0, description="Previous image size in bytes", ge=0
    )
    new_image_size_bytes: int = Field(
        default=0, description="New image size in bytes", ge=0
    )
    image_format: str = Field(
        default="jpeg", description="Image format (jpeg, png, webp)"
    )
    quality_score: float = Field(
        default=0.0, description="Quality score of the new image", ge=0.0, le=1.0
    )


class CollageMetadataUpdated(DomainEvent):
    """
    Event raised when collage metadata is updated (beyond just renaming).

    Captures changes to processing information, quality scores,
    or other metadata fields.
    """

    collage_id: str = Field(..., description="Unique identifier for the collage")
    field_name: str = Field(..., description="Name of the metadata field updated")
    old_value: str | None = Field(
        default=None, description="Previous value (serialized as string)"
    )
    new_value: str | None = Field(
        default=None, description="New value (serialized as string)"
    )
    updated_by: str | None = Field(
        default=None, description="User or system that made the update"
    )
