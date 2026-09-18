"""Parsers for the Rent Board's banded / free-text categorical fields.

Values observed in the dataset (Sep 2026) include clean bands like ``"$2251-$2500"``,
``"501-750 Sq.Ft"``, ``"One-Bedroom"``, ``"One and a half bathrooms"`` plus a long tail of
owner-typed junk (``"2A"``, ``"Garage"``, ``"$D$61"``). Anything unparseable returns ``None``.
"""

from __future__ import annotations

import re

_RANGE = re.compile(r"^\$?\s*([\d,]+)\s*-\s*\$?\s*([\d,]+)")
_OPEN_TOP = re.compile(r"^\$?\s*([\d,]+)\s*\+")
_NUMBER = re.compile(r"^\d+(\.\d+)?$")
_LEADING_DIGIT = re.compile(
    r"^(\d)\s*(br|bd|bed|bedroom|bedrooms|bedriin|bedroomq|brd)?s?\s*$", re.I
)

_WORD_NUMBERS = {
    "studio": 0,
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _to_number(text: str) -> float:
    return float(text.replace(",", ""))


def parse_band(value: str | None) -> tuple[float | None, float | None]:
    """``"$2251-$2500"`` -> (2251, 2500); ``"$7000+"`` -> (7000, None); junk -> (None, None)."""
    if not value:
        return None, None
    text = value.strip()
    if match := _RANGE.match(text):
        return _to_number(match.group(1)), _to_number(match.group(2))
    if match := _OPEN_TOP.match(text):
        return _to_number(match.group(1)), None
    return None, None


def band_midpoint(low: float | None, high: float | None) -> float | None:
    """Point estimate for a closed band; open-ended bands stay ``None`` (no imputation)."""
    if low is None or high is None:
        return None
    return (low + high) / 2


def parse_rent_band(value: str | None) -> tuple[float | None, float | None]:
    """Rent bands; ``"$0 (no rent paid...)"`` and ``"0"`` map to (0, 0) so callers can drop them."""
    if value and value.strip().startswith(("$0", "0")) and "-" not in value:
        return 0.0, 0.0
    return parse_band(value)


def parse_sqft_band(value: str | None) -> tuple[float | None, float | None]:
    low, high = parse_band(value)
    if low == 0 and high is not None:
        low = 1.0  # "0-250 Sq.Ft": a unit cannot have zero area
    return low, high


def parse_bedrooms(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip().lower()
    if text in {"5+", "5 +"}:
        return 5
    first_word = re.split(r"[\s\-(]", text, maxsplit=1)[0]
    if first_word in _WORD_NUMBERS and ("bed" in text or first_word in {"studio", "zero"}):
        return _WORD_NUMBERS[first_word]
    if match := _LEADING_DIGIT.match(text):
        return int(match.group(1))
    return None


def parse_bathrooms(value: str | None) -> float | None:
    """Word forms to floats; shared facilities count as 0 private bathrooms."""
    if not value:
        return None
    text = value.strip().lower()
    if text == "none":
        return None
    if "shared" in text:
        return 0.0
    if "bedroom" in text:
        return None
    first_word = re.split(r"[\s\-]", text, maxsplit=1)[0]
    if _NUMBER.match(first_word):
        return float(first_word)
    base = _WORD_NUMBERS.get(first_word)
    if base is None:
        return None
    return base + 0.5 if "half" in text else float(base)
