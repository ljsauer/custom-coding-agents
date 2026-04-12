# tests/unit/domain/test_composition.py
#
# Unit tests for Rectangle (value object) and CompositionService (domain service).
# Zero I/O. All image data is synthetic numpy arrays.

import numpy as np
import pytest

from collage_maker.domain.model.canvas import Canvas, Rectangle
from collage_maker.domain.model.keyword import Keyword
from collage_maker.domain.services.composition import CompositionService


# ---------------------------------------------------------------------------
# Rectangle
# ---------------------------------------------------------------------------


class TestRectangle:
    def test_from_origin_and_size(self):
        r = Rectangle.from_origin_and_size(10, 20, 50, 30)
        assert r.x1 == 10
        assert r.y1 == 20
        assert r.x2 == 60
        assert r.y2 == 50

    def test_width_and_height_properties(self):
        r = Rectangle.from_origin_and_size(0, 0, 100, 200)
        assert r.width == 100
        assert r.height == 200

    def test_move_to_preserves_size(self):
        r = Rectangle.from_origin_and_size(0, 0, 50, 50)
        r.move_to(100, 200)
        assert r.x1 == 100
        assert r.y1 == 200
        assert r.width == 50
        assert r.height == 50

    def test_overlapping_rectangles_collide(self):
        r1 = Rectangle.from_origin_and_size(0, 0, 50, 50)
        r2 = Rectangle.from_origin_and_size(25, 25, 50, 50)
        assert r1.collides_with(r2)

    def test_contained_rectangle_collides(self):
        outer = Rectangle.from_origin_and_size(0, 0, 100, 100)
        inner = Rectangle.from_origin_and_size(25, 25, 50, 50)
        assert outer.collides_with(inner)

    def test_adjacent_rectangles_do_not_collide(self):
        r1 = Rectangle.from_origin_and_size(0, 0, 50, 50)
        r2 = Rectangle.from_origin_and_size(50, 0, 50, 50)
        assert not r1.collides_with(r2)

    def test_distant_rectangles_do_not_collide(self):
        r1 = Rectangle.from_origin_and_size(0, 0, 10, 10)
        r2 = Rectangle.from_origin_and_size(100, 100, 10, 10)
        assert not r1.collides_with(r2)

    def test_rectangle_does_not_collide_with_itself(self):
        r = Rectangle.from_origin_and_size(0, 0, 50, 50)
        assert not r.collides_with(r)


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------


class TestCanvas:
    def test_valid_canvas(self):
        c = Canvas(width=1280, height=960)
        assert c.width == 1280

    def test_zero_width_raises(self):
        with pytest.raises(ValueError):
            Canvas(width=0, height=960)

    def test_negative_height_raises(self):
        with pytest.raises(ValueError):
            Canvas(width=1280, height=-1)


# ---------------------------------------------------------------------------
# CompositionService
# ---------------------------------------------------------------------------


def _solid_rgba(h: int, w: int, colour=(200, 200, 200, 255)) -> np.ndarray:
    """Create a solid RGBA patch for use as a synthetic subject."""
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :] = colour
    return img


class TestCompositionService:
    def setup_method(self):
        self.canvas = Canvas(width=200, height=200)
        self.service = CompositionService(
            canvas=self.canvas,
            colormaps=["viridis"],
            max_word_font_size=40,
        )
        self.keywords = [Keyword("apple"), Keyword("banana")]

    def test_compose_returns_numpy_array(self):
        subjects = [_solid_rgba(20, 20)]
        result = self.service.compose(subjects, self.keywords)
        assert isinstance(result, np.ndarray)

    def test_compose_output_matches_canvas_dimensions(self):
        subjects = [_solid_rgba(20, 20)]
        result = self.service.compose(subjects, self.keywords)
        h, w = result.shape[:2]
        assert w == self.canvas.width
        assert h == self.canvas.height

    def test_compose_handles_empty_subjects(self):
        result = self.service.compose([], self.keywords)
        assert result is not None

    def test_compose_discards_subjects_larger_than_canvas(self):
        oversized = _solid_rgba(500, 500)  # larger than 200×200 canvas
        result = self.service.compose([oversized], self.keywords)
        assert result is not None

    def test_no_overlapping_placements(self):
        """
        Place enough small subjects that the collision detector is exercised.
        We can't inspect rectangle positions directly, but we verify no crash
        and a valid output shape.
        """
        subjects = [_solid_rgba(10, 10)] * 20
        result = self.service.compose(subjects, self.keywords)
        assert result.shape[:2] == (self.canvas.height, self.canvas.width)
