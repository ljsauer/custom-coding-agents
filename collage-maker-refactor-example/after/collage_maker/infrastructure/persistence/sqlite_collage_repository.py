"""
SqliteCollageRepository — Infrastructure Adapter

Implements ICollageRepository using SQLAlchemy + SQLite.

This class is the translator between the domain world (Collage aggregates,
Keyword value objects) and the relational world (CollageRow ORM records).
No code outside this module should know that SQLite or SQLAlchemy is in use.

Dependency direction: this module imports from domain/ports and domain/model.
The domain never imports from here.
"""

from __future__ import annotations

from sqlalchemy import Engine

from collage_maker.domain.model.collage import Collage
from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.ports.collage_repository import ICollageRepository
from collage_maker.infrastructure.persistence.database import make_session
from collage_maker.infrastructure.persistence.orm_models import CollageRow


class SqliteCollageRepository(ICollageRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # ICollageRepository implementation
    # ------------------------------------------------------------------

    def save(self, collage: Collage) -> None:
        with make_session(self._engine) as session:
            row = session.get(CollageRow, collage.id)
            if row is None:
                row = CollageRow(
                    id=collage.id,
                    name=collage.name,
                    keywords_csv=self._keywords_to_csv(collage.keywords),
                    created_at=collage.created_at,
                    updated_at=collage.updated_at,
                )
                session.add(row)
            else:
                row.name = collage.name
                row.keywords_csv = self._keywords_to_csv(collage.keywords)
                row.updated_at = collage.updated_at
            session.commit()

    def find_by_id(self, collage_id: str) -> Collage | None:
        with make_session(self._engine) as session:
            row = session.get(CollageRow, collage_id)
            return self._to_domain(row) if row else None

    def find_all(self) -> list[Collage]:
        with make_session(self._engine) as session:
            rows = (
                session.query(CollageRow).order_by(CollageRow.created_at.desc()).all()
            )
            return [self._to_domain(row) for row in rows]

    def delete(self, collage_id: str) -> None:
        with make_session(self._engine) as session:
            row = session.get(CollageRow, collage_id)
            if row:
                session.delete(row)
                session.commit()

    # ------------------------------------------------------------------
    # Private mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: CollageRow) -> Collage:
        keywords = [
            Keyword(text=word) for word in row.keywords_csv.split(",") if word.strip()
        ]
        return Collage(
            id=row.id,
            name=row.name,
            keywords=keywords,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _keywords_to_csv(keywords: list[Keyword]) -> str:
        return ",".join(kw.text for kw in keywords)
