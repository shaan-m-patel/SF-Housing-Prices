"""Commute layer.

Stage A (implemented): great-circle distance from every listing to an arbitrary work point,
computed at query time with a vectorized haversine; no external service, works offline.

Stage B (planned): travel minutes by driving / cycling / walking from each H3 res-9 hex
centroid to the work point via a routing matrix. Locally: OSRM (``osrm-backend`` docker image,
Geofabrik ``norcal-latest.osm.pbf``), ``/table/v1/<profile>`` with ~1,150 hex origins and one
destination per call. From the hosted app: OpenRouteService ``/v2/matrix`` (free tier, key in
``ORS_API_KEY``), same origins/destination shape. Store results as ``hex_commute.parquet``
keyed by (h3_r9, destination_id, mode).

Stage C (planned): transit minutes precomputed locally from each hex to the ``HUBS`` below
with r5py (Java 21 + GTFS from 511.org, free key, plus BART GTFS). Published as part of
``data/public``; arbitrary transit destinations fall back to the nearest hub or Stage A/B.
"""

from __future__ import annotations

import math

import polars as pl

EARTH_RADIUS_KM = 6371.0088

# Common Bay Area work destinations for the precomputed transit matrix (Stage C).
HUBS: dict[str, tuple[float, float]] = {
    "financial_district": (37.7894, -122.4013),  # Montgomery St BART
    "embarcadero": (37.7929, -122.3969),
    "soma_salesforce": (37.7897, -122.3972),
    "civic_center": (37.7793, -122.4193),
    "mission_bay_ucsf": (37.7680, -122.3920),
    "caltrain_4th_king": (37.7764, -122.3947),
    "ucsf_parnassus": (37.7631, -122.4586),
    "presidio": (37.7989, -122.4662),
    "south_sf_genentech": (37.6560, -122.3820),
    "oakland_12th_st": (37.8033, -122.2715),
    "berkeley_downtown": (37.8701, -122.2681),
    "menlo_park": (37.4848, -122.1484),
    "palo_alto_caltrain": (37.4433, -122.1651),
    "mountain_view": (37.3944, -122.0761),
    "cupertino": (37.3349, -122.0090),
}

DEFAULT_BANDS_KM = (0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 40.0, 80.0)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def add_distance_km(
    frame: pl.DataFrame, work_lat: float, work_lng: float, column: str = "distance_km"
) -> pl.DataFrame:
    """Vectorized haversine from each row's (lat, lng) to the work point; null when no geo."""
    lat1 = pl.col("lat").radians()
    lng1 = pl.col("lng").radians()
    lat2, lng2 = math.radians(work_lat), math.radians(work_lng)
    a = ((lat1 - lat2) / 2).sin().pow(2) + lat1.cos() * math.cos(lat2) * (
        (lng1 - lng2) / 2
    ).sin().pow(2)
    return frame.with_columns((2 * EARTH_RADIUS_KM * a.sqrt().arcsin()).alias(column))


def rent_by_distance_band(
    frame: pl.DataFrame,
    work_lat: float,
    work_lng: float,
    *,
    bedrooms: int | None = None,
    bands_km: tuple[float, ...] = DEFAULT_BANDS_KM,
    rent_column: str = "rent_adj",
) -> pl.DataFrame:
    """Median rent and count per straight-line distance band from the work point."""
    data = add_distance_km(frame, work_lat, work_lng).drop_nulls(["distance_km", rent_column])
    if "is_modelable" in data.columns:
        data = data.filter(pl.col("is_modelable"))
    if bedrooms is not None:
        data = data.filter(pl.col("bedrooms") == bedrooms)
    labels = [f"{lo:g}-{hi:g} km" for lo, hi in zip(bands_km[:-1], bands_km[1:], strict=True)]
    return (
        data.with_columns(
            pl.col("distance_km")
            .cut(list(bands_km[1:-1]), labels=labels)
            .cast(pl.Utf8)
            .alias("band")
        )
        .group_by("band")
        .agg(
            pl.len().alias("n"),
            pl.col(rent_column).median().round(0).alias("rent_median"),
            pl.col(rent_column).quantile(0.25).round(0).alias("rent_p25"),
            pl.col(rent_column).quantile(0.75).round(0).alias("rent_p75"),
            pl.col("distance_km").min().alias("_order"),
        )
        .sort("_order")
        .drop("_order")
    )
