"""
Domain-specific exceptions for the Collage Maker application.

These exceptions represent business rule violations and error conditions
that can occur within the domain layer. They are caught and handled
appropriately by the application and presentation layers.

All domain exceptions inherit from DomainError to enable consistent
error handling patterns throughout the application.
"""

from __future__ import annotations


class DomainError(Exception):
    """
    Base class for all domain-specific errors.

    Domain errors represent violations of business rules or constraints
    within the domain layer. They should be caught and handled gracefully
    by the application layer, often converting them to appropriate
    HTTP responses or user messages.
    """

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        """
        Initialize a domain error with message and optional error code.

        Args:
            message: Human-readable error description
            error_code: Optional machine-readable error identifier
        """
        super().__init__(message)
        self.error_code = error_code or self.__class__.__name__.lower()


class CollageNotFoundError(DomainError):
    """
    Raised when attempting to access a collage that doesn't exist.

    This typically occurs when:
    - Trying to rename a non-existent collage
    - Attempting to delete a collage that was already removed
    - Accessing a collage by an invalid or expired ID
    """

    def __init__(self, collage_id: str) -> None:
        message = f"No collage found with id={collage_id!r}"
        super().__init__(message, error_code="collage_not_found")
        self.collage_id = collage_id


class CollageCreationError(DomainError):
    """
    Raised when collage creation fails due to business rule violations.

    This can occur during various stages of collage creation:
    - Insufficient or invalid source text
    - Keyword extraction failures
    - Image processing errors
    - Composition failures
    """

    def __init__(
        self, message: str, *, stage: str | None = None, cause: Exception | None = None
    ) -> None:
        super().__init__(message, error_code="collage_creation_failed")
        self.stage = stage  # Which stage of creation failed
        self.cause = cause  # Original exception if applicable


class InvalidCollageNameError(DomainError):
    """
    Raised when a collage name violates naming constraints.

    Common violations include:
    - Empty or whitespace-only names
    - Names that are too long or too short
    - Names containing forbidden characters
    - Names that conflict with reserved words
    """

    def __init__(self, name: str, reason: str) -> None:
        message = f"Invalid collage name '{name}': {reason}"
        super().__init__(message, error_code="invalid_collage_name")
        self.invalid_name = name
        self.reason = reason


class KeywordExtractionError(DomainError):
    """
    Raised when keyword extraction fails or produces insufficient results.

    This can occur when:
    - Source text is too short or lacks meaningful content
    - Text processing libraries encounter errors
    - No keywords meet quality thresholds after filtering
    """

    def __init__(self, message: str, *, text_length: int = 0) -> None:
        super().__init__(message, error_code="keyword_extraction_failed")
        self.text_length = text_length


class ImageSourceError(DomainError):
    """
    Raised when image source operations fail.

    This can occur when:
    - External image APIs are unavailable
    - Rate limits are exceeded
    - Network connectivity issues
    - Invalid search queries or parameters
    """

    def __init__(self, message: str, *, source_name: str | None = None) -> None:
        super().__init__(message, error_code="image_source_error")
        self.source_name = source_name


class CompositionError(DomainError):
    """
    Raised when collage composition fails.

    This can occur when:
    - Unable to place images without collisions
    - Canvas dimensions are too small for content
    - Image processing operations fail
    - Wordcloud generation encounters errors
    """

    def __init__(self, message: str, *, images_processed: int = 0) -> None:
        super().__init__(message, error_code="composition_failed")
        self.images_processed = images_processed


class StorageError(DomainError):
    """
    Raised when storage operations fail.

    This can occur when:
    - Filesystem permissions prevent file operations
    - Disk space is insufficient
    - File corruption is detected
    - Network storage is unavailable
    """

    def __init__(
        self, message: str, *, operation: str | None = None, path: str | None = None
    ) -> None:
        super().__init__(message, error_code="storage_error")
        self.operation = operation  # "save", "delete", "read", etc.
        self.path = path


class RateLimitError(DomainError):
    """
    Raised when rate limits are exceeded for external services.

    This helps the application handle API rate limiting gracefully
    and provide appropriate user feedback about temporary restrictions.
    """

    def __init__(self, service_name: str, reset_time: int | None = None) -> None:
        message = f"Rate limit exceeded for {service_name}"
        if reset_time:
            message += f". Try again in {reset_time} seconds"
        super().__init__(message, error_code="rate_limit_exceeded")
        self.service_name = service_name
        self.reset_time = reset_time
