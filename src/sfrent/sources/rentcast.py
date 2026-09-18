"""RentCast long-term rental listings for San Francisco (``/v1/listings/rental/long-term``).

Every request is billed, so a lifetime budget guard (``RENTCAST_REQUEST_BUDGET``, default 40)
is enforced from a cumulative counter in ``data/raw/rentcast/budget.json``; it never resets.
``coverage_check`` spends two requests to read ``X-Total-Count`` for Active and in-window
Inactive listings; ``pull`` pages 500 listings per request and stops (keeping the partial
snapshot) when the budget runs out. Raw RentCast records are private (plan section 6); only
derived ``Listing`` rows leave ``data/raw``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from sfrent.config import (
    PROCESSED_DIR,
    RAW_DIR,
    SF_BBOX,
    SF_CITY,
    SF_STATE,
    WINDOW_START,
    days_since_window_start,
    env,
    raw_path,
    utc_stamp,
)
from sfrent.http import Http
from sfrent.normalize.schema import GeoPrecision, Listing, PropertyType, Source, listings_frame
from sfrent.rawio import raw_files, read_jsonl_gz, write_jsonl_gz

log = logging.getLogger(__name__)

SOURCE = Source.RENTCAST.value
ENDPOINT = "https://api.rentcast.io/v1/listings/rental/long-term"
PAGE_SIZE = 500
PROCESSED_PATH = PROCESSED_DIR / "rentcast.parquet"
BUDGET_PATH = RAW_DIR / SOURCE / "budget.json"

_PROPERTY_TYPES = {
    "Apartment": PropertyType.APARTMENT,
    "Condo": PropertyType.CONDO,
    "Single Family": PropertyType.HOUSE,
    "Townhouse": PropertyType.TOWNHOUSE,
    "Multi-Family": PropertyType.APARTMENT,
    "Manufactured": PropertyType.OTHER,
    "Land": PropertyType.OTHER,
}


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    """Lifetime request counter shared by every run; the key has a fixed total allowance."""

    path: Path = BUDGET_PATH
    limit: int = int(env("RENTCAST_REQUEST_BUDGET", "40") or 40)

    def used(self) -> int:
        if not self.path.exists():
            return 0
        return int(json.loads(self.path.read_text()).get("used", 0))

    def remaining(self) -> int:
        return max(self.limit - self.used(), 0)

    def spend(self, n: int = 1) -> None:
        used = self.used()
        if used + n > self.limit:
            raise BudgetExceeded(f"RentCast budget exhausted: {used}/{self.limit} requests used")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "used": used + n,
            "limit": self.limit,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.path.write_text(json.dumps(payload))


def _client() -> Http:
    key = env("RENTCAST_API_KEY")
    if not key:
        raise RuntimeError("RENTCAST_API_KEY is not set (see .env.example)")
    return Http(headers={"X-Api-Key": key}, min_delay_s=0.5)


def _params(status: str, **extra: Any) -> dict[str, Any]:
    params: dict[str, Any] = {"city": SF_CITY, "state": SF_STATE, "status": status.capitalize()}
    if status.lower() == "inactive":
        params["daysOld"] = f"*:{days_since_window_start()}"  # first listed within the window
    params.update(extra)
    return params


def coverage_check(budget: Budget | None = None) -> dict[str, int]:
    """Total SF listings per status (2 billed requests). Decides whether a backfill is worth it."""
    budget = budget or Budget()
    counts: dict[str, int] = {}
    with _client() as http:
        for status in ("active", "inactive"):
            budget.spend()
            response = http.get(ENDPOINT, params=_params(status, limit=1, includeTotalCount="true"))
            counts[status] = int(response.headers.get("X-Total-Count", "0"))
    log.info(
        "rentcast coverage: %s (budget: %d of %d left)", counts, budget.remaining(), budget.limit
    )
    return counts


def pull(
    status: str = "active", max_requests: int | None = None, budget: Budget | None = None
) -> tuple[Path, int]:
    """Page through all SF listings with the given status into one raw snapshot."""
    budget = budget or Budget()
    stamp = utc_stamp()
    fetched_at = datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    requests = 0
    with _client() as http:
        offset = 0
        while max_requests is None or requests < max_requests:
            try:
                budget.spend()
            except BudgetExceeded as exc:
                log.warning("%s; keeping the %d listings fetched so far", exc, len(rows))
                break
            page = http.get(ENDPOINT, params=_params(status, limit=PAGE_SIZE, offset=offset)).json()
            requests += 1
            for item in page:
                item["_fetched_at"] = fetched_at
                rows.append(item)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    path = raw_path(SOURCE, f"{stamp}.{status}")
    write_jsonl_gz(path, rows)
    log.info("rentcast: %d listings in %d requests -> %s", len(rows), requests, path)
    return path, len(rows)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _in_bbox(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    south, west, north, east = SF_BBOX
    return south <= lat <= north and west <= lng <= east


def to_listing(item: dict[str, Any], raw_ref: str) -> Listing | None:
    listed = _date(item.get("listedDate"))
    if listed is None or listed < WINDOW_START or not item.get("price"):
        return None
    lat, lng = item.get("latitude"), item.get("longitude")
    has_geo = _in_bbox(lat, lng)
    observed = item.get("lastSeenDate") or item.get("_fetched_at")
    try:
        return Listing(
            source=Source.RENTCAST,
            source_id=str(item["id"]),
            observed_at=datetime.fromisoformat(observed.replace("Z", "+00:00")),
            listed_date=listed,
            removed_date=_date(item.get("removedDate")),
            rent=float(item["price"]),
            bedrooms=item.get("bedrooms"),
            bathrooms=item.get("bathrooms"),
            sqft=item.get("squareFootage") or None,
            lat=lat if has_geo else None,
            lng=lng if has_geo else None,
            geo_precision=GeoPrecision.EXACT if has_geo else None,
            zip=item.get("zipCode") or None,
            property_type=_PROPERTY_TYPES.get(item.get("propertyType"), PropertyType.UNKNOWN),
            year_built=item.get("yearBuilt") or None,
            raw_ref=raw_ref,
        )
    except (ValidationError, ValueError) as exc:
        log.debug("rentcast: skipping %s: %s", item.get("id"), exc)
        return None


def normalize(raws: list[Path]) -> list[Listing]:
    """Latest observation per listing id across every raw snapshot (oldest first)."""
    latest: dict[str, Listing] = {}
    for raw in raws:
        for item in read_jsonl_gz(raw):
            listing = to_listing(item, f"{SOURCE}/{raw.name}#{item.get('id')}")
            if listing is not None:
                latest[listing.source_id] = listing
    return list(latest.values())


def build() -> tuple[Path, int]:
    listings = normalize(raw_files(SOURCE))
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    listings_frame(listings).write_parquet(PROCESSED_PATH)
    return PROCESSED_PATH, len(listings)
