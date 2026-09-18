"""HTML parsing for Craigslist search and posting pages (structure as of Sep 2026).

Search pages (no-JS ``/search/subarea/sfc?cat=apa``) list ``li.cl-static-search-result``
with title, price, location, and an opaque ``/view/d/<slug>/<token>`` link. Posting pages
carry the numeric post id, ``#map`` coordinates, schema.org JSON-LD with address, and
``div.attrgroup`` attributes whose ``<a href>`` query parameter names key each attribute.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

_PRICE = re.compile(r"\$?\s*([\d,]+)")
_POST_ID = re.compile(r"post id:\s*(\d+)", re.I)
_BR_BA = re.compile(r"(\d+)\s*BR\s*/\s*([\d.]+)\s*Ba", re.I)
_SQFT = re.compile(r"^\s*([\d,]+)\s*ft", re.I)
_LD_TYPES = {"Apartment", "House", "SingleFamilyResidence", "Residence", "Accommodation"}


@dataclass
class SearchHit:
    url: str
    token: str
    title: str
    price: int | None
    location: str | None


def parse_price(text: str | None) -> int | None:
    match = _PRICE.search(text or "")
    return int(match.group(1).replace(",", "")) if match else None


def parse_search(html: str) -> list[SearchHit]:
    soup = BeautifulSoup(html, "lxml")
    hits: list[SearchHit] = []
    for li in soup.select("li.cl-static-search-result"):
        link = li.find("a", href=True)
        if not link:
            continue
        url = link["href"].split("?")[0]
        price = li.select_one(".price")
        location = li.select_one(".location")
        hits.append(
            SearchHit(
                url=url,
                token=url.rstrip("/").rsplit("/", 1)[-1],
                title=(li.get("title") or link.get_text(" ", strip=True)).strip(),
                price=parse_price(price.get_text() if price else None),
                location=location.get_text(" ", strip=True) if location else None,
            )
        )
    return hits


@dataclass
class Posting:
    post_id: str | None = None
    title: str | None = None
    price: int | None = None
    posted_at: str | None = None
    updated_at: str | None = None
    lat: float | None = None
    lng: float | None = None
    map_accuracy: int | None = None
    zip: str | None = None
    street: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    body: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def parse_posting(html: str) -> Posting:
    soup = BeautifulSoup(html, "lxml")
    post = Posting()

    if match := _POST_ID.search(soup.get_text(" ")):
        post.post_id = match.group(1)
    if title := soup.select_one("#titletextonly"):
        post.title = title.get_text(" ", strip=True)
    if price := soup.select_one(".postingtitletext .price, .price"):
        post.price = parse_price(price.get_text())

    times = sorted(t["datetime"] for t in soup.select("time.date.timeago[datetime]"))
    if times:
        post.posted_at, post.updated_at = times[0], times[-1]

    if map_div := soup.select_one("#map[data-latitude][data-longitude]"):
        post.lat = float(map_div["data-latitude"])
        post.lng = float(map_div["data-longitude"])
        accuracy = map_div.get("data-accuracy")
        post.map_accuracy = int(accuracy) if accuracy and accuracy.isdigit() else None

    _apply_json_ld(soup, post)
    _apply_attrgroups(soup, post)

    if body := soup.select_one("#postingbody"):
        for junk in body.select(".print-information"):
            junk.decompose()
        post.body = re.sub(r"\s+\n", "\n", body.get_text("\n", strip=True))
    return post


def _apply_json_ld(soup: BeautifulSoup, post: Posting) -> None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if data.get("@type") not in _LD_TYPES and "address" not in data:
            continue
        address = data.get("address") or {}
        post.zip = post.zip or address.get("postalCode")
        post.street = post.street or address.get("streetAddress")
        if post.bedrooms is None and data.get("numberOfBedrooms") is not None:
            post.bedrooms = int(data["numberOfBedrooms"])
        if post.bathrooms is None and data.get("numberOfBathroomsTotal") is not None:
            post.bathrooms = float(data["numberOfBathroomsTotal"])


def _apply_attrgroups(soup: BeautifulSoup, post: Posting) -> None:
    for span in soup.select("div.attrgroup span.attr.important"):
        text = span.get_text(" ", strip=True)
        if match := _BR_BA.search(text):
            post.bedrooms, post.bathrooms = int(match.group(1)), float(match.group(2))
        elif match := _SQFT.match(text):
            post.sqft = int(match.group(1).replace(",", ""))
    for attr in soup.select("div.attrgroup div.attr"):
        value_el = attr.select_one(".valu") or attr
        value = value_el.get_text(" ", strip=True)
        key = _attr_key(attr)
        if key and value:
            post.attributes[key] = value


def _attr_key(attr: Any) -> str | None:
    link = attr.find("a", href=True)
    if link:
        params = parse_qs(urlparse(link["href"]).query)
        keys = [k for k in params if k != "cat"]
        if keys:
            return keys[0]
    label = attr.select_one(".labl")
    if label:
        return label.get_text(strip=True).rstrip(":").replace(" ", "_")
    classes = [c for c in attr.get("class", []) if c != "attr"]
    return classes[0] if classes else None
