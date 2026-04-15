# tests/unit/domain/test_collage.py
#
# Unit tests for the Collage aggregate root.
# Zero I/O. Zero framework. Pure domain logic.

import pytest
from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword


def _keywords(*words: str):
    return [Keyword(w) for w in words]


class TestCollageCreate:
    def test_create_assigns_id(self):
        collage = Collage.create(keywords=_keywords("apple", "banana"))
        assert collage.id is not None
        assert len(collage.id) > 0

    def test_create_derives_default_name_from_id(self):
        collage = Collage.create(keywords=_keywords("apple"))
        assert collage.name.startswith("collage-")

    def test_create_accepts_explicit_name(self):
        collage = Collage.create(keywords=_keywords("apple"), name="My Collage")
        assert collage.name == "My Collage"

    def test_create_raises_when_no_keywords(self):
        with pytest.raises(ValueError, match="at least one keyword"):
            Collage.create(keywords=[])

    def test_two_collages_have_different_ids(self):
        a = Collage.create(keywords=_keywords("apple"))
        b = Collage.create(keywords=_keywords("apple"))
        assert a.id != b.id


class TestCollageRename:
    def test_rename_updates_name(self):
        collage = Collage.create(keywords=_keywords("apple"))
        collage.rename("Summer 2024")
        assert collage.name == "Summer 2024"

    def test_rename_trims_whitespace(self):
        collage = Collage.create(keywords=_keywords("apple"))
        collage.rename("  padded  ")
        assert collage.name == "padded"

    def test_rename_updates_updated_at(self):
        collage = Collage.create(keywords=_keywords("apple"))
        before = collage.updated_at
        collage.rename("New Name")
        assert collage.updated_at >= before

    def test_rename_raises_on_blank_name(self):
        collage = Collage.create(keywords=_keywords("apple"))
        with pytest.raises(ValueError, match="must not be blank"):
            collage.rename("   ")

    def test_rename_raises_on_empty_string(self):
        collage = Collage.create(keywords=_keywords("apple"))
        with pytest.raises(ValueError):
            collage.rename("")


class TestCollageKeywords:
    def test_keyword_texts_returns_list_of_strings(self):
        collage = Collage.create(keywords=_keywords("apple", "banana", "cherry"))
        assert collage.keyword_texts() == ["apple", "banana", "cherry"]
