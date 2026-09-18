import gzip
import json
from pathlib import Path

import pytest

from sfrent.sources import rentcast

FIXTURE = Path(__file__).parent / "fixtures" / "rentcast_listings.jsonl"


def _items():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def _snapshot(path, items):
    with gzip.open(path, "wt") as fh:
        for item in items:
            fh.write(json.dumps(item) + "\n")
    return path


def test_documented_listing_maps_to_schema():
    listing = rentcast.to_listing(_items()[0], "rentcast/x#1")
    assert listing.rent == 2200.0 and listing.bedrooms == 3 and listing.bathrooms == 2.5
    assert listing.sqft == 1681 and listing.year_built == 2019 and listing.zip == "78754"
    assert listing.property_type == "house"
    assert listing.listed_date.isoformat() == "2024-09-18"
    assert listing.lat is None and listing.geo_precision is None  # Austin is outside SF bbox


def test_sf_listing_keeps_exact_geo_and_removed_date():
    listing = rentcast.to_listing(_items()[2], "rentcast/x#3")
    assert listing.geo_precision == "exact" and abs(listing.lat - 37.7708) < 1e-6
    assert listing.removed_date.isoformat() == "2023-06-10"
    assert listing.property_type == "apartment"


def test_pre_window_or_priceless_listings_are_dropped():
    item = _items()[0]
    assert rentcast.to_listing({**item, "listedDate": "2021-12-31T00:00:00.000Z"}, "r") is None
    assert rentcast.to_listing({**item, "price": None}, "r") is None


def test_normalize_keeps_latest_observation_per_id(tmp_path):
    items = _items()
    older = _snapshot(tmp_path / "2026-01-01T000000Z.active.jsonl.gz", items)
    updated = {**items[0], "price": 2100, "lastSeenDate": "2026-02-01T00:00:00.000Z"}
    newer = _snapshot(tmp_path / "2026-02-01T000000Z.active.jsonl.gz", [updated])
    listings = {listing.source_id: listing for listing in rentcast.normalize([older, newer])}
    assert len(listings) == 3
    assert listings[items[0]["id"]].rent == 2100.0


def test_budget_guard_is_lifetime_and_blocks(tmp_path):
    budget = rentcast.Budget(path=tmp_path / "budget.json", limit=2)
    budget.spend()
    budget.spend()
    reloaded = rentcast.Budget(path=tmp_path / "budget.json", limit=2)
    assert reloaded.used() == 2 and reloaded.remaining() == 0
    with pytest.raises(rentcast.BudgetExceeded):
        budget.spend()


def test_pull_keeps_partial_snapshot_when_budget_runs_out(tmp_path, monkeypatch):
    fake = _FakeHttp()
    monkeypatch.setattr(rentcast, "_client", lambda: fake)
    monkeypatch.setattr("sfrent.config.RAW_DIR", tmp_path)
    budget = rentcast.Budget(path=tmp_path / "budget.json", limit=1)
    _, rows = rentcast.pull(status="active", budget=budget)
    assert rows == rentcast.PAGE_SIZE and len(fake.calls) == 1 and budget.remaining() == 0


class _FakeHttp:
    """Stands in for the RentCast API in tests only: two full pages then a short one."""

    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def get(self, url, params=None):
        self.calls.append(params)
        offset = params["offset"]
        size = rentcast.PAGE_SIZE if offset < 2 * rentcast.PAGE_SIZE else 7
        items = [{"id": f"{offset}-{i}", "price": 3000} for i in range(size)]
        return type("R", (), {"json": lambda self: items})()


def test_pull_pages_until_short_page_and_bounds_inactive_by_window(tmp_path, monkeypatch):
    fake = _FakeHttp()
    monkeypatch.setattr(rentcast, "_client", lambda: fake)
    monkeypatch.setattr(rentcast, "RAW_DIR", tmp_path)
    monkeypatch.setattr("sfrent.config.RAW_DIR", tmp_path)
    budget = rentcast.Budget(path=tmp_path / "budget.json", limit=10)
    path, rows = rentcast.pull(status="inactive", budget=budget)
    assert rows == 2 * rentcast.PAGE_SIZE + 7 and len(fake.calls) == 3
    assert budget.used() == 3
    assert fake.calls[0]["status"] == "Inactive" and fake.calls[0]["daysOld"].startswith("*:")
    assert path.name.endswith(".inactive.jsonl.gz")
