# BAP — Plan

Written from the resolved [Discovery map](https://github.com/austinbreunig/bap/issues/1). Each decision lives in its ticket; this file gists it and links. Words like *cluster*, *part*, *gate* are defined in `CONTEXT.md`.

## Problem statement

You have a GeoParquet file of polygons (parcels, buildings). You want to group nearby ones and draw one tight outline around each group. A rounded buffer wastes area. A convex hull wastes more. Nothing off the shelf gives a square-cornered, tight wrap that also checks itself.

## Goals

- One CLI command: GeoParquet in, Parquet out, each cluster with a unique ID and one tight square-cornered boundary.
- Boundaries that are honestly tight: a gate checks them, and loose ones are redone at a smaller distance.
- Same input and settings always give the same IDs.
- Handles 100k to ~5M polygons in about an hour.

## Success criteria

- `bap in.parquet out.parquet --key-field COL` runs end to end and writes the agreed columns.
- Every cluster boundary has tightness >= 0.75, or its polygons are in the output as outliers with a null ID.
- No input row is lost. Bad geometry is repaired or kept as an outlier, never silently dropped.
- Shuffling the input rows gives the same IDs.
- The synthetic ~1M-polygon benchmark finishes well under an hour (run once in Tracer).

## Stakeholders

- Austin Breunig: author and only user for v1.

## Scope

### In scope

- **Clustering** ([#4](https://github.com/austinbreunig/bap/issues/4)): DBSCAN-style, edge-to-edge gap <= epsilon, `min_samples` 3, within the same key value, in UTM, no scikit-learn.
- **Boundary** ([#3](https://github.com/austinbreunig/bap/issues/3)): union the cluster, then mitre close (grow epsilon, shrink epsilon).
- **Gate and passes** ([#7](https://github.com/austinbreunig/bap/issues/7)): tightness >= 0.75, epsilon ladder `[80, 35]` m, close then split into parts, failing parts retry at the next epsilon.
- **Validation** ([#5](https://github.com/austinbreunig/bap/issues/5)): `make_valid` and keep; empty rows become outliers; non-polygon types and missing CRS fail the run.
- **I/O** ([#6](https://github.com/austinbreunig/bap/issues/6), amended by [#11](https://github.com/austinbreunig/bap/issues/11)): columns `cluster_id`, `part_id`, `source_ids`, key column, `pass_number`, `tightness`, `polygon_count`, `area`, `geom_status`, `geometry`.
- **IDs** ([#8](https://github.com/austinbreunig/bap/issues/8)): `C0012` and part 1..n, unique across the file, deterministic, assigned after all passes.
- **CLI** ([#9](https://github.com/austinbreunig/bap/issues/9)): `bap INPUT OUTPUT --key-field COL` plus flags; exit 0, 1, 2.
- **Summary** ([#11](https://github.com/austinbreunig/bap/issues/11)): plain text to stderr.
- **Scale** ([#10](https://github.com/austinbreunig/bap/issues/10)): whole file in memory, one key value at a time, no parallelism.
- **Packaging** ([#13](https://github.com/austinbreunig/bap/issues/13)): `ab-bap`, command `bap`, Python >= 3.10, `geopandas>=0.14`, `shapely>=2.0`, `pyarrow>=14`, stdlib `argparse`, hatchling.
- **Tests** ([#12](https://github.com/austinbreunig/bap/issues/12)): see Test plan.

### Out of scope

- Plumber integration ([#14](https://github.com/austinbreunig/bap/issues/14)).
- Formats other than Parquet.
- Interactive or map UI.
- Parallelism, chunked I/O, and a giant-cluster cap (add only if the benchmark misses).
- PyPI publishing and a release workflow. For v1, install with `pip install git+https://github.com/austinbreunig/bap`. Add releases when someone else needs them. This amends #13.

## Design

Deep modules. `bap.py` is the one public entrypoint and holds the whole workflow. The step modules never call each other. All internals are plain functions (Wu Wei).

```
src/bap/
  __init__.py    __version__ = "0.1.0"
  cli.py         argparse, read/write Parquet, exit codes, print summary
  bap.py         cluster_polygons(gdf, key_field, id_field=None, epsilons=(80, 35),
                 min_samples=3, min_tightness=0.75) -> (gdf, summary_dict)
                 validate -> UTM -> [cluster -> boundary -> gate] per epsilon -> ids -> back
  validate.py    make_valid, empty/null, type and CRS checks, geom_status
  cluster.py     STRtree + union-find, per key value
  boundary.py    mitre close, tightness, split into parts
  ids.py         C0012 cluster IDs, part IDs, deterministic order
```

Bad input raises `ValueError` from `cluster_polygons`. `cli.py` turns it into exit 1.

## Assumptions

- Austin is the only user for v1.
- Input is a single-CRS GeoParquet, and epsilon is in meters in UTM.
- One epsilon drives both clustering and the close, so the close can bridge gaps up to 2 x epsilon. The gate catches over-wrapping from that.
- `estimate_utm_crs()` picks one zone from the data center. Data spanning a zone edge is a known v1 limit.
- Duplicate rows are kept and can raise `min_samples` counts. Deduping is the user's job.

## Constraints

- **CI:** `ruff check .` and `pytest -q` on Python 3.10 and 3.12. Benchmarks never run in CI.
- **Dev setup:** same as the sibling projects (Nix flake, `uv`, `direnv`, hatchling), line length 100.

## Test plan

The case table in the [#12 answer](https://github.com/austinbreunig/bap/issues/12#issuecomment-6125497565) is the source. Generators are plain functions in `tests/cases.py` (built in meters, converted to EPSG:4326). One CLI end-to-end test runs on the ~50-polygon `data/sample/` Parquet.

Stress scripts are ready for Tracer. They live in `scripts/bench_*.py`, are seeded, run by hand, and check properties only: `bench_1m`, `bench_giant_cluster`, `bench_many_tiny`, `bench_many_keys`, `bench_dense_overlap`.

## Risks

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| The close bridges gaps up to 2 x epsilon, so boundaries over-wrap | Loose boundaries | The gate at 0.75 and the smaller second epsilon. Test `tightness_at_gate` and `pass2_rescue`. |
| The close is proven only on the prototype, not at scale | Wrong or slow boundaries on real data | Run `bench_1m` early in Tracer and compare with the prototype results. |
| Giant clusters make the union and close slow | Run exceeds an hour | The summary shows the largest cluster size. `bench_giant_cluster` shows the cost. Add a cap only if it bites. |

## Open questions

* [ ] Mitre limit for very sharp corners: the prototype used the default. Confirm on real data in Tracer.

---

## Next phase

Tracer: `/to-spec`, then `/to-tickets`. See `playbook/phases.md` in the `ab_spatial` workspace.
