"""DataSF Rent Board Housing Inventory (dataset ``gdc7-dmcn``).

Keeps non-owner-occupied units whose tenancy started on/after ``WINDOW_START`` and that
report a rent band. The same unit appears in several annual filings; ``normalize`` keeps the
earliest filing after the tenancy start, whose rent is closest to the move-in (market) rent.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from sfrent.config import PROCESSED_DIR, WINDOW_START, effective_limit, raw_path, utc_stamp
from sfrent.normalize.bands import (
    band_midpoint,
    parse_bathrooms,
    parse_bedrooms,
    parse_rent_band,
    parse_sqft_band,
)
from sfrent.normalize.schema import GeoPrecision, Listing, Source, listings_frame
from sfrent.rawio import read_jsonl_gz, write_jsonl_gz
from sfrent.sources import datasf

log = logging.getLogger(__name__)

SOURCE = Source.RENT_BOARD.value
DATASET_ID = "gdc7-dmcn"
PROCESSED_PATH = PROCESSED_DIR / "rent_board.parquet"

_UTILITY_FLAGS = {
    "base_rent_includes_water_sewer": "water_sewer",
    "base_rent_includes_natural_gas": "natural_gas",
    "base_rent_includes_electricity": "electricity",
    "base_rent_includes_refuse_recycling": "refuse_recycling",
    "base_rent_includes_other_utilities": "other",
}


def in_window_filter() -> str:
    return (
        "occupancy_type='Occupied by non-owner' AND monthly_rent IS NOT NULL "
        f"AND occupancy_or_vacancy_date >= '{WINDOW_START.isoformat()}T00:00:00'"
    )


def pull(limit: int | None = None) -> tuple[Path, int]:
    """Download in-window rows to a raw snapshot. Returns (path, row count)."""
    path = raw_path(SOURCE, utc_stamp())
    rows = datasf.iter_rows(DATASET_ID, where=in_window_filter(), limit=effective_limit(limit))
    count = write_jsonl_gz(path, rows)
    log.info("rent_board: wrote %d raw rows to %s", count, path)
    return path, count


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def unit_key(row: dict[str, Any]) -> tuple[str, ...]:
    """Best-available identity for a unit-tenancy across annual filings (no unit ID exists)."""
    return tuple(
        str(row.get(field) or "")
        for field in (
            "block_num",
            "block_address",
            "unit_count",
            "bedroom_count",
            "bathroom_count",
            "square_footage",
        )
    ) + ((row.get("occupancy_or_vacancy_date") or "")[:10],)


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per unit-tenancy: the earliest filing on/after the tenancy start."""
    best: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = unit_key(row)
        current = best.get(key)
        if current is None or _filing_order(row) < _filing_order(current):
            best[key] = row
    return list(best.values())


def _filing_order(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("submission_year") or "9999"), str(row.get("signature_date") or ""))


def to_listing(row: dict[str, Any], raw_ref: str) -> Listing | None:
    rent_low, rent_high = parse_rent_band(row.get("monthly_rent"))
    if rent_low is None or (rent_low == 0 and rent_high == 0):
        return None
    tenancy_start = _parse_date(row.get("occupancy_or_vacancy_date"))
    observed = _parse_date(row.get("signature_date")) or _parse_date(row.get("data_as_of"))
    if tenancy_start is None or observed is None or tenancy_start < WINDOW_START:
        return None
    if tenancy_start > observed:
        return None  # typo such as a 2035 move-in date

    sqft_low, sqft_high = parse_sqft_band(row.get("square_footage"))
    coords = (row.get("point") or {}).get("coordinates") or [None, None]
    year_built = _int_in_range(row.get("year_property_built"), 1800, 2100)
    units = _int_in_range(row.get("unit_count"), 1, 10_000)

    try:
        return Listing(
            source=Source.RENT_BOARD,
            source_id=str(row["unique_id"]),
            observed_at=datetime.combine(observed, datetime.min.time(), tzinfo=UTC),
            listed_date=tenancy_start,
            rent=band_midpoint(rent_low, rent_high),
            rent_low=rent_low,
            rent_high=rent_high,
            bedrooms=parse_bedrooms(row.get("bedroom_count")),
            bathrooms=parse_bathrooms(row.get("bathroom_count")),
            sqft=band_midpoint(sqft_low, sqft_high),
            sqft_low=sqft_low,
            sqft_high=sqft_high,
            lat=coords[1],
            lng=coords[0],
            geo_precision=GeoPrecision.BLOCK if coords[0] is not None else None,
            analysis_neighborhood=row.get("analysis_neighborhood") or None,
            year_built=year_built,
            building_units=units,
            utilities_included=[
                name for field, name in _UTILITY_FLAGS.items() if row.get(field) == "Y"
            ],
            raw_ref=raw_ref,
        )
    except ValidationError as exc:
        log.debug("rent_board: skipping %s: %s", row.get("unique_id"), exc)
        return None


def _int_in_range(value: Any, low: int, high: int) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def normalize(raw: Path) -> list[Listing]:
    raw_rows = list(read_jsonl_gz(raw))
    rows = dedupe(raw_rows)
    ref_prefix = f"{SOURCE}/{raw.name}#"
    listings = [to_listing(row, ref_prefix + str(row.get("unique_id"))) for row in rows]
    kept = [listing for listing in listings if listing is not None]
    log.info("rent_board: %d raw -> %d deduped -> %d listings", len(raw_rows), len(rows), len(kept))
    return kept


def build(raw: Path) -> tuple[Path, int]:
    """Normalize a raw snapshot into ``data/processed/rent_board.parquet``."""
    listings = normalize(raw)
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    listings_frame(listings).write_parquet(PROCESSED_PATH)
    return PROCESSED_PATH, len(listings)
