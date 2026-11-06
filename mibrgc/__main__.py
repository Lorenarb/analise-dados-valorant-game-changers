from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mibrgc.client import VlrClient
from mibrgc.config import MATCH_LIST_URL, TEAM_LABEL, YEAR
from mibrgc.parse_list import parse_match_list
from mibrgc.tables import build_tables, write_tables

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def fetch(refresh: bool = False, limit: int | None = None) -> list[dict]:
    client = VlrClient(RAW, refresh=refresh)
    print(f"Match list: {MATCH_LIST_URL}", flush=True)
    html = client.get(MATCH_LIST_URL, "team-matches.html")
    series = parse_match_list(html)
    series.sort(key=lambda row: row["date"])
    if limit is not None:
        series = series[:limit]
    print(f"{len(series)} completed {TEAM_LABEL} series in {YEAR}", flush=True)
    for index, row in enumerate(series, start=1):
        match_id = row["match_id"]
        base = row["url"]
        print(f"[{index}/{len(series)}] {row['date']} {row['event']} vs {row['opponent']}", flush=True)
        try:
            client.get(base, f"matches/{match_id}-overview.html")
            client.get(f"{base}?tab=performance", f"matches/{match_id}-performance.html")
            client.get(f"{base}?tab=economy", f"matches/{match_id}-economy.html")
        except Exception as exc:  # one broken page should not drop the season
            print(f"  skipped {match_id}: {exc}", file=sys.stderr, flush=True)
    return series


def build() -> None:
    html_path = RAW / "team-matches.html"
    if not html_path.exists():
        raise SystemExit("No cached match list. Run: python -m mibrgc fetch")
    series = parse_match_list(html_path.read_text(encoding="utf-8", errors="replace"))
    frames = build_tables(series, RAW)
    write_tables(frames, PROCESSED)
    print(
        f"Wrote {len(frames['matches'])} series and {len(frames['maps'])} maps to {PROCESSED}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download and tabulate MIBR GC VLR matches.")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_parser = sub.add_parser("fetch", help="Download the season and rebuild the tables")
    fetch_parser.add_argument("--refresh", action="store_true", help="Ignore the HTML cache")
    fetch_parser.add_argument("--limit", type=int, default=None, help="Only the first N series, oldest first")

    sub.add_parser("build", help="Rebuild CSV tables from cached HTML")

    args = parser.parse_args(argv)
    if args.command == "fetch":
        fetch(refresh=args.refresh, limit=args.limit)
        build()
    elif args.command == "build":
        build()


if __name__ == "__main__":
    main()
