"""
Canvas — Pydantic Value Object   (the surface dimensions of a collage)
Rectangle — Dataclass (axis-aligned bounding box used during layout)

Canvas is a pure geometric concept with immutable dimensions.
Rectangle is intentionally mutable for the placement algorithm.
"""

from __future__ import annotations
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator, model_validator


class Canvas(BaseModel):
    """The rectangular surface onto which a collage is composed."""

    width: int = Field(..., description="Canvas width in pixels", gt=0, le=8192)
    height: int = Field(..., description="Canvas height in pixels", gt=0, le=8192)

    @field_validator('width', 'height')
    @classmethod
    def validate_reasonable_dimensions(cls, v: int, info) -> int:
        """Ensure canvas dimensions are reasonable for image processing."""
        if v < 256:
            raise ValueError(f"Canvas {info.field_name} should be at least 256px for quality results")
        if v > 4096:
            raise ValueError(f"Canvas {info.field_name} above 4096px may cause memory issues")
        return v

    @model_validator(mode='after')
    def validate_aspect_ratio(self) -> 'Canvas':
        """Ensure reasonable aspect ratios."""
        aspect_ratio = self.width / self.height
        if aspect_ratio < 0.25 or aspect_ratio > 4.0:
            raise ValueError(
                f"Extreme aspect ratio {aspect_ratio:.2f}. "
                "Keep between 0.25 and 4.0 for best visual results."
            )
        return self

    @property
    def aspect_ratio(self) -> float:
        """Calculate the width/height aspect ratio."""
        return self.width / self.height

    @property
    def area(self) -> int:
        """Calculate the total area in pixels."""
        return self.width * self.height

    def is_landscape(self) -> bool:
        """Check if canvas is wider than it is tall."""
        return self.width > self.height

    def is_portrait(self) -> bool:
        """Check if canvas is taller than it is wide."""
        return self.height > self.width

    def is_square(self) -> bool:
        """Check if canvas has equal width and height."""
        return self.width == self.height

    model_config = {"frozen": True}


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

    def __post_init__(self):
        """Validate rectangle coordinates."""
        if self.x2 <= self.x1:
            raise ValueError(f"Invalid rectangle: x2 ({self.x2}) must be > x1 ({self.x1})")
        if self.y2 <= self.y1:
            raise ValueError(f"Invalid rectangle: y2 ({self.y2}) must be > y1 ({self.y1})")

    @classmethod
    def from_origin_and_size(cls, x: int, y: int, w: int, h: int) -> Rectangle:
        """Create rectangle from top-left corner and dimensions."""
        if w <= 0 or h <= 0:
            raise ValueError(f"Rectangle dimensions must be positive: width={w}, height={h}")
        return cls(x1=x, y1=y, x2=x + w, y2=y + h)

    @classmethod
    def from_center_and_size(cls, cx: int, cy: int, w: int, h: int) -> Rectangle:
        """Create rectangle from center point and dimensions."""
        if w <= 0 or h <= 0:
            raise ValueError(f"Rectangle dimensions must be positive: width={w}, height={h}")
        half_w, half_h = w // 2, h // 2
        return cls(x1=cx - half_w, y1=cy - half_h, x2=cx + half_w, y2=cy + half_h)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        """Calculate the area of the rectangle."""
        return self.width * self.height

    @property
    def center(self) -> tuple[int, int]:
        """Get the center point of the rectangle."""
        return (self.x1 + self.width // 2, self.y1 + self.height // 2)

    def move_to(self, x: int, y: int) -> None:
        """Translate so the top-left corner is at (x, y), preserving size."""
        w, h = self.width, self.height
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def move_center_to(self, cx: int, cy: int) -> None:
        """Move rectangle so its center is at (cx, cy)."""
        half_w, half_h = self.width // 2, self.height // 2
        self.move_to(cx - half_w, cy - half_h)

    def collides_with(self, other: Rectangle) -> bool:
        """
        Return True if this rectangle overlaps with *other*.
        Rectangles that share only an edge are NOT colliding, allowing
        objects to be placed flush against one another.
        """
        if self is other:
            return False
        
        # Check for overlap (not just touching at edges)
        return (
            self.x2 > other.x1 and self.x1 < other.x2 and
            self.y2 > other.y1 and self.y1 < other.y2
        )

    def contains_point(self, x: int, y: int) -> bool:
        """Check if point (x, y) is inside this rectangle."""
        return self.x1 <= x < self.x2 and self.y1 <= y < self.y2

    def intersect(self, other: Rectangle) -> Rectangle | None:
        """Return the intersection rectangle, or None if no overlap."""
        if not self.collides_with(other):
            return None
        
        x1 = max(self.x1, other.x1)
        y1 = max(self.y1, other.y1)
        x2 = min(self.x2, other.x2)
        y2 = min(self.y2, other.y2)
        
        return Rectangle(x1, y1, x2, y2)

    def __repr__(self) -> str:
        return f"Rectangle({self.x1}, {self.y1}, {self.x2}, {self.y2})"
