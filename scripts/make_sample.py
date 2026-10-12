"""Write data/sample/sample.parquet: 50 seeded polygons (4 tight blocks + 10 strays).

Run from the repo root: python scripts/make_sample.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely import affinity

sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from cases import grid_of_squares, meters_to_lonlat, square  # noqa: E402


def main():
    rng = np.random.default_rng(42)
    geoms, zones = [], []
    # Four blocks of 10 squares (2 x 5, 1 m gaps), far apart. Two blocks per zone.
    for b in range(4):
        dx, dy = (b % 2) * 2000, (b // 2) * 2000
        for g in grid_of_squares(2, 5, gap=1.0):
            geoms.append(affinity.translate(g, dx, dy))
            zones.append("north" if b < 2 else "south")
    # Ten strays, far from the blocks and from each other.
    for i in range(10):
        x = 600 + i * 400 + rng.uniform(0, 50)
        geoms.append(square(x, 6000 + rng.uniform(0, 50)))
        zones.append("north" if i % 2 else "south")
    gdf = gpd.GeoDataFrame(
        {"parcel_id": [f"P{i:03d}" for i in range(len(geoms))], "zone": zones},
        geometry=[meters_to_lonlat(g) for g in geoms],
        crs="EPSG:4326",
    )
    out = Path(__file__).parent.parent / "data" / "sample" / "sample.parquet"
    gdf.to_parquet(out)
    print(f"Wrote {len(gdf)} polygons to {out}")


if __name__ == "__main__":
    main()
