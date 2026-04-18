# domain/services/composition.py
#
# CompositionService — Domain Service
#
# Lays out a set of subject images on a canvas without overlap, then
# composites them over a wordcloud background. Returns the finished collage
# as a numpy array.
#
# Classification: Domain Service
#   - Encapsulates the layout and blending rules that define what a valid
#     collage composition looks like.
#   - Accepts and returns numpy arrays and domain value objects (Canvas,
#     Rectangle, Keyword). No file paths, no HTTP, no DB.
#   - cv2, numpy, and wordcloud are computation libraries used as
#     pure functions here — they are not infrastructure adapters.
#
# Replaces: the layout/blending portions of app/computer_vision/collage_generator.py
# The I/O portions of CollageGenerator (image fetching, disk writes) have been
# moved to their correct layers (IReferenceImageSource, ICollageStorage).

from __future__ import annotations

from random import choice, randint
from typing import List, Tuple

import cv2
import numpy as np
from wordcloud import WordCloud

from collage_maker.domain.model.canvas import Canvas, Rectangle
from collage_maker.domain.model.keyword import Keyword

# Maximum placement attempts per object before giving up and discarding it.
_PLACEMENT_ATTEMPT_CAP = 1000


class CompositionService:
    """
    Composes a list of RGBA subject images onto a word-cloud background.

    Usage:
        service = CompositionService(canvas, colormaps, max_word_font_size)
        collage_array = service.compose(subjects, keywords)
    """

    def __init__(
        self,
        canvas: Canvas,
        colormaps: List[str],
        max_word_font_size: int = 175,
    ) -> None:
        self._canvas = canvas
        self._colormaps = colormaps
        self._max_word_font_size = max_word_font_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(
        self,
        subjects: List[np.ndarray],
        keywords: List[Keyword],
    ) -> np.ndarray:
        """
        Place each subject image on the canvas without overlap, render a
        word-cloud background from the keywords, then re-draw the subjects
        on top. Returns the finished BGR image as a numpy array.
        """
        background = self._blank_canvas()
        placed, rectangles = self._place_subjects(subjects, background)

        # First pass: draw subjects to create the mask that shapes the wordcloud
        mask_canvas = background.copy()
        self._draw_subjects(mask_canvas, placed, rectangles)

        # Render the wordcloud using the subject silhouettes as a mask
        background = self._render_wordcloud(mask_canvas, keywords)

        # Second pass: draw subjects over the wordcloud background
        self._draw_subjects(background, placed, rectangles)

        return background

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _blank_canvas(self) -> np.ndarray:
        return np.zeros((self._canvas.height, self._canvas.width, 4), dtype=np.uint8)

    def _place_subjects(
        self,
        subjects: List[np.ndarray],
        background: np.ndarray,
    ) -> Tuple[List[np.ndarray], List[Rectangle]]:
        H, W = background.shape[:2]
        placed: List[np.ndarray] = []
        rectangles: List[Rectangle] = []

        for i, subject in enumerate(subjects):
            h, w = subject.shape[:2]
            if w > W or h > H:
                continue  # subject larger than canvas — discard silently

            rect = Rectangle.from_origin_and_size(
                randint(0, W - w), randint(0, H - h), w, h
            )
            attempts = 0
            while self._has_collisions(rect, rectangles):
                rect.move_to(randint(0, W - w), randint(0, H - h))
                attempts += 1
                if attempts > _PLACEMENT_ATTEMPT_CAP:
                    rect = None
                    break

            if rect is not None:
                placed.append(subject)
                rectangles.append(rect)

        return placed, rectangles

    @staticmethod
    def _has_collisions(rect: Rectangle, others: List[Rectangle]) -> bool:
        return any(rect.collides_with(other) for other in others)

    @staticmethod
    def _draw_subjects(
        background: np.ndarray,
        subjects: List[np.ndarray],
        rectangles: List[Rectangle],
    ) -> None:
        for rect, subject in zip(rectangles, subjects):
            x1, y1, x2, y2 = rect.x1, rect.y1, rect.x2, rect.y2
            try:
                alpha_s = subject[:, :, 3] / 255.0
                alpha_l = 1.0 - alpha_s
                for c in range(3):
                    background[y1:y2, x1:x2, c] = (
                        alpha_s * subject[:, :, c]
                        + alpha_l * background[y1:y2, x1:x2, c]
                    )
            except ValueError, IndexError:
                # Mismatched shapes can occur when subjects are near the edge;
                # skip rather than crash.
                continue

    def _render_wordcloud(
        self,
        mask: np.ndarray,
        keywords: List[Keyword],
    ) -> np.ndarray:
        colormap = choice(self._colormaps)
        word_string = " ".join(kw.text for kw in keywords)
        wc = WordCloud(
            width=self._canvas.width,
            height=self._canvas.height,
            colormap=colormap,
            background_color=(
                randint(0, 255),
                randint(0, 255),
                randint(0, 255),
            ),
            max_font_size=self._max_word_font_size,
            mask=mask,
        ).generate(word_string)
        return cv2.cvtColor(np.array(wc), cv2.COLOR_RGB2BGR)
