"""Check and repair input geometries, and set `geom_status` (ok / repaired / empty)."""

import shapely
from shapely.geometry import MultiPolygon, Polygon

POLYGONAL = {"Polygon", "MultiPolygon"}
POLYGON_TYPES = POLYGONAL | {"GeometryCollection"}


def _polygon_parts(geom):
    """Keep only the polygon parts of a geometry; an empty polygon if there are none."""
    polys = []
    for part in shapely.get_parts(geom):
        if part.geom_type == "Polygon":
            polys.append(part)
        elif part.geom_type == "MultiPolygon":
            polys.extend(part.geoms)
    if not polys:
        return Polygon()
    return polys[0] if len(polys) == 1 else MultiPolygon(polys)


def _check_geometry_types(geoms):
    bad = [
        i
        for i, g in enumerate(geoms)
        if g is not None and not g.is_empty and g.geom_type not in POLYGON_TYPES
    ]
    if bad:
        rows = ", ".join(str(i) for i in bad)
        raise ValueError(f"Only polygons are allowed. Non-polygon rows (0-based): {rows}")


def _validate_one(g):
    """Return (geometry, status) for one geometry."""
    if g is None or g.is_empty:
        return Polygon(), "empty"
    status = "ok"
    if not g.is_valid:
        g = shapely.make_valid(g)
        status = "repaired"
    if g.geom_type == "GeometryCollection":
        if any(p.geom_type not in POLYGONAL for p in shapely.get_parts(g)):
            status = "repaired"  # lines or points were stripped
        g = _polygon_parts(g)
    if g.is_empty:
        return g, "empty"
    return g, status


def validate_geometries(gdf):
    """Return a copy of `gdf` with repaired geometry and a `geom_status` column.

    Raises ValueError for a missing CRS or for point/line rows (lists row numbers).
    Empty/null rows are kept and marked `empty`.
    """
    if gdf.crs is None:
        raise ValueError("Input has no CRS.")
    geoms = list(gdf.geometry)
    _check_geometry_types(geoms)

    results = [_validate_one(g) for g in geoms]
    out = gdf.copy()
    out["geometry"] = [g for g, _ in results]
    out["geom_status"] = [s for _, s in results]
    return out
