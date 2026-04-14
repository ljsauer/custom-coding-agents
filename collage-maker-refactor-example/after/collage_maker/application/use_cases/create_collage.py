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

import cv2
import numpy as np

from collage_maker.domain.exceptions import CollageCreationError
from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.collage_repository import ICollageRepository
from collage_maker.domain.ports.collage_storage import ICollageStorage
from collage_maker.domain.ports.reference_image_source import IReferenceImageSource
from collage_maker.domain.services.composition import CompositionService
from collage_maker.domain.services.keyword_extraction import KeywordExtractor
from collage_maker.domain.services.subject_isolation import SubjectIsolator


class CreateCollageUseCase:
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

    # ------------------------------------------------------------------
    # Command
    # ------------------------------------------------------------------

    def execute(self, text: str) -> Collage:
        """
        Create and persist a new Collage from the supplied plain text.
        Returns the saved Collage aggregate.
        """
        # 1. Extract keywords
        keywords: list[Keyword] = self._keyword_extractor.extract(text)

        # 2. Fetch + isolate subject images
        subjects = self._collect_subjects(keywords)

        # 3. Compose
        rendered: np.ndarray = self._composition_service.compose(subjects, keywords)

        # 4. Encode to JPEG bytes
        success, buffer = cv2.imencode(".jpg", rendered)
        if not success:
            raise CollageCreationError("Failed to encode collage image as JPEG.")
        image_bytes: bytes = buffer.tobytes()

        # 5. Create aggregate and save
        collage = Collage.create(keywords=keywords)
        self._repository.save(collage)

        # 6. Persist image using the stable collage id as the storage key
        self._storage.save(collage.id, image_bytes)

        return collage

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_subjects(self, keywords: list[Keyword]) -> list[np.ndarray]:
        subjects = []
        for keyword in keywords:
            raw_images = self._image_source.fetch_for_keyword(keyword)
            for raw in raw_images:
                array = self._decode(raw)
                if array is None:
                    continue
                subject = self._subject_isolator.isolate(array)
                if subject is not None:
                    subjects.append(subject)
        return subjects

    @staticmethod
    def _decode(raw: bytes) -> np.ndarray | None:
        """Decode raw image bytes to a BGR numpy array, or None on failure."""
        try:
            arr = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img if img is not None else None
        except Exception:
            return None
