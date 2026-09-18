"""Cross-source duplicate detection between listing sources (RentCast vs Craigslist).

The same unit is often listed on both. Two listings are treated as one unit when they share
an H3 res-9 hex and bedroom count, ask within 2% of each other, and were listed within 45
days. The RentCast copy (exact geocode) is kept as primary; the Craigslist copy is flagged
``is_duplicate`` so aggregates do not double count, while its amenities remain available.
Rent Board rows are tenancies, not listings, and are never matched.
"""

from __future__ import annotations

import polars as pl

from sfrent.normalize.schema import Source

RENT_TOLERANCE = 0.02
DAYS_TOLERANCE = 45
_PRIMARY, _SECONDARY = Source.RENTCAST.value, Source.CRAIGSLIST.value


def mark_cross_source_duplicates(frame: pl.DataFrame) -> pl.DataFrame:
    if "is_duplicate" not in frame.columns:
        frame = frame.with_columns(pl.lit(False).alias("is_duplicate"))
    key = ["h3_r9", "bedrooms"]
    primary = frame.filter(pl.col("source") == _PRIMARY).select(
        *key, pl.col("rent").alias("_p_rent"), pl.col("listed_date").alias("_p_date")
    )
    secondary = frame.filter(pl.col("source") == _SECONDARY)
    if primary.height == 0 or secondary.height == 0:
        return frame

    matches = (
        secondary.select("source", "source_id", *key, "rent", "listed_date")
        .drop_nulls(key)
        .join(primary.drop_nulls(key), on=key, how="inner")
        .filter(
            ((pl.col("rent") - pl.col("_p_rent")).abs() <= pl.col("_p_rent") * RENT_TOLERANCE)
            & ((pl.col("listed_date") - pl.col("_p_date")).dt.total_days().abs() <= DAYS_TOLERANCE)
        )
        .select("source", "source_id")
        .unique()
        .with_columns(pl.lit(True).alias("_dup"))
    )
    return (
        frame.join(matches, on=["source", "source_id"], how="left")
        .with_columns(
            (pl.col("is_duplicate") | pl.col("_dup").fill_null(False)).alias("is_duplicate")
        )
        .drop("_dup")
    )
