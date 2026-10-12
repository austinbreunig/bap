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

## Install

```bash
pip install git+https://github.com/austinbreunig/bap
```

## Usage

```bash
bap INPUT.parquet OUTPUT.parquet --key-field zone
```

Try it on the sample file (50 polygons: 4 tight blocks and 10 strays):

```bash
bap data/sample/sample.parquet out.parquet --key-field zone --id-field parcel_id
```

| Flag | Default | Meaning |
|---|---|---|
| `--key-field COL` | required | Polygons with different values never share a cluster |
| `--id-field COL` | row index | Column used for `source_ids` |
| `--epsilon METERS` | 80, then 35 | Gap for each pass. Repeat the flag. Largest first |
| `--min-samples N` | 3 | Neighbors a core polygon needs, counting itself |
| `--min-tightness X` | 0.75 | A boundary must score at least this |
| `--overwrite` | off | Replace an existing output file |
| `--quiet` | off | Hide the summary on stderr |

Exit codes: `0` success, `1` failed run (bad data, unreadable file, output exists), `2` bad usage
(bad settings, or a column that is not in the file). Settings are checked before any rows are read.

From Python: `from bap.bap import cluster_polygons` returns `(gdf, summary)`.

## Development

```bash
uv sync --extra dev
ruff check . && pytest -q
python scripts/make_sample.py   # rebuild data/sample/sample.parquet
```

## Development workflow

See `playbook/phases.md` in the `ab_spatial` workspace.

## Issue tracker

GitHub Issues. See `docs/agents/issue-tracker.md`.
