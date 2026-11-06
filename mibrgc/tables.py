from __future__ import annotations

from pathlib import Path

import pandas as pd

from mibrgc import config
from mibrgc.config import YEAR
from mibrgc.parse_match import parse_match


PROCESSED_FILES = (
    "matches.csv",
    "maps.csv",
    "players.csv",
    "performance.csv",
    "economy_opening.csv",
    "economy_buys.csv",
    "rounds.csv",
)


def _series_fields(series: dict) -> dict:
    return {
        "match_id": series["match_id"],
        "url": series["url"],
        "date": series["date"],
        "event": series["event"],
        "stage": series["stage"],
        "opponent": series["opponent"],
        "opponent_tag": series["opponent_tag"],
    }


def build_tables(series_list: list[dict], raw_dir: Path) -> dict[str, pd.DataFrame]:
    match_rows = []
    map_rows = []
    player_rows = []
    performance_rows = []
    opening_rows = []
    buy_rows = []
    round_rows = []

    for series in series_list:
        match_rows.append(series)
        match_id = series["match_id"]
        overview = raw_dir / "matches" / f"{match_id}-overview.html"
        if not overview.exists():
            continue
        performance = raw_dir / "matches" / f"{match_id}-performance.html"
        economy = raw_dir / "matches" / f"{match_id}-economy.html"
        maps = parse_match(
            overview.read_text(encoding="utf-8", errors="replace"),
            performance.read_text(encoding="utf-8", errors="replace") if performance.exists() else None,
            economy.read_text(encoding="utf-8", errors="replace") if economy.exists() else None,
        )
        base = _series_fields(series)
        for game in maps:
            game_base = {
                **base,
                "game_id": game["game_id"],
                "map_number": game["map_number"],
                "map_name": game["map_name"],
                "rounds": (game["our_score"] or 0) + (game["opp_score"] or 0),
            }
            map_rows.append(
                {
                    **game_base,
                    "our_score": game["our_score"],
                    "opp_score": game["opp_score"],
                    "result": game["result"],
                    "our_attack_rounds": game["our_attack_rounds"],
                    "our_defense_rounds": game["our_defense_rounds"],
                    "opp_attack_rounds": game["opp_attack_rounds"],
                    "opp_defense_rounds": game["opp_defense_rounds"],
                    "duration": game["duration"],
                    "picked_by": game["picked_by"],
                }
            )
            for player in game["players"]:
                player_rows.append({**game_base, **player, "map_result": game["result"]})
            for player in game["performance"]:
                performance_rows.append({**game_base, **player})
            for row in game["economy_opening"]:
                opening_rows.append({**game_base, **row})
            for row in game["economy_buys"]:
                buy_rows.append({**game_base, **row})
            for rnd in game["rounds"]:
                round_rows.append({**game_base, **rnd, "map_result": game["result"]})

    frames = {
        "matches": pd.DataFrame(match_rows),
        "maps": pd.DataFrame(map_rows),
        "players": pd.DataFrame(player_rows),
        "performance": pd.DataFrame(performance_rows),
        "economy_opening": pd.DataFrame(opening_rows),
        "economy_buys": pd.DataFrame(buy_rows),
        "rounds": pd.DataFrame(round_rows),
    }
    for frame in frames.values():
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"])
    return frames


def write_tables(frames: dict[str, pd.DataFrame], processed_dir: Path) -> None:
    processed_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False)
    summary = processed_dir / "README.txt"
    matches = frames["matches"]
    maps = frames["maps"]
    summary.write_text(
        "\n".join(
            [
                f"team: {config.TEAM_LABEL}",
                f"year: {YEAR}",
                f"series: {len(matches)}",
                f"maps: {len(maps)}",
                f"source: {config.MATCH_LIST_URL}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def load_tables(processed_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    for name in ("matches", "maps", "players", "performance", "economy_opening", "economy_buys", "rounds"):
        path = processed_dir / f"{name}.csv"
        frame = pd.read_csv(path)
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"])
        frames[name] = frame
    return frames
