import pytest

from sfrent.normalize.bands import (
    band_midpoint,
    parse_bathrooms,
    parse_bedrooms,
    parse_rent_band,
    parse_sqft_band,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("$2251-$2500", (2251.0, 2500.0)),
        ("$1-$250", (1.0, 250.0)),
        ("$7000+", (7000.0, None)),
        ("$0 (no rent paid by the occupant)", (0.0, 0.0)),
        ("0", (0.0, 0.0)),
        (None, (None, None)),
        ("garbage", (None, None)),
    ],
)
def test_rent_bands(value, expected):
    assert parse_rent_band(value) == expected


def test_sqft_bands_and_midpoint():
    assert parse_sqft_band("501-750 Sq.Ft") == (501.0, 750.0)
    assert parse_sqft_band("0-250 Sq.Ft") == (1.0, 250.0)
    assert parse_sqft_band("4000+ Sq.Ft") == (4000.0, None)
    assert parse_sqft_band("Unknown") == (None, None)
    assert band_midpoint(501.0, 750.0) == 625.5
    assert band_midpoint(4000.0, None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Studio", 0),
        ("Studio (sm)", 0),
        ("Zero -(Studio)", 0),
        ("One-Bedroom", 1),
        ("One Bedroom", 1),
        ("Two-Bedroom", 2),
        ("Three-Bedroom", 3),
        ("Four-Bedroom", 4),
        ("Five-Bedroom", 5),
        ("5+", 5),
        ("1", 1),
        ("1br", 1),
        ("2 bedriin", 2),
        ("3bedroom", 3),
        ("2A", None),
        ("Garage", None),
        ("$D$61", None),
        ("Vacant", None),
        (None, None),
    ],
)
def test_bedrooms(value, expected):
    assert parse_bedrooms(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("One bathroom", 1.0),
        ("Two bathrooms", 2.0),
        ("One and a half bathrooms", 1.5),
        ("Two and a half bathrooms", 2.5),
        ("Three bathrooms or more", 3.0),
        ("Shared bathroom facilities with other units", 0.0),
        ("1.00", 1.0),
        ("2.5", 2.5),
        ("2 batroom", 2.0),
        ("One-Bedroom", None),
        ("None", None),
        ("E3", None),
        (None, None),
    ],
)
def test_bathrooms(value, expected):
    assert parse_bathrooms(value) == expected
