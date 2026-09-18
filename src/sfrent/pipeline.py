"""Merge processed sources into ``data/processed/listings.parquet`` and publish aggregates.

Steps: concat per-source Parquet -> geo columns (H3, neighborhood) -> cross-source dedupe ->
quality flags -> ZORI deflator (``rent_adj`` in latest-month dollars) -> ``publish.write_all``
for the public artifacts in ``data/public/`` (the only data that is committed / served).
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from sfrent import publish
from sfrent.config import PROCESSED_DIR
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

    published = publish.write_all(listings)
    summary = {
        "listings": listings.height,
        "by_source": published["by_source"],
        "modelable": published["modelable"],
        "duplicates": int(listings["is_duplicate"].sum()),
        "suspicious": int(listings["is_suspicious"].sum()),
        "model": published["model"],
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
