# domain/model/keyword.py
#
# Keyword — Value Object
#
# A keyword is a meaningful word extracted from source text that drives both
# the wordcloud composition and the reference-image search.
#
# Value objects are immutable and defined entirely by their value.
# Two Keywords with the same text are equal regardless of object identity.

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Keyword:
    text: str

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError(
                "A keyword must contain at least one non-whitespace character."
            )
        # Normalise to lowercase so 'Apple' and 'apple' are the same keyword.
        object.__setattr__(self, "text", self.text.strip().lower())

    def __str__(self) -> str:
        return self.text
