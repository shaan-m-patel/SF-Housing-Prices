"""Amenity extraction. Attribute dicts use Craigslist's fixed vocabulary as recorded from the
first scrape; description sentences are invented."""

import pytest

from sfrent.normalize.amenities import extract, kitchen_from_text
from sfrent.normalize.schema import AMENITIES, Kitchen, Laundry, Parking, Pets, PropertyType

RECORDED_ATTRS = {
    "rent_period": "monthly",
    "pets_cat": "cats are OK - purrr",
    "housing_type": "apartment",
    "pets_dog": "dogs are OK - wooof",
    "laundry": "laundry on site",
    "is_furnished": "furnished",
    "parking": "no parking",
    "no_smoking": "no smoking",
}


def test_structured_attributes_are_authoritative():
    out = extract(RECORDED_ATTRS, "Bright apartment", "")
    assert out.laundry == Laundry.IN_BUILDING and out.parking == Parking.NONE
    assert out.pets == Pets.BOTH and out.furnished is True
    assert out.property_type == PropertyType.APARTMENT and out.amenities == ["no_smoking"]
    assert out.is_room_or_sublet is False and out.has_concession is None


@pytest.mark.parametrize(
    ("laundry", "expected"),
    [
        ("w/d in unit", Laundry.IN_UNIT),
        ("w/d hookups", Laundry.HOOKUPS),
        ("laundry in bldg", Laundry.IN_BUILDING),
        ("no laundry on site", Laundry.NONE),
        ("", Laundry.UNKNOWN),
    ],
)
def test_laundry_vocabulary(laundry, expected):
    assert extract({"laundry": laundry}).laundry == expected


@pytest.mark.parametrize(
    ("parking", "expected"),
    [
        ("attached garage", Parking.GARAGE),
        ("carport", Parking.OFF_STREET),
        ("street parking", Parking.STREET),
        ("valet parking", Parking.GARAGE),
    ],
)
def test_parking_vocabulary(parking, expected):
    assert extract({"parking": parking}).parking == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cozy studio with a kitchenette and shared bath.", Kitchen.KITCHENETTE),
        ("Room in a flat; the kitchen is shared with two others.", Kitchen.SHARED),
        ("Renovated kitchen with gas range and dishwasher.", Kitchen.FULL),
        ("Sleeping room, no kitchen.", Kitchen.NONE),
        ("Great light and hardwood floors.", Kitchen.UNKNOWN),
    ],
)
def test_kitchen_from_text(text, expected):
    assert kitchen_from_text(text) == expected


def test_text_amenities_and_flags_stay_in_vocabulary():
    body = (
        "Rooftop deck, fitness center, elevator building with a doorman. Private balcony with "
        "city views, in-unit A/C, bike room and a package room. Two weeks free on 12-month leases."
    )
    out = extract({}, "", body)
    assert set(out.amenities) <= AMENITIES
    assert {
        "roof_deck",
        "gym",
        "elevator",
        "doorman",
        "balcony",
        "view",
        "bike_storage",
        "package_room",
        "air_conditioning",
    } <= set(out.amenities)
    assert out.has_concession is True


def test_room_sublet_and_short_term_detection():
    assert extract({}, "Private room in shared flat", "").is_room_or_sublet is True
    assert extract({}, "North Beach residential hotel rooms", "").is_room_or_sublet is True
    assert extract({"rent_period": "weekly"}, "Studio", "").is_room_or_sublet is True
    assert extract({}, "Sunny 1BR", "No pets, unfurnished.").pets == Pets.NONE
    assert extract({}, "Sunny 1BR", "No pets, unfurnished.").furnished is False
