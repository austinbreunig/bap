"""Dense overlap: 100k random boxes piled ~15 deep in a 2 km square, one key.

Run by hand: python scripts/bench_dense_overlap.py [--n 100000]
"""

import sys

import numpy as np
import shapely
from bench_common import make_gdf, parse_n, run_bench

SEED = 5


def build(n):
    rng = np.random.default_rng(SEED)
    extent = np.sqrt(n * 4_000_000 / 100_000)  # keep the same density at any n
    x, y = rng.uniform(0, extent, (2, n))
    w, h = rng.uniform(10, 40, (2, n))
    return make_gdf(shapely.box(x, y, x + w, y + h), ["a"] * n)


if __name__ == "__main__":
    sys.exit(run_bench("bench_dense_overlap", build(parse_n(100_000, __doc__))))
