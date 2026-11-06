from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mibrgc import config
from mibrgc.client import VlrClient
from mibrgc.config import YEAR, team_dirs, use_team
from mibrgc.parse_list import parse_match_list
from mibrgc.tables import build_tables, write_tables

ROOT = Path(__file__).resolve().parents[1]


def fetch(raw: Path, refresh: bool = False, limit: int | None = None) -> list[dict]:
    client = VlrClient(raw, refresh=refresh)
    print(f"Match list: {config.MATCH_LIST_URL}", flush=True)
    html = client.get(config.MATCH_LIST_URL, "team-matches.html")
    series = parse_match_list(html)
    series.sort(key=lambda row: row["date"])
    if limit is not None:
        series = series[:limit]
    print(f"{len(series)} completed {config.TEAM_LABEL} series in {YEAR}", flush=True)
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


def build(raw: Path, processed: Path) -> None:
    html_path = raw / "team-matches.html"
    if not html_path.exists():
        raise SystemExit("No cached match list. Run: python -m mibrgc fetch")
    series = parse_match_list(html_path.read_text(encoding="utf-8", errors="replace"))
    frames = build_tables(series, raw)
    write_tables(frames, processed)
    print(
        f"Wrote {len(frames['matches'])} series and {len(frames['maps'])} maps to {processed}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download and tabulate a Game Changers roster from VLR.")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_parser = sub.add_parser("fetch", help="Download the season and rebuild the tables")
    fetch_parser.add_argument("--team", default="mibr-gc", help="Roster slug, for example mibr-gc or team-liquid-brazil")
    fetch_parser.add_argument("--refresh", action="store_true", help="Ignore the HTML cache")
    fetch_parser.add_argument("--limit", type=int, default=None, help="Only the first N series, oldest first")

    build_parser = sub.add_parser("build", help="Rebuild CSV tables from cached HTML")
    build_parser.add_argument("--team", default="mibr-gc", help="Roster slug, for example mibr-gc or team-liquid-brazil")

    args = parser.parse_args(argv)
    use_team(args.team)
    raw, processed = team_dirs(args.team, ROOT)
    if args.command == "fetch":
        fetch(raw, refresh=args.refresh, limit=args.limit)
        build(raw, processed)
    elif args.command == "build":
        build(raw, processed)


if __name__ == "__main__":
    main()
