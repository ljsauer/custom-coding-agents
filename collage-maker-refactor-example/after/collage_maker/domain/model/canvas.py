# domain/model/canvas.py
#
# Canvas — Value Object   (the surface dimensions of a collage)
# Rectangle — Value Object (axis-aligned bounding box used during layout)
#
# These are pure geometric concepts belonging to the composition domain.
# They carry no I/O, no framework references, and no mutable global state.

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Canvas:
    """The rectangular surface onto which a collage is composed."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Canvas dimensions must be positive; got ({self.width}, {self.height})."
            )


@dataclass
class Rectangle:
    """
    Axis-aligned bounding box expressed as two corners:
      (x1, y1) — top-left
      (x2, y2) — bottom-right

    Intentionally mutable: the placement algorithm repositions rectangles
    iteratively before committing them to the final layout.
    """

    x1: int
    y1: int
    x2: int
    y2: int

    @classmethod
    def from_origin_and_size(cls, x: int, y: int, w: int, h: int) -> Rectangle:
        return cls(x1=x, y1=y, x2=x + w, y2=y + h)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def move_to(self, x: int, y: int) -> None:
        """Translate so the top-left corner is at (x, y), preserving size."""
        w, h = self.width, self.height
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def collides_with(self, other: Rectangle) -> bool:
        """
        Return True if this rectangle overlaps or fully contains *other*.
        Rectangles that share only an edge are NOT colliding, allowing
        objects to be placed flush against one another.
        """
        if self is other:
            return False
        overlap = (
            self.x2 > other.x1
            and self.x1 < other.x2
            and self.y2 > other.y1
            and self.y1 < other.y2
        )
        contains = (
            self.x1 >= other.x1
            and self.x2 <= other.x2
            and self.y1 >= other.y1
            and self.y2 <= other.y2
        )
        return overlap or contains
