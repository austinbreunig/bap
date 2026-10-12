"""Public entrypoint: cluster polygons and wrap each cluster in a tight boundary."""

import geopandas as gpd
import numpy as np

from bap.boundary import build_boundary
from bap.cluster import OUTLIER, cluster_labels
from bap.validate import validate_geometries

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

    `pos` indexes the polygons to cluster. Returns (kept, outliers):
    kept is a list of ((pass_number, label), part) where part["members"] holds
    indices into `all_geoms`; outliers is a list of indices. A part that passes the
    gate is kept. A part under min_samples polygons is dropped to outliers. A part
    below min_tightness retries at the next epsilon with only its own polygons.
    """
    kept, outliers = [], []
    remaining = pos
    for pass_number, epsilon in enumerate(epsilons, start=1):
        if len(remaining) == 0:
            break
        labels = cluster_labels(all_geoms[remaining], epsilon, min_samples)
        outliers.extend(remaining[labels == OUTLIER])
        failed = []
        for label in range(labels.max(initial=-1) + 1):
            members = remaining[labels == label]
            for part in build_boundary(all_geoms[members], epsilon):
                part["members"] = members[part["members"]]
                if part["polygon_count"] < min_samples:
                    outliers.extend(part["members"])
                elif part["tightness"] >= min_tightness:
                    kept.append(((pass_number, label), part))
                else:
                    failed.extend(part["members"])
        remaining = np.array(sorted(failed), dtype=int)
    outliers.extend(remaining)  # failed the last pass
    return kept, outliers


def cluster_polygons(
    gdf,
    key_field,
    id_field=None,
    epsilons=(80, 35),
    min_samples=3,
    min_tightness=0.75,
):
    """Return (output_gdf, summary_dict).

    Projects to local UTM, clusters by gap, wraps each cluster in a mitre-close boundary
    and gates each part on tightness. Failing parts retry at the next epsilon; parts that
    fail every pass become outliers. Projects back to the input CRS.
    """
    for col in (key_field, id_field):
        if col is not None and col not in gdf.columns:
            raise ValueError(f"Column not found: {col}")

    gdf = validate_geometries(gdf)
    work = gdf.to_crs(gdf.estimate_utm_crs())

    ids = list(gdf[id_field] if id_field else gdf.index)
    keys = gdf[key_field].to_numpy()
    status = gdf["geom_status"].to_numpy()
    all_geoms = work.geometry.to_numpy()
    rows, geoms = [], []
    n_clusters = 0
    for key in dict.fromkeys(keys):  # one key value at a time, in order of appearance
        in_key = keys == key
        # Empty rows never cluster; they pass through as outliers with status "empty".
        empty = np.flatnonzero(in_key & (status == "empty"))
        pos = np.flatnonzero(in_key & (status != "empty"))
        kept, outliers = _run_ladder(all_geoms, pos, epsilons, min_samples, min_tightness)
        # IDs go to clusters that have a kept part, after every pass has finished.
        cluster_ids = {}
        for group, _ in kept:
            if group not in cluster_ids:
                n_clusters += 1
                cluster_ids[group] = f"C{n_clusters:04d}"
        part_counts = {}
        for group, part in kept:
            part_counts[group] = part_counts.get(group, 0) + 1
            members = part["members"]
            rows.append(
                {
                    "cluster_id": cluster_ids[group],
                    "part_id": part_counts[group],
                    "source_ids": [ids[i] for i in members],
                    key_field: key,
                    "pass_number": group[0],
                    "tightness": part["tightness"],
                    "polygon_count": part["polygon_count"],
                    "area": part["area"],
                    "geom_status": "repaired" if "repaired" in status[members] else "ok",
                }
            )
            geoms.append(part["geometry"])
        for i in sorted([*empty, *outliers]):
            rows.append(_outlier_row(ids[i], key_field, key, status[i]))
            geoms.append(work.geometry.iloc[i])

    out = gpd.GeoDataFrame(rows, geometry=geoms, crs=work.crs).to_crs(gdf.crs)
    # Spec column order: key column sits after source_ids.
    columns = OUTPUT_COLUMNS.copy()
    columns.insert(columns.index("source_ids") + 1, key_field)
    out = out[[*columns, "geometry"]]

    summary = {
        "input_rows": len(gdf),
        "output_rows": len(out),
        "outliers": int(out["cluster_id"].isna().sum()),
    }
    return out, summary
