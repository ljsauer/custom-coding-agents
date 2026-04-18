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

import logging

import cv2
import imutils
import numpy as np

logger = logging.getLogger(__name__)


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
        try:
            # Validate input image
            if image is None or image.size == 0:
                logger.warning("Input image is None or empty")
                return None
                
            if len(image.shape) not in [2, 3]:
                logger.warning(f"Invalid image shape: {image.shape}")
                return None
                
            # Convert to color if grayscale
            if len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            elif image.shape[2] == 4:
                # Convert RGBA to BGR for processing
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
                
            logger.debug(f"Processing image of shape: {image.shape}")
            
            contour_mask = np.zeros(image.shape[:2], dtype="uint8")
            edge_image = self._detect_edges(image)
            
            if edge_image is None:
                logger.warning("Edge detection failed")
                return None
                
            contours = self._find_contours(edge_image)

            if not contours:
                logger.info("No contours found in image")
                return None

            # Find the largest contour
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            
            # Validate contour size (should be substantial part of image)
            image_area = image.shape[0] * image.shape[1]
            area_ratio = area / image_area
            
            if area_ratio < 0.01:  # Less than 1% of image
                logger.info(f"Largest contour too small (area ratio: {area_ratio:.3f})")
                return None
                
            logger.debug(f"Found largest contour with area {area} ({area_ratio:.3f} of image)")
            
            cv2.drawContours(contour_mask, [largest], -1, (200, 200, 55), 3)

            poly = cv2.approxPolyDP(largest, 3, True)
            bounding_rect = list(cv2.boundingRect(poly))
            
            # Validate bounding rectangle
            if not self._validate_bounding_rect(bounding_rect, image.shape):
                logger.warning("Invalid bounding rectangle")
                return None

            return self._crop_subject(image, contour_mask, bounding_rect)
            
        except Exception as e:
            logger.error(f"Subject isolation failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_edges(image: np.ndarray) -> np.ndarray | None:
        """Apply automatic Canny edge detection using median-based thresholds."""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
                
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Automatic Canny thresholds based on median
            v = np.median(blurred)
            sigma = 0.33
            lower = int(max(0, (1.0 - sigma) * v))
            upper = int(min(255, (1.0 + sigma) * v))
            
            edges = cv2.Canny(blurred, lower, upper)
            
            logger.debug(f"Canny thresholds: {lower}, {upper}")
            return edges
            
        except Exception as e:
            logger.error(f"Edge detection failed: {e}")
            return None

    @staticmethod
    def _find_contours(edge_image: np.ndarray) -> list[np.ndarray]:
        """Find contours from edge image with error handling."""
        try:
            raw = cv2.findContours(edge_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(raw)
            
            # Filter out very small contours
            min_area = 100  # Minimum contour area
            filtered_contours = [c for c in contours if cv2.contourArea(c) >= min_area]
            
            logger.debug(f"Found {len(contours)} total contours, {len(filtered_contours)} after filtering")
            return filtered_contours
            
        except Exception as e:
            logger.error(f"Contour detection failed: {e}")
            return []
    
    @staticmethod
    def _validate_bounding_rect(bounding_rect: list[int], image_shape: tuple) -> bool:
        """Validate that bounding rectangle is reasonable."""
        try:
            x, y, w, h = bounding_rect
            img_h, img_w = image_shape[:2]
            
            # Check bounds
            if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                logger.warning(f"Bounding rect ({x},{y},{w},{h}) exceeds image bounds ({img_w},{img_h})")
                return False
                
            # Check minimum size
            if w < 10 or h < 10:
                logger.warning(f"Bounding rect too small: {w}x{h}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Bounding rect validation failed: {e}")
            return False

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
        try:
            x, y, w, h = bounding_rect
            
            # GrabCut requires coordinates > 0
            if x == 0:
                bounding_rect[0] = 1
                x = 1
                w -= 1
            if y == 0:
                bounding_rect[1] = 1
                y = 1
                h -= 1
                
            # Validate adjusted rectangle
            if w <= 0 or h <= 0:
                logger.warning("Invalid adjusted bounding rectangle")
                return None

            bg_model = np.zeros((1, 65), dtype="float")
            fg_model = np.zeros((1, 65), dtype="float")
            image_copy = image.copy()

            # Initialize mask for GrabCut
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            
            try:
                mask, _, _ = cv2.grabCut(
                    image_copy,
                    mask,
                    tuple(bounding_rect),
                    bg_model,
                    fg_model,
                    iterCount=5,
                    mode=cv2.GC_INIT_WITH_RECT,
                )
            except cv2.error as e:
                logger.warning(f"GrabCut failed: {e}")
                # Fallback to simple thresholding
                gray = cv2.cvtColor(image_copy, cv2.COLOR_BGR2GRAY)
                _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                # Convert to GrabCut mask format
                mask = np.where(mask > 0, cv2.GC_FGD, cv2.GC_BGD).astype(np.uint8)

            # Create output mask
            output_mask = np.where(
                (mask == cv2.GC_BGD) | (mask == cv2.GC_PR_BGD), 0, 1
            ).astype("uint8") * 255

            # Apply mask to get the object
            obj = cv2.bitwise_and(image_copy, image_copy, mask=output_mask)
            
            # Create alpha channel from the mask
            grey = cv2.cvtColor(obj, cv2.COLOR_BGR2GRAY)
            _, alpha = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY)
            
            # Combine BGR channels with alpha
            b, g, r = cv2.split(obj)
            rgba = cv2.merge([b, g, r, alpha])

            # Crop to bounding rectangle
            cropped = rgba[y : y + h, x : x + w, :]
            
            # Validate cropped result
            if cropped is None or cropped.size == 0:
                logger.warning("Cropped result is empty")
                return None
                
            # Check if alpha channel has any non-zero values
            if np.sum(cropped[:, :, 3]) == 0:
                logger.warning("Alpha channel is completely transparent")
                return None
                
            logger.debug(f"Successfully isolated subject of size: {cropped.shape}")
            return cropped
            
        except Exception as e:
            logger.error(f"Subject cropping failed: {e}")
            return None
