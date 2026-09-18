"""H3 indexing and neighborhood fill for canonical listing frames."""

from __future__ import annotations

import h3
import polars as pl

from sfrent.geo.neighborhoods import NeighborhoodIndex

H3_RESOLUTION = 9  # ~0.1 km^2 hexes; ~1,150 cover San Francisco


def h3_cell(lat: float | None, lng: float | None, resolution: int = H3_RESOLUTION) -> str | None:
    if lat is None or lng is None:
        return None
    return h3.latlng_to_cell(lat, lng, resolution)


def add_geo_columns(frame: pl.DataFrame, index: NeighborhoodIndex | None = None) -> pl.DataFrame:
    """Fill ``h3_r9`` for every geo-located row and ``analysis_neighborhood`` where missing."""
    if frame.height == 0:
        return frame
    lats = frame["lat"].to_list()
    lngs = frame["lng"].to_list()
    cells = [h3_cell(lat, lng) for lat, lng in zip(lats, lngs, strict=True)]
    index = index or NeighborhoodIndex.load()
    assigned = index.assign(lats, lngs)
    return frame.with_columns(
        pl.Series("h3_r9", cells, dtype=pl.Utf8),
        pl.coalesce(
            pl.col("analysis_neighborhood"), pl.Series("_nhood", assigned, dtype=pl.Utf8)
        ).alias("analysis_neighborhood"),
    )
