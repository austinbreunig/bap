"""Public entrypoint: cluster polygons and wrap each cluster in a tight boundary."""

import time

import geopandas as gpd
import numpy as np
import pandas as pd

from bap.boundary import build_boundary
from bap.cluster import OUTLIER, cluster_labels
from bap.ids import assign_ids, key_order
from bap.validate import validate_geometries

DEFAULT_EPSILONS = (80, 35)
DEFAULT_MIN_SAMPLES = 3
DEFAULT_MIN_TIGHTNESS = 0.75

OUTPUT_COLUMNS = [
    "cluster_id",
    "part_id",
    "source_ids",
    "pass_number",
    "tightness",
    "polygon_count",
    "area",
    "geom_status",
]


def _outlier_row(own_id, key_field, key, status="ok"):
    return {
        "cluster_id": None,
        "part_id": None,
        "source_ids": [own_id],
        key_field: key,
        "pass_number": None,
        "tightness": None,
        "polygon_count": None,
        "area": None,
        "geom_status": status,
    }


def _run_ladder(all_geoms, pos, epsilons, min_samples, min_tightness):
    """Run cluster -> boundary -> gate for each epsilon on one key value.

    `pos` indexes the polygons to cluster. Returns (kept, outliers, largest):
    kept is a list of ((pass_number, label), part) where part["members"] holds
    indices into `all_geoms`; outliers is a list of indices; largest is the biggest
    first-pass cluster, in polygons, before any gate. A part that passes the
    gate is kept. A part under min_samples polygons is dropped to outliers. A part
    below min_tightness retries at the next epsilon with only its own polygons.
    """
    kept, outliers = [], []
    largest = 0
    remaining = pos
    for pass_number, epsilon in enumerate(epsilons, start=1):
        if len(remaining) == 0:
            break
        labels = cluster_labels(all_geoms[remaining], epsilon, min_samples)
        outliers.extend(remaining[labels == OUTLIER])
        if pass_number == 1:
            largest = int(np.bincount(labels[labels != OUTLIER]).max(initial=0))
        failed = []
        for label in range(labels.max(initial=-1) + 1):
            members = remaining[labels == label]
            parts = build_boundary(all_geoms[members], epsilon)
            covered = [i for part in parts for i in part["members"]]
            # A member no part claims must not vanish: it becomes an outlier.
            outliers.extend(members[np.setdiff1d(np.arange(len(members)), covered)])
            for part in parts:
                part["members"] = members[part["members"]]
                if part["polygon_count"] < min_samples:
                    outliers.extend(part["members"])
                elif part["tightness"] >= min_tightness:
                    kept.append(((pass_number, label), part))
                else:
                    failed.extend(part["members"])
        remaining = np.array(sorted(failed), dtype=int)
    outliers.extend(remaining)  # failed the last pass
    return kept, outliers, largest


def cluster_polygons(
    gdf,
    key_field,
    id_field=None,
    epsilons=DEFAULT_EPSILONS,
    min_samples=DEFAULT_MIN_SAMPLES,
    min_tightness=DEFAULT_MIN_TIGHTNESS,
):
    """Return (output_gdf, summary_dict).

    Projects to local UTM, clusters by gap, wraps each cluster in a mitre-close boundary
    and gates each part on tightness. Failing parts retry at the next epsilon; parts that
    fail every pass become outliers. Projects back to the input CRS.
    """
    start = time.perf_counter()
    for col in (key_field, id_field):
        if col is not None and col not in gdf.columns:
            raise ValueError(f"Column not found: {col}")

    gdf = validate_geometries(gdf)
    status = gdf["geom_status"].to_numpy()
    # With no real geometry there is nothing to project (UTM needs a data center).
    work = gdf.to_crs(gdf.estimate_utm_crs()) if (status != "empty").any() else gdf

    ids = list(gdf[id_field]) if id_field else list(range(len(gdf)))
    # Null keys (None or NaN) are one group of their own, so no row is lost.
    codes, keys = pd.factorize(gdf[key_field], use_na_sentinel=False)
    all_geoms = work.geometry.to_numpy()
    parts, outlier_rows = [], []
    largest_cluster = 0
    for code, key in enumerate(keys):  # one key value at a time
        in_key = codes == code
        # Empty rows never cluster; they pass through as outliers with status "empty".
        empty = np.flatnonzero(in_key & (status == "empty"))
        pos = np.flatnonzero(in_key & (status != "empty"))
        kept, outliers, largest = _run_ladder(all_geoms, pos, epsilons, min_samples, min_tightness)
        largest_cluster = max(largest_cluster, largest)
        for group, part in kept:
            part["group"] = (code, *group)
            part["key"] = key
            part["source_ids"] = sorted(ids[i] for i in part["members"])
            parts.append(part)
        outlier_rows.extend((key, ids[i], i) for i in [*empty, *outliers])

    # IDs go on only now, after every pass has finished. Output order is fixed too:
    # boundary parts by ID, then outliers by key and source ID.
    rows, geoms = [], []
    cluster_ids = set()
    numbered = zip(parts, assign_ids(parts), strict=True)
    for part, (cluster_id, part_id) in sorted(numbered, key=lambda x: x[1]):
        members = part["members"]
        cluster_ids.add(cluster_id)
        rows.append(
            {
                "cluster_id": cluster_id,
                "part_id": part_id,
                "source_ids": part["source_ids"],
                key_field: part["key"],
                "pass_number": part["group"][1],
                "tightness": part["tightness"],
                "polygon_count": part["polygon_count"],
                "area": part["area"],
                "geom_status": "repaired" if "repaired" in status[members] else "ok",
            }
        )
        geoms.append(part["geometry"])
    n_boundary_rows = len(rows)
    for key, own_id, i in sorted(outlier_rows, key=lambda x: (key_order(x[0]), x[1])):
        rows.append(_outlier_row(own_id, key_field, key, status[i]))
        geoms.append(work.geometry.iloc[i])

    # Spec column order: key column sits after source_ids.
    columns = OUTPUT_COLUMNS.copy()
    columns.insert(columns.index("source_ids") + 1, key_field)
    out = gpd.GeoDataFrame(rows, columns=columns, geometry=geoms, crs=work.crs).to_crs(gdf.crs)

    summary = {
        "input_rows": len(gdf),
        "geom_status": {k: int(v) for k, v in gdf["geom_status"].value_counts().items()},
        "largest_cluster": largest_cluster,
        "clusters": len(cluster_ids),
        "parts": n_boundary_rows,
        "outliers": len(out) - n_boundary_rows,
        "output_rows": len(out),
        "seconds": time.perf_counter() - start,
    }
    return out, summary
