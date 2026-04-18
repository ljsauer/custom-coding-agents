"""
OpenCVRenderer — Infrastructure Adapter (thin wrapper)

Wires together the domain's CompositionService with a Canvas value object
constructed from configuration values supplied at startup.

Why is this in infrastructure rather than the domain?
The CompositionService itself is pure domain logic (layout rules, blending
algorithm). This wrapper exists only to translate flat config values
(integers, a list of colour-map names) into the typed domain objects
(Canvas) that CompositionService requires. It is the configuration-to-
domain-object bridge — an adapter concern, not a domain concern.
"""

from __future__ import annotations

from collage_maker.domain.model.canvas import Canvas
from collage_maker.domain.services.composition import CompositionService

__all__ = ["OpenCVRenderer"]


class OpenCVRenderer:
    """
    Infrastructure adapter that bridges configuration to domain services.
    
    Converts flat configuration values into domain objects required by
    the CompositionService, acting as the configuration-to-domain bridge.
    
    Args:
        canvas_width: Width of the canvas in pixels
        canvas_height: Height of the canvas in pixels
        max_word_font_size: Maximum font size for text rendering
        colormaps: List of colormap names for image processing
    """
    
    def __init__(
        self,
        canvas_width: int,
        canvas_height: int,
        max_word_font_size: int,
        colormaps: list[str],
    ) -> None:
        canvas = Canvas(width=canvas_width, height=canvas_height)
        self._service = CompositionService(
            canvas=canvas,
            colormaps=colormaps,
            max_word_font_size=max_word_font_size,
        )

    @property
    def composition_service(self) -> CompositionService:
        """
        Expose the domain service so the use case can receive it directly.
        
        Returns:
            The configured composition service instance
        """
        return self._service
