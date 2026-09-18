"""Merge processed sources into ``data/processed/listings.parquet`` and publish aggregates.

Steps: concat per-source Parquet -> geo columns (H3, neighborhood) -> cross-source dedupe ->
quality flags -> ZORI deflator (``rent_adj`` in latest-month dollars) -> public aggregates
in ``data/public/`` (the only data that is committed / served).
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import polars as pl

from sfrent.config import PROCESSED_DIR, PUBLIC_DIR
from sfrent.geo import neighborhoods
from sfrent.geo.index import add_geo_columns
from sfrent.normalize.dedupe import mark_cross_source_duplicates
from sfrent.normalize.filters import add_quality_flags
from sfrent.sources import zori

log = logging.getLogger(__name__)

SOURCE_FILES = ("rent_board.parquet", "rentcast.parquet", "craigslist.parquet")
LISTINGS_PATH = PROCESSED_DIR / "listings.parquet"


def build() -> dict[str, Any]:
    frames = [
        pl.read_parquet(PROCESSED_DIR / name)
        for name in SOURCE_FILES
        if (PROCESSED_DIR / name).exists()
    ]
    if not frames:
        raise RuntimeError("no processed sources found; run `sfrent pull ...` first")
    listings = pl.concat(frames, how="vertical_relaxed")
    listings = add_geo_columns(listings)
    listings = mark_cross_source_duplicates(listings)
    listings = add_quality_flags(listings)
    if zori.PROCESSED_PATH.exists():
        listings = attach_deflator(listings, zori.load())
    LISTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    listings.write_parquet(LISTINGS_PATH)

    publish(listings)
    summary = {
        "listings": listings.height,
        "by_source": dict(listings.group_by("source").len().iter_rows()),
        "modelable": int(listings["is_modelable"].sum()),
        "duplicates": int(listings["is_duplicate"].sum()),
        "suspicious": int(listings["is_suspicious"].sum()),
        "path": str(LISTINGS_PATH),
    }
    log.info("build: %s", summary)
    return summary


def attach_deflator(listings: pl.DataFrame, index: pl.DataFrame) -> pl.DataFrame:
    """Join ZORI by (zip or city, listing month); months after the index end get 1.0."""
    regions = set(index["region"].to_list())
    deflators = index.select("region", "month", "deflator_to_latest")
    return (
        listings.with_columns(
            pl.col("listed_date").dt.month_start().alias("_month"),
            pl.when(pl.col("zip").is_in(list(regions)))
            .then(pl.col("zip"))
            .otherwise(pl.lit(zori.CITY_REGION))
            .alias("_region"),
        )
        .join(deflators, left_on=["_region", "_month"], right_on=["region", "month"], how="left")
        .with_columns(
            pl.col("deflator_to_latest").fill_null(1.0),
            (pl.col("rent") * pl.col("deflator_to_latest").fill_null(1.0)).alias("rent_adj"),
        )
        .drop("_month", "_region")
    )


def publish(listings: pl.DataFrame, public_dir: Path = PUBLIC_DIR) -> None:
    """Aggregates safe to commit: no raw listing text, addresses, or per-listing rows."""
    public_dir.mkdir(parents=True, exist_ok=True)
    rent_col = "rent_adj" if "rent_adj" in listings.columns else "rent"
    modelable = listings.filter(pl.col("is_modelable"))

    by_cell = (
        modelable.group_by("analysis_neighborhood", "bedrooms")
        .agg(
            pl.len().alias("n"),
            pl.col(rent_col).median().round(0).alias("rent_median"),
            pl.col(rent_col).quantile(0.25).round(0).alias("rent_p25"),
            pl.col(rent_col).quantile(0.75).round(0).alias("rent_p75"),
            pl.col("sqft").median().round(0).alias("sqft_median"),
        )
        .filter(pl.col("n") >= 5)
        .sort("analysis_neighborhood", "bedrooms")
    )
    by_cell.write_parquet(public_dir / "neighborhood_bedroom_stats.parquet")
    (public_dir / "neighborhood_bedroom_stats.json").write_text(json.dumps(by_cell.to_dicts()))

    by_hex = (
        modelable.drop_nulls("h3_r9")
        .group_by("h3_r9", "bedrooms")
        .agg(pl.len().alias("n"), pl.col(rent_col).median().round(0).alias("rent_median"))
        .filter(pl.col("n") >= 5)
    )
    by_hex.write_parquet(public_dir / "hex_bedroom_stats.parquet")

    if neighborhoods.REFERENCE_PATH.exists():
        shutil.copy(neighborhoods.REFERENCE_PATH, public_dir / "analysis_neighborhoods.geojson")
