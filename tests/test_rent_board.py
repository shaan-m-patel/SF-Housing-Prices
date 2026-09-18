import gzip
import json
from pathlib import Path

import polars as pl

from sfrent.sources import rent_board

FIXTURE = Path(__file__).parent / "fixtures" / "rent_board_rows.jsonl"


def _rows():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def _raw_snapshot(tmp_path, rows):
    path = tmp_path / "2026-09-18T000000Z.jsonl.gz"
    with gzip.open(path, "wt") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_real_rows_normalize_to_listings(tmp_path):
    rows = _rows()
    listings = rent_board.normalize(_raw_snapshot(tmp_path, rows))
    assert len(listings) == len(rows)
    first = listings[0]
    assert first.source == "rent_board"
    assert first.rent_low == 1501.0 and first.rent_high == 1750.0 and first.rent == 1625.5
    assert first.bedrooms == 0 and first.bathrooms == 1.0
    assert first.sqft_low == 251.0 and first.sqft_high == 500.0
    assert first.geo_precision == "block" and -122.6 < first.lng < -122.3
    assert first.analysis_neighborhood == "Chinatown"
    assert first.listed_date.isoformat() == "2022-07-29"
    assert first.raw_ref.startswith("rent_board/2026-09-18T000000Z.jsonl.gz#")


def test_dedupe_keeps_earliest_filing_per_unit_tenancy():
    row = _rows()[0]
    later = {**row, "unique_id": "later", "submission_year": "2026", "monthly_rent": "$1751-$2000"}
    other_tenancy = {
        **row,
        "unique_id": "other",
        "occupancy_or_vacancy_date": "2025-03-01T00:00:00",
    }
    kept = rent_board.dedupe([later, row, other_tenancy])
    assert {r["unique_id"] for r in kept} == {row["unique_id"], "other"}


def test_out_of_window_and_zero_rent_rows_are_dropped(tmp_path):
    row = _rows()[0]
    too_old = {**row, "unique_id": "old", "occupancy_or_vacancy_date": "2021-12-31T00:00:00"}
    typo = {**row, "unique_id": "typo", "occupancy_or_vacancy_date": "2035-01-01T00:00:00"}
    free = {**row, "unique_id": "free", "monthly_rent": "$0 (no rent paid by the occupant)"}
    listings = rent_board.normalize(_raw_snapshot(tmp_path, [row, too_old, typo, free]))
    assert [listing.source_id for listing in listings] == [row["unique_id"]]


def test_build_writes_typed_parquet(tmp_path, monkeypatch):
    out = tmp_path / "rent_board.parquet"
    monkeypatch.setattr(rent_board, "PROCESSED_PATH", out)
    path, count = rent_board.build(_raw_snapshot(tmp_path, _rows()))
    frame = pl.read_parquet(path)
    assert count == frame.height == 6
    assert frame.schema["listed_date"] == pl.Date
    assert frame["utilities_included"].dtype == pl.List(pl.Utf8)
