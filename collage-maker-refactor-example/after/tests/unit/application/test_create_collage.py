# tests/unit/application/test_create_collage.py
#
# Unit tests for CreateCollageUseCase.
#
# All infrastructure is replaced with fakes — zero network, zero disk, zero DB.
# This verifies that the use case correctly orchestrates its dependencies
# without testing any infrastructure implementation detail.

import pytest
from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.domain.model.canvas import Canvas
from collage_maker.domain.services.composition import CompositionService
from collage_maker.domain.services.keyword_extraction import KeywordExtractor

from tests.fakes.fake_collage_repository import FakeCollageRepository
from tests.fakes.fake_collage_storage import FakeCollageStorage
from tests.fakes.fake_image_source import FakeReferenceImageSource

_SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "The fox was very quick and the dog was very lazy. "
    "Foxes and dogs are animals that live in different habitats. "
    "Brown foxes are known for their quick movements. "
    "Lazy dogs prefer to sleep rather than jump."
)


def _make_use_case(images_per_keyword: int = 0) -> tuple:
    """Return (use_case, repo, storage, image_source) wired with fakes."""
    repo = FakeCollageRepository()
    storage = FakeCollageStorage()
    image_source = FakeReferenceImageSource(images_per_keyword=images_per_keyword)
    canvas = Canvas(width=200, height=200)
    composition_service = CompositionService(
        canvas=canvas,
        colormaps=["viridis"],
        max_word_font_size=40,
    )
    keyword_extractor = KeywordExtractor(n_keywords=5)
    use_case = CreateCollageUseCase(
        image_source=image_source,
        composition_service=composition_service,
        storage=storage,
        repository=repo,
        keyword_extractor=keyword_extractor,
    )
    return use_case, repo, storage, image_source


class TestCreateCollageUseCase:
    def test_returns_collage_with_id(self):
        use_case, *_ = _make_use_case()
        collage = use_case.execute(_SAMPLE_TEXT)
        assert collage.id is not None

    def test_collage_is_persisted_in_repository(self):
        use_case, repo, *_ = _make_use_case()
        collage = use_case.execute(_SAMPLE_TEXT)
        found = repo.find_by_id(collage.id)
        assert found is not None
        assert found.id == collage.id

    def test_collage_image_is_persisted_in_storage(self):
        use_case, _, storage, _ = _make_use_case()
        collage = use_case.execute(_SAMPLE_TEXT)
        assert storage.has(collage.id)

    def test_collage_has_keywords(self):
        use_case, *_ = _make_use_case()
        collage = use_case.execute(_SAMPLE_TEXT)
        assert len(collage.keywords) > 0

    def test_image_source_is_called_per_keyword(self):
        use_case, _, _, image_source = _make_use_case(images_per_keyword=1)
        collage = use_case.execute(_SAMPLE_TEXT)
        # One fetch call per extracted keyword
        assert len(image_source.calls) == len(collage.keywords)

    def test_each_keyword_fetched_once(self):
        use_case, _, _, image_source = _make_use_case(images_per_keyword=1)
        collage = use_case.execute(_SAMPLE_TEXT)
        keyword_texts = [kw.text for kw in collage.keywords]
        assert image_source.calls == keyword_texts

    def test_raises_on_empty_text(self):
        use_case, *_ = _make_use_case()
        # KeywordExtractor returns [] → Collage.create raises ValueError
        with pytest.raises(ValueError):
            use_case.execute("")


class TestRenameCollageUseCase:
    """Smoke test for rename — full suite in test_collage.py (domain layer)."""

    def test_rename_persists(self):
        from collage_maker.application.use_cases.rename_collage import (
            RenameCollageUseCase,
        )

        repo = FakeCollageRepository()
        use_case_create, *_ = _make_use_case()
        # Re-wire create to use the same repo
        use_case_create._repository = repo
        collage = use_case_create.execute(_SAMPLE_TEXT)

        rename_uc = RenameCollageUseCase(repository=repo)
        renamed = rename_uc.execute(collage.id, "My Renamed Collage")

        assert renamed.name == "My Renamed Collage"
        assert repo.find_by_id(collage.id).name == "My Renamed Collage"

    def test_rename_raises_on_missing_collage(self):
        from collage_maker.application.use_cases.rename_collage import (
            RenameCollageUseCase,
        )

        repo = FakeCollageRepository()
        rename_uc = RenameCollageUseCase(repository=repo)
        with pytest.raises(LookupError):
            rename_uc.execute("does-not-exist", "Any Name")


class TestDeleteCollageUseCase:
    def test_delete_removes_from_repo_and_storage(self):
        from collage_maker.application.use_cases.delete_collage import (
            DeleteCollageUseCase,
        )

        use_case_create, repo, storage, _ = _make_use_case()
        collage = use_case_create.execute(_SAMPLE_TEXT)

        delete_uc = DeleteCollageUseCase(repository=repo, storage=storage)
        delete_uc.execute(collage.id)

        assert repo.find_by_id(collage.id) is None
        assert not storage.has(collage.id)

    def test_delete_raises_on_missing_collage(self):
        from collage_maker.application.use_cases.delete_collage import (
            DeleteCollageUseCase,
        )

        repo = FakeCollageRepository()
        storage = FakeCollageStorage()
        delete_uc = DeleteCollageUseCase(repository=repo, storage=storage)
        with pytest.raises(LookupError):
            delete_uc.execute("does-not-exist")
