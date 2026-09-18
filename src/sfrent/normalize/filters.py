"""Quality flags applied to the merged listing frame (plan section 3, Tier 2 constraints).

Nothing is deleted here; rows get boolean flags so analyses can choose their own strictness.
``is_suspicious`` marks likely scams: a scraped listing far below its neighborhood/bedroom
median, or one with no usable location. ``is_modelable`` is the default analysis subset.
"""

from __future__ import annotations

import polars as pl

from sfrent.normalize.schema import Source

SCAM_RENT_RATIO = 0.5  # below half the local median for the same bedroom count
MIN_CELL_SIZE = 5


def add_quality_flags(frame: pl.DataFrame) -> pl.DataFrame:
    medians = (
        frame.filter(pl.col("source") != Source.CRAIGSLIST.value)
        .drop_nulls(["analysis_neighborhood", "bedrooms", "rent"])
        .group_by("analysis_neighborhood", "bedrooms")
        .agg(pl.col("rent").median().alias("_ref_rent"), pl.len().alias("_ref_n"))
        .filter(pl.col("_ref_n") >= MIN_CELL_SIZE)
        .drop("_ref_n")
    )
    scraped = pl.col("source") == Source.CRAIGSLIST.value
    too_cheap = pl.col("rent") < pl.col("_ref_rent") * SCAM_RENT_RATIO
    no_geo = pl.col("lat").is_null()
    duplicate = pl.col("is_duplicate") if "is_duplicate" in frame.columns else pl.lit(False)

    return (
        frame.join(medians, on=["analysis_neighborhood", "bedrooms"], how="left")
        .with_columns(
            (scraped & (too_cheap.fill_null(False) | no_geo)).alias("is_suspicious"),
        )
        .with_columns(
            (
                ~pl.col("is_suspicious")
                & ~pl.col("is_room_or_sublet")
                & ~duplicate
                & pl.col("rent").is_not_null()
                & pl.col("bedrooms").is_not_null()
                & pl.col("analysis_neighborhood").is_not_null()
            ).alias("is_modelable")
        )
        .drop("_ref_rent")
    )
