"""Raw snapshot storage: gzip'd JSON lines under ``data/raw/<source>/<stamp>.jsonl.gz``."""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from sfrent.config import RAW_DIR


def write_jsonl_gz(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def read_jsonl_gz(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def raw_files(source: str, ext: str = "jsonl.gz") -> list[Path]:
    """All raw snapshots for a source, oldest first (stamps sort lexicographically)."""
    folder = RAW_DIR / source
    if not folder.exists():
        return []
    return sorted(folder.glob(f"*.{ext}"))


def latest_raw(source: str, ext: str = "jsonl.gz") -> Path | None:
    files = raw_files(source, ext)
    return files[-1] if files else None
