# infrastructure/persistence/orm_models.py
#
# ORM Models — Infrastructure only
#
# These are SQLAlchemy table definitions. They are NOT the domain Collage
# class and must never be passed to the application or domain layers.
#
# The repository (SqliteCollageRepository) is the only code that touches
# these models. It maps between ORM rows and domain objects in both
# directions so that the rest of the system never sees SQLAlchemy types.

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from collage_maker.infrastructure.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class CollageRow(Base):
    """
    Flat relational representation of a Collage aggregate.

    Keywords are stored as a comma-separated string. This is a deliberate
    simplification — for a production system consider a separate keywords
    table or a JSON column.
    """

    __tablename__ = "collages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    keywords_csv: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<CollageRow id={self.id!r} name={self.name!r}>"
