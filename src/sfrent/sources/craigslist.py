"""Polite Craigslist collector for San Francisco apartments (``sfc`` / ``apa``).

Operating rules (plan section 3, Tier 2): run from a home IP only, one request every few
seconds, weekly cadence, stop at the first 403. The no-JS search page returns at most ~350
posts per query and ignores offsets, so coverage comes from partitioning: price bands first,
then bedrooms when a band is still truncated. Posting HTML is stored privately under
``data/raw/craigslist/html`` and never published; only derived ``Listing`` rows leave raw.
"""

from __future__ import annotations

import gzip
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from sfrent.config import (
    PROCESSED_DIR,
    RAW_DIR,
    SF_BBOX,
    USER_AGENT,
    WINDOW_START,
    env,
    is_prod,
    raw_path,
    utc_stamp,
)
from sfrent.http import Blocked, Http
from sfrent.normalize import amenities
from sfrent.normalize.schema import GeoPrecision, Listing, Source, listings_frame
from sfrent.rawio import raw_files, read_jsonl_gz, write_jsonl_gz
from sfrent.sources.craigslist_parse import SearchHit, parse_posting, parse_search

log = logging.getLogger(__name__)

SOURCE = Source.CRAIGSLIST.value
SEARCH_URL = "https://www.craigslist.org/search/subarea/sfc"
TRUNCATED_AT = 340  # static results cap is ~350; treat this many as "more exist"
MIN_DELAY_S = 4.0
PRICE_STEP = 500
PRICE_MAX = 10_000
BEDROOM_SPLITS = ((0, 0), (1, 1), (2, 2), (3, 3), (4, 8))
DEV_MAX_PAGES, DEV_MAX_DETAILS = 2, 5

PROCESSED_PATH = PROCESSED_DIR / "craigslist.parquet"
STATE_PATH = RAW_DIR / SOURCE / "seen.json"
HTML_DIR = RAW_DIR / SOURCE / "html"


@dataclass
class PullResult:
    search_requests: int = 0
    search_rows: int = 0
    new_details: int = 0
    blocked: bool = False


def _client() -> Http:
    return Http(min_delay_s=MIN_DELAY_S, user_agent=env("CRAIGSLIST_USER_AGENT", USER_AGENT))


def _initial_partitions() -> deque[dict[str, Any]]:
    queue: deque[dict[str, Any]] = deque()
    for low in range(0, PRICE_MAX, PRICE_STEP):
        queue.append(
            {"cat": "apa", "sort": "date", "min_price": low, "max_price": low + PRICE_STEP - 1}
        )
    queue.append({"cat": "apa", "sort": "date", "min_price": PRICE_MAX})
    return queue


def _split(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Narrow a truncated query: by bedrooms first, then by halving the price band."""
    if "min_bedrooms" not in params:
        return [{**params, "min_bedrooms": lo, "max_bedrooms": hi} for lo, hi in BEDROOM_SPLITS]
    low, high = params.get("min_price", 0), params.get("max_price")
    if high is None or high - low < 100:
        return []
    mid = (low + high) // 2
    return [{**params, "max_price": mid}, {**params, "min_price": mid + 1}]


def _load_state() -> dict[str, dict[str, Any]]:
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}


def _save_state(state: dict[str, dict[str, Any]]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state))


def pull(max_pages: int | None = None, max_details: int | None = None) -> PullResult:
    if max_pages is None and not is_prod():
        max_pages = DEV_MAX_PAGES
    if max_details is None and not is_prod():
        max_details = DEV_MAX_DETAILS
    result = PullResult()
    now = datetime.now(UTC).isoformat()
    hits: dict[str, SearchHit] = {}
    queue = _initial_partitions()

    with _client() as http:
        while queue and (max_pages is None or result.search_requests < max_pages):
            params = queue.popleft()
            try:
                page = parse_search(http.get(SEARCH_URL, params=params).text)
            except Blocked:
                result.blocked = True
                break
            result.search_requests += 1
            for hit in page:
                hits[hit.token] = hit
            if len(page) >= TRUNCATED_AT:
                queue.extend(_split(params))

        state = _load_state()
        records: list[dict[str, Any]] = []
        for token, hit in hits.items():
            if token in state:
                state[token]["last_seen"] = now
                continue
            if result.blocked or (max_details is not None and result.new_details >= max_details):
                continue
            try:
                html = http.get(hit.url).text
            except Blocked:
                result.blocked = True
                continue
            posting = parse_posting(html)
            if not posting.post_id:
                continue
            _store_html(posting.post_id, html)
            records.append(
                {
                    **posting.to_dict(),
                    "url": hit.url,
                    "token": token,
                    "location": hit.location,
                    "search_price": hit.price,
                    "fetched_at": now,
                }
            )
            state[token] = {"post_id": posting.post_id, "first_seen": now, "last_seen": now}
            result.new_details += 1

    result.search_rows = len(hits)
    _save_state(state)
    if records:
        write_jsonl_gz(raw_path(SOURCE, utc_stamp()), records)
    log.info("craigslist: %s", result)
    if result.blocked:
        log.warning("craigslist: received 403, stopped early; wait before running again")
    return result


def _store_html(post_id: str, html: str) -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(HTML_DIR / f"{post_id}.html.gz", "wt", encoding="utf-8") as fh:
        fh.write(html)


def _in_bbox(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    south, west, north, east = SF_BBOX
    return south <= lat <= north and west <= lng <= east


def to_listing(rec: dict[str, Any], raw_ref: str, removed: date | None = None) -> Listing | None:
    price = rec.get("price") or rec.get("search_price")
    posted = rec.get("posted_at")
    if not price or price < 100 or not posted:
        return None
    listed = datetime.fromisoformat(posted).date()
    if listed < WINDOW_START:
        return None
    extracted = amenities.extract(
        rec.get("attributes") or {}, rec.get("title") or "", rec.get("body") or ""
    )
    sqft = rec.get("sqft")
    has_geo = _in_bbox(rec.get("lat"), rec.get("lng"))
    zip_code = rec.get("zip")
    try:
        return Listing(
            source=Source.CRAIGSLIST,
            source_id=str(rec["post_id"]),
            observed_at=datetime.fromisoformat(rec["fetched_at"]),
            listed_date=listed,
            removed_date=removed,
            rent=float(price),
            bedrooms=rec.get("bedrooms"),
            bathrooms=rec.get("bathrooms"),
            sqft=float(sqft) if sqft and 100 <= sqft <= 10_000 else None,
            lat=rec.get("lat") if has_geo else None,
            lng=rec.get("lng") if has_geo else None,
            geo_precision=GeoPrecision.POST if has_geo else None,
            zip=zip_code if zip_code and len(zip_code) == 5 and zip_code.isdigit() else None,
            property_type=extracted.property_type,
            laundry=extracted.laundry,
            kitchen=extracted.kitchen,
            parking=extracted.parking,
            pets=extracted.pets,
            furnished=extracted.furnished,
            amenities=extracted.amenities,
            is_room_or_sublet=extracted.is_room_or_sublet,
            has_concession=extracted.has_concession,
            raw_ref=raw_ref,
        )
    except (ValidationError, ValueError) as exc:
        log.debug("craigslist: skipping %s: %s", rec.get("post_id"), exc)
        return None


def normalize(raws: list[Path], state: dict[str, dict[str, Any]] | None = None) -> list[Listing]:
    """Latest record per post; posts absent from the most recent run get a removed_date."""
    state = _load_state() if state is None else state
    last_seen = {
        entry["post_id"]: entry["last_seen"] for entry in state.values() if entry.get("post_id")
    }
    newest = max(last_seen.values(), default=None)
    latest: dict[str, Listing] = {}
    for raw in raws:
        for rec in read_jsonl_gz(raw):
            seen = last_seen.get(str(rec.get("post_id")))
            removed = (
                datetime.fromisoformat(seen).date() if seen and newest and seen < newest else None
            )
            listing = to_listing(rec, f"{SOURCE}/{raw.name}#{rec.get('post_id')}", removed)
            if listing is not None:
                latest[listing.source_id] = listing
    return list(latest.values())


def build() -> tuple[Path, int]:
    listings = normalize(raw_files(SOURCE))
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    listings_frame(listings).write_parquet(PROCESSED_PATH)
    return PROCESSED_PATH, len(listings)
