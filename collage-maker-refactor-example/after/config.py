"""
Pure configuration values using Pydantic BaseSettings.

This provides environment variable support, validation, and type safety.
Configuration can be overridden via environment variables prefixed with "COLLAGE_".

Directory bootstrapping remains the responsibility of main.py (the composition
root), executed once at startup, not at import time.
"""

from __future__ import annotations

import os
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """
    Application configuration with environment variable support.
    
    Environment variables should be prefixed with "COLLAGE_", e.g.:
    COLLAGE_DATABASE_PATH=/custom/path/db.sqlite
    COLLAGE_N_KEYWORDS=30
    """
    
    # -----------------------------------------------------------------------
    # Filesystem paths
    # -----------------------------------------------------------------------
    collage_dir: str = Field(
        default_factory=lambda: os.path.join(os.getcwd(), "static"),
        description="Directory for storing rendered collage images"
    )
    download_dir: str = Field(
        default_factory=lambda: os.path.join(os.getcwd(), "downloads"),
        description="Directory for temporary download files"
    )
    database_path: str = Field(
        default_factory=lambda: os.path.join(os.getcwd(), "database.sqlite"),
        description="Path to SQLite database file"
    )

    # -----------------------------------------------------------------------
    # Collage composition parameters
    # -----------------------------------------------------------------------
    n_keywords: int = Field(
        default=25,
        description="Number of keywords to extract from source text",
        ge=1,
        le=100
    )
    images_per_keyword: int = Field(
        default=4,
        description="Number of images to fetch per keyword",
        ge=1,
        le=10
    )
    canvas_width: int = Field(
        default=1280,
        description="Canvas width in pixels",
        ge=100
    )
    canvas_height: int = Field(
        default=960,
        description="Canvas height in pixels", 
        ge=100
    )
    max_word_font_size: int = Field(
        default=175,
        description="Maximum font size for wordcloud text",
        ge=10,
        le=500
    )

    # -----------------------------------------------------------------------
    # NLP — domain-specific noise words added on top of NLTK's English list
    # -----------------------------------------------------------------------
    extra_stopwords: list[str] = Field(
        default_factory=lambda: [
            "said", "might", "towards", "found", "must", "things", "last",
            "make", "upon", "shall", "gutenberg", "many", "with", "without",
            "like", "project", "thee", "thou", "thus", "x80", "x9d", "x9ci", "xe2",
        ],
        description="Additional stopwords for keyword extraction"
    )

    # -----------------------------------------------------------------------
    # Wordcloud colour maps
    # -----------------------------------------------------------------------
    colormaps: list[str] = Field(
        default_factory=lambda: [
            "Accent", "Blues", "BrBG", "BuGn", "BuPu", "CMRmap", "Dark2", "GnBu",
            "Greens", "Greys", "OrRd", "Oranges", "PRGn", "Paired", "Pastel1",
            "Pastel2", "PiYG", "PuBu", "PuBuGn", "PuOr", "PuRd", "Purples",
            "RdBu", "RdGy", "RdPu", "RdYlBu", "RdYlGn", "Reds", "Set1", "Set2",
            "Set3", "Spectral", "Wistia", "YlGn", "YlGnBu", "YlOrBr", "YlOrRd",
            "afmhot", "autumn", "bone", "cool", "coolwarm", "copper", "cubehelix",
            "hot", "inferno", "jet", "magma", "ocean", "pink", "plasma", "rainbow",
            "seismic", "spring", "summer", "tab10", "tab20", "terrain", "turbo",
            "twilight", "viridis", "winter",
        ],
        description="Available matplotlib colormaps for wordcloud generation"
    )

    class Config:
        env_prefix = "COLLAGE_"
        case_sensitive = False


# ---------------------------------------------------------------------------
# Module-level singleton. Import this symbol everywhere configuration is needed.
# ---------------------------------------------------------------------------
default_config = Settings()
