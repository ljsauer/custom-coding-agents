"""
ORM Models — Infrastructure only

These are SQLAlchemy table definitions. They are NOT the domain Collage
class and must never be passed to the application or domain layers.

The repository (SqliteCollageRepository) is the only code that touches
these models. It maps between ORM rows and domain objects in both
directions so that the rest of the system never sees SQLAlchemy types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from collage_maker.infrastructure.persistence.database import Base

__all__ = ["CollageRow"]


def utc_now() -> datetime:
    """Generate current UTC datetime for default values."""
    return datetime.now(timezone.utc)


class CollageRow(Base):
    """
    Flat relational representation of a Collage aggregate.

    Keywords are stored as a comma-separated string. This is a deliberate
    simplification — for a production system consider a separate keywords
    table or a JSON column.

    Attributes:
        id: Primary key - unique identifier for the collage
        name: Human-readable name for the collage
        keywords_csv: Comma-separated list of keywords
        created_at: Timestamp when the collage was first created
        updated_at: Timestamp when the collage was last modified
    """

    __tablename__ = "collages"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    keywords_csv: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False,
        default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def __repr__(self) -> str:
        return f"<CollageRow id={self.id!r} name={self.name!r} created_at={self.created_at}>"
