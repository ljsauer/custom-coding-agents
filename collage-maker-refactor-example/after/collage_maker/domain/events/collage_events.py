# domain/events/collage_events.py
#
# Domain Events
#
# A domain event is a record that something meaningful happened within the
# domain. Events are named in the past tense and carry only the data that
# describes what changed.
#
# These are plain frozen dataclasses — no framework, no serialisation logic.
# If an event bus or async queue is ever introduced, adapters in the
# infrastructure layer will be responsible for translating these into the
# appropriate wire format.

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from collage_maker.domain.model.keyword import Keyword


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True)
class CollageCreated:
    collage_id: str
    name: str
    keywords: List[Keyword]
    occurred_at: datetime = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", self.occurred_at or _utcnow())


@dataclass(frozen=True)
class CollageRenamed:
    collage_id: str
    old_name: str
    new_name: str
    occurred_at: datetime = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", self.occurred_at or _utcnow())


@dataclass(frozen=True)
class CollageDeleted:
    collage_id: str
    occurred_at: datetime = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", self.occurred_at or _utcnow())
