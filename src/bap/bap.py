"""Public entrypoint: cluster polygons and wrap each cluster in a tight boundary."""

import geopandas as gpd
import numpy as np
import shapely

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


def cluster_polygons(
    gdf,
    key_field,
    id_field=None,
    epsilons=(80, 35),
    min_samples=3,
    min_tightness=0.75,
):
    """Return (output_gdf, summary_dict).

    Walking skeleton: projects to local UTM and back, and returns every row as an
    outlier. Clustering, boundaries and the gate come in later tickets.
    """
    for col in (key_field, id_field):
        if col is not None and col not in gdf.columns:
            raise ValueError(f"Column not found: {col}")

    gdf = validate_geometries(gdf)
    work = gdf.to_crs(gdf.estimate_utm_crs())

    ids = list(gdf[id_field] if id_field else gdf.index)
    keys = gdf[key_field].to_numpy()
    rows, geoms = [], []
    n_clusters = 0
    status = gdf["geom_status"].to_numpy()
    for key in dict.fromkeys(keys):  # one key value at a time, in order of appearance
        in_key = keys == key
        # Empty rows never cluster; they pass through as outliers with status "empty".
        empty = np.flatnonzero(in_key & (status == "empty"))
        pos = np.flatnonzero(in_key & (status != "empty"))
        sub = work.geometry.to_numpy()[pos]
        labels = cluster_labels(sub, epsilons[0], min_samples) if len(pos) else np.array([], int)
        for label in range(labels.max(initial=-1) + 1):
            members = pos[labels == label]
            n_clusters += 1
            # Stand-in boundary: plain union. Real boundary comes in a later ticket.
            union = shapely.union_all(work.geometry.to_numpy()[members])
            parts = shapely.get_parts(union)
            for part_id, part in enumerate(parts, start=1):
                rows.append(
                    {
                        "cluster_id": f"C{n_clusters:04d}",
                        "part_id": part_id,
                        "source_ids": [ids[i] for i in members],
                        key_field: key,
                        "pass_number": 1,
                        "tightness": None,
                        "polygon_count": len(members),
                        "area": part.area,
                        "geom_status": "repaired" if "repaired" in status[members] else "ok",
                    }
                )
                geoms.append(part)
        for i in sorted([*empty, *pos[labels == OUTLIER]]):
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
