"""``sfrent`` command line: collectors, build, and run log.

sfrent pull rent-board [--limit N]
sfrent pull zori
sfrent pull rentcast [--status active|inactive] [--check-only] [--max-requests N]
sfrent pull craigslist [--max-pages N] [--max-details N]
sfrent pull neighborhoods
sfrent build
sfrent commute (--lat LAT --lng LNG | --hub NAME) [--bedrooms N]
sfrent runlog [-n 20]
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable

from sfrent.runlog import record_run, tail

Handler = Callable[[argparse.Namespace], None]


def _pull_rent_board(args: argparse.Namespace) -> None:
    from sfrent.sources import rent_board

    with record_run("rent_board", limit=args.limit) as run:
        raw, raw_rows = rent_board.pull(limit=args.limit)
        processed, rows = rent_board.build(raw)
        run["rows"] = rows
        run["notes"].append(f"raw_rows={raw_rows}")
        print(f"rent_board: {raw_rows} raw rows -> {rows} listings -> {processed}")


def _pull_zori(args: argparse.Namespace) -> None:
    from sfrent.sources import zori

    with record_run("zori") as run:
        path, rows = zori.pull()
        run["rows"] = rows
        print(f"zori: {rows} zip-month rows -> {path}")


def _pull_rentcast(args: argparse.Namespace) -> None:
    from sfrent.sources import rentcast

    with record_run("rentcast", status=args.status, check_only=args.check_only) as run:
        if args.check_only:
            counts = rentcast.coverage_check()
            run["notes"].append(f"coverage={counts}")
            for status, count in counts.items():
                print(f"rentcast {status}: {count} SF listings")
            return
        raw, rows = rentcast.pull(status=args.status, max_requests=args.max_requests)
        processed, kept = rentcast.build()
        run["rows"] = kept
        run["notes"].append(f"raw_rows={rows}")
        print(f"rentcast: {rows} raw rows from {raw} -> {kept} listings -> {processed}")


def _pull_craigslist(args: argparse.Namespace) -> None:
    from sfrent.sources import craigslist

    with record_run("craigslist", max_pages=args.max_pages, max_details=args.max_details) as run:
        result = craigslist.pull(max_pages=args.max_pages, max_details=args.max_details)
        processed, kept = craigslist.build()
        run["rows"] = kept
        run["notes"].append(f"search_rows={result.search_rows} new_details={result.new_details}")
        print(
            f"craigslist: {result.search_rows} search rows, {result.new_details} new posts"
            f" -> {kept} listings -> {processed}"
        )


def _pull_neighborhoods(args: argparse.Namespace) -> None:
    from sfrent.geo import neighborhoods

    path = neighborhoods.pull()
    print(f"neighborhoods: {path}")


def _build(args: argparse.Namespace) -> None:
    from sfrent import pipeline

    with record_run("build") as run:
        summary = pipeline.build()
        run["rows"] = summary["listings"]
        print(summary)


def _commute(args: argparse.Namespace) -> None:
    import polars as pl

    from sfrent.geo.commute import HUBS, rent_by_distance_band
    from sfrent.pipeline import LISTINGS_PATH

    if args.hub:
        args.lat, args.lng = HUBS[args.hub]
    if args.lat is None or args.lng is None:
        raise SystemExit("provide --lat/--lng or --hub " + "|".join(HUBS))
    frame = pl.read_parquet(LISTINGS_PATH)
    with pl.Config(tbl_rows=50):
        print(rent_by_distance_band(frame, args.lat, args.lng, bedrooms=args.bedrooms))


def _runlog(args: argparse.Namespace) -> None:
    for entry in tail(args.n):
        details = " ".join([*entry.get("notes", []), entry.get("error", "")]).strip()
        print(
            f"{entry['started_at'][:19]}  {entry['source']:<12} {entry.get('status', '?'):<5}"
            f" rows={entry.get('rows', 0):<7} {entry.get('duration_s', 0):>7}s  {details}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sfrent", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    pull = sub.add_parser("pull", help="run a collector").add_subparsers(
        dest="source", required=True
    )
    rent_board = pull.add_parser("rent-board")
    rent_board.add_argument(
        "--limit", type=int, default=None, help="max raw rows (dev default 500)"
    )
    rent_board.set_defaults(func=_pull_rent_board)

    pull.add_parser("zori").set_defaults(func=_pull_zori)

    rentcast = pull.add_parser("rentcast")
    rentcast.add_argument("--status", choices=["active", "inactive"], default="active")
    rentcast.add_argument("--check-only", action="store_true", help="only report X-Total-Count")
    rentcast.add_argument("--max-requests", type=int, default=None)
    rentcast.set_defaults(func=_pull_rentcast)

    craigslist = pull.add_parser("craigslist")
    craigslist.add_argument("--max-pages", type=int, default=None)
    craigslist.add_argument("--max-details", type=int, default=None)
    craigslist.set_defaults(func=_pull_craigslist)

    pull.add_parser("neighborhoods").set_defaults(func=_pull_neighborhoods)

    sub.add_parser("build", help="merge processed sources into listings.parquet").set_defaults(
        func=_build
    )
    commute = sub.add_parser("commute", help="median rent by distance from a work point")
    commute.add_argument("--lat", type=float)
    commute.add_argument("--lng", type=float)
    commute.add_argument("--hub", help="named work hub instead of --lat/--lng")
    commute.add_argument("--bedrooms", type=int, default=None)
    commute.set_defaults(func=_commute)

    runlog = sub.add_parser("runlog", help="show recent runs")
    runlog.add_argument("-n", type=int, default=20)
    runlog.set_defaults(func=_runlog)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
