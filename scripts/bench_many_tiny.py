"""Many tiny clusters: 500k clusters of exactly 3 parcels each (1.5M polygons).

Run by hand: python scripts/bench_many_tiny.py [--n 500000]   (n = number of clusters)
"""

import sys

import numpy as np
import shapely
from bench_common import make_gdf, parse_n, run_bench

SEED = 3
SPACING = 200.0  # meters between triples; the triple is ~34 m wide, so gaps are > 2 x 80 m


def build(n):
    rng = np.random.default_rng(SEED)
    side = int(np.ceil(np.sqrt(n)))
    i = np.arange(n)
    x0 = (i % side) * SPACING
    y0 = (i // side) * SPACING
    size = rng.uniform(8, 12, (n, 3))
    geoms = np.stack(
        [shapely.box(x0 + k * 12, y0, x0 + k * 12 + size[:, k], y0 + size[:, k]) for k in range(3)],
        axis=1,
    ).ravel()
    return make_gdf(geoms, ["a"] * len(geoms))


if __name__ == "__main__":
    sys.exit(run_bench("bench_many_tiny", build(parse_n(500_000, __doc__))))
