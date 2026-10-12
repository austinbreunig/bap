"""Public entrypoint: cluster polygons and wrap each cluster in a tight boundary."""

import geopandas as gpd

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

    ids = gdf[id_field] if id_field else gdf.index
    out = gpd.GeoDataFrame(
        {
            "cluster_id": None,
            "part_id": None,
            "source_ids": [[i] for i in ids],
            key_field: gdf[key_field].to_numpy(),
            "pass_number": None,
            "tightness": None,
            "polygon_count": None,
            "area": None,
            "geom_status": gdf["geom_status"].to_numpy(),
        },
        geometry=work.geometry.to_crs(gdf.crs).to_numpy(),
        crs=gdf.crs,
    )
    # Spec column order: key column sits after source_ids.
    columns = OUTPUT_COLUMNS.copy()
    columns.insert(columns.index("source_ids") + 1, key_field)
    out = out[[*columns, "geometry"]]

    summary = {"input_rows": len(gdf), "output_rows": len(out), "outliers": len(out)}
    return out, summary
