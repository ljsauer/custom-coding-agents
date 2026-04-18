"""
CreateCollageUseCase — Application Service

Orchestrates the end-to-end flow of producing a new collage from raw text:
  1. Extract keywords from the supplied text (domain service).
  2. Fetch reference images for each keyword (infrastructure port).
  3. Decode each image and isolate its foreground subject (domain service).
  4. Compose subjects onto a word-cloud canvas (domain service).
  5. Encode the result and persist the image (infrastructure port).
  6. Create and save the Collage aggregate (domain model + repository port).

Classification: Application Service
  - Holds NO business logic — every decision is delegated to domain services.
  - Holds NO infrastructure code — every I/O operation goes through a port.
  - Receives all dependencies via constructor injection so the use case can
    be exercised in tests with fakes and zero real I/O.
"""

from __future__ import annotations

import logging
import time
import cv2
import numpy as np

from collage_maker.domain.exceptions import CollageCreationError
from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.collage_repository import ICollageRepository
from collage_maker.domain.ports.collage_storage import ICollageStorage
from collage_maker.domain.ports.reference_image_source import (
    IReferenceImageSource,
    ImageQuality,
    ImageLicense
)
from collage_maker.domain.services.composition import CompositionService
from collage_maker.domain.services.keyword_extraction import KeywordExtractor
from collage_maker.domain.services.subject_isolation import SubjectIsolator

logger = logging.getLogger(__name__)


class CreateCollageUseCase:
    """Enhanced use case with timing, quality control, and better error handling."""
    
    def __init__(
        self,
        image_source: IReferenceImageSource,
        composition_service: CompositionService,
        storage: ICollageStorage,
        repository: ICollageRepository,
        keyword_extractor: KeywordExtractor,
    ) -> None:
        self._image_source = image_source
        self._composition_service = composition_service
        self._storage = storage
        self._repository = repository
        self._keyword_extractor = keyword_extractor
        self._subject_isolator = SubjectIsolator()

    def execute(self, text: str, collage_name: str | None = None) -> Collage:
        """
        Create and persist a new Collage from the supplied plain text.
        Returns the saved Collage aggregate.
        
        Args:
            text: Source text to extract keywords from
            collage_name: Optional custom name for the collage
            
        Returns:
            The created and saved Collage aggregate
            
        Raises:
            CollageCreationError: If creation fails at any stage
        """
        start_time = time.time()
        
        try:
            # 1. Extract keywords with validation
            logger.info("Extracting keywords from text (%d characters)", len(text))
            keywords = self._keyword_extractor.extract(text)
            
            if not keywords:
                raise CollageCreationError(
                    "No meaningful keywords could be extracted from the provided text. "
                    "Please ensure the text contains substantive content."
                )
            
            logger.info("Extracted %d keywords: %s", 
                       len(keywords), 
                       ", ".join(kw.text for kw in keywords[:5]) + "..." if len(keywords) > 5 else ", ".join(kw.text for kw in keywords))

            # 2. Fetch and process images
            logger.info("Fetching reference images for keywords")
            subjects = self._collect_subjects(keywords)
            
            if not subjects:
                raise CollageCreationError(
                    "No suitable images could be found and processed for the extracted keywords. "
                    "This may be due to network issues or content filtering."
                )
            
            logger.info("Successfully processed %d subject images", len(subjects))

            # 3. Compose the collage
            logger.info("Composing collage with %d subjects", len(subjects))
            rendered = self._composition_service.compose(subjects, keywords)

            # 4. Encode to JPEG bytes with quality validation
            success, buffer = cv2.imencode(
                ".jpg", 
                rendered, 
                [cv2.IMWRITE_JPEG_QUALITY, 90]  # High quality JPEG
            )
            if not success or buffer is None:
                raise CollageCreationError("Failed to encode collage image as JPEG.")
            
            image_bytes = buffer.tobytes()
            if len(image_bytes) < 1024:  # Sanity check
                raise CollageCreationError("Generated image is too small - composition may have failed.")

            # 5. Calculate processing metrics
            processing_time = time.time() - start_time
            logger.info("Collage processing completed in %.2f seconds", processing_time)

            # 6. Create aggregate with metadata
            collage = Collage.create(
                keywords=keywords,
                name=collage_name,
                source_text=text,
                processing_time=processing_time,
            )
            
            # Add image metadata
            collage.add_metadata(
                image_count=len(subjects),
                processing_time=processing_time
            )

            # 7. Persist to repository first (for referential integrity)
            self._repository.save(collage)
            logger.info("Saved collage to repository with ID: %s", collage.id)

            # 8. Persist image using the stable collage id as the storage key
            self._storage.save(collage.id, image_bytes)
            logger.info("Saved collage image to storage")

            return collage
            
        except CollageCreationError:
            # Re-raise domain errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors in domain exception
            logger.error("Unexpected error during collage creation: %s", e, exc_info=True)
            raise CollageCreationError(f"Collage creation failed due to an unexpected error: {e}")

    def _collect_subjects(self, keywords: list[Keyword]) -> list[np.ndarray]:
        """
        Collect and process subject images from keywords.
        
        Enhanced with better error handling and quality filtering.
        """
        subjects = []
        processed_images = 0
        skipped_images = 0
        
        for i, keyword in enumerate(keywords):
            logger.debug("Processing keyword %d/%d: '%s'", i + 1, len(keywords), keyword.text)
            
            try:
                # Fetch images with quality requirements
                image_results = self._image_source.fetch_for_keyword(
                    keyword,
                    min_quality=ImageQuality.MEDIUM,
                    required_license=ImageLicense.ANY,
                    max_results=3  # Limit per keyword to prevent overwhelming
                )
                
                if not image_results:
                    logger.debug("No images found for keyword '%s'", keyword.text)
                    continue
                
                # Process each image result
                for result in image_results:
                    processed_images += 1
                    
                    # Decode image
                    array = self._decode_image(result.data)
                    if array is None:
                        skipped_images += 1
                        continue
                    
                    # Isolate subject
                    subject = self._subject_isolator.isolate(array)
                    if subject is not None:
                        subjects.append(subject)
                        logger.debug("Successfully processed subject from '%s'", keyword.text)
                    else:
                        skipped_images += 1
                        logger.debug("Could not isolate subject from image for '%s'", keyword.text)
                        
            except Exception as e:
                logger.warning("Failed to process images for keyword '%s': %s", keyword.text, e)
                continue
        
        logger.info("Image processing complete: %d processed, %d subjects extracted, %d skipped", 
                   processed_images, len(subjects), skipped_images)
        
        return subjects

    @staticmethod
    def _decode_image(raw: bytes) -> np.ndarray | None:
        """
        Decode raw image bytes to a BGR numpy array with validation.
        
        Enhanced with better error handling and format validation.
        """
        if not raw or len(raw) < 100:  # Too small to be a valid image
            return None
            
        try:
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            # Basic validation of decoded image
            height, width = img.shape[:2]
            if height < 50 or width < 50:  # Too small
                return None
            
            if height > 2048 or width > 2048:  # Too large, resize
                scale = min(2048 / height, 2048 / width)
                new_height = int(height * scale)
                new_width = int(width * scale)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            return img
            
        except Exception as e:
            logger.debug("Failed to decode image: %s", e)
            return None
