import pytest
from shapely.geometry import LineString, Polygon

from bap.bap import cluster_polygons
from cases import grid_of_squares, make_gdf, square

FAR = 1000  # meters; farther apart than any epsilon used here

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


def test_far_apart_rows_are_all_outliers_with_spec_columns():
    gdf = make_gdf(grid_of_squares(2, 3), keys=["a", "a", "a", "b", "b", "b"])

    out, summary = cluster_polygons(gdf, key_field="key", epsilons=(1,))

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

    out, _ = cluster_polygons(gdf, key_field="key", epsilons=(1,))

    assert out.crs == gdf.crs
    assert out.geometry.geom_equals_exact(gdf.geometry, tolerance=1e-7).all()


def test_id_field_is_used_for_source_ids():
    gdf = make_gdf(grid_of_squares(1, 2))
    gdf["pid"] = ["p1", "p2"]

    out, _ = cluster_polygons(gdf, key_field="key", id_field="pid", epsilons=(1,))

    assert out["source_ids"].tolist() == [["p1"], ["p2"]]


def test_other_input_columns_are_dropped():
    gdf = make_gdf(grid_of_squares(1, 2))
    gdf["extra"] = [1, 2]

    out, _ = cluster_polygons(gdf, key_field="key")

    assert "extra" not in out.columns


def run(geoms, keys=None, eps=10, **kw):
    out, _ = cluster_polygons(make_gdf(geoms, keys), "key", epsilons=(eps,), **kw)
    clusters = out[out["cluster_id"].notna()]
    return out, clusters


def n_clusters(clusters):
    # The stand-in boundary is a plain union, so one cluster can have several parts.
    return clusters["cluster_id"].nunique()


def three(x0, gap=5, y=0):
    return [square(x0 + i * (10 + gap), y) for i in range(3)]


def test_cluster_row_has_ids_and_counts():
    out, clusters = run(three(0))
    assert len(out) == 3  # three disjoint squares -> three parts of one cluster
    row = clusters.iloc[0]
    assert row["cluster_id"] == "C0001"
    assert sorted(clusters["part_id"]) == [1, 2, 3]
    assert sorted(row["source_ids"]) == [0, 1, 2]
    assert row["polygon_count"] == 3
    assert row["geometry"].geom_type == "Polygon"


def test_gap_just_under_epsilon_clusters():
    # Exact gap == epsilon is covered in test_cluster.py; lon/lat round trips blur it here.
    _, clusters = run(three(0, gap=9.5), eps=10)
    assert n_clusters(clusters) == 1


def test_gap_over_epsilon_is_all_outliers():
    out, clusters = run(three(0, gap=10.5), eps=10)
    assert clusters.empty
    assert len(out) == 3


def test_touching_and_overlapping_cluster():
    _, clusters = run([square(0, 0), square(10, 0), square(15, 0)], eps=1)
    assert n_clusters(clusters) == 1


def test_min_samples_edge():
    out, clusters = run(three(0)[:2], min_samples=3)
    assert clusters.empty and len(out) == 2
    _, clusters = run(three(0), min_samples=3)
    assert n_clusters(clusters) == 1


def test_border_polygon_joins_core_cluster():
    # 4 tight squares plus one 25 m away from the last one (eps 30): border
    geoms = [square(i * 12, 0) for i in range(4)] + [square(36 + 10 + 25, 0)]
    out, clusters = run(geoms, eps=30, min_samples=4)
    assert n_clusters(clusters) == 1
    assert sorted(clusters.iloc[0]["source_ids"]) == [0, 1, 2, 3, 4]
    assert out["cluster_id"].notna().all()


def test_chain_is_one_cluster():
    geoms = [square(i * 80, 0) for i in range(10)]  # 70 m gaps
    _, clusters = run(geoms, eps=72)
    assert n_clusters(clusters) == 1
    assert clusters.iloc[0]["polygon_count"] == 10


def test_polygons_never_mix_across_keys():
    geoms = three(0) + three(0, y=15)  # second group right next to the first
    out, clusters = run(geoms, keys=["a"] * 3 + ["b"] * 3)
    assert n_clusters(clusters) == 2
    for _, r in clusters.iterrows():
        assert all((i < 3) == (r["key"] == "a") for i in r["source_ids"])


def test_two_groups_get_unique_cluster_ids():
    _, clusters = run(three(0) + three(FAR))
    assert sorted(clusters["cluster_id"].unique()) == ["C0001", "C0002"]


def test_outlier_keeps_own_geometry_and_id_next_to_clusters():
    out, clusters = run(three(0) + [square(FAR, 0)])
    outliers = out[out["cluster_id"].isna()]
    assert outliers["source_ids"].tolist() == [[3]]
    assert n_clusters(clusters) == 1


def test_summary_counts_outliers():
    gdf = make_gdf(three(0) + [square(FAR, 0)])
    _, summary = cluster_polygons(gdf, "key", epsilons=(10,))
    assert summary["outliers"] == 1


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
