"""Map Craigslist structured attributes plus free text onto the canonical vocabularies.

Structured attributes (``laundry``, ``parking``, ``housing_type``, ``pets_cat`` ...) are
authoritative; description text only fills what the attributes do not cover (kitchen type,
building amenities, concessions, room/sublet signals).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sfrent.normalize.schema import Kitchen, Laundry, Parking, Pets, PropertyType

_LAUNDRY = {
    "w/d in unit": Laundry.IN_UNIT,
    "w/d hookups": Laundry.HOOKUPS,
    "laundry in bldg": Laundry.IN_BUILDING,
    "laundry on site": Laundry.IN_BUILDING,
    "no laundry on site": Laundry.NONE,
}
_PARKING = {
    "attached garage": Parking.GARAGE,
    "detached garage": Parking.GARAGE,
    "valet parking": Parking.GARAGE,
    "carport": Parking.OFF_STREET,
    "off-street parking": Parking.OFF_STREET,
    "street parking": Parking.STREET,
    "no parking": Parking.NONE,
}
_HOUSING = {
    "apartment": PropertyType.APARTMENT,
    "flat": PropertyType.APARTMENT,
    "condo": PropertyType.CONDO,
    "house": PropertyType.HOUSE,
    "cottage/cabin": PropertyType.HOUSE,
    "townhouse": PropertyType.TOWNHOUSE,
    "in-law": PropertyType.IN_LAW,
    "duplex": PropertyType.DUPLEX,
    "loft": PropertyType.LOFT,
}
_ATTR_AMENITIES = {
    "airconditioning": "air_conditioning",
    "ev_charging": "ev_charging",
    "wheelchaccess": "wheelchair_accessible",
    "no_smoking": "no_smoking",
}
_TEXT_AMENITIES: dict[str, re.Pattern[str]] = {
    "dishwasher": re.compile(r"\bdishwasher\b", re.I),
    "gym": re.compile(r"\b(gym|fitness (center|room|studio))\b", re.I),
    "roof_deck": re.compile(r"\b(roof ?deck|rooftop)\b", re.I),
    "elevator": re.compile(r"\belevator\b", re.I),
    "doorman": re.compile(r"\b(doorman|attended lobby|24.hour (lobby|attendant))\b", re.I),
    "concierge": re.compile(r"\bconcierge\b", re.I),
    "balcony": re.compile(r"\b(balcony|balconies|private patio|private deck)\b", re.I),
    "view": re.compile(r"\b(bay|city|ocean|bridge|panoramic|sweeping) views?\b", re.I),
    "hardwood": re.compile(r"\bhardwood\b", re.I),
    "bike_storage": re.compile(r"\bbike (storage|room|parking)\b", re.I),
    "pool": re.compile(r"\b(swimming )?pool\b", re.I),
    "fireplace": re.compile(r"\bfireplace\b", re.I),
    "storage": re.compile(r"\b(storage (unit|space|locker|room)|extra storage)\b", re.I),
    "package_room": re.compile(r"\bpackage (room|locker|lockers|concierge)\b", re.I),
    "yard": re.compile(r"\b(backyard|back yard|private yard|shared yard|garden)\b", re.I),
    "air_conditioning": re.compile(r"\b(air conditioning|central a/?c|\bA/C\b)", re.I),
}
_KITCHEN_NONE = re.compile(r"\bno kitchen\b", re.I)
_KITCHEN_SHARED = re.compile(r"\b(shared|communal|common) kitchen|kitchen (is )?shared\b", re.I)
_KITCHEN_ETTE = re.compile(r"\b(kitchenette|efficiency kitchen|mini.?kitchen)\b", re.I)
_KITCHEN_FULL = re.compile(
    r"\b(full|chef'?s|gourmet|updated|renovated|remodeled|modern|spacious|eat-in) kitchen\b"
    r"|\bkitchen (with|features|includes)\b|\b(gas|electric) (stove|range)\b|\bdishwasher\b",
    re.I,
)
_ROOM_OR_SUBLET = re.compile(
    r"\b(rooms? for rent|roommates?|shared (room|apartment|house|flat)|sublet|sublease|"
    r"short.term|private room|bedroom for rent|furnished rooms?|clean rooms?|"
    r"residential hotel|hotel rooms?|sro|single.room occupancy)\b",
    re.I,
)
_CONCESSION = re.compile(
    r"\b(\d+|one|two|three|four|six|eight) (weeks?|months?) free\b|\bmove.in special\b"
    r"|\bconcession\b|\bfree rent\b|\blook and lease\b",
    re.I,
)
_NO_PETS = re.compile(r"\bno pets\b", re.I)


@dataclass
class Extracted:
    laundry: Laundry = Laundry.UNKNOWN
    parking: Parking = Parking.UNKNOWN
    pets: Pets = Pets.UNKNOWN
    kitchen: Kitchen = Kitchen.UNKNOWN
    property_type: PropertyType = PropertyType.UNKNOWN
    furnished: bool | None = None
    amenities: list[str] = field(default_factory=list)
    is_room_or_sublet: bool = False
    has_concession: bool | None = None


def extract(attributes: dict[str, str], title: str = "", body: str = "") -> Extracted:
    text = f"{title}\n{body}"
    out = Extracted()
    out.laundry = _LAUNDRY.get(attributes.get("laundry", "").lower(), Laundry.UNKNOWN)
    out.parking = _PARKING.get(attributes.get("parking", "").lower(), Parking.UNKNOWN)
    out.property_type = _HOUSING.get(
        attributes.get("housing_type", "").lower(), PropertyType.UNKNOWN
    )
    out.pets = _pets(attributes, text)
    out.kitchen = kitchen_from_text(text)
    out.furnished = (
        True
        if "is_furnished" in attributes
        else (False if re.search(r"\bunfurnished\b", text, re.I) else None)
    )
    amenities = {name for key, name in _ATTR_AMENITIES.items() if key in attributes}
    amenities |= {name for name, pattern in _TEXT_AMENITIES.items() if pattern.search(text)}
    out.amenities = sorted(amenities)
    rent_period = attributes.get("rent_period", "monthly").lower()
    out.is_room_or_sublet = bool(_ROOM_OR_SUBLET.search(text)) or rent_period not in {"monthly", ""}
    out.has_concession = bool(_CONCESSION.search(text)) if body else None
    return out


def kitchen_from_text(text: str) -> Kitchen:
    if _KITCHEN_NONE.search(text):
        return Kitchen.NONE
    if _KITCHEN_SHARED.search(text):
        return Kitchen.SHARED
    if _KITCHEN_ETTE.search(text):
        return Kitchen.KITCHENETTE
    if _KITCHEN_FULL.search(text):
        return Kitchen.FULL
    return Kitchen.UNKNOWN


def _pets(attributes: dict[str, str], text: str) -> Pets:
    cats, dogs = "pets_cat" in attributes, "pets_dog" in attributes
    if cats and dogs:
        return Pets.BOTH
    if cats:
        return Pets.CATS
    if dogs:
        return Pets.DOGS
    return Pets.NONE if _NO_PETS.search(text) else Pets.UNKNOWN
