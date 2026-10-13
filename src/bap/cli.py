"""Command line entry point: `bap INPUT OUTPUT --key-field COL ...`.

Exit codes: 0 success, 1 failed run, 2 bad usage.
"""

import argparse
import math
import os
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import pyarrow as pa
import pyarrow.parquet as pq

from bap.bap import (
    DEFAULT_EPSILONS,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_MIN_TIGHTNESS,
    cluster_polygons,
)


def build_parser():
    defaults = " then ".join(str(e) for e in DEFAULT_EPSILONS)
    parser = argparse.ArgumentParser(
        prog="bap",
        description="Cluster nearby polygons and wrap each in a tight square-cornered boundary.",
    )
    parser.add_argument("input", help="input GeoParquet file")
    parser.add_argument("output", help="output GeoParquet file")
    parser.add_argument(
        "--key-field",
        required=True,
        metavar="COL",
        help="polygons with different values here never share a cluster",
    )
    parser.add_argument(
        "--id-field", metavar="COL", help="column used for source_ids (default: row index)"
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help=f"neighbors for a core polygon, counting itself (default {DEFAULT_MIN_SAMPLES})",
    )
    parser.add_argument(
        "--min-tightness",
        type=float,
        default=DEFAULT_MIN_TIGHTNESS,
        help=f"minimum boundary score to pass the gate (default {DEFAULT_MIN_TIGHTNESS})",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        action="append",
        metavar="METERS",
        help=f"gap in meters; repeat for more passes, largest first (default {defaults})",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace an existing output")
    parser.add_argument("--quiet", action="store_true", help="hide the summary")
    return parser


def usage_errors(args, columns):
    """List everything wrong with the settings, using only the file's column names."""
    errors = []
    eps = args.epsilon or []
    if not all(math.isfinite(e) and e > 0 for e in eps):
        errors.append("--epsilon values must be greater than 0")
    if not all(a > b for a, b in zip(eps, eps[1:], strict=False)):
        errors.append("--epsilon values must be strictly descending (largest first)")
    if args.min_samples < 1:
        errors.append("--min-samples must be at least 1")
    if not 0 < args.min_tightness <= 1:
        errors.append("--min-tightness must be above 0 and at most 1")
    for flag, col in (("--key-field", args.key_field), ("--id-field", args.id_field)):
        if col is not None and col not in columns:
            errors.append(f"{flag}: column not found: {col}")
    return errors


def format_summary(s):
    status = ", ".join(f"{k} {v}" for k, v in sorted(s["geom_status"].items()))
    return "\n".join(
        [
            f"input rows:      {s['input_rows']} ({status})",
            f"largest cluster: {s['largest_cluster']} polygons (before the gate)",
            f"clusters:        {s['clusters']}",
            f"parts:           {s['parts']}",
            f"outliers:        {s['outliers']}",
            f"output rows:     {s['output_rows']}",
            f"seconds:         {s['seconds']:.1f}",
        ]
    )


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        columns = pq.read_schema(args.input).names  # schema only, no rows
    except (OSError, pa.ArrowException) as e:
        print(f"error: cannot read {args.input}: {e}", file=sys.stderr)
        return 1
    errors = usage_errors(args, columns)
    if errors:
        parser.error("; ".join(errors))

    if Path(args.output).exists() and not args.overwrite:
        print(f"error: {args.output} exists (use --overwrite)", file=sys.stderr)
        return 1

    tmp = None
    try:
        gdf = gpd.read_parquet(args.input)
        out, summary = cluster_polygons(
            gdf,
            args.key_field,
            id_field=args.id_field,
            min_samples=args.min_samples,
            epsilons=tuple(args.epsilon or DEFAULT_EPSILONS),
            min_tightness=args.min_tightness,
        )
        # Write next to the target, then rename, so a failure never leaves a partial file.
        fd, tmp = tempfile.mkstemp(dir=Path(args.output).parent, suffix=".tmp")
        os.close(fd)
        out.to_parquet(tmp)
        os.replace(tmp, args.output)
        tmp = None
    except (ValueError, OSError, pa.ArrowException) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if tmp is not None:
            Path(tmp).unlink(missing_ok=True)

    if not args.quiet:
        print(format_summary(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
