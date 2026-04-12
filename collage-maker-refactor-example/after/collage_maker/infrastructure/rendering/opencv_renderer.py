# infrastructure/rendering/opencv_renderer.py
#
# OpenCVRenderer — Infrastructure Adapter (thin wrapper)
#
# Wires together the domain's CompositionService with a Canvas value object
# constructed from configuration values supplied at startup.
#
# Why is this in infrastructure rather than the domain?
# The CompositionService itself is pure domain logic (layout rules, blending
# algorithm). This wrapper exists only to translate flat config values
# (integers, a list of colour-map names) into the typed domain objects
# (Canvas) that CompositionService requires. It is the configuration-to-
# domain-object bridge — an adapter concern, not a domain concern.

from __future__ import annotations

from typing import List

from collage_maker.domain.model.canvas import Canvas
from collage_maker.domain.services.composition import CompositionService


class OpenCVRenderer:
    def __init__(
        self,
        canvas_width: int,
        canvas_height: int,
        max_word_font_size: int,
        colormaps: List[str],
    ) -> None:
        canvas = Canvas(width=canvas_width, height=canvas_height)
        self._service = CompositionService(
            canvas=canvas,
            colormaps=colormaps,
            max_word_font_size=max_word_font_size,
        )

    @property
    def composition_service(self) -> CompositionService:
        """Expose the domain service so the use case can receive it directly."""
        return self._service
