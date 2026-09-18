import polars as pl

from sfrent.geo.commute import HUBS, add_distance_km, haversine_km, rent_by_distance_band

FIDI = HUBS["financial_district"]


def test_haversine_known_distance():
    # Montgomery St BART to Civic Center BART is roughly 1.9 km.
    km = haversine_km(*FIDI, *HUBS["civic_center"])
    assert 1.7 < km < 2.1
    assert haversine_km(*FIDI, *FIDI) == 0.0


def test_vectorized_distance_matches_scalar_and_keeps_nulls():
    frame = pl.DataFrame({"lat": [37.7793, None], "lng": [-122.4193, None]})
    out = add_distance_km(frame, *FIDI)
    assert abs(out["distance_km"][0] - haversine_km(37.7793, -122.4193, *FIDI)) < 1e-9
    assert out["distance_km"][1] is None


def test_rent_by_distance_band_orders_bands_and_filters_bedrooms():
    frame = pl.DataFrame(
        {
            "lat": [37.7893, 37.7793, 37.7631, 37.7631],
            "lng": [-122.4014, -122.4193, -122.4586, -122.4586],
            "bedrooms": [1, 1, 1, 2],
            "rent_adj": [4000.0, 3600.0, 3200.0, 5000.0],
            "is_modelable": [True, True, True, True],
        }
    )
    out = rent_by_distance_band(frame, *FIDI, bedrooms=1)
    assert out["band"].to_list() == ["0-1 km", "1-2 km", "5-8 km"]
    assert out["n"].to_list() == [1, 1, 1]
    assert out["rent_median"].to_list() == [4000.0, 3600.0, 3200.0]
