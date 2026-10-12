# BAP (Big Ass Polygons)

Clusters nearby polygons and wraps each cluster in a tight, square-edged boundary.

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
