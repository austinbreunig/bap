import numpy as np
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
    # Gate off by default: these tests cover clustering and boundaries, not the gate.
    kw.setdefault("min_tightness", 0.01)
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
    _, summary = cluster_polygons(gdf, "key", epsilons=(10,), min_tightness=0.01)
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


def run_ladder(geoms, epsilons, **kw):
    out, _ = cluster_polygons(make_gdf(geoms), "key", epsilons=epsilons, **kw)
    return out


def test_tightness_at_gate():
    # Two squares 8 m apart close into one loose boundary.
    pair = [square(0, 0), square(18, 0)]
    loose = run_ladder(pair, (10,), min_samples=2, min_tightness=0.01)
    tightness = loose.iloc[0]["tightness"]
    assert tightness == pytest.approx(200 / 280, rel=1e-2)

    # A threshold equal to the score passes; a hair above it fails.
    at_gate = run_ladder(pair, (10,), min_samples=2, min_tightness=tightness)
    assert at_gate["cluster_id"].notna().sum() == 1
    over_gate = run_ladder(pair, (10,), min_samples=2, min_tightness=tightness + 1e-6)
    assert over_gate["cluster_id"].isna().all()


def test_pass2_rescue():
    # Two tight rows of 3 squares (2 m gaps), 15 m apart. Eps 20 wraps both as one loose
    # boundary (tightness ~0.72); eps 5 wraps each row tightly.
    geoms = three(0, gap=2) + three(49, gap=2)
    out = run_ladder(geoms, (20, 5))
    assert len(out) == 2
    assert (out["pass_number"] == 2).all()
    assert (out["tightness"] >= 0.75).all()
    assert out["cluster_id"].nunique() == 2
    assert sorted(sum(out["source_ids"], [])) == [0, 1, 2, 3, 4, 5]


def test_pass1_success_keeps_pass_number_1():
    out = run_ladder(three(0, gap=2), (20, 5))
    assert out["pass_number"].tolist() == [1]


def test_fails_all_passes():
    pair = [square(0, 0), square(18, 0)]
    out = run_ladder(pair, (10, 9), min_samples=2)
    assert len(out) == 2
    for col in ["cluster_id", "part_id", "pass_number", "tightness", "polygon_count", "area"]:
        assert out[col].isna().all()
    assert out["source_ids"].tolist() == [[0], [1]]
    assert out.geometry.geom_equals_exact(make_gdf(pair).geometry, tolerance=1e-7).all()


def test_tiny_part_dropped():
    # One row is a MultiPolygon with pieces 200 m apart. The cluster splits in two parts;
    # the far part holds only 2 polygons, under min_samples, so they become outliers.
    multi = square(0, 0).union(square(200, 0))
    geoms = [multi, square(15, 0), square(30, 0), square(215, 0), square(230, 0)]
    out = run_ladder(geoms, (10,), min_samples=3, min_tightness=0.01)
    clusters = out[out["cluster_id"].notna()]
    assert len(clusters) == 1
    assert clusters.iloc[0]["cluster_id"] == "C0001"
    outliers = out[out["cluster_id"].isna()]
    assert sorted(sum(outliers["source_ids"], [])) == [3, 4]


def test_id_determinism_shuffled_input_gives_identical_output():
    geoms = three(0) + three(1000) + three(0, y=2000) + [square(5000, 5000)]
    keys = ["b"] * 3 + ["a"] * 3 + ["a"] * 3 + ["a"]
    gdf = make_gdf(geoms, keys)
    gdf["pid"] = [f"p{i:02d}" for i in range(len(gdf))]
    kw = {"id_field": "pid", "epsilons": (10,), "min_tightness": 0.01}

    base, _ = cluster_polygons(gdf, "key", **kw)
    other, _ = cluster_polygons(gdf.sample(frac=1, random_state=7), "key", **kw)

    # key "a" sorts before "b": its two clusters are C0001 and C0002, key "b" is C0003.
    assert base["cluster_id"].dropna().tolist() == ["C0001", "C0002", "C0003"]
    assert base["source_ids"].tolist()[0] == ["p03", "p04", "p05"]
    cols = ["cluster_id", "part_id", "source_ids", "key", "polygon_count"]
    assert base[cols].equals(other[cols])
    assert base.geometry.geom_equals_exact(other.geometry, tolerance=1e-7).all()


def test_id_field_missing_falls_back_to_row_index():
    gdf = make_gdf(three(0))
    gdf.index = [10, 11, 12]

    out, _ = cluster_polygons(gdf, "key", epsilons=(10,), min_tightness=0.01)

    assert out["source_ids"].tolist() == [[0, 1, 2]]


def test_null_keys_keep_every_row():
    geoms = three(0) + three(1000, y=1000)
    out, _ = cluster_polygons(
        make_gdf(geoms, ["a", None, np.nan, "a", None, np.nan]),
        "key",
        epsilons=(10,),
        min_tightness=0.01,
    )

    assert len(out) >= 3
    ids = sorted(i for ids in out["source_ids"] for i in ids)
    assert ids == [0, 1, 2, 3, 4, 5]


def test_three_rows_with_null_key_are_three_rows_out():
    out, _ = cluster_polygons(
        make_gdf([square(0, 0), square(1000, 0), square(2000, 0)], [None, "a", None]),
        "key",
        epsilons=(10,),
    )

    assert len(out) == 3


def test_null_keys_form_their_own_cluster():
    out, clusters = run(three(0), keys=[None] * 3)

    assert len(out) == 1 and n_clusters(clusters) == 1


def test_all_empty_input_is_all_empty_outliers():
    out, summary = cluster_polygons(make_gdf([Polygon(), None]), "key")

    assert out["geom_status"].tolist() == ["empty", "empty"]
    assert out["cluster_id"].isna().all()
    assert summary["outliers"] == 2


def test_zero_rows_in_zero_rows_out():
    out, summary = cluster_polygons(make_gdf([]), "key")

    assert len(out) == 0 and summary["output_rows"] == 0


def test_a_member_dropped_by_the_boundary_becomes_an_outlier(monkeypatch):
    import bap.bap as bap_module

    real = bap_module.build_boundary

    def lossy(geoms, epsilon):
        parts = real(geoms, epsilon)
        parts[0]["members"] = parts[0]["members"][:-1]  # forget one member
        parts[0]["polygon_count"] -= 1
        return parts

    monkeypatch.setattr(bap_module, "build_boundary", lossy)
    out, _ = cluster_polygons(
        make_gdf(three(0) + [square(45, 0)]), "key", epsilons=(10,), min_samples=3,
        min_tightness=0.01,
    )

    assert sorted(i for ids in out["source_ids"] for i in ids) == [0, 1, 2, 3]


def test_largest_cluster_is_counted_before_the_gate():
    # A long thin chain fails the gate at its only pass, so no cluster survives.
    geoms = [square(i * 15, 0) for i in range(4)] + [square(0, 15 * k + 15) for k in range(3)]
    gdf = make_gdf(geoms)
    _, summary = cluster_polygons(gdf, "key", epsilons=(10,), min_tightness=1.0)

    assert summary["clusters"] == 0
    assert summary["largest_cluster"] == 7


def test_summary_matches_spec():
    bowtie = Polygon([(3000, 0), (3010, 10), (3010, 0), (3000, 10)])
    # a 3-cluster, a 2-polygon fragment (dropped to outliers), a bowtie, an empty row
    geoms = three(0) + [square(1000, 0), square(1015, 0), bowtie, Polygon()]
    gdf = make_gdf(geoms)

    _, summary = cluster_polygons(gdf, "key", epsilons=(10,), min_tightness=0.01)

    assert summary["input_rows"] == 7
    assert summary["geom_status"] == {"ok": 5, "repaired": 1, "empty": 1}
    assert summary["largest_cluster"] == 3
    assert summary["clusters"] == 1
    assert summary["parts"] == 1
    assert summary["outliers"] == 4
    assert summary["output_rows"] == 5
    assert summary["seconds"] >= 0
