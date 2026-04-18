"""
Pure configuration values using Pydantic BaseSettings with modern Python features.

This provides environment variable support, validation, and type safety.
Configuration can be overridden via environment variables prefixed with "COLLAGE_".

Directory bootstrapping remains the responsibility of main.py (the composition
root), executed once at startup, not at import time.

The configuration is organized into logical sections for easy maintenance
and includes comprehensive validation to catch configuration errors early.
"""

from __future__ import annotations

from pathlib import Path
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application configuration with environment variable support.

    Environment variables should be prefixed with "COLLAGE_", e.g.:
    COLLAGE_DATABASE_PATH=/custom/path/db.sqlite
    COLLAGE_N_KEYWORDS=30
    COLLAGE_CANVAS_WIDTH=1920

    All settings include sensible defaults and comprehensive validation
    to ensure the application starts with a valid configuration.
    """

    # -----------------------------------------------------------------------
    # Filesystem paths
    # -----------------------------------------------------------------------
    collage_dir: str = Field(
        default_factory=lambda: str(Path.cwd() / "static"),
        description="Directory for storing rendered collage images",
    )
    download_dir: str = Field(
        default_factory=lambda: str(Path.cwd() / "downloads"),
        description="Directory for temporary download files",
    )
    database_path: str = Field(
        default_factory=lambda: str(Path.cwd() / "database.sqlite"),
        description="Path to SQLite database file",
    )

    # -----------------------------------------------------------------------
    # Computer Vision & Image Processing
    # -----------------------------------------------------------------------
    min_image_resolution: int = Field(
        default=512,
        description="Minimum image resolution (width or height) to accept",
        ge=256,
        le=2048,
    )
    max_image_resolution: int = Field(
        default=2048,
        description="Maximum image resolution before downscaling",
        ge=512,
        le=4096,
    )
    subject_isolation_method: str = Field(
        default="grabcut",
        description="Method for subject isolation: 'grabcut', 'watershed', or 'threshold'",
    )
    edge_detection_method: str = Field(
        default="canny_auto",
        description="Edge detection method: 'canny_auto', 'canny_manual', or 'sobel'",
    )
    composition_algorithm: str = Field(
        default="collision_avoidance",
        description="Layout algorithm: 'collision_avoidance', 'grid', or 'semantic'",
    )

    # -----------------------------------------------------------------------
    # Collage composition parameters
    # -----------------------------------------------------------------------
    n_keywords: int = Field(
        default=25,
        description="Number of keywords to extract from source text",
        ge=1,
        le=100,
    )
    images_per_keyword: int = Field(
        default=4, description="Number of images to fetch per keyword", ge=1, le=10
    )
    canvas_width: int = Field(
        default=1280, description="Canvas width in pixels", ge=512, le=4096
    )
    canvas_height: int = Field(
        default=960, description="Canvas height in pixels", ge=384, le=3072
    )
    max_word_font_size: int = Field(
        default=175, description="Maximum font size for wordcloud text", ge=10, le=500
    )

    # -----------------------------------------------------------------------
    # Image Quality & Processing
    # -----------------------------------------------------------------------
    jpeg_quality: int = Field(
        default=90, description="JPEG compression quality (1-100)", ge=50, le=100
    )
    enable_upscaling: bool = Field(
        default=True, description="Enable AI-based image upscaling for low-res sources"
    )
    blur_threshold: float = Field(
        default=100.0,
        description="Laplacian variance threshold for blur detection",
        ge=10.0,
        le=1000.0,
    )

    # -----------------------------------------------------------------------
    # API Keys and External Services
    # -----------------------------------------------------------------------
    unsplash_access_key: str | None = Field(
        default=None, description="Unsplash API access key for high-quality images"
    )
    pixabay_api_key: str | None = Field(
        default=None, description="Pixabay API key for stock photos"
    )
    use_google_fallback: bool = Field(
        default=True, description="Fall back to Google Images if API sources fail"
    )

    # -----------------------------------------------------------------------
    # NLP — domain-specific noise words added on top of NLTK's English list
    # -----------------------------------------------------------------------
    extra_stopwords: list[str] = Field(
        default_factory=lambda: [
            # Classic text artifacts
            "said",
            "might",
            "towards",
            "found",
            "must",
            "things",
            "last",
            "make",
            "upon",
            "shall",
            "gutenberg",
            "many",
            "with",
            "without",
            "like",
            "project",
            "thee",
            "thou",
            "thus",
            # Encoding artifacts
            "x80",
            "x9d",
            "x9ci",
            "xe2",
            # Modern web noise words
            "www",
            "http",
            "https",
            "com",
            "org",
            "html",
            "jpg",
            "png",
            "gif",
            "click",
            "here",
            "more",
            "link",
            "page",
            "site",
            "website",
            # Document structure words
            "chapter",
            "section",
            "paragraph",
            "figure",
            "table",
            "image",
            "document",
            "file",
            "pdf",
            "doc",
            "text",
            "content",
            # Navigation and UI words
            "next",
            "previous",
            "back",
            "home",
            "menu",
            "search",
            "login",
            "register",
            "submit",
            "cancel",
            "save",
            "delete",
            "edit",
        ],
        description="Additional stopwords for keyword extraction beyond NLTK defaults",
    )

    # -----------------------------------------------------------------------
    # Advanced wordcloud colormaps organized by aesthetic category
    # -----------------------------------------------------------------------
    colormaps: list[str] = Field(
        default_factory=lambda: [
            # Perceptually uniform (preferred for accessibility)
            "viridis",
            "plasma",
            "inferno",
            "magma",
            "cividis",
            # Qualitative (good for distinct categories)
            "Set1",
            "Set2",
            "Set3",
            "tab10",
            "tab20",
            "Accent",
            "Dark2",
            "Paired",
            # Sequential (good for intensity gradients)
            "Blues",
            "Greens",
            "Oranges",
            "Reds",
            "Purples",
            "BuGn",
            "BuPu",
            "GnBu",
            "OrRd",
            "PuBu",
            "PuBuGn",
            "PuRd",
            "RdPu",
            "YlGn",
            "YlGnBu",
            "YlOrBr",
            "YlOrRd",
            # Diverging (good for contrasts and emphasis)
            "RdBu",
            "RdGy",
            "RdYlBu",
            "RdYlGn",
            "PiYG",
            "PRGn",
            "BrBG",
            "PuOr",
            "seismic",
            # Artistic and creative options
            "rainbow",
            "turbo",
            "twilight",
            "coolwarm",
            "cubehelix",
            "terrain",
        ],
        description="Available matplotlib colormaps for wordcloud generation",
    )

    @field_validator("canvas_width", "canvas_height")
    @classmethod
    def validate_positive_dimensions(cls, v: int, info) -> int:
        """Ensure canvas dimensions are positive integers."""
        if v <= 0:
            raise ValueError(f"Canvas {info.field_name} must be positive; got {v}")
        return v

    @field_validator("subject_isolation_method")
    @classmethod
    def validate_isolation_method(cls, v: str) -> str:
        """Validate subject isolation method against supported algorithms."""
        allowed = {"grabcut", "watershed", "threshold", "contour"}
        if v not in allowed:
            raise ValueError(
                f"subject_isolation_method must be one of: {', '.join(sorted(allowed))}"
            )
        return v

    @field_validator("edge_detection_method")
    @classmethod
    def validate_edge_method(cls, v: str) -> str:
        """Validate edge detection method against supported algorithms."""
        allowed = {"canny_auto", "canny_manual", "sobel", "laplacian"}
        if v not in allowed:
            raise ValueError(
                f"edge_detection_method must be one of: {', '.join(sorted(allowed))}"
            )
        return v

    @field_validator("composition_algorithm")
    @classmethod
    def validate_composition_algorithm(cls, v: str) -> str:
        """Validate composition algorithm against supported methods."""
        allowed = {"collision_avoidance", "grid", "semantic", "random"}
        if v not in allowed:
            raise ValueError(
                f"composition_algorithm must be one of: {', '.join(sorted(allowed))}"
            )
        return v

    @field_validator("colormaps")
    @classmethod
    def validate_colormaps(cls, v: list[str]) -> list[str]:
        """Ensure at least some colormaps are available."""
        if not v:
            raise ValueError("At least one colormap must be specified")

        # Remove any empty strings or None values
        clean_colormaps = [cm for cm in v if cm and cm.strip()]
        if not clean_colormaps:
            raise ValueError("All colormaps appear to be empty or invalid")

        return clean_colormaps

    @model_validator(mode="after")
    def validate_cross_field_constraints(self) -> "Settings":
        """Validate constraints that span multiple fields."""

        # Ensure max resolution > min resolution
        if self.max_image_resolution <= self.min_image_resolution:
            raise ValueError(
                f"max_image_resolution ({self.max_image_resolution}) must be larger than "
                f"min_image_resolution ({self.min_image_resolution})"
            )

        # Ensure reasonable canvas aspect ratio
        aspect_ratio = self.canvas_width / self.canvas_height
        if not (0.5 <= aspect_ratio <= 3.0):
            raise ValueError(
                f"Canvas aspect ratio {aspect_ratio:.2f} is extreme. "
                "Keep between 0.5 and 3.0 for best visual results."
            )

        # Validate keyword extraction parameters
        if self.n_keywords > 50 and self.images_per_keyword > 5:
            # This would result in potentially > 250 image requests
            raise ValueError(
                f"Combination of n_keywords ({self.n_keywords}) and "
                f"images_per_keyword ({self.images_per_keyword}) may cause "
                "excessive API usage. Reduce one or both values."
            )

        return self

    model_config = {
        "env_prefix": "COLLAGE_",
        "case_sensitive": False,
        "validate_assignment": True,
        "extra": "forbid",  # Prevent typos in environment variables
        "str_strip_whitespace": True,  # Auto-strip string values
        "validate_default": True,  # Validate default values too
    }


# ---------------------------------------------------------------------------
# Module-level singleton. Import this symbol everywhere configuration is needed.
# ---------------------------------------------------------------------------
default_config = Settings()
