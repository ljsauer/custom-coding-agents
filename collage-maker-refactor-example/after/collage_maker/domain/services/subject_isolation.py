"""
SubjectIsolator — Domain Service

Given a single image (as a numpy array), isolates the largest foreground
subject using automatic Canny edge detection followed by GrabCut
segmentation. Returns the cropped subject with an alpha channel, or None
if no subject could be located.

Classification: Domain Service
  - Encapsulates domain logic (what constitutes "the subject" of an image)
    that operates on a single value with no side effects.
  - Accepts and returns numpy arrays — plain data, not file paths or URLs.
  - Has no knowledge of where images came from or where results will go.
  - cv2/numpy are computation libraries, not infrastructure adapters.

Replaces: app/computer_vision/edge_detector.py  (EdgeDetector)
Renamed because "EdgeDetector" describes the CV technique used, not the
domain intent. "SubjectIsolator" names what the service accomplishes.
"""

from __future__ import annotations

import cv2
import imutils
import numpy as np


class SubjectIsolator:
    """
    Locates and extracts the largest foreground subject from an image.

    Usage:
        isolator = SubjectIsolator()
        subject = isolator.isolate(image_array)   # np.ndarray | None
    """

    def isolate(self, image: np.ndarray) -> np.ndarray | None:
        """
        Return the largest subject as an RGBA numpy array with a transparent
        background, or None if no subject could be found.
        """
        contour_mask = np.zeros(image.shape[:2], dtype="uint8")
        edge_image = self._detect_edges(image)
        contours = self._find_contours(edge_image)

        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        cv2.drawContours(contour_mask, largest, -1, (200, 200, 55), 3)

        poly = cv2.approxPolyDP(largest, 3, True)
        bounding_rect = list(cv2.boundingRect(poly))

        return self._crop_subject(image, contour_mask, bounding_rect)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
        raw = cv2.findContours(edge_image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        return imutils.grab_contours(raw)

    @staticmethod
    def _crop_subject(
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
                bounding_rect,
                bg_model,
                fg_model,
                iterCount=1,
                mode=cv2.GC_INIT_WITH_RECT,
            )
        except cv2.error:
            return None

        output_mask = (
            np.where((mask == cv2.GC_BGD) | (mask == cv2.GC_PR_BGD), 0, 1).astype(
                "uint8"
            )
            * 255
        )

        obj = cv2.bitwise_and(image_copy, image_copy, mask=output_mask)
        grey = cv2.cvtColor(obj, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY)
        b, g, r = cv2.split(obj)
        rgba = cv2.merge([b, g, r, alpha])

        return rgba[y : y + h, x : x + w, :]
