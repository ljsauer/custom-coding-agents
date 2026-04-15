"""
Pydantic response models for the collage API.

These models define the structure and validation for API responses,
ensuring consistent data formatting and enabling automatic OpenAPI
documentation generation.

All response models use modern Pydantic v2 features and include
comprehensive field documentation for API consumers.
"""

from __future__ import annotations

from datetime import datetime as dt

from pydantic import BaseModel, Field


class CollageResponse(BaseModel):
    """
    Response model for individual collage data.

    Used in both single collage responses and as elements in
    collage list responses. Includes all essential metadata
    for display and further processing.
    """

    id: str = Field(..., description="Unique identifier for the collage")
    name: str = Field(..., description="Human-readable name of the collage")
    keywords: list[str] = Field(
        ..., description="List of keywords extracted from source text", min_length=1
    )
    image_url: str = Field(..., description="URL to access the collage image")
    created_at: dt = Field(..., description="When the collage was created (UTC)")
    updated_at: dt = Field(..., description="When the collage was last modified (UTC)")

    # Optional metadata fields
    image_count: int = Field(
        default=0, description="Number of images used in the collage", ge=0
    )
    processing_time_seconds: float = Field(
        default=0.0, description="Time taken to create the collage", ge=0.0
    )
    quality_score: float = Field(
        default=0.0,
        description="Quality score of the collage (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    model_config = {
        "from_attributes": True,  # Enable ORM mode for SQLAlchemy models
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Beautiful Landscape",
                "keywords": ["mountain", "lake", "forest", "nature"],
                "image_url": "/static/collages/123e4567-e89b-12d3-a456-426614174000.jpg",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "image_count": 15,
                "processing_time_seconds": 45.2,
                "quality_score": 0.85,
            }
        },
    }


class CollageListResponse(BaseModel):
    """
    Response model for paginated collage lists.

    Provides both the collage data and metadata about the collection
    to support pagination, filtering, and UI state management.
    """

    collages: list[CollageResponse] = Field(..., description="List of collage objects")
    total: int = Field(
        ..., description="Total number of collages in the collection", ge=0
    )

    # Pagination support (optional, for future enhancement)
    page: int = Field(default=1, description="Current page number (1-based)", ge=1)
    page_size: int = Field(
        default=50, description="Number of items per page", ge=1, le=100
    )
    has_more: bool = Field(
        default=False, description="Whether there are more pages available"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "collages": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Beautiful Landscape",
                        "keywords": ["mountain", "lake", "forest"],
                        "image_url": "/static/collages/123e4567-e89b-12d3-a456-426614174000.jpg",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 50,
                "has_more": False,
            }
        }
    }


class MessageResponse(BaseModel):
    """
    Generic response model for operations that return status messages.

    Used for operations like create, update, delete that don't return
    specific data but need to communicate success/failure and context
    to the client.
    """

    message: str = Field(
        ..., description="Human-readable status or confirmation message", min_length=1
    )
    success: bool = Field(
        default=True, description="Whether the operation was successful"
    )
    error_code: str | None = Field(
        default=None, description="Machine-readable error identifier (if applicable)"
    )
    details: dict[str, str] | None = Field(
        default=None, description="Additional context or error details"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"message": "Collage created successfully", "success": True},
                {
                    "message": "Collage not found",
                    "success": False,
                    "error_code": "collage_not_found",
                    "details": {"collage_id": "invalid-id-123"},
                },
            ]
        }
    }


class ErrorResponse(BaseModel):
    """
    Standardized error response model for API errors.

    Provides consistent error reporting across all endpoints
    with sufficient detail for debugging while maintaining
    security by not exposing sensitive information.
    """

    error: str = Field(..., description="Error type or category")
    message: str = Field(..., description="Human-readable error description")
    success: bool = Field(default=False, description="Always False for error responses")
    timestamp: dt = Field(
        default_factory=lambda: dt.now(dt.UTC),
        description="When the error occurred (UTC)",
    )
    path: str | None = Field(
        default=None, description="API endpoint where the error occurred"
    )
    request_id: str | None = Field(
        default=None, description="Unique request identifier for tracing"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "validation_error",
                "message": "Invalid collage name: too short",
                "success": False,
                "timestamp": "2024-01-15T10:30:00Z",
                "path": "/api/collage/123/rename",
                "request_id": "req_7c9e6d8f-4b3a-11ee-be56-0242ac120002",
            }
        }
    }


class HealthCheckResponse(BaseModel):
    """
    Response model for health check endpoints.

    Provides system status information for monitoring and
    service discovery systems.
    """

    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(default="2.0.0", description="Service version")
    timestamp: dt = Field(
        default_factory=lambda: dt.now(dt.UTC),
        description="Health check timestamp (UTC)",
    )
    uptime_seconds: float = Field(
        default=0.0, description="Service uptime in seconds", ge=0.0
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "service": "collage-maker",
                "version": "2.0.0",
                "timestamp": "2024-01-15T10:30:00Z",
                "uptime_seconds": 3661.5,
            }
        }
    }
