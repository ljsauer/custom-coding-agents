"""
Pure configuration values. No side effects. No os.mkdir. No I/O of any kind.

This is a frozen dataclass — import it anywhere that needs configuration
without fear of triggering filesystem operations or database connections.

Directory bootstrapping is the responsibility of main.py (the composition
root), executed once at startup, not at import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Config:
    # -----------------------------------------------------------------------
    # Filesystem paths
    # -----------------------------------------------------------------------
    collage_dir: str = field(
        default_factory=lambda: os.path.join(os.getcwd(), "static")
    )
    download_dir: str = field(
        default_factory=lambda: os.path.join(os.getcwd(), "downloads")
    )
    database_path: str = field(
        default_factory=lambda: os.path.join(os.getcwd(), "database.sqlite")
    )

    # -----------------------------------------------------------------------
    # Collage composition parameters
    # -----------------------------------------------------------------------
    n_keywords: int = 25
    images_per_keyword: int = 4
    canvas_width: int = 1280
    canvas_height: int = 960
    max_word_font_size: int = 175

    # -----------------------------------------------------------------------
    # NLP — domain-specific noise words added on top of NLTK's English list
    # -----------------------------------------------------------------------
    extra_stopwords: list[str] = field(
        default_factory=lambda: [
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
            "x80",
            "x9d",
            "x9ci",
            "xe2",
        ]
    )

    # -----------------------------------------------------------------------
    # Wordcloud colour maps
    # -----------------------------------------------------------------------
    colormaps: list[str] = field(
        default_factory=lambda: [
            "Accent",
            "Blues",
            "BrBG",
            "BuGn",
            "BuPu",
            "CMRmap",
            "Dark2",
            "GnBu",
            "Greens",
            "Greys",
            "OrRd",
            "Oranges",
            "PRGn",
            "Paired",
            "Pastel1",
            "Pastel2",
            "PiYG",
            "PuBu",
            "PuBuGn",
            "PuOr",
            "PuRd",
            "Purples",
            "RdBu",
            "RdGy",
            "RdPu",
            "RdYlBu",
            "RdYlGn",
            "Reds",
            "Set1",
            "Set2",
            "Set3",
            "Spectral",
            "Wistia",
            "YlGn",
            "YlGnBu",
            "YlOrBr",
            "YlOrRd",
            "afmhot",
            "autumn",
            "bone",
            "cool",
            "coolwarm",
            "copper",
            "cubehelix",
            "hot",
            "inferno",
            "jet",
            "magma",
            "ocean",
            "pink",
            "plasma",
            "rainbow",
            "seismic",
            "spring",
            "summer",
            "tab10",
            "tab20",
            "terrain",
            "turbo",
            "twilight",
            "viridis",
            "winter",
        ]
    )


# ---------------------------------------------------------------------------
# Module-level singleton. Import this symbol everywhere configuration is needed.
# ---------------------------------------------------------------------------
default_config = Config()
