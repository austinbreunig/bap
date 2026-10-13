"""Giant cluster: 200k parcels in one chained grid, so every polygon joins one cluster.

Run by hand: python scripts/bench_giant_cluster.py [--n 200000]
"""

import sys

import numpy as np
from bench_common import grid_boxes, make_gdf, parse_n, run_bench

SEED = 2


def build(n):
    rng = np.random.default_rng(SEED)
    cols = int(np.ceil(np.sqrt(n * 1.25)))  # a slightly wide grid
    rows = int(np.ceil(n / cols))
    geoms = grid_boxes(0, 0, rows, cols, rng)[:n]
    return make_gdf(geoms, ["a"] * n)


if __name__ == "__main__":
    sys.exit(run_bench("bench_giant_cluster", build(parse_n(200_000, __doc__))))
