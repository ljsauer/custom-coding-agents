"""
CompositionService — Domain Service

Lays out a set of subject images on a canvas without overlap, then
composites them over a wordcloud background. Returns the finished collage
as a numpy array.

Classification: Domain Service
  - Encapsulates the layout and blending rules that define what a valid
    collage composition looks like.
  - Accepts and returns numpy arrays and domain value objects (Canvas,
    Rectangle, Keyword). No file paths, no HTTP, no DB.
  - cv2, numpy, and wordcloud are computation libraries used as
    pure functions here — they are not infrastructure adapters.

Replaces: the layout/blending portions of app/computer_vision/collage_generator.py
The I/O portions of CollageGenerator (image fetching, disk writes) have been
moved to their correct layers (IReferenceImageSource, ICollageStorage).
"""

from __future__ import annotations

import logging
from random import choice, randint

import cv2
import numpy as np
from wordcloud import WordCloud

from collage_maker.domain.model.canvas import Canvas, Rectangle
from collage_maker.domain.model.keyword import Keyword

# Maximum placement attempts per object before giving up and discarding it.
_PLACEMENT_ATTEMPT_CAP = 1000

logger = logging.getLogger(__name__)


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
        colormaps: list[str],
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
        subjects: list[np.ndarray],
        keywords: list[Keyword],
    ) -> np.ndarray:
        """
        Place each subject image on the canvas without overlap, render a
        word-cloud background from the keywords, then re-draw the subjects
        on top. Returns the finished BGR image as a numpy array.
        """
        logger.info(
            f"Starting composition with {len(subjects)} subjects and {len(keywords)} keywords"
        )
        
        background = self._blank_canvas()
        placed, rectangles = self._place_subjects(subjects, background)

        logger.info(f"Successfully placed {len(placed)} out of {len(subjects)} subjects")
        
        if not placed:
            logger.warning("No subjects could be placed on canvas - creating wordcloud-only collage")

        # First pass: draw subjects to create the mask that shapes the wordcloud
        mask_canvas = background.copy()
        self._draw_subjects(mask_canvas, placed, rectangles)

        # Render the wordcloud using the subject silhouettes as a mask
        try:
            background = self._render_wordcloud(mask_canvas, keywords)
        except Exception as e:
            logger.error(f"Failed to render wordcloud: {e}")
            # Continue with blank background if wordcloud fails
            background = self._blank_canvas()

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
        subjects: list[np.ndarray],
        background: np.ndarray,
    ) -> tuple[list[np.ndarray], list[Rectangle]]:
        H, W = background.shape[:2]
        placed: list[np.ndarray] = []
        rectangles: list[Rectangle] = []
        discarded_count = 0

        for i, subject in enumerate(subjects):
            if subject is None or subject.size == 0:
                logger.warning(f"Subject {i} is empty or invalid - skipping")
                discarded_count += 1
                continue
                
            h, w = subject.shape[:2]
            if w > W or h > H:
                logger.warning(f"Subject {i} ({w}x{h}) larger than canvas ({W}x{H}) - discarding")
                discarded_count += 1
                continue

            rect = Rectangle.from_origin_and_size(
                randint(0, W - w), randint(0, H - h), w, h
            )
            attempts = 0
            while self._has_collisions(rect, rectangles):
                rect.move_to(randint(0, W - w), randint(0, H - h))
                attempts += 1
                if attempts > _PLACEMENT_ATTEMPT_CAP:
                    logger.warning(f"Subject {i} could not be placed after {_PLACEMENT_ATTEMPT_CAP} attempts")
                    rect = None
                    discarded_count += 1
                    break

            if rect is not None:
                placed.append(subject)
                rectangles.append(rect)
                logger.debug(f"Placed subject {i} at {rect.x1},{rect.y1} after {attempts} attempts")

        if discarded_count > 0:
            logger.info(f"Discarded {discarded_count} subjects during placement")
            
        return placed, rectangles

    @staticmethod
    def _has_collisions(rect: Rectangle, others: list[Rectangle]) -> bool:
        return any(rect.collides_with(other) for other in others)

    @staticmethod
    def _draw_subjects(
        background: np.ndarray,
        subjects: list[np.ndarray],
        rectangles: list[Rectangle],
    ) -> None:
        """Draw subjects with robust error handling for alpha blending."""
        for i, (rect, subject) in enumerate(zip(rectangles, subjects)):
            try:
                x1, y1, x2, y2 = rect.x1, rect.y1, rect.x2, rect.y2
                
                # Validate bounds
                bg_h, bg_w = background.shape[:2]
                if x1 < 0 or y1 < 0 or x2 > bg_w or y2 > bg_h:
                    logger.warning(f"Subject {i} bounds ({x1},{y1},{x2},{y2}) exceed background ({bg_w},{bg_h})")
                    continue
                    
                # Validate subject dimensions match expected region
                expected_h, expected_w = y2 - y1, x2 - x1
                subject_h, subject_w = subject.shape[:2]
                
                if subject_h != expected_h or subject_w != expected_w:
                    logger.warning(
                        f"Subject {i} dimensions ({subject_w}x{subject_h}) don't match expected ({expected_w}x{expected_h})"
                    )
                    continue

                # Ensure subject has alpha channel
                if subject.shape[2] < 4:
                    logger.warning(f"Subject {i} missing alpha channel - skipping")
                    continue
                    
                alpha_s = subject[:, :, 3] / 255.0
                alpha_l = 1.0 - alpha_s
                
                # Alpha blend each color channel
                for c in range(3):
                    background[y1:y2, x1:x2, c] = (
                        alpha_s * subject[:, :, c]
                        + alpha_l * background[y1:y2, x1:x2, c]
                    ).astype(background.dtype)
                    
            except (ValueError, IndexError) as e:
                # Mismatched shapes can occur when subjects are near the edge;
                # skip rather than crash.
                logger.warning(f"Failed to blend subject {i}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error blending subject {i}: {e}")
                continue

    def _render_wordcloud(
        self,
        mask: np.ndarray,
        keywords: list[Keyword],
    ) -> np.ndarray:
        """Render wordcloud with better error handling and fallback options."""
        if not keywords:
            logger.warning("No keywords provided for wordcloud")
            return self._blank_canvas()
            
        try:
            colormap = choice(self._colormaps) if self._colormaps else "viridis"
            word_string = " ".join(kw.text for kw in keywords)
            
            if not word_string.strip():
                logger.warning("Empty keyword string - cannot generate wordcloud")
                return self._blank_canvas()
                
            # Create wordcloud mask from subjects (convert RGBA to grayscale)
            if mask.shape[2] == 4:
                # Use alpha channel as mask
                wc_mask = mask[:, :, 3]
            else:
                # Convert to grayscale
                wc_mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
                
            # Invert mask so subjects appear as holes
            wc_mask = 255 - wc_mask
            
            # Ensure mask has some free space
            if np.sum(wc_mask > 0) < 1000:  # Less than 1000 white pixels
                logger.warning("Mask too restrictive - using no mask")
                wc_mask = None
                
            wc = WordCloud(
                width=self._canvas.width,
                height=self._canvas.height,
                colormap=colormap,
                background_color=(
                    randint(50, 200),  # Avoid pure black/white
                    randint(50, 200),
                    randint(50, 200),
                ),
                max_font_size=self._max_word_font_size,
                min_font_size=10,
                mask=wc_mask,
                prefer_horizontal=0.9,
                relative_scaling=0.5,
                max_words=100,
            ).generate(word_string)
            
            # Convert RGB to BGR for OpenCV
            wordcloud_array = cv2.cvtColor(np.array(wc), cv2.COLOR_RGB2BGR)
            
            # Add alpha channel
            h, w = wordcloud_array.shape[:2]
            alpha = np.ones((h, w, 1), dtype=np.uint8) * 255
            return np.concatenate([wordcloud_array, alpha], axis=2)
            
        except Exception as e:
            logger.error(f"WordCloud generation failed: {e}")
            # Return a solid color background as fallback
            return self._create_fallback_background()
            
    def _create_fallback_background(self) -> np.ndarray:
        """Create a simple gradient background when wordcloud fails."""
        h, w = self._canvas.height, self._canvas.width
        
        # Create a simple vertical gradient
        background = np.zeros((h, w, 4), dtype=np.uint8)
        
        # Random color scheme
        color1 = [randint(100, 200), randint(100, 200), randint(100, 200)]
        color2 = [randint(50, 150), randint(50, 150), randint(50, 150)]
        
        for y in range(h):
            blend_factor = y / h
            for c in range(3):
                background[y, :, c] = int(
                    color1[c] * (1 - blend_factor) + color2[c] * blend_factor
                )
                
        # Full opacity
        background[:, :, 3] = 255
        
        return background
