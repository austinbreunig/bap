import geopandas as gpd
import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon

from bap.validate import validate_geometries
from cases import square

BOWTIE = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])


def gdf_of(geoms, crs="EPSG:4326"):
    return gpd.GeoDataFrame({"key": ["a"] * len(geoms)}, geometry=geoms, crs=crs)


def test_valid_polygon_is_ok_and_unchanged():
    out = validate_geometries(gdf_of([square(0, 0)]))
    assert out["geom_status"].tolist() == ["ok"]
    assert out.geometry.iloc[0].equals(square(0, 0))


def test_bowtie_is_repaired():
    out = validate_geometries(gdf_of([BOWTIE]))
    assert out["geom_status"].tolist() == ["repaired"]
    assert out.geometry.iloc[0].is_valid
    assert out.geometry.iloc[0].geom_type in ("Polygon", "MultiPolygon")


def test_empty_and_null_are_marked_empty():
    out = validate_geometries(gdf_of([None, Polygon(), square(0, 0)]))
    assert out["geom_status"].tolist() == ["empty", "empty", "ok"]
    assert len(out) == 3


def test_geometry_collection_keeps_polygon_parts_only():
    gc = GeometryCollection([square(0, 0), LineString([(20, 0), (30, 0)]), Point(40, 0)])
    out = validate_geometries(gdf_of([gc]))
    geom = out.geometry.iloc[0]
    assert geom.geom_type == "Polygon"
    assert geom.equals(square(0, 0))
    assert out["geom_status"].tolist() == ["repaired"]


def test_geometry_collection_without_polygons_is_empty():
    gc = GeometryCollection([Point(0, 0)])
    out = validate_geometries(gdf_of([gc]))
    assert out["geom_status"].tolist() == ["empty"]


def test_multipolygon_stays_one_row():
    mp = MultiPolygon([square(0, 0), square(50, 0)])
    out = validate_geometries(gdf_of([mp]))
    assert len(out) == 1
    assert out.geometry.iloc[0].geom_type == "MultiPolygon"
    assert out["geom_status"].tolist() == ["ok"]


def test_duplicates_are_kept():
    out = validate_geometries(gdf_of([square(0, 0), square(0, 0)]))
    assert len(out) == 2


def test_points_and_lines_error_lists_row_numbers():
    gdf = gdf_of([square(0, 0), Point(1, 1), LineString([(0, 0), (1, 1)])])
    with pytest.raises(ValueError, match=r"1, 2"):
        validate_geometries(gdf)


def test_missing_crs_errors():
    with pytest.raises(ValueError, match="CRS"):
        validate_geometries(gdf_of([square(0, 0)], crs=None))


def test_input_is_not_mutated():
    gdf = gdf_of([BOWTIE])
    validate_geometries(gdf)
    assert "geom_status" not in gdf.columns


def test_geometry_collection_of_only_polygons_stays_ok():
    gc = GeometryCollection([square(0, 0), square(50, 0)])
    out = validate_geometries(gdf_of([gc]))
    assert out["geom_status"].tolist() == ["ok"]
    assert out.geometry.iloc[0].geom_type == "MultiPolygon"
