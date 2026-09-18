"""Paths, environment, and plan-wide constants.

Environment (``SFRENT_ENV``): ``dev`` caps collector row counts unless ``--limit`` is
given, ``test`` is used by pytest with recorded fixtures, ``prod`` pulls everything
(the scheduled launchd jobs set this).
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Plan section 2: hard 2022-forward window for every source.
WINDOW_START = date(2022, 1, 1)

SF_CITY = "San Francisco"
SF_STATE = "CA"
# Bounding box used to reject obviously mis-geocoded records (lat, lng).
SF_BBOX = (37.70, -122.52, 37.84, -122.35)

ENV = os.environ.get("SFRENT_ENV", "dev").lower()
DEV_ROW_CAP = 500

DATA_DIR = Path(os.environ.get("SFRENT_DATA_DIR") or REPO_ROOT / "data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PUBLIC_DIR = DATA_DIR / "public"
REFERENCE_DIR = DATA_DIR / "reference"
RUNLOG_PATH = DATA_DIR / "runlog.jsonl"

USER_AGENT = "sfrent/0.1 (SF-Housing-Prices; personal rent research tool) python-httpx"


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def is_prod() -> bool:
    return ENV == "prod"


def effective_limit(requested: int | None) -> int | None:
    """Row cap for a collector run: explicit ``--limit`` wins, dev gets a small default."""
    if requested is not None:
        return requested
    return None if is_prod() else DEV_ROW_CAP


def utc_stamp(now: datetime | None = None) -> str:
    """Filesystem-safe UTC timestamp used to name raw snapshot files."""
    now = now or datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H%M%SZ")


def raw_path(source: str, stamp: str, ext: str = "jsonl.gz") -> Path:
    path = RAW_DIR / source / f"{stamp}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def days_since_window_start(today: date | None = None) -> int:
    """Age in days of the window start; feeds RentCast's ``daysOld`` upper bound."""
    return ((today or date.today()) - WINDOW_START).days
