"""1M-polygon benchmark: city blocks of 100 parcels plus 5% stray parcels, 20 key values.

Run by hand: python scripts/bench_1m.py [--n 1000000]
"""

import sys

import numpy as np
import shapely
from bench_common import grid_boxes, make_gdf, parse_n, run_bench

SEED = 1
BLOCK = 100  # parcels per block (10 x 10)
SPACING = 700.0  # meters between block origins, well past 2 x 80 m


def build(n):
    rng = np.random.default_rng(SEED)
    n_blocks = int(n * 0.95) // BLOCK
    side = int(np.ceil(np.sqrt(n_blocks)))
    geoms, keys = [], []
    for b in range(n_blocks):
        geoms.append(grid_boxes((b % side) * SPACING, (b // side) * SPACING, 10, 10, rng))
        keys += [f"k{b % 20}"] * BLOCK
    n_strays = n - n_blocks * BLOCK
    x, y = rng.uniform(0, side * SPACING, (2, n_strays))
    geoms.append(shapely.box(x, y, x + 20, y + 20))
    keys += [f"k{k}" for k in rng.integers(0, 20, n_strays)]
    return make_gdf(np.concatenate(geoms), keys)


if __name__ == "__main__":
    sys.exit(run_bench("bench_1m", build(parse_n(1_000_000, __doc__))))
