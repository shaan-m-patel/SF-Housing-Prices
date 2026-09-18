"""Public artifacts: aggregates safe to commit and serve (no raw text, addresses, or rows).

Everything here lands in ``data/public/`` and is mirrored into ``web/public/data/`` so the
static web app ships with the data baked in and needs no runtime access to raw files.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import h3
import polars as pl
import shapely
from shapely.geometry import mapping, shape

from sfrent import model
from sfrent.config import PUBLIC_DIR, REPO_ROOT
from sfrent.geo import neighborhoods
from sfrent.normalize.schema import Source
from sfrent.sources import zori

log = logging.getLogger(__name__)

WEB_DATA_DIR = REPO_ROOT / "web" / "public" / "data"
MIN_CELL_N = 5
SIMPLIFY_TOLERANCE_DEG = 0.0002  # ~20 m; keeps the neighborhood file small for the browser


def write_all(listings: pl.DataFrame, public_dir: Path = PUBLIC_DIR) -> dict[str, Any]:
    public_dir.mkdir(parents=True, exist_ok=True)
    rent_col = "rent_adj" if "rent_adj" in listings.columns else "rent"
    modelable = listings.filter(pl.col("is_modelable"))

    cells = _neighborhood_stats(modelable, rent_col)
    cells.write_parquet(public_dir / "neighborhood_bedroom_stats.parquet")
    _dump(public_dir / "neighborhood_bedroom_stats.json", cells.to_dicts())

    hexes = _hex_stats(modelable, rent_col)
    hexes.write_parquet(public_dir / "hex_bedroom_stats.parquet")
    _dump(public_dir / "hexes.json", _hex_geometry(hexes))

    if neighborhoods.REFERENCE_PATH.exists():
        _dump(public_dir / "analysis_neighborhoods.geojson", _simplified_neighborhoods())
    if zori.PROCESSED_PATH.exists():
        _dump(public_dir / "zori.json", _zori_series(zori.load()))

    fitted = model.fit_and_publish(listings, public_dir / "model.json")
    summary = _summary(listings, fitted)
    _dump(public_dir / "summary.json", summary)
    _mirror_to_web(public_dir)
    return summary


def _dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, separators=(",", ":")))


def _neighborhood_stats(modelable: pl.DataFrame, rent_col: str) -> pl.DataFrame:
    return (
        modelable.group_by("analysis_neighborhood", "bedrooms")
        .agg(
            pl.len().alias("n"),
            pl.col(rent_col).median().round(0).alias("rent_median"),
            pl.col(rent_col).quantile(0.25).round(0).alias("rent_p25"),
            pl.col(rent_col).quantile(0.75).round(0).alias("rent_p75"),
            pl.col("sqft").median().round(0).alias("sqft_median"),
        )
        .filter(pl.col("n") >= MIN_CELL_N)
        .sort("analysis_neighborhood", "bedrooms")
    )


def _hex_stats(modelable: pl.DataFrame, rent_col: str) -> pl.DataFrame:
    return (
        modelable.drop_nulls("h3_r9")
        .group_by("h3_r9", "bedrooms")
        .agg(pl.len().alias("n"), pl.col(rent_col).median().round(0).alias("rent_median"))
        .filter(pl.col("n") >= MIN_CELL_N)
        .sort("h3_r9", "bedrooms")
    )


def _hex_geometry(hexes: pl.DataFrame) -> dict[str, Any]:
    """Compact per-cell payload: center, boundary ring ([lng, lat]), stats per bedroom count."""
    cells: dict[str, Any] = {}
    for cell, bedrooms, n, median in hexes.iter_rows():
        if cell not in cells:
            lat, lng = h3.cell_to_latlng(cell)
            ring = [[round(b, 6), round(a, 6)] for a, b in h3.cell_to_boundary(cell)]
            cells[cell] = {"c": [round(lat, 6), round(lng, 6)], "b": ring, "s": {}}
        cells[cell]["s"][str(bedrooms)] = [n, median]
    return {"resolution": 9, "cells": cells}


def _simplified_neighborhoods() -> dict[str, Any]:
    source = json.loads(neighborhoods.REFERENCE_PATH.read_text())
    features = []
    for feature in source["features"]:
        geom = shape(feature["geometry"]).simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        label = geom.representative_point()
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": feature["properties"]["name"],
                    "label": [round(label.y, 5), round(label.x, 5)],
                },
                "geometry": mapping(shapely.set_precision(geom, 1e-5)),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _zori_series(index: pl.DataFrame) -> dict[str, Any]:
    regions: dict[str, list[list[Any]]] = {}
    series = index.sort("region", "month").select("region", "month", "zori")
    for region, month, value in series.iter_rows():
        regions.setdefault(region, []).append([month.strftime("%Y-%m"), round(value)])
    latest = index["latest_month"].max()
    return {"latest_month": latest.strftime("%Y-%m"), "regions": regions}


def _summary(listings: pl.DataFrame, fitted: dict[str, Any]) -> dict[str, Any]:
    by_source = dict(listings.group_by("source").len().iter_rows())
    craigslist = listings.filter(pl.col("source") == Source.CRAIGSLIST.value)
    amenity_rows = craigslist.filter(pl.col("amenities").list.len() > 0).height
    reference = None
    if zori.PROCESSED_PATH.exists():
        reference = zori.load()["latest_month"].max().strftime("%Y-%m")
    rent_col = "rent_adj" if "rent_adj" in listings.columns else "rent"
    citywide = {
        str(bedrooms): {"n": n, "rent_median": median, "rent_p25": p25, "rent_p75": p75}
        for bedrooms, n, median, p25, p75 in listings.filter(pl.col("is_modelable"))
        .group_by("bedrooms")
        .agg(
            pl.len(),
            pl.col(rent_col).median().round(0),
            pl.col(rent_col).quantile(0.25).round(0).alias("p25"),
            pl.col(rent_col).quantile(0.75).round(0).alias("p75"),
        )
        .sort("bedrooms")
        .iter_rows()
    }
    return {
        "citywide": citywide,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "reference_month": reference,
        "listings": listings.height,
        "modelable": int(listings["is_modelable"].sum()),
        "by_source": by_source,
        "amenity_listings": amenity_rows,
        "neighborhoods": int(listings["analysis_neighborhood"].n_unique()),
        "hexes": int(listings["h3_r9"].n_unique()),
        "date_range": [str(listings["listed_date"].min()), str(listings["listed_date"].max())],
        "model": {"n": fitted["n"], **fitted["fit"]},
    }


def _mirror_to_web(public_dir: Path) -> None:
    if not WEB_DATA_DIR.parent.parent.exists():
        return
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in list(public_dir.glob("*.json")) + list(public_dir.glob("*.geojson")):
        shutil.copy(path, WEB_DATA_DIR / path.name)
    log.info("publish: mirrored web artifacts to %s", WEB_DATA_DIR)
