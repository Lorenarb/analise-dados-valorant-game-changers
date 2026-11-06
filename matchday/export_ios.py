"""Write the brief the iOS app draws. Run after `python -m mibrgc build`."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from matchday.brief import (
    SCOPES,
    economy_note,
    economy_rows,
    economy_strategies,
    filter_scope,
    opponent_pack,
    opponent_read,
    preparation_cues,
    season_headline,
    veto_steps,
)
from matchday.copy import COPY, ROLES
from mibrgc.config import TEAMS, YEAR, team_dirs, use_team
from mibrgc.insights import map_decisions, player_assignments
from mibrgc.tables import load_tables

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ios" / "MIBRGC" / "brief.json"


def _num(value):
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return None
    return round(float(value), 4)


def _date(value) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10]


def _language(frames, decisions, lang: str, team: dict) -> dict:
    text = COPY[lang]
    roster = player_assignments(frames["players"], frames["performance"], lang=lang)
    roles = ROLES[lang]
    return {
        "title": f"{team['label']} · {'dia de jogo' if lang == 'pt' else 'match day'}",
        "caption": text["caption"],
        "report": text["report"],
        "liquid": team["rival_tab"][lang],
        "veto": text["veto"],
        "cues": text["cues"],
        "series": text["series"],
        "maps": text["maps"],
        "roundDiff": text["round_diff"],
        "attack": text["attack"],
        "defense": text["defense"],
        "call": text["call"],
        "contactLabel": text["contact"],
        "say": text["say"],
        "roster": text["roster"],
        "opponent": team["rival_label"],
        "seriesHeading": text["series_heading"],
        "mapsHeading": text["maps_heading"],
        "rosterHeading": text["roster_heading"],
        "vetoHeading": text["veto_heading"],
        "vetoCaption": text["veto_caption"],
        "cuesHeading": text["cues_heading"],
        "cuesCaption": text["cues_caption"],
        "win": text["win"],
        "loss": text["loss"],
        "rating": text["rating"],
        "economy": "Onde as rodadas se perdem" if lang == "pt" else "Where rounds are lost",
        "economyNote": economy_note(economy_rows(frames["economy_opening"], frames["economy_buys"]), lang),
        "economyPlans": economy_strategies(frames["economy_opening"], frames["economy_buys"], lang),
        "economyLabels": (
            {
                "pistol": "Pistola",
                "bonus": "Bônus",
                "full_full": "Full contra full",
                "full_half": "Full contra half",
                "full_eco": "Full contra eco",
                "half_half": "Half contra half",
                "eco_full": "Eco contra full",
            }
            if lang == "pt"
            else {
                "pistol": "Pistol",
                "bonus": "Bonus",
                "full_full": "Full vs full",
                "full_half": "Full vs half",
                "full_eco": "Full vs eco",
                "half_half": "Half vs half",
                "eco_full": "Eco vs full",
            }
        ),
        "contact": roster.get("shape") or "",
        "liquidRead": opponent_read(opponent_pack(frames), lang=lang),
        "steps": veto_steps(decisions, lang=lang),
        "cueCards": preparation_cues(frames, roster, lang=lang),
        "rosterCards": [
            {"player": card["player"], "role": roles.get(card["role"], card["role"]), "detail": card["detail"]}
            for card in roster.get("cards", [])
        ],
    }


def _scope_payload(frames: dict, scope: dict, team: dict) -> dict:
    scoped = filter_scope(frames, scope["id"])
    decisions = map_decisions(scoped["maps"])
    head = season_headline(scoped["matches"], scoped["maps"])
    maps = []
    for _, row in decisions.iterrows():
        wins, losses = (int(part) for part in str(row["record"]).split("-"))
        maps.append(
            {
                "map": row["map"],
                "wins": wins,
                "losses": losses,
                "attack": _num(row["attack"]),
                "defense": _num(row["defense"]),
                "decision": row["decision"],
            }
        )
    liquid = opponent_pack(scoped, team["rival_query"])
    series = []
    for row in liquid["series"].sort_values("date", ascending=False).itertuples(index=False):
        series.append(
            {
                "date": _date(row.date),
                "event": str(row.event),
                "stage": str(row.stage),
                "score": f"{int(row.our_score)}-{int(row.opp_score)}",
                "result": str(row.result),
                "url": str(row.url),
            }
        )
    liquid_maps = []
    pool = liquid["pool"]
    if not pool.empty:
        ordered = pool.sort_values(["win_rate", "maps"], ascending=[False, False])
        for _, row in ordered.iterrows():
            liquid_maps.append(
                {
                    "map": row["map_name"],
                    "wins": int(row["wins"]),
                    "losses": int(row["maps"] - row["wins"]),
                    "attack": _num(row["attack_win_rate"]),
                    "defense": _num(row["defense_win_rate"]),
                    "roundDiff": int(row["round_diff"]),
                }
            )
    players = []
    summary = liquid["players"]
    if not summary.empty:
        for _, row in summary.sort_values("rating", ascending=False).iterrows():
            players.append(
                {
                    "player": row["player"],
                    "rating": _num(row["rating"]),
                    "acs": _num(row["acs"]),
                    "kast": _num(row["kast"]),
                    "fk": int(row["fk"]) if "fk" in summary.columns and pd.notna(row["fk"]) else 0,
                }
            )
    liquid_head = liquid.get("headline") or season_headline(liquid["series"], liquid["maps"])
    return {
        "id": scope["id"],
        "name": scope["name"],
        "note": scope["note"],
        "headline": {
            "series": head["series"],
            "maps": head["maps"],
            "roundDiff": head["round_diff"],
            "attack": _num(head["attack"]),
            "defense": _num(head["defense"]),
        },
        "maps": maps,
        "economy": economy_rows(scoped["economy_opening"], scoped["economy_buys"]),
        "liquid": {
            "seriesRecord": liquid_head["series"],
            "mapRecord": liquid_head["maps"],
            "roundDiff": liquid_head["round_diff"],
            "attack": _num(liquid_head["attack"]),
            "defense": _num(liquid_head["defense"]),
            "series": series,
            "maps": liquid_maps,
            "players": players,
        },
        "copy": {lang: _language(scoped, decisions, lang, team) for lang in ("en", "pt")},
    }


def build_payload(root: Path | None = None) -> dict:
    root = root or ROOT
    teams = []
    for team in TEAMS:
        use_team(team["slug"])
        _, processed = team_dirs(team["slug"], root)
        if not (processed / "matches.csv").exists():
            print(f"skip {team['slug']}: no tables", flush=True)
            continue
        frames = load_tables(processed)
        teams.append(
            {
                "id": team["slug"],
                "label": team["label"],
                "scopes": [_scope_payload(frames, scope, team) for scope in SCOPES],
            }
        )
    return {"year": YEAR, "teams": teams}


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
