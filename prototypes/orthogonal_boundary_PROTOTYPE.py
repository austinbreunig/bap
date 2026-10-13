"""PROTOTYPE (throwaway) for issue #3: morphological close with mitre joins.
Run: uv run --with shapely python prototypes/orthogonal_boundary_PROTOTYPE.py
"""
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

BIG = 100.0  # mitre_limit: big so corners stay sharp


def close(geom, dist):
    """Grow by dist, then shrink by the SAME dist. Input must be valid: union first."""
    assert geom.is_valid, "close() needs a valid input; unary_union the polygons first"
    grown = geom.buffer(dist, join_style="mitre", mitre_limit=BIG)
    out = grown.buffer(-dist, join_style="mitre", mitre_limit=BIG)
    assert out.is_valid, "close() produced an invalid geometry"
    return out


def report(name, geom, eps):
    union = unary_union(geom)  # a bare MultiPolygon of touching boxes is invalid
    out = close(union, eps)
    ratio = out.area / union.area
    print(f"\n== {name} (eps={eps})")
    print(f"  in : {union.geom_type}, area={union.area:.4f}, parts={len(getattr(union, 'geoms', [union]))}")
    print(f"  out: {out.geom_type}, area={out.area:.4f}, ratio={ratio:.4f}, "
          f"verts={len(out.exterior.coords) - 1 if out.geom_type == 'Polygon' else 'n/a'}")
    print(f"  holes in out: {len(out.interiors) if out.geom_type == 'Polygon' else 'n/a'}")
    print(f"  out == union (equals): {out.equals(union)}")
    return out, union


def main():
    # 1. 2x2 grid of adjacent squares
    grid = MultiPolygon([box(0, 0, 1, 1), box(1, 0, 2, 1), box(0, 1, 1, 2), box(1, 1, 2, 2)])
    out, union = report("1. 2x2 grid", grid, 0.1)
    assert out.geom_type == "Polygon"
    assert abs(out.area - 4.0) < 1e-9
    assert out.equals(box(0, 0, 2, 2)) and out.equals(union)

    # 2. gap smaller than 2*eps (gap 0.15, eps 0.1) and larger (gap 0.3)
    for gap in (0.15, 0.2, 0.3):
        two = MultiPolygon([box(0, 0, 1, 1), box(1 + gap, 0, 2 + gap, 1)])
        out, union = report(f"2. two squares, gap={gap}", two, 0.1)
        if out.geom_type == "Polygon":
            bridge = out.difference(union)
            print(f"  bridge: {bridge.geom_type}, area={bridge.area:.4f}, bounds={bridge.bounds}")
            # bridge is a rectangle gap wide, as tall as the squares' facing sides
            assert abs(bridge.area - gap * 1.0) < 1e-9
        else:
            assert abs(out.area - union.area) < 1e-9
    # staggered: facing sides only partly overlap -> what does the bridge look like?
    stag = MultiPolygon([box(0, 0, 1, 1), box(1.15, 0.5, 2.15, 1.5)])
    out, union = report("2b. staggered pair, gap=0.15", stag, 0.1)
    print("  out coords:", [(round(x, 3), round(y, 3)) for x, y in out.exterior.coords])

    # 3a. L shape with a notch: two boxes sharing an edge, notch 0.15 wide (< 2 eps) and 1 wide
    notch_small = MultiPolygon([box(0, 0, 1, 2), box(1.15, 0, 2.15, 2), box(0, 0, 2.15, 0.5)])
    report("3a. U-shape, narrow notch 0.15", notch_small, 0.1)
    notch_big = MultiPolygon([box(0, 0, 1, 2), box(2, 0, 3, 2), box(0, 0, 3, 0.5)])
    report("3a. U-shape, wide notch 1.0", notch_big, 0.1)
    ell = unary_union([box(0, 0, 2, 1), box(0, 0, 1, 2)])
    report("3a. plain L (concave corner)", ell, 0.1)

    # 3b. polygon with a hole (small hole 0.15, big hole 1.0)
    for h in (0.15, 1.0):
        c = 1.5
        holed = Polygon(box(0, 0, 3, 3).exterior.coords,
                        [box(c - h / 2, c - h / 2, c + h / 2, c + h / 2).exterior.coords])
        report(f"3b. square with hole size {h}", holed, 0.1)

    # 3c. rotated pair (45 deg), gap 0.15
    pair = MultiPolygon([box(0, 0, 1, 1), box(1.15, 0, 2.15, 1)])
    rot = affinity.rotate(pair, 45, origin=(0, 0))
    out, union = report("3c. rotated 45deg pair, gap=0.15", rot, 0.1)
    if out.geom_type == "Polygon":
        print("  rotated-back out coords:",
              [(round(x, 3), round(y, 3))
               for x, y in affinity.rotate(out, -45, origin=(0, 0)).exterior.coords])
        print("  is a rectangle (area == min rotated rect):",
              abs(out.area - out.minimum_rotated_rectangle.area) < 1e-9)


main()
