# tests/integration/test_sqlite_repository.py
#
# Integration tests for SqliteCollageRepository.
#
# These tests run against a real (in-memory) SQLite database via SQLAlchemy.
# They verify that the adapter correctly translates between domain objects and
# relational rows — something fakes cannot prove.
#
# Scope: infrastructure adapter only. No Flask, no use cases, no image I/O.

import pytest

from sqlalchemy import create_engine

from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword
from collage_maker.infrastructure.persistence.database import Base
from collage_maker.infrastructure.persistence.sqlite_collage_repository import (
    SqliteCollageRepository,
)


@pytest.fixture()
def repo() -> SqliteCollageRepository:
    """Fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return SqliteCollageRepository(engine)


def _make_collage(*words: str) -> Collage:
    return Collage.create(keywords=[Keyword(w) for w in words])


class TestSqliteCollageRepository:
    def test_save_and_find_by_id(self, repo):
        collage = _make_collage("apple", "banana")
        repo.save(collage)
        found = repo.find_by_id(collage.id)
        assert found is not None
        assert found.id == collage.id
        assert found.name == collage.name

    def test_keywords_round_trip(self, repo):
        collage = _make_collage("apple", "banana", "cherry")
        repo.save(collage)
        found = repo.find_by_id(collage.id)
        assert found.keyword_texts() == ["apple", "banana", "cherry"]

    def test_find_by_id_returns_none_when_missing(self, repo):
        assert repo.find_by_id("does-not-exist") is None

    def test_find_all_returns_all_saved_collages(self, repo):
        a = _make_collage("apple")
        b = _make_collage("banana")
        repo.save(a)
        repo.save(b)
        all_collages = repo.find_all()
        assert len(all_collages) == 2

    def test_find_all_orders_by_created_at_descending(self, repo):
        import time

        a = _make_collage("apple")
        repo.save(a)
        time.sleep(0.01)  # ensure distinct timestamps
        b = _make_collage("banana")
        repo.save(b)
        results = repo.find_all()
        assert results[0].id == b.id  # most recent first

    def test_save_updates_existing_collage(self, repo):
        collage = _make_collage("apple")
        repo.save(collage)
        collage.rename("Updated Name")
        repo.save(collage)
        found = repo.find_by_id(collage.id)
        assert found.name == "Updated Name"

    def test_delete_removes_collage(self, repo):
        collage = _make_collage("apple")
        repo.save(collage)
        repo.delete(collage.id)
        assert repo.find_by_id(collage.id) is None

    def test_delete_nonexistent_is_silent(self, repo):
        repo.delete("does-not-exist")  # should not raise

    def test_find_all_empty_when_nothing_saved(self, repo):
        assert repo.find_all() == []
