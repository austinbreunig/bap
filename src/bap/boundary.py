"""Wrap a cluster in a square-cornered boundary (mitre close).

Grow by epsilon, then shrink by epsilon, both with mitre joins. Gaps and notches
narrower than 2 x epsilon fill in; corners stay square at any rotation.
Geometries must be in a projected CRS so that epsilon is in meters.
"""

import shapely
from shapely import STRtree

# Very large, so even sharp corners are not cut off.
MITRE_LIMIT = 100.0


def _close(union, epsilon):
    grown = union.buffer(epsilon, join_style="mitre", mitre_limit=MITRE_LIMIT)
    return grown.buffer(-epsilon, join_style="mitre", mitre_limit=MITRE_LIMIT)


def build_boundary(geoms, epsilon):
    """Return the boundary parts for one cluster, as a list of dicts.

    Each part is one Polygon (holes kept as interior rings) with:
    geometry, members (indices into `geoms`), polygon_count, area, and
    tightness = area of the members' union (overlaps once) / boundary area.
    Parts are sorted by (min x, min y) so the order never depends on input order.
    """
    geoms = list(geoms)
    if not geoms:
        return []
    union = shapely.union_all(geoms)
    closed = _close(union, epsilon)
    polygons = [p for p in shapely.get_parts(closed) if p.geom_type == "Polygon" and p.area > 0]
    polygons.sort(key=lambda p: p.bounds[:2])

    # Each member is connected and inside the closed shape, so it sits in one part.
    member_idx, part_idx = STRtree(polygons).query(geoms, predicate="intersects")
    part_of = {}
    for m, p in zip(member_idx, part_idx, strict=True):
        part_of.setdefault(int(m), int(p))
    members = [[] for _ in polygons]
    for m in sorted(part_of):
        members[part_of[m]].append(m)

    return [
        {
            "geometry": polygon,
            "members": idx,
            "polygon_count": len(idx),
            "area": polygon.area,
            "tightness": union.intersection(polygon).area / polygon.area,
        }
        for polygon, idx in zip(polygons, members, strict=True)
    ]
