from datetime import UTC, date, datetime

import polars as pl
import pytest
from pydantic import ValidationError

from sfrent.normalize.schema import Laundry, Listing, Source, listings_frame


def _listing(**overrides):
    base = dict(
        source=Source.RENT_BOARD,
        source_id="abc",
        observed_at=datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
        rent=2375.0,
        rent_low=2251.0,
        rent_high=2500.0,
        bedrooms=1,
        listed_date=date(2025, 8, 20),
    )
    base.update(overrides)
    return Listing(**base)


def test_defaults_are_unknown_not_imputed():
    listing = _listing()
    assert listing.laundry == Laundry.UNKNOWN
    assert listing.sqft is None
    assert listing.amenities == []


def test_amenity_vocabulary_is_enforced():
    with pytest.raises(ValidationError):
        _listing(amenities=["hot_tub"])
    assert _listing(amenities=["gym", "gym", "dishwasher"]).amenities == ["dishwasher", "gym"]


def test_band_order_is_enforced():
    with pytest.raises(ValidationError):
        _listing(rent_low=3000.0, rent_high=2000.0)


def test_listings_frame_has_typed_columns():
    frame = listings_frame([_listing(), _listing(source_id="def", listed_date=None)])
    assert frame.height == 2
    assert frame.schema["observed_at"] == pl.Datetime("us", "UTC")
    assert frame.schema["listed_date"] == pl.Date
    assert frame["listed_date"].null_count() == 1
    assert frame.schema["amenities"] == pl.List(pl.Utf8)
