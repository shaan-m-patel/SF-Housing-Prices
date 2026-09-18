"""Canonical ``Listing`` record and the fixed vocabularies every source maps onto.

Rules (plan section 4): missing values stay ``None``; nothing is imputed at collection
time. Banded sources (Rent Board) fill ``*_low``/``*_high`` and set the point value to the
band midpoint so a single ``rent``/``sqft`` column is always usable.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Source(StrEnum):
    RENT_BOARD = "rent_board"
    RENTCAST = "rentcast"
    CRAIGSLIST = "craigslist"


class GeoPrecision(StrEnum):
    EXACT = "exact"  # geocoded street address
    POST = "post"  # listing's own map pin (may be nudged by the poster)
    BLOCK = "block"  # block midpoint (Rent Board geo-masking)


class Laundry(StrEnum):
    IN_UNIT = "in_unit"
    HOOKUPS = "hookups"
    IN_BUILDING = "in_building"
    NONE = "none"
    UNKNOWN = "unknown"


class Kitchen(StrEnum):
    FULL = "full"
    KITCHENETTE = "kitchenette"
    SHARED = "shared"
    NONE = "none"
    UNKNOWN = "unknown"


class Parking(StrEnum):
    GARAGE = "garage"
    OFF_STREET = "off_street"
    STREET = "street"
    NONE = "none"
    UNKNOWN = "unknown"


class Pets(StrEnum):
    CATS = "cats"
    DOGS = "dogs"
    BOTH = "both"
    NONE = "none"
    UNKNOWN = "unknown"


class PropertyType(StrEnum):
    APARTMENT = "apartment"
    CONDO = "condo"
    HOUSE = "house"
    TOWNHOUSE = "townhouse"
    IN_LAW = "in_law"
    DUPLEX = "duplex"
    LOFT = "loft"
    OTHER = "other"
    UNKNOWN = "unknown"


# Fixed amenity vocabulary. Parsers may only emit these tokens.
AMENITIES: frozenset[str] = frozenset(
    {
        "air_conditioning",
        "balcony",
        "bike_storage",
        "concierge",
        "dishwasher",
        "doorman",
        "elevator",
        "ev_charging",
        "fireplace",
        "gym",
        "hardwood",
        "no_smoking",
        "package_room",
        "pool",
        "roof_deck",
        "storage",
        "view",
        "wheelchair_accessible",
        "yard",
    }
)

UTILITIES: frozenset[str] = frozenset(
    {"water_sewer", "natural_gas", "electricity", "refuse_recycling", "other"}
)


class Listing(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)

    source: Source
    source_id: str
    observed_at: datetime
    listed_date: date | None = None
    removed_date: date | None = None

    rent: float | None = None
    rent_low: float | None = None
    rent_high: float | None = None

    bedrooms: int | None = Field(default=None, ge=0, description="0 = studio")
    bathrooms: float | None = Field(default=None, ge=0)
    sqft: float | None = Field(default=None, gt=0)
    sqft_low: float | None = None
    sqft_high: float | None = None

    lat: float | None = None
    lng: float | None = None
    geo_precision: GeoPrecision | None = None
    h3_r9: str | None = None
    analysis_neighborhood: str | None = None
    zip: str | None = Field(default=None, pattern=r"^\d{5}$")

    property_type: PropertyType = PropertyType.UNKNOWN
    year_built: int | None = Field(default=None, ge=1800, le=2100)
    building_units: int | None = Field(default=None, ge=1)
    utilities_included: list[str] = Field(default_factory=list)

    laundry: Laundry = Laundry.UNKNOWN
    kitchen: Kitchen = Kitchen.UNKNOWN
    parking: Parking = Parking.UNKNOWN
    pets: Pets = Pets.UNKNOWN
    furnished: bool | None = None
    amenities: list[str] = Field(default_factory=list)
    is_room_or_sublet: bool = False
    has_concession: bool | None = None

    raw_ref: str | None = Field(default=None, description="private pointer into data/raw")

    @field_validator("amenities")
    @classmethod
    def _amenities_in_vocab(cls, values: list[str]) -> list[str]:
        unknown = set(values) - AMENITIES
        if unknown:
            raise ValueError(f"amenities not in vocabulary: {sorted(unknown)}")
        return sorted(set(values))

    @field_validator("utilities_included")
    @classmethod
    def _utilities_in_vocab(cls, values: list[str]) -> list[str]:
        unknown = set(values) - UTILITIES
        if unknown:
            raise ValueError(f"utilities not in vocabulary: {sorted(unknown)}")
        return sorted(set(values))

    @model_validator(mode="after")
    def _bands_ordered(self) -> Listing:
        for low, high in ((self.rent_low, self.rent_high), (self.sqft_low, self.sqft_high)):
            if low is not None and high is not None and low > high:
                raise ValueError(f"band low > high: {low} > {high}")
        return self

    def to_row(self) -> dict[str, object]:
        return self.model_dump(mode="json")


POLARS_SCHEMA: dict[str, pl.DataType] = {
    "source": pl.Utf8,
    "source_id": pl.Utf8,
    "observed_at": pl.Utf8,
    "listed_date": pl.Utf8,
    "removed_date": pl.Utf8,
    "rent": pl.Float64,
    "rent_low": pl.Float64,
    "rent_high": pl.Float64,
    "bedrooms": pl.Int64,
    "bathrooms": pl.Float64,
    "sqft": pl.Float64,
    "sqft_low": pl.Float64,
    "sqft_high": pl.Float64,
    "lat": pl.Float64,
    "lng": pl.Float64,
    "geo_precision": pl.Utf8,
    "h3_r9": pl.Utf8,
    "analysis_neighborhood": pl.Utf8,
    "zip": pl.Utf8,
    "property_type": pl.Utf8,
    "year_built": pl.Int64,
    "building_units": pl.Int64,
    "utilities_included": pl.List(pl.Utf8),
    "laundry": pl.Utf8,
    "kitchen": pl.Utf8,
    "parking": pl.Utf8,
    "pets": pl.Utf8,
    "furnished": pl.Boolean,
    "amenities": pl.List(pl.Utf8),
    "is_room_or_sublet": pl.Boolean,
    "has_concession": pl.Boolean,
    "raw_ref": pl.Utf8,
}


def listings_frame(listings: list[Listing]) -> pl.DataFrame:
    """Typed DataFrame with real date/datetime columns, ready to write to Parquet."""
    frame = pl.DataFrame([listing.to_row() for listing in listings], schema=POLARS_SCHEMA)
    return frame.with_columns(
        pl.col("observed_at").str.to_datetime(time_zone="UTC"),
        pl.col("listed_date").str.to_date(),
        pl.col("removed_date").str.to_date(),
    )
