import pytest
from shapely import affinity
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
    return clusters["cluster_id"].nunique()


def three(x0, gap=5, y=0):
    return [square(x0 + i * (10 + gap), y) for i in range(3)]


def test_cluster_row_has_ids_and_counts():
    out, clusters = run(three(0))
    assert len(out) == 1  # gaps of 5 m close up: one part
    row = clusters.iloc[0]
    assert row["cluster_id"] == "C0001"
    assert row["part_id"] == 1
    assert row["pass_number"] == 1
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


def test_boundary_rows_have_square_corners_and_tightness():
    # Three 10 m squares 5 m apart close into a 40 x 10 rectangle.
    _, clusters = run(three(0))
    row = clusters.iloc[0]
    assert row["area"] == pytest.approx(40 * 10, rel=1e-2)
    assert row["tightness"] == pytest.approx(300 / 400, rel=1e-2)


def test_rotated_group_boundary_is_a_rectangle():
    geoms = [affinity.rotate(g, 37, origin=(0, 0)) for g in three(0)]
    _, clusters = run(geoms)
    assert n_clusters(clusters) == 1
    assert clusters.iloc[0]["area"] == pytest.approx(40 * 10, rel=1e-2)


def test_notch_under_two_epsilon_is_filled():
    # U shape with a 15 m notch (eps 10): filled, so tightness is the filled share.
    geoms = [
        Polygon([(0, 0), (50, 0), (50, 100), (0, 100)]),
        Polygon([(65, 0), (115, 0), (115, 100), (65, 100)]),
        Polygon([(0, 0), (115, 0), (115, 30), (0, 30)]),
    ]
    _, clusters = run(geoms, eps=10)
    assert len(clusters) == 1
    assert clusters.iloc[0]["area"] == pytest.approx(115 * 100, rel=1e-2)


def test_big_hole_is_kept_as_interior_ring():
    geoms = [
        Polygon([(0, 0), (100, 0), (100, 30), (0, 30)]),
        Polygon([(0, 70), (100, 70), (100, 100), (0, 100)]),
        Polygon([(0, 30), (30, 30), (30, 70), (0, 70)]),
        Polygon([(70, 30), (100, 30), (100, 70), (70, 70)]),
    ]
    _, clusters = run(geoms, eps=10, min_samples=3)
    assert len(clusters) == 1
    row = clusters.iloc[0]
    assert len(row["geometry"].interiors) == 1
    assert row["tightness"] == pytest.approx(1.0, rel=1e-2)


def test_separate_clusters_never_merge_into_multipolygon_rows():
    _, clusters = run(three(0) + three(FAR))
    assert (clusters["geometry"].geom_type == "Polygon").all()
    assert (clusters["tightness"] <= 1.0 + 1e-9).all()
