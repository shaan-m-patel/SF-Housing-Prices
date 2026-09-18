"""Zillow Observed Rent Index (ZORI) for San Francisco zips plus the citywide series.

Produces ``data/processed/zori.parquet`` with one row per (region, month) from
``WINDOW_START`` onward and a ``deflator_to_latest`` column: multiply a rent observed in
``month`` by it to express that rent in the latest month's dollars. ``region`` is a 5-digit
zip, or ``"city"`` for records without a zip (e.g. block-masked Rent Board units).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import polars as pl

from sfrent.config import PROCESSED_DIR, SF_CITY, SF_STATE, WINDOW_START, raw_path, utc_stamp
from sfrent.http import Http

log = logging.getLogger(__name__)

SOURCE = "zori"
BASE = "https://files.zillowstatic.com/research/public_csvs/zori"
ZIP_URL = f"{BASE}/Zip_zori_uc_sfrcondomfr_sm_month.csv"
CITY_URL = f"{BASE}/City_zori_uc_sfrcondomfr_sm_month.csv"
PROCESSED_PATH = PROCESSED_DIR / "zori.parquet"
CITY_REGION = "city"


def pull() -> tuple[Path, int]:
    """Download both CSVs, keep raw copies, and write the SF long-format Parquet."""
    stamp = utc_stamp()
    with Http() as http:
        zip_csv = http.get(ZIP_URL).text
        city_csv = http.get(CITY_URL).text
    raw_path(SOURCE, stamp, "zip.csv").write_text(zip_csv, encoding="utf-8")
    raw_path(SOURCE, stamp, "city.csv").write_text(city_csv, encoding="utf-8")

    frame = build_frame(zip_csv, city_csv)
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(PROCESSED_PATH)
    log.info("zori: %d region-month rows -> %s", frame.height, PROCESSED_PATH)
    return PROCESSED_PATH, frame.height


def build_frame(zip_csv: str, city_csv: str) -> pl.DataFrame:
    zips = _read_wide(zip_csv).filter((pl.col("City") == SF_CITY) & (pl.col("State") == SF_STATE))
    city = (
        _read_wide(city_csv)
        .filter((pl.col("RegionName") == SF_CITY) & (pl.col("State") == SF_STATE))
        .with_columns(pl.lit(CITY_REGION).alias("RegionName"))
    )
    long = pl.concat([_to_long(zips), _to_long(city)], how="vertical")
    return _with_deflator(long).sort(["region", "month"])


def _read_wide(csv_text: str) -> pl.DataFrame:
    return pl.read_csv(io.StringIO(csv_text), schema_overrides={"RegionName": pl.Utf8})


def _to_long(wide: pl.DataFrame) -> pl.DataFrame:
    month_cols = [col for col in wide.columns if col[:4].isdigit()]
    return (
        wide.select(["RegionName", *month_cols])
        .unpivot(index="RegionName", on=month_cols, variable_name="month", value_name="zori")
        .rename({"RegionName": "region"})
        .with_columns(
            pl.col("month").str.to_date().dt.month_start(),
            # Empty months come through as strings when a column is blank for every row.
            pl.col("zori").cast(pl.Float64, strict=False),
        )
        .filter(pl.col("zori").is_not_null() & (pl.col("month") >= WINDOW_START))
    )


def _with_deflator(long: pl.DataFrame) -> pl.DataFrame:
    latest = (
        long.sort("month")
        .group_by("region")
        .agg(
            pl.col("zori").last().alias("zori_latest"), pl.col("month").last().alias("latest_month")
        )
    )
    return long.join(latest, on="region").with_columns(
        (pl.col("zori_latest") / pl.col("zori")).alias("deflator_to_latest")
    )


def load() -> pl.DataFrame:
    return pl.read_parquet(PROCESSED_PATH)
