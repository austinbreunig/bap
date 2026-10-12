"""End-to-end CLI test on the ~50-polygon sample file."""

from pathlib import Path

import geopandas as gpd
import pytest

from bap.cli import main

SAMPLE = str(Path(__file__).parent.parent / "data" / "sample" / "sample.parquet")
COLUMNS = [
    "cluster_id",
    "part_id",
    "source_ids",
    "zone",
    "pass_number",
    "tightness",
    "polygon_count",
    "area",
    "geom_status",
    "geometry",
]


def test_cli_end_to_end(tmp_path, capsys):
    out = str(tmp_path / "out.parquet")
    args = [SAMPLE, out, "--key-field", "zone", "--id-field", "parcel_id"]

    assert main(args) == 0
    result = gpd.read_parquet(out)
    assert list(result.columns) == COLUMNS
    assert result["cluster_id"].notna().sum() == 4  # four tight blocks
    assert result["cluster_id"].isna().sum() == 10  # ten strays
    assert result.crs.to_epsg() == 4326
    err = capsys.readouterr().err
    assert "input rows" in err and "50" in err
    assert "clusters" in err and "outliers" in err

    # Existing output fails unless --overwrite.
    assert main(args) == 1
    assert "exists" in capsys.readouterr().err
    assert main([*args, "--overwrite", "--quiet"]) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "extra",
    [
        ["--key-field", "nope"],
        ["--key-field", "zone", "--id-field", "nope"],
        ["--key-field", "zone", "--epsilon", "35", "80"],
        ["--key-field", "zone", "--epsilon", "0"],
        ["--key-field", "zone", "--epsilon", "50", "50"],
        ["--key-field", "zone", "--epsilon", "nan"],
        ["--key-field", "zone", "--epsilon", "inf"],
        ["--key-field", "zone", "--min-samples", "0"],
        ["--key-field", "zone", "--min-tightness", "0"],
        ["--key-field", "zone", "--min-tightness", "1.1"],
        [],  # key field is required
    ],
)
def test_bad_usage_exits_2_before_writing(tmp_path, extra):
    out = tmp_path / "out.parquet"
    with pytest.raises(SystemExit) as exc:
        main([SAMPLE, str(out), *extra])
    assert exc.value.code == 2
    assert not out.exists()


def test_custom_epsilons_run(tmp_path):
    out = str(tmp_path / "out.parquet")
    args = [SAMPLE, out, "--key-field", "zone", "--epsilon", "80", "--epsilon", "35"]
    assert main(args) == 0


def test_failed_run_exits_1(tmp_path, capsys):
    # A missing input file is a failed run, not bad usage.
    out = tmp_path / "out.parquet"
    assert main([str(tmp_path / "missing.parquet"), str(out), "--key-field", "zone"]) == 1
    assert "error" in capsys.readouterr().err.lower()


def test_unreadable_input_exits_1_with_message(tmp_path, capsys):
    bad = tmp_path / "bad.parquet"
    bad.write_text("this is not parquet")
    out = tmp_path / "out.parquet"

    assert main([str(bad), str(out), "--key-field", "zone"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error") and "Traceback" not in err
    assert not out.exists()


def test_failed_write_leaves_no_partial_output(tmp_path, monkeypatch, capsys):
    import geopandas as gpd

    def boom(self, path, *args, **kwargs):
        Path(path).write_text("half")
        raise OSError("disk full")

    monkeypatch.setattr(gpd.GeoDataFrame, "to_parquet", boom)
    out = tmp_path / "out.parquet"

    assert main([SAMPLE, str(out), "--key-field", "zone"]) == 1
    assert list(tmp_path.iterdir()) == []
