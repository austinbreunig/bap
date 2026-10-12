"""Shared helpers for the hand-run stress scripts (never collected by pytest, never in CI).

Each script builds a seeded GeoDataFrame in meters, then calls `run_bench`, which prints
timing and exits non-zero (via the return code) if a property fails.
"""

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely

from bap.bap import DEFAULT_MIN_TIGHTNESS, cluster_polygons

# The meters-to-lon/lat helper lives with the test fixtures; use that one copy.
sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from cases import meters_to_lonlat  # noqa: E402

MIN_TIGHTNESS = DEFAULT_MIN_TIGHTNESS


def parse_n(default_n, description):
    """Read the optional --n size flag (smaller sizes are for smoke tests)."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--n", type=int, default=default_n, help=f"size (default {default_n})")
    return parser.parse_args().n


def grid_boxes(x0, y0, rows, cols, rng, cell=30.0, gap=(1.0, 3.0)):
    """Parcels in a rows x cols grid of `cell` m squares, each 1-3 m smaller than its cell."""
    w = cell - rng.uniform(*gap, (rows, cols))
    h = cell - rng.uniform(*gap, (rows, cols))
    x = x0 + np.broadcast_to(np.arange(cols) * cell, (rows, cols))
    y = y0 + np.broadcast_to(np.arange(rows)[:, None] * cell, (rows, cols))
    return shapely.box(x.ravel(), y.ravel(), (x + w).ravel(), (y + h).ravel())


def make_gdf(geoms_m, keys):
    """EPSG:4326 GeoDataFrame from meter geometries, with `key` and unique `pid` columns."""
    geoms = meters_to_lonlat(np.asarray(geoms_m))
    pid = [f"P{i:07d}" for i in range(len(geoms))]
    return gpd.GeoDataFrame({"pid": pid, "key": keys}, geometry=geoms, crs="EPSG:4326")


def check_properties(gdf, out):
    """Return a list of failed-property messages (empty list means all passed)."""
    failures = []
    boundary = out[out["cluster_id"].notna()]
    outliers = out[out["cluster_id"].isna()]

    # No row lost: every input id shows up exactly once across all source_ids.
    seen = [s for ids in out["source_ids"] for s in ids]
    if len(seen) != len(gdf) or set(seen) != set(gdf["pid"]):
        failures.append(f"row lost or duplicated: {len(seen)} source ids for {len(gdf)} rows")

    # A cluster_id may span parts, but (cluster_id, part_id) is unique, and a cluster
    # never mixes key values.
    if boundary.duplicated(["cluster_id", "part_id"]).any():
        failures.append("duplicate (cluster_id, part_id)")
    if (boundary.groupby("cluster_id")["key"].nunique() > 1).any():
        failures.append("a cluster mixes key values")
    key_of = dict(zip(gdf["pid"], gdf["key"], strict=True))
    if any(key != key_of[ids[0]] for key, ids in zip(out["key"], out["source_ids"], strict=True)):
        failures.append("output key differs from a source row's key")

    if not (boundary.geom_type == "Polygon").all():
        failures.append("a boundary part is not a single Polygon")
    if len(boundary) and boundary["tightness"].min() < MIN_TIGHTNESS:
        failures.append(f"tightness {boundary['tightness'].min():.3f} < {MIN_TIGHTNESS}")

    # CRS round trip: same CRS, and an outlier comes back as its original polygon.
    if out.crs != gdf.crs:
        failures.append(f"CRS changed: {gdf.crs} -> {out.crs}")
    if len(outliers):
        original = gdf.set_index("pid").geometry.loc[[ids[0] for ids in outliers["source_ids"]]]
        same = shapely.equals_exact(original.to_numpy(), outliers.geometry.to_numpy(), 1e-6)
        if not same.all():
            failures.append(f"{int((~same).sum())} outliers differ from their input polygon")
    return failures


def run_bench(name, gdf, **kwargs):
    """Cluster `gdf`, print timing and summary, check properties. Returns an exit code."""
    print(f"{name}: {len(gdf):,} polygons, {gdf['key'].nunique():,} key values", flush=True)
    start = time.perf_counter()
    out, summary = cluster_polygons(gdf, "key", id_field="pid", **kwargs)
    elapsed = time.perf_counter() - start
    print(f"  time: {elapsed:.1f} s ({elapsed / 60:.1f} min)")
    print(f"  summary: {summary}")
    failures = check_properties(gdf, out)
    for message in failures:
        print(f"  FAIL: {message}")
    print("  properties: " + ("FAILED" if failures else "all passed"))
    return 1 if failures else 0
