"""
SubjectIsolator — Domain Service

Given a single image (as a numpy array), isolates the largest foreground
subject using modern learned segmentation (U2-Net via rembg) as the primary
method, with automatic Canny edge detection + GrabCut as a fallback.
Returns the cropped subject with an alpha channel, or None if no subject
could be located.

Classification: Domain Service
  - Encapsulates domain logic (what constitutes "the subject" of an image)
    that operates on a single value with no side effects.
  - Accepts and returns numpy arrays — plain data, not file paths or URLs.
  - Has no knowledge of where images came from or where results will go.
  - cv2/numpy/rembg are computation libraries, not infrastructure adapters.

Replaces: app/computer_vision/edge_detector.py  (EdgeDetector)
Renamed because "EdgeDetector" describes the CV technique used, not the
domain intent. "SubjectIsolator" names what the service accomplishes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

# Optional imports for modern segmentation
try:
    import rembg

    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False
    logger.info("rembg not available, using fallback segmentation only")

try:
    from PIL import Image

    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class SubjectIsolator:
    """
    Locates and extracts the largest foreground subject from an image.

    Uses modern U2-Net segmentation as the primary method with
    traditional Canny+GrabCut as a fallback for robustness.

    Usage:
        isolator = SubjectIsolator()
        subject = isolator.isolate(image_array)   # np.ndarray | None
    """

    def __init__(self) -> None:
        self._rembg_session: Any = None
        if _REMBG_AVAILABLE and _PIL_AVAILABLE:
            try:
                # Create a single session for the instance to share across calls
                self._rembg_session = rembg.new_session("u2net")
                logger.debug("Initialized U2-Net session for modern segmentation")
            except Exception as e:
                logger.warning("Failed to initialize U2-Net session: %s", e)
                self._rembg_session = None

    def isolate(self, image: np.ndarray) -> np.ndarray | None:
        """
        Return the largest subject as an RGBA numpy array with a transparent
        background, or None if no subject could be found.

        Tries modern U2-Net segmentation first, falls back to Canny+GrabCut
        if modern method is unavailable or fails.
        """
        if image is None or image.size == 0:
            return None

        # Validate input dimensions
        if len(image.shape) != 3 or image.shape[2] != 3:
            logger.debug("Input image must be a 3-channel BGR image")
            return None

        # Try modern segmentation first
        if self._rembg_session is not None:
            try:
                result = self._isolate_with_rembg(image)
                if result is not None:
                    logger.debug("Successfully isolated subject using U2-Net")
                    return result
                logger.debug("U2-Net segmentation returned no result, trying fallback")
            except Exception as e:
                logger.debug("U2-Net segmentation failed: %s, trying fallback", e)

        # Fallback to traditional method
        try:
            result = self._isolate_with_grabcut(image)
            if result is not None:
                logger.debug("Successfully isolated subject using GrabCut fallback")
            return result
        except Exception as e:
            logger.debug("GrabCut fallback also failed: %s", e)
            return None

    def _isolate_with_rembg(self, image: np.ndarray) -> np.ndarray | None:
        """
        Isolate subject using modern U2-Net segmentation via rembg.

        Args:
            image: Input BGR image as numpy array

        Returns:
            RGBA numpy array with transparent background, or None if failed
        """
        try:
            # rembg.remove expects PIL Image for best results
            # Convert BGR to RGB for PIL
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)

            # CRITICAL: session parameter is keyword-only
            result_pil = rembg.remove(pil_image, session=self._rembg_session)

            # Convert back to numpy array (RGBA)
            result_rgba = np.array(result_pil)

            # Check if we actually have a meaningful alpha channel
            alpha_channel = result_rgba[:, :, 3]
            if np.all(alpha_channel == 0):
                # Completely transparent - no subject found
                return None

            # Convert RGB to BGR while keeping alpha
            if result_rgba.shape[2] == 4:
                bgr_result = cv2.cvtColor(result_rgba[:, :, :3], cv2.COLOR_RGB2BGR)
                result_bgra = np.dstack([bgr_result, result_rgba[:, :, 3]])

                # Crop to the bounding box of non-transparent pixels
                return self._crop_to_subject(result_bgra)

            return None

        except Exception as e:
            logger.debug("rembg processing failed: %s", e)
            return None

    def _isolate_with_grabcut(self, image: np.ndarray) -> np.ndarray | None:
        """
        Fallback isolation using Canny edge detection + GrabCut segmentation.

        Args:
            image: Input BGR image as numpy array

        Returns:
            RGBA numpy array with transparent background, or None if failed
        """
        contour_mask = np.zeros(image.shape[:2], dtype="uint8")
        edge_image = self._detect_edges(image)
        contours = self._find_contours(edge_image)

        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        cv2.drawContours(contour_mask, [largest], -1, (200, 200, 55), 3)

        poly = cv2.approxPolyDP(largest, 3, True)
        bounding_rect = list(cv2.boundingRect(poly))

        return self._crop_subject_grabcut(image, contour_mask, bounding_rect)

    def _crop_to_subject(self, rgba_image: np.ndarray) -> np.ndarray | None:
        """
        Crop RGBA image to the bounding box of non-transparent pixels.

        Args:
            rgba_image: RGBA numpy array

        Returns:
            Cropped RGBA array, or None if no valid subject area found
        """
        alpha = rgba_image[:, :, 3]
        coords = cv2.findNonZero(alpha)

        if coords is None:
            return None

        x, y, w, h = cv2.boundingRect(coords)

        # Ensure we have a meaningful subject size
        if w < 10 or h < 10:
            return None

        return rgba_image[y : y + h, x : x + w]

    @staticmethod
    def _detect_edges(image: np.ndarray) -> np.ndarray:
        """Apply automatic Canny edge detection using median-based thresholds."""
        v = np.median(image)
        sigma = 0.75
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        return cv2.Canny(image, lower, upper)

    @staticmethod
    def _find_contours(edge_image: np.ndarray) -> list[np.ndarray]:
        """Find contours using modern OpenCV API."""
        # Use modern cv2.findContours API that returns (contours, hierarchy)
        contours, _ = cv2.findContours(
            edge_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )
        return contours

    @staticmethod
    def _crop_subject_grabcut(
        image: np.ndarray,
        contour_mask: np.ndarray,
        bounding_rect: list[int],
    ) -> np.ndarray | None:
        """
        Run GrabCut within the bounding rect, composite an alpha channel onto
        the isolated subject, and return the tightly-cropped RGBA patch.
        """
        x, y, w, h = bounding_rect
        # GrabCut requires coordinates > 0
        if x == 0:
            bounding_rect[0] = 1
        if y == 0:
            bounding_rect[1] = 1

        bg_model = np.zeros((1, 65), dtype="float")
        fg_model = np.zeros((1, 65), dtype="float")
        image_copy = image.copy()

        try:
            mask, _, _ = cv2.grabCut(
                image_copy,
                contour_mask * 0,
                tuple(bounding_rect),  # GrabCut expects tuple, not list
                bg_model,
                fg_model,
                iterCount=1,
                mode=cv2.GC_INIT_WITH_RECT,
            )
        except cv2.error:
            return None

        output_mask = (
            np.where(
                (mask == cv2.GC_BGD) | (mask == cv2.GC_PR_BGD),
                0,
                1,
            ).astype("uint8")
            * 255
        )

        obj = cv2.bitwise_and(image_copy, image_copy, mask=output_mask)
        grey = cv2.cvtColor(obj, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY)
        b, g, r = cv2.split(obj)
        rgba = cv2.merge([b, g, r, alpha])

        return rgba[y : y + h, x : x + w, :]
