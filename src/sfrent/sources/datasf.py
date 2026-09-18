"""Thin Socrata (SODA 2.1) client for DataSF datasets, shared by all DataSF pulls."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sfrent.config import env
from sfrent.http import Http

BASE_URL = "https://data.sf.gov"
PAGE_SIZE = 50_000  # SODA 2.1 maximum


def _headers() -> dict[str, str]:
    token = env("SOCRATA_APP_TOKEN")
    return {"X-App-Token": token} if token else {}


def iter_rows(
    dataset_id: str,
    *,
    where: str | None = None,
    select: str | None = None,
    limit: int | None = None,
    http: Http | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield rows for a dataset, paging on ``:id`` so results are stable across pages."""
    client = http or Http(headers=_headers())
    url = f"{BASE_URL}/resource/{dataset_id}.json"
    yielded = 0
    offset = 0
    try:
        while True:
            page_size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - yielded)
            if page_size <= 0:
                return
            params: dict[str, Any] = {"$limit": page_size, "$offset": offset, "$order": ":id"}
            if where:
                params["$where"] = where
            if select:
                params["$select"] = select
            rows = client.get(url, params=params).json()
            for row in rows:
                yield row
                yielded += 1
            if len(rows) < page_size:
                return
            offset += len(rows)
    finally:
        if http is None:
            client.close()


def fetch_geojson(dataset_id: str, http: Http | None = None) -> dict[str, Any]:
    client = http or Http(headers=_headers())
    try:
        return client.get(
            f"{BASE_URL}/resource/{dataset_id}.geojson", params={"$limit": 5000}
        ).json()
    finally:
        if http is None:
            client.close()
