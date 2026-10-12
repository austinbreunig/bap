"""Many key values: 10k keys, 60 parcels each. Every block is drawn twice over the same
spot under two different keys, so keys must never mix.

Run by hand: python scripts/bench_many_keys.py [--n 10000]   (n = number of keys)
"""

import sys

import numpy as np
from bench_common import grid_boxes, make_gdf, parse_n, run_bench

SEED = 4
SPACING = 400.0


def build(n):
    rng = np.random.default_rng(SEED)
    side = int(np.ceil(np.sqrt(n)))
    geoms, keys = [], []
    for k in range(n):
        # Key k and key (k + 1) % n get the same shapes in the same spot.
        block = grid_boxes((k % side) * SPACING, (k // side) * SPACING, 5, 6, rng)
        for owner in (k, (k + 1) % n):
            geoms.append(block)
            keys += [f"key{owner:05d}"] * len(block)
    return make_gdf(np.concatenate(geoms), keys)


if __name__ == "__main__":
    sys.exit(run_bench("bench_many_keys", build(parse_n(10_000, __doc__))))
