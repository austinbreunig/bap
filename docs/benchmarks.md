# Benchmarks

Run by hand with the scripts in `scripts/` (never in CI). All runs: seeded synthetic data, EPSG:4326 in, default settings (`epsilon` 80 then 35, `min_samples` 3, `min_tightness` 0.75), one process. Machine: Intel Core Ultra 7 255H, 16 threads, 62 GB RAM.

## Results

| Script | Size | Time | Properties |
|---|---|---|---|
| `bench_1m` | 1,000,000 polygons, 20 keys | 254 s (4.2 min), 1.5 GB peak memory | all passed |
| `bench_many_tiny` | 1,500,000 polygons, 499,731 clusters of 3 | 383 s (6.4 min) | all passed |
| `bench_many_keys` | 600,000 polygons, 10,000 keys | 262 s (4.4 min) | all passed |
| `bench_dense_overlap` | 100,000 polygons, 1 cluster | 206 s (3.4 min) | all passed |
| `bench_giant_cluster` | 200,000 chained polygons | **not run at full size** | n/a |

Properties checked: no row lost, unique `cluster_id`, every part a single Polygon, tightness >= 0.75, CRS round trip.

### Against the one-hour target

`bench_1m` took 4.2 minutes, about 14x under the one-hour target. The spec's upper range is ~5M polygons. Time looked roughly linear in rows in the other runs, so 5M should land near 20-25 minutes, but this was not measured.

### Caveats

- `bench_many_tiny`, `bench_many_keys` and `bench_dense_overlap` ran at the same time as each other (and as the start of the giant-cluster run), so their times are inflated by CPU contention. `bench_1m` ran separately.
- `bench_many_tiny` ran at 1.5M polygons because it builds 500k clusters of 3, as the ticket asks.

## Giant cluster: not run

The full 200k run was stopped because it overloaded the local machine. It was not rerun. Smaller sizes (one run each) were:

| Polygons | Time |
|---|---|
| 2,500 | 3.1 s |
| 5,000 | 6.7 s |
| 10,000 | 15.3 s |
| 20,000 | 34.4 s |

That is roughly linear, but nothing at 200k confirms it. Treat giant clusters as an open risk: the run summary's `largest_cluster` shows how big the biggest cluster is. If this matters, run `scripts/bench_giant_cluster.py` alone on an idle machine.

## Mitre limit (spec open question)

`scripts/check_mitre.py` closes sharp shapes at `mitre_limit` 2, 5 and 100 with epsilon 35 m.

- **Sharp convex tips (1 to 90 degrees):** no area lost and no bridging to a square 3 x epsilon past the tip, at every limit.
- **Sharp V notches cut into a block:** limit 100 (the current `MITRE_LIMIT`) never lost coverage. Low limits bevel the corners, which changes how much of a notch gets filled (20-degree notch: 3,052 m² filled at limit 2, 124 m² at 5, 0 at 100).

Finding: keep `MITRE_LIMIT = 100`. Low limits behave differently on sharp notches, and 100 matches the prototype. This used synthetic shapes only. Confirm on real data when you have some.
