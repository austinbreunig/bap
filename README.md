# BAP (Big Ass Polygons)

Clusters nearby polygons from a Parquet file and wraps each cluster in a tight, square-edged boundary. Writes the result to Parquet.

Status: Discovery done. See `plan.md` and the [Discovery map](https://github.com/austinbreunig/bap/issues/1).

## Plan

**Problem.** You have a GeoParquet file of polygons (parcels, buildings). You want to group nearby ones and draw one tight outline around each group. A rounded buffer wastes area, and a convex hull wastes more.

**Solution.** One CLI command: `bap INPUT OUTPUT --key-field COL`. It clusters polygons within a distance (DBSCAN-style, per key value), wraps each cluster in a square-cornered boundary, and checks how tight it is. A loose boundary is redone at a smaller distance (default `80` m, then `35` m). Each result gets a unique cluster ID. Polygons that join no cluster stay in the output with a null ID.

**Design.** One public function holds the whole workflow. Each step is a plain-function module that never calls another step.

```text
src/bap/
├── cli.py        # args, read/write Parquet, exit codes, summary
├── bap.py        # cluster_polygons(...): the one entrypoint and the workflow
├── validate.py   # repair or flag bad geometry
├── cluster.py    # find neighbors, group them
├── boundary.py   # square-cornered close, tightness, split into parts
└── ids.py        # deterministic cluster and part IDs
```

```text
cluster_polygons
  validate
  project to UTM
  for each epsilon
    cluster -> boundary -> gate (tightness >= 0.75)
  assign IDs
  project back
```

## Setup

TBD after Discovery.

## Development workflow

See `playbook/phases.md` in the `ab_spatial` workspace.

## Issue tracker

GitHub Issues. See `docs/agents/issue-tracker.md`.
