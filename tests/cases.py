"""Plain fixture helpers. Shapes are built in meters, then converted to lon/lat."""

import math

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import Polygon

# Meters per degree of latitude (approx). Good enough for small test shapes.
M_PER_DEG = 111_320.0


def square(x, y, size=10.0):
    """A square with lower-left corner (x, y), in meters."""
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


def grid_of_squares(rows, cols, size=10.0, gap=5.0):
    """rows x cols squares in meters, `gap` meters apart edge to edge."""
    step = size + gap
    return [square(c * step, r * step, size) for r in range(rows) for c in range(cols)]


def meters_to_lonlat(geom, lon0=-105.0, lat0=40.0):
    """Turn a geometry in meters (origin at lon0, lat0) into EPSG:4326 degrees."""
    m_per_deg_lon = M_PER_DEG * math.cos(math.radians(lat0))
    scale = np.array([1 / m_per_deg_lon, 1 / M_PER_DEG])
    return shapely.transform(geom, lambda xy: np.array([lon0, lat0]) + xy * scale)


def make_gdf(geoms_m, keys=None):
    """GeoDataFrame in EPSG:4326 from meter geometries, with a `key` column."""
    keys = keys if keys is not None else ["a"] * len(geoms_m)
    geoms = [meters_to_lonlat(g) for g in geoms_m]
    return gpd.GeoDataFrame({"key": keys}, geometry=geoms, crs="EPSG:4326")
