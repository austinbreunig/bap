import pytest
from shapely.geometry import LineString, Polygon

from bap.bap import cluster_polygons
from cases import grid_of_squares, make_gdf

OUTPUT_COLUMNS = [
    "cluster_id",
    "part_id",
    "source_ids",
    "key",
    "pass_number",
    "tightness",
    "polygon_count",
    "area",
    "geom_status",
    "geometry",
]


def test_every_row_is_an_outlier_with_spec_columns():
    gdf = make_gdf(grid_of_squares(2, 3), keys=["a", "a", "a", "b", "b", "b"])

    out, summary = cluster_polygons(gdf, key_field="key")

    assert list(out.columns) == OUTPUT_COLUMNS
    assert len(out) == 6
    for col in ["cluster_id", "part_id", "pass_number", "tightness", "polygon_count", "area"]:
        assert out[col].isna().all()
    assert out["source_ids"].tolist() == [[0], [1], [2], [3], [4], [5]]
    assert out["key"].tolist() == ["a", "a", "a", "b", "b", "b"]
    assert (out["geom_status"] == "ok").all()
    assert isinstance(summary, dict)


def test_crs_round_trips_and_geometry_is_preserved():
    gdf = make_gdf(grid_of_squares(2, 2))

    out, _ = cluster_polygons(gdf, key_field="key")

    assert out.crs == gdf.crs
    assert out.geometry.geom_equals_exact(gdf.geometry, tolerance=1e-7).all()


def test_id_field_is_used_for_source_ids():
    gdf = make_gdf(grid_of_squares(1, 2))
    gdf["pid"] = ["p1", "p2"]

    out, _ = cluster_polygons(gdf, key_field="key", id_field="pid")

    assert out["source_ids"].tolist() == [["p1"], ["p2"]]


def test_other_input_columns_are_dropped():
    gdf = make_gdf(grid_of_squares(1, 2))
    gdf["extra"] = [1, 2]

    out, _ = cluster_polygons(gdf, key_field="key")

    assert "extra" not in out.columns


def test_bowtie_and_empty_rows_are_kept_with_status():
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    gdf = make_gdf(grid_of_squares(1, 2) + [bowtie, Polygon()])
    gdf.loc[1, "geometry"] = None

    out, _ = cluster_polygons(gdf, key_field="key")

    assert len(out) == 4
    assert out["geom_status"].tolist() == ["ok", "empty", "repaired", "empty"]
    assert out["cluster_id"].isna().all()


def test_lines_and_missing_crs_raise():
    lines = make_gdf([LineString([(0, 0), (10, 0)])])
    with pytest.raises(ValueError, match="0"):
        cluster_polygons(lines, key_field="key")
    no_crs = make_gdf(grid_of_squares(1, 1)).set_crs(None, allow_override=True)
    with pytest.raises(ValueError, match="CRS"):
        cluster_polygons(no_crs, key_field="key")
