import gzip
import json
from pathlib import Path

from sfrent.sources import craigslist
from sfrent.sources.craigslist_parse import parse_posting, parse_search

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_search_extracts_hits_with_optional_price():
    hits = parse_search((FIXTURES / "craigslist_search.html").read_text())
    assert [hit.token for hit in hits] == ["aaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbb"]
    assert hits[0].price == 3450 and hits[0].location == "haight ashbury"
    assert hits[1].price is None and hits[1].title == "Studio downtown"


def test_parse_posting_reads_id_geo_attributes_and_body():
    post = parse_posting((FIXTURES / "craigslist_posting.html").read_text())
    assert post.post_id == "7900000001" and post.price == 3450
    assert post.posted_at.startswith("2026-09-10") and post.updated_at.startswith("2026-09-12")
    assert (post.lat, post.lng, post.map_accuracy) == (37.7708, -122.4412, 10)
    assert post.zip == "94117" and post.street == "1200 Haight Street"
    assert (post.bedrooms, post.bathrooms, post.sqft) == (1, 1.0, 650)
    assert post.attributes["laundry"] == "w/d in unit"
    assert post.attributes["parking"] == "off-street parking"
    assert "pets_cat" in post.attributes and "no_smoking" in post.attributes
    assert post.attributes["rent_period"] == "monthly"
    assert "QR Code" not in post.body and "full kitchen" in post.body


def _record(**overrides):
    post = parse_posting((FIXTURES / "craigslist_posting.html").read_text())
    rec = {
        **post.to_dict(),
        "url": "u",
        "token": "aaaaaaaaaaaaaaaaaaaaaa",
        "location": "haight",
        "search_price": 3450,
        "fetched_at": "2026-09-18T17:00:00+00:00",
    }
    rec.update(overrides)
    return rec


def test_to_listing_maps_amenities_and_flags():
    listing = craigslist.to_listing(_record(), "craigslist/x#1")
    assert listing.rent == 3450.0 and listing.bedrooms == 1 and listing.sqft == 650.0
    assert listing.laundry == "in_unit" and listing.parking == "off_street"
    assert listing.pets == "cats" and listing.kitchen == "full"
    assert listing.property_type == "apartment" and listing.geo_precision == "post"
    assert set(listing.amenities) >= {
        "dishwasher",
        "hardwood",
        "view",
        "bike_storage",
        "no_smoking",
    }
    assert listing.has_concession is True and listing.is_room_or_sublet is False
    assert listing.listed_date.isoformat() == "2026-09-10" and listing.zip == "94117"


def test_to_listing_rejects_bogus_sqft_geo_and_old_posts():
    listing = craigslist.to_listing(_record(sqft=1, lat=30.0, lng=-97.0), "r")
    assert listing.sqft is None and listing.lat is None and listing.geo_precision is None
    assert craigslist.to_listing(_record(posted_at="2021-06-01T00:00:00-0700"), "r") is None
    assert craigslist.to_listing(_record(price=None, search_price=None), "r") is None


def test_normalize_sets_removed_date_for_posts_missing_from_latest_run(tmp_path):
    raw = tmp_path / "2026-09-18T000000Z.jsonl.gz"
    with gzip.open(raw, "wt") as fh:
        fh.write(json.dumps(_record()) + "\n")
        fh.write(json.dumps(_record(post_id="7900000002", token="bbbbbbbbbbbbbbbbbbbbbb")) + "\n")
    state = {
        "aaaaaaaaaaaaaaaaaaaaaa": {
            "post_id": "7900000001",
            "last_seen": "2026-09-18T17:00:00+00:00",
        },
        "bbbbbbbbbbbbbbbbbbbbbb": {
            "post_id": "7900000002",
            "last_seen": "2026-09-25T17:00:00+00:00",
        },
    }
    listings = {item.source_id: item for item in craigslist.normalize([raw], state)}
    assert listings["7900000001"].removed_date.isoformat() == "2026-09-18"
    assert listings["7900000002"].removed_date is None


def test_split_partitions_by_bedrooms_then_price():
    band = {"cat": "apa", "min_price": 3000, "max_price": 3499}
    by_bed = craigslist._split(band)
    assert len(by_bed) == len(craigslist.BEDROOM_SPLITS) and by_bed[0]["min_bedrooms"] == 0
    halves = craigslist._split(by_bed[1])
    assert [h["max_price"] for h in halves] == [3249, 3499] and halves[1]["min_price"] == 3250
    assert craigslist._split({**by_bed[1], "min_price": 3400, "max_price": 3499}) == []
