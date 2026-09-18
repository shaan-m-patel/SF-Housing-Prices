from datetime import date
from pathlib import Path

import polars as pl

from sfrent.sources import zori

FIXTURES = Path(__file__).parent / "fixtures"


def _frame():
    return zori.build_frame(
        (FIXTURES / "zori_zip_sf.csv").read_text(), (FIXTURES / "zori_city_sf.csv").read_text()
    )


def test_only_sf_regions_and_window_months():
    frame = _frame()
    regions = set(frame["region"].to_list())
    assert "city" in regions and "94110" in regions and len(regions) == 26
    assert frame["month"].min() == date(2022, 1, 1)
    assert frame.schema["month"] == pl.Date
    assert frame["zori"].null_count() == 0


def test_deflator_is_one_at_latest_month_and_above_one_earlier():
    frame = _frame().filter(pl.col("region") == "city").sort("month")
    latest = frame.row(-1, named=True)
    assert abs(latest["deflator_to_latest"] - 1.0) < 1e-9
    assert latest["latest_month"] == latest["month"]
    first = frame.row(0, named=True)
    assert first["deflator_to_latest"] * first["zori"] == latest["zori"]
