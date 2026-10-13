import pytest
from shapely import affinity
from shapely.geometry import Polygon, box

from bap.boundary import build_boundary

EPS = 10.0
GRID = [box(0, 0, 50, 50), box(60, 0, 110, 50), box(0, 60, 50, 110), box(60, 60, 110, 110)]


def test_square_corners_for_a_grid_with_small_gaps():
    (part,) = build_boundary(GRID, EPS)

    assert part["geometry"].equals(box(0, 0, 110, 110))
    assert part["members"] == [0, 1, 2, 3]
    assert part["polygon_count"] == 4
    assert part["area"] == pytest.approx(110 * 110)


def test_rotated_group_still_has_square_corners():
    rotated = [affinity.rotate(g, 37, origin=(0, 0)) for g in GRID]

    (part,) = build_boundary(rotated, EPS)

    rect = part["geometry"].minimum_rotated_rectangle
    assert part["geometry"].symmetric_difference(rect).area < 1e-6
    assert part["area"] == pytest.approx(110 * 110)


def test_notch_under_two_epsilon_is_filled():
    # U shape: notch is 15 wide (< 2 * 10), 70 deep.
    geoms = [box(0, 0, 50, 100), box(65, 0, 115, 100), box(0, 0, 115, 30)]

    (part,) = build_boundary(geoms, EPS)

    assert part["geometry"].equals(box(0, 0, 115, 100))


def test_hole_wider_than_two_epsilon_is_kept():
    # Ring of four rectangles around a 40 x 40 hole.
    geoms = [box(0, 0, 100, 30), box(0, 70, 100, 100), box(0, 30, 30, 70), box(70, 30, 100, 70)]

    (part,) = build_boundary(geoms, EPS)

    assert len(part["geometry"].interiors) == 1
    assert Polygon(part["geometry"].interiors[0]).area == pytest.approx(40 * 40)


def test_disjoint_pieces_become_separate_polygon_parts():
    geoms = [box(0, 0, 50, 50), box(52, 0, 100, 50), box(500, 0, 550, 50), box(552, 0, 600, 50)]

    parts = build_boundary(geoms, EPS)

    assert len(parts) == 2
    assert all(isinstance(p["geometry"], Polygon) for p in parts)
    assert [p["members"] for p in parts] == [[0, 1], [2, 3]]
    assert [p["polygon_count"] for p in parts] == [2, 2]


def test_part_order_does_not_depend_on_input_order():
    geoms = [box(500, 0, 550, 50), box(0, 0, 50, 50)]

    parts = build_boundary(geoms, EPS)

    assert [p["geometry"].bounds[0] for p in parts] == [0, 500]
    assert [p["members"] for p in parts] == [[1], [0]]


def test_tightness_is_underlying_area_over_boundary_area():
    # Two 50 x 50 squares 15 apart: the bridge adds 15 x 50.
    geoms = [box(0, 0, 50, 50), box(65, 0, 115, 50)]

    (part,) = build_boundary(geoms, EPS)

    assert part["tightness"] == pytest.approx(5000 / (115 * 50))


def test_tightness_counts_overlaps_once():
    geoms = [box(0, 0, 50, 50), box(0, 0, 50, 50), box(25, 0, 75, 50)]

    (part,) = build_boundary(geoms, EPS)

    assert part["tightness"] == pytest.approx(1.0)
    assert part["polygon_count"] == 3


def test_empty_input_gives_no_parts():
    assert build_boundary([], EPS) == []
