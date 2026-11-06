from __future__ import annotations

import pandas as pd


def weighted_mean(frame: pd.DataFrame, column: str, weight: str = "rounds") -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    values = frame[[column, weight]].dropna()
    values = values[values[weight] > 0]
    total = values[weight].sum()
    if total == 0 or values.empty:
        return None
    return float((values[column] * values[weight]).sum() / total)


def rate(won: float, played: float) -> float | None:
    if not played:
        return None
    return float(won) / float(played)


def our_map_rows(maps: pd.DataFrame) -> pd.DataFrame:
    if maps.empty:
        return maps
    frame = maps.dropna(subset=["our_score", "opp_score"]).copy()
    frame["rounds"] = frame["our_score"] + frame["opp_score"]
    frame["win"] = frame["result"].eq("win").astype(int)
    return frame


def our_player_rows(players: pd.DataFrame) -> pd.DataFrame:
    if players.empty:
        return players
    frame = players[(players["is_us"] == True) & (players["side"] == "both")].copy()  # noqa: E712
    return frame


def map_pool(maps: pd.DataFrame) -> pd.DataFrame:
    frame = our_map_rows(maps)
    if frame.empty:
        return frame
    grouped = (
        frame.groupby("map_name", dropna=False)
        .agg(
            maps=("map_name", "size"),
            wins=("win", "sum"),
            rounds_for=("our_score", "sum"),
            rounds_against=("opp_score", "sum"),
            attack_rounds=("our_attack_rounds", "sum"),
            defense_rounds=("our_defense_rounds", "sum"),
        )
        .reset_index()
    )
    attack_played = []
    defense_played = []
    for map_name, group in frame.groupby("map_name"):
        # Attack rounds played ≈ our attack wins + opponent defense wins.
        attack_played.append((map_name, (group["our_attack_rounds"].fillna(0) + group["opp_defense_rounds"].fillna(0)).sum()))
        defense_played.append((map_name, (group["our_defense_rounds"].fillna(0) + group["opp_attack_rounds"].fillna(0)).sum()))
    attack_played = dict(attack_played)
    defense_played = dict(defense_played)
    grouped["attack_played"] = grouped["map_name"].map(attack_played)
    grouped["defense_played"] = grouped["map_name"].map(defense_played)
    grouped["win_rate"] = grouped["wins"] / grouped["maps"]
    grouped["round_diff"] = grouped["rounds_for"] - grouped["rounds_against"]
    grouped["attack_win_rate"] = grouped.apply(lambda row: rate(row["attack_rounds"], row["attack_played"]), axis=1)
    grouped["defense_win_rate"] = grouped.apply(lambda row: rate(row["defense_rounds"], row["defense_played"]), axis=1)
    return grouped.sort_values(["win_rate", "maps"], ascending=[False, False])


def event_summary(matches: pd.DataFrame, maps: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches
    series = (
        matches.assign(win=matches["result"].eq("win").astype(int), loss=matches["result"].eq("loss").astype(int))
        .groupby("event", dropna=False)
        .agg(series=("match_id", "size"), series_wins=("win", "sum"), series_losses=("loss", "sum"))
        .reset_index()
    )
    map_frame = our_map_rows(maps)
    if map_frame.empty:
        return series
    by_map = (
        map_frame.groupby("event", dropna=False)
        .agg(
            maps=("map_name", "size"),
            map_wins=("win", "sum"),
            rounds_for=("our_score", "sum"),
            rounds_against=("opp_score", "sum"),
        )
        .reset_index()
    )
    by_map["map_win_rate"] = by_map["map_wins"] / by_map["maps"]
    by_map["round_diff"] = by_map["rounds_for"] - by_map["rounds_against"]
    return series.merge(by_map, on="event", how="left").sort_values("series", ascending=False)


def player_summary(players: pd.DataFrame) -> pd.DataFrame:
    frame = our_player_rows(players)
    if frame.empty:
        return frame
    rows = []
    for player_id, group in frame.groupby("player_id"):
        name = group.sort_values("date")["player"].iloc[-1]
        agents = (
            group["agent"].fillna("").replace("", pd.NA).dropna().value_counts().head(3).index.tolist()
        )
        kills = group["kills"].sum()
        deaths = group["deaths"].sum()
        rows.append(
            {
                "player_id": player_id,
                "player": name,
                "maps": len(group),
                "rounds": group["rounds"].sum(),
                "rating": weighted_mean(group, "rating"),
                "acs": weighted_mean(group, "acs"),
                "kast": weighted_mean(group, "kast"),
                "adr": weighted_mean(group, "adr"),
                "hs": weighted_mean(group, "hs"),
                "kills": kills,
                "deaths": deaths,
                "assists": group["assists"].sum(),
                "kd": rate(kills, deaths),
                "fk": group["fk"].sum(),
                "fd": group["fd"].sum(),
                "fk_diff": group["fk_diff"].sum(),
                "agents": ", ".join(agents),
            }
        )
    return pd.DataFrame(rows).sort_values("rating", ascending=False)


def player_by_event(players: pd.DataFrame) -> pd.DataFrame:
    frame = our_player_rows(players)
    if frame.empty:
        return frame
    rows = []
    for (player_id, event), group in frame.groupby(["player_id", "event"]):
        kills = group["kills"].sum()
        deaths = group["deaths"].sum()
        rows.append(
            {
                "player_id": player_id,
                "player": group.sort_values("date")["player"].iloc[-1],
                "event": event,
                "maps": len(group),
                "rating": weighted_mean(group, "rating"),
                "acs": weighted_mean(group, "acs"),
                "kast": weighted_mean(group, "kast"),
                "adr": weighted_mean(group, "adr"),
                "kd": rate(kills, deaths),
                "fk_diff": group["fk_diff"].sum(),
            }
        )
    return pd.DataFrame(rows).sort_values(["event", "rating"], ascending=[True, False])


def side_rates(maps: pd.DataFrame) -> dict[str, float | None]:
    frame = our_map_rows(maps)
    if frame.empty:
        return {"attack": None, "defense": None}
    attack_won = frame["our_attack_rounds"].fillna(0).sum()
    defense_won = frame["our_defense_rounds"].fillna(0).sum()
    attack_played = (frame["our_attack_rounds"].fillna(0) + frame["opp_defense_rounds"].fillna(0)).sum()
    defense_played = (frame["our_defense_rounds"].fillna(0) + frame["opp_attack_rounds"].fillna(0)).sum()
    return {"attack": rate(attack_won, attack_played), "defense": rate(defense_won, defense_played)}
