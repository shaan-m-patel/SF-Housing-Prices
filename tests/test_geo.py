import h3
import polars as pl

from sfrent.geo.index import H3_RESOLUTION, add_geo_columns, h3_cell
from sfrent.geo.neighborhoods import NeighborhoodIndex

# Two simple squares standing in for neighborhood polygons (test geometry only).
FEATURES = [
    {
        "type": "Feature",
        "properties": {"name": "West"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-122.5, 37.7], [-122.45, 37.7], [-122.45, 37.8], [-122.5, 37.8], [-122.5, 37.7]]
            ],
        },
    },
    {
        "type": "Feature",
        "properties": {"name": "East"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-122.45, 37.7], [-122.4, 37.7], [-122.4, 37.8], [-122.45, 37.8], [-122.45, 37.7]]
            ],
        },
    },
]


def test_h3_cell_resolution_and_missing():
    cell = h3_cell(37.7708, -122.4412)
    assert h3.get_resolution(cell) == H3_RESOLUTION
    assert h3_cell(None, -122.4) is None


def test_assign_points_to_polygons():
    index = NeighborhoodIndex(FEATURES)
    names = index.assign([37.75, 37.75, 37.75, None], [-122.48, -122.42, -122.0, None])
    assert names == ["West", "East", None, None]


def test_add_geo_columns_fills_missing_neighborhood_only():
    frame = pl.DataFrame(
        {
            "lat": [37.75, 37.75, None],
            "lng": [-122.48, -122.42, None],
            "analysis_neighborhood": [None, "Given", None],
        }
    )
    out = add_geo_columns(frame, NeighborhoodIndex(FEATURES))
    assert out["analysis_neighborhood"].to_list() == ["West", "Given", None]
    assert out["h3_r9"].null_count() == 1
