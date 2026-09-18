"""Append-only run log: one JSON line per collector/build run with row counts.

The scheduled jobs (scripts/launchd) rely on this to show what each run produced.
``sfrent runlog`` prints the most recent entries.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sfrent.config import RUNLOG_PATH


class RunRecord(dict[str, Any]):
    """Mutable record for one run; collectors set ``rows`` and ``notes`` as they go."""


@contextmanager
def record_run(source: str, **params: Any) -> Iterator[RunRecord]:
    started = datetime.now(UTC)
    rec = RunRecord(source=source, started_at=started.isoformat(), params=params, rows=0, notes=[])
    try:
        yield rec
        rec["status"] = "ok"
    except BaseException as exc:
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        finished = datetime.now(UTC)
        rec["finished_at"] = finished.isoformat()
        rec["duration_s"] = round((finished - started).total_seconds(), 1)
        _append(rec)


def _append(rec: dict[str, Any]) -> None:
    RUNLOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUNLOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def tail(n: int = 20) -> list[dict[str, Any]]:
    if not RUNLOG_PATH.exists():
        return []
    lines = RUNLOG_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-n:] if line.strip()]
