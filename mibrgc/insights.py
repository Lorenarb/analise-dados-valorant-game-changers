from __future__ import annotations

import pandas as pd

from mibrgc.metrics import map_pool, our_map_rows, our_player_rows, player_summary, rate, side_rates, weighted_mean

# Tune these before treating a split as something to ban, keep, or coach.
MIN_MAPS = 4
MIN_PLAYER_MAPS = 8
WEAK_MAP_WIN_RATE = 0.45
STRONG_MAP_WIN_RATE = 0.60
SIDE_GAP = 0.08
PISTOL_WEAK = 0.45
FULL_BUY_WEAK = 0.48


def _pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.0%}"


def _notes_from_maps(maps: pd.DataFrame) -> list[str]:
    notes = []
    pool = map_pool(maps)
    if pool.empty:
        return notes
    enough = pool[pool["maps"] >= MIN_MAPS]
    if enough.empty:
        return notes
    weak = enough[enough["win_rate"] < WEAK_MAP_WIN_RATE].sort_values("win_rate")
    strong = enough[enough["win_rate"] >= STRONG_MAP_WIN_RATE].sort_values("win_rate", ascending=False)
    if not weak.empty:
        row = weak.iloc[0]
        notes.append(
            f"Ban candidate: {row['map_name']} is {int(row['wins'])}-{int(row['maps'] - row['wins'])} "
            f"({_pct(row['win_rate'])}) over {int(row['maps'])} maps, "
            f"attack {_pct(row['attack_win_rate'])} and defense {_pct(row['defense_win_rate'])}. "
            "Leave it in only when the opponent's attack on that map is the weaker side."
        )
    if not strong.empty:
        row = strong.iloc[0]
        notes.append(
            f"Keep: {row['map_name']} is {int(row['wins'])}-{int(row['maps'] - row['wins'])} "
            f"({_pct(row['win_rate'])}). It is the first permaban to take away from opponents."
        )
    sided = enough.dropna(subset=["attack_win_rate", "defense_win_rate"]).copy()
    if not sided.empty:
        sided["gap"] = sided["attack_win_rate"] - sided["defense_win_rate"]
        leak = sided[sided["gap"] <= -SIDE_GAP].sort_values("gap")
        if not leak.empty:
            row = leak.iloc[0]
            notes.append(
                f"Attack leak on {row['map_name']}: attack {_pct(row['attack_win_rate'])} vs "
                f"defense {_pct(row['defense_win_rate'])}. Review default executes and the post-plant, "
                "not the retake."
            )
        fortress = sided[sided["gap"] >= SIDE_GAP].sort_values("gap", ascending=False)
        if not fortress.empty:
            row = fortress.iloc[0]
            notes.append(
                f"Defense leak on {row['map_name']}: defense {_pct(row['defense_win_rate'])} vs "
                f"attack {_pct(row['attack_win_rate'])}. Review the site hold and the retake. "
                "Attack is already winning rounds on this map, so the comp should not depend on retakes."
            )
    sides = side_rates(maps)
    if sides["attack"] is not None and sides["defense"] is not None:
        notes.append(
            f"Season sides: attack {_pct(sides['attack'])}, defense {_pct(sides['defense'])}. "
            + (
                "The roster wins more gunfights on defense, so comps should protect retakes and still add one execute duel."
                if sides["defense"] - sides["attack"] >= SIDE_GAP
                else "Attack and defense are close. Map pool choices matter more than a side-specific rebuild."
                if abs(sides["defense"] - sides["attack"]) < SIDE_GAP
                else "Attack is ahead of defense. Prioritize site holds and the player who is dying first on defense."
            )
        )
    return notes


def _notes_from_economy(opening: pd.DataFrame, buys: pd.DataFrame) -> list[str]:
    notes = []
    if not opening.empty:
        ours = opening[opening["is_us"] == True]  # noqa: E712
        pistol = rate(ours["pistol_won"].sum(), ours["pistol_played"].sum())
        conversion = rate(ours["conversion_won"].sum(), ours["conversion_played"].sum())
        if pistol is not None:
            text = f"Pistols: {_pct(pistol)} ({int(ours['pistol_won'].sum())}/{int(ours['pistol_played'].sum())})."
            if conversion is not None:
                text += f" Conversion of the pistol into the next buy is {_pct(conversion)}."
            if pistol < PISTOL_WEAK:
                text += " That is a coaching priority: pistol comps, the bonus, and who takes the first duel."
            notes.append(text)
    if not buys.empty:
        ours = buys[buys["is_us"] == True]  # noqa: E712
        full = ours[(ours["our_buy"] == "full") & (ours["opp_buy"] == "full")]
        full_rate = rate(full["won"].sum(), full["played"].sum()) if not full.empty else None
        anti = ours[(ours["our_buy"] == "full") & (ours["opp_buy"] == "eco")]
        anti_rate = rate(anti["won"].sum(), anti["played"].sum()) if not anti.empty else None
        if full_rate is not None:
            label = "below a stable full-buy baseline" if full_rate < FULL_BUY_WEAK else "in a playable range"
            notes.append(
                f"Full buy vs full buy: {_pct(full_rate)} ({int(full['won'].sum())}/{int(full['played'].sum())}), {label}. "
                "Use this as the read on gun rounds, separate from eco swings."
            )
        if anti_rate is not None and anti["played"].sum() >= 8 and anti_rate < 0.8:
            notes.append(
                f"Anti-eco is {_pct(anti_rate)} on full buys against ecos "
                f"({int(anti['won'].sum())}/{int(anti['played'].sum())}). "
                "Save a VOD pass for force rounds before changing the map pool."
            )
    return notes


def _notes_from_players(players: pd.DataFrame, performance: pd.DataFrame) -> list[str]:
    notes = []
    summary = player_summary(players)
    if summary.empty:
        return notes
    regulars = summary[summary["maps"] >= MIN_PLAYER_MAPS]
    if regulars.empty:
        regulars = summary
    best = regulars.iloc[0]
    worst = regulars.sort_values("rating").iloc[0]
    notes.append(
        f"Form guide: {best['player']} leads the regulars at {best['rating']:.2f} rating "
        f"over {int(best['maps'])} maps ({best['agents']}). "
        f"{worst['player']} is the low end at {worst['rating']:.2f}, "
        f"KAST {_pct(worst['kast'])}, first-duel diff {int(worst['fk_diff']):+d}."
    )
    duelists = regulars[regulars["fk_diff"] < 0].sort_values("fk_diff")
    if not duelists.empty:
        row = duelists.iloc[0]
        notes.append(
            f"Opening duels: {row['player']} is {int(row['fk_diff']):+d} first kills minus first deaths "
            f"on {row['agents']}. If that player is the entry, the contact needs a second body. "
            "If they are the anchor, the negative diff is a site-hold problem, not an execute problem."
        )
    if not performance.empty:
        ours = performance[performance["is_us"] == True]  # noqa: E712
        if not ours.empty:
            # Performance tables do not link player ids, so the name is the key.
            grouped = ours.groupby("player", as_index=False).agg(
                k3=("k3", "sum"), k4=("k4", "sum"), k5=("k5", "sum"), clutches=("clutch_1v2", "sum")
            )
            grouped["multies"] = grouped["k3"] + grouped["k4"] + grouped["k5"]
            top = grouped.sort_values("multies", ascending=False).iloc[0]
            if top["multies"] > 0 and pd.notna(top["player"]):
                notes.append(
                    f"Multikill load sits on {top['player']}: {int(top['k3'])} triples, "
                    f"{int(top['k4'])} quads, {int(top['k5'])} aces, plus {int(top['clutches'])} 1v2 clutches. "
                    "Set pieces should give that player the second contact, not the utility dump."
                )
    return notes


def _notes_from_rounds(rounds: pd.DataFrame) -> list[str]:
    if rounds.empty:
        return []
    ours = rounds.copy()
    attack = ours[ours["our_side"] == "attack"]
    if attack.empty:
        return []
    lost = attack[attack["winner_is_us"] == False]  # noqa: E712
    defuses = (lost["win_method"] == "defuse").sum()
    played = len(attack)
    if played < 20 or defuses == 0:
        return []
    share = defuses / played
    if share < 0.12:
        return []
    return [
        f"Post-plant: opponents defused {int(defuses)} of {played} attack rounds ({share:.0%}). "
        "That is the plant-and-leave pattern. Pair the post-plant positions with the player who is already winning opening duels."
    ]


def _notes_from_events(matches: pd.DataFrame, maps: pd.DataFrame) -> list[str]:
    if matches.empty or maps.empty:
        return []
    frame = our_map_rows(maps)
    rows = []
    for event, group in frame.groupby("event"):
        if group["match_id"].nunique() < 3:
            continue
        rows.append((event, group["win"].mean(), len(group), group["match_id"].nunique()))
    if len(rows) < 2:
        return []
    event, win_rate, map_count, series_count = sorted(rows, key=lambda item: item[1])[0]
    best = sorted(rows, key=lambda item: item[1], reverse=True)[0]
    notes = [
        f"Event floor: {event} is the weakest sample with at least three series, "
        f"{win_rate:.0%} map win rate across {map_count} maps in {series_count} series."
    ]
    if best[0] != event:
        notes.append(
            f"Event ceiling: {best[0]} is {best[1]:.0%} on maps ({best[2]} maps, {best[3]} series). "
            "Compare comps and the map pool between those two events before copying a playbook forward."
        )
    return notes


def strategy_notes(frames: dict[str, pd.DataFrame]) -> list[dict[str, str]]:
    """Short coaching reads. Each one is a hypothesis from the public stats, not a VOD verdict."""
    sections = [
        ("Map pool", _notes_from_maps(frames["maps"])),
        ("Championships", _notes_from_events(frames["matches"], frames["maps"])),
        ("Players", _notes_from_players(frames["players"], frames["performance"])),
        ("Economy", _notes_from_economy(frames["economy_opening"], frames["economy_buys"])),
        ("Rounds", _notes_from_rounds(frames["rounds"])),
    ]
    notes = []
    for area, items in sections:
        for item in items:
            notes.append({"area": area, "detail": item})
    if not notes:
        notes.append(
            {
                "area": "Sample",
                "detail": "Not enough 2026 maps yet to separate a trend from one series. Fetch again after the next event.",
            }
        )
    return notes


def _count_phrase(count, singular: str) -> str:
    number = int(count)
    word = singular if number == 1 else f"{singular}s"
    return f"{number} {word}"


def _map_record(row: pd.Series) -> str:
    wins = int(row["wins"])
    losses = int(row["maps"] - row["wins"])
    return f"{row['map_name']} {wins}-{losses}"


def _standout_player(players: pd.DataFrame, performance: pd.DataFrame) -> tuple[str, str]:
    """Rating leader for one event, plus the stat that made them the read."""
    summary = player_summary(players)
    if summary.empty:
        return "", "No player rows for this event."
    summary = summary.sort_values(["rating", "acs"], ascending=False)
    top = summary.iloc[0]
    reason = (
        f"Led the event at {top['rating']:.2f} rating over {int(top['maps'])} maps "
        f"({top['agents']}), with ACS {top['acs']:.0f}, KAST {_pct(top['kast'])}, "
        f"and a first-duel differential of {int(top['fk_diff']):+d}."
    )
    if len(summary) > 1 and pd.notna(top["rating"]) and pd.notna(summary.iloc[1]["rating"]):
        second = summary.iloc[1]
        gap = float(top["rating"]) - float(second["rating"])
        if gap >= 0.08:
            reason += (
                f" That is {gap:.2f} above {second['player']} ({second['rating']:.2f}), "
                "so the event's level sat on this player."
            )
        else:
            reason += (
                f" {second['player']} was close at {second['rating']:.2f}, "
                "so the rating lead was shared."
            )
    if not performance.empty and "is_us" in performance.columns:
        ours = performance[performance["is_us"] == True]  # noqa: E712
        if not ours.empty and {"k3", "k4", "k5"}.issubset(ours.columns):
            grouped = ours.groupby("player", as_index=False).agg(k3=("k3", "sum"), k4=("k4", "sum"), k5=("k5", "sum"))
            grouped["multies"] = grouped["k3"] + grouped["k4"] + grouped["k5"]
            leader = grouped.sort_values("multies", ascending=False).iloc[0]
            multikill_bits = [
                _count_phrase(leader["k3"], "triple"),
                _count_phrase(leader["k4"], "quad"),
                _count_phrase(leader["k5"], "ace"),
            ]
            multikill_bits = [bit for bit, count in zip(multikill_bits, (leader["k3"], leader["k4"], leader["k5"])) if int(count) > 0]
            if multikill_bits and leader["player"] == top["player"]:
                reason += " They also held the multikill count: " + ", ".join(multikill_bits) + "."
            elif multikill_bits:
                reason += (
                    f" Multikills sat with {leader['player']} ({', '.join(multikill_bits)}), "
                    "a different job from the rating lead."
                )
    return str(top["player"]), reason


def championship_reports(frames: dict[str, pd.DataFrame]) -> list[dict]:
    """One written summary per championship: record, map pool, and the player who defined it."""
    matches = frames.get("matches", pd.DataFrame())
    maps = frames.get("maps", pd.DataFrame())
    players = frames.get("players", pd.DataFrame())
    performance = frames.get("performance", pd.DataFrame())
    if matches.empty or "event" not in matches.columns:
        return []

    order = matches.groupby("event")["date"].min().sort_values(ascending=False)
    reports = []
    for event in order.index:
        event_matches = matches[matches["event"] == event].sort_values("date")
        event_maps = maps[maps["event"] == event] if not maps.empty and "event" in maps.columns else maps.iloc[0:0]
        event_players = (
            players[players["event"] == event] if not players.empty and "event" in players.columns else players.iloc[0:0]
        )
        event_perf = (
            performance[performance["event"] == event]
            if not performance.empty and "event" in performance.columns
            else performance.iloc[0:0]
        )
        map_rows = our_map_rows(event_maps)
        series_wins = int(event_matches["result"].eq("win").sum())
        series_losses = int(event_matches["result"].eq("loss").sum())
        map_wins = int(map_rows["win"].sum()) if not map_rows.empty else 0
        map_count = len(map_rows)
        round_diff = int(map_rows["our_score"].sum() - map_rows["opp_score"].sum()) if not map_rows.empty else 0
        sides = side_rates(event_maps)
        pool = map_pool(event_maps)
        best_map = ""
        worst_map = ""
        if not pool.empty:
            repeated = pool[pool["maps"] >= 2]
            source = repeated if not repeated.empty else pool
            best = source.sort_values(["win_rate", "maps"], ascending=[False, False]).iloc[0]
            worst = source.sort_values(["win_rate", "maps"], ascending=[True, False]).iloc[0]
            best_map = _map_record(best)
            if best["map_name"] != worst["map_name"]:
                worst_map = _map_record(worst)
        player, reason = _standout_player(event_players, event_perf)
        series_bits = [
            f"{row.opponent} {int(row.our_score)}-{int(row.opp_score)}"
            for row in event_matches.itertuples(index=False)
        ]
        summary = (
            f"{series_wins}-{series_losses} in series and {map_wins}-{map_count - map_wins} on maps, "
            f"round differential {round_diff:+d}. "
            f"Attack {_pct(sides['attack'])}, defense {_pct(sides['defense'])}."
        )
        if best_map:
            summary += f" Best map: {best_map}."
        if worst_map:
            summary += f" Worst map: {worst_map}."
        if series_bits:
            summary += " Series: " + ", ".join(series_bits) + "."
        reports.append(
            {
                "event": event,
                "series_wins": series_wins,
                "series_losses": series_losses,
                "map_wins": map_wins,
                "map_losses": map_count - map_wins,
                "round_diff": round_diff,
                "attack": sides["attack"],
                "defense": sides["defense"],
                "summary": summary,
                "player": player,
                "reason": reason,
            }
        )
    return reports


ROLES = {
    "jett": "duelist",
    "neon": "duelist",
    "raze": "duelist",
    "phoenix": "duelist",
    "reyna": "duelist",
    "yoru": "duelist",
    "iso": "duelist",
    "waylay": "duelist",
    "sova": "initiator",
    "fade": "initiator",
    "skye": "initiator",
    "kayo": "initiator",
    "kay/o": "initiator",
    "breach": "initiator",
    "tejo": "initiator",
    "gekko": "initiator",
    "omen": "controller",
    "astra": "controller",
    "brimstone": "controller",
    "viper": "controller",
    "harbor": "controller",
    "clove": "controller",
    "cypher": "sentinel",
    "killjoy": "sentinel",
    "chamber": "sentinel",
    "sage": "sentinel",
    "vyse": "sentinel",
    "deadlock": "sentinel",
}


def _agent_floor(maps_played: int) -> int:
    if maps_played >= 20:
        return 8
    if maps_played >= 8:
        return 4
    return 2


def _role_for(agents: pd.Series) -> str:
    counts: dict[str, int] = {}
    for agent, played in agents.dropna().value_counts().items():
        role = ROLES.get(str(agent).casefold(), "")
        if role:
            counts[role] = counts.get(role, 0) + int(played)
    if not counts:
        return "flex"
    return max(counts, key=counts.get)


def map_decisions(maps: pd.DataFrame) -> pd.DataFrame:
    """One call per map with enough games: ban, keep, or which side to play."""
    pool = map_pool(maps)
    if pool.empty:
        return pool
    pool = pool[pool["maps"] >= MIN_MAPS].copy()
    if pool.empty:
        return pool
    rows = []
    for _, row in pool.iterrows():
        attack = row["attack_win_rate"]
        defense = row["defense_win_rate"]
        gap = (attack or 0) - (defense or 0)
        record = f"{int(row['wins'])}-{int(row['maps'] - row['wins'])}"
        weak_side = pd.notna(attack) and pd.notna(defense) and abs(gap) >= SIDE_GAP and min(attack, defense) < 0.49
        if row["win_rate"] < WEAK_MAP_WIN_RATE:
            decision = "Ban"
            note = "Leave it in only when the opponent's stronger side is the one you can avoid."
        elif weak_side and gap > 0:
            decision = "Attack side"
            note = "Defense is the leak. Take it when the veto lets you start on attack."
        elif weak_side:
            decision = "Defense side"
            note = "Attack is the leak. Review the execute before this stays in the pool."
        elif row["win_rate"] >= STRONG_MAP_WIN_RATE:
            decision = "Keep"
            note = "First map to take away from the opponent."
        elif pd.notna(attack) and pd.notna(defense) and abs(gap) >= SIDE_GAP:
            if gap > 0:
                decision = "Attack side"
                note = "The map is playable, and the rounds are won on attack."
            else:
                decision = "Defense side"
                note = "The map is playable, and the rounds are won on defense."
        else:
            decision = "Playable"
            note = "Win rate and both sides sit in the middle. Not a ban and not a permaban."
        rows.append(
            {
                "map": row["map_name"],
                "record": record,
                "maps": int(row["maps"]),
                "attack": attack,
                "defense": defense,
                "decision": decision,
                "note": note,
            }
        )
    order = {"Ban": 0, "Attack side": 1, "Defense side": 2, "Keep": 3, "Playable": 4}
    frame = pd.DataFrame(rows)
    frame["_order"] = frame["decision"].map(order)
    return frame.sort_values(["_order", "maps"], ascending=[True, False]).drop(columns="_order")


def round_plan(opening: pd.DataFrame, buys: pd.DataFrame, rounds: pd.DataFrame) -> list[dict[str, str]]:
    """Practice target for pistols, gun rounds, anti-ecos, and post-plants."""
    items: list[dict[str, str]] = []
    if not opening.empty and "is_us" in opening.columns:
        ours = opening[opening["is_us"] == True]  # noqa: E712
        pistol = rate(ours["pistol_won"].sum(), ours["pistol_played"].sum())
        conversion = rate(ours["conversion_won"].sum(), ours["conversion_played"].sum())
        if pistol is not None:
            result = f"Pistols {_pct(pistol)} ({int(ours['pistol_won'].sum())}/{int(ours['pistol_played'].sum())})"
            if conversion is not None:
                result += f", conversion {_pct(conversion)} ({int(ours['conversion_won'].sum())}/{int(ours['conversion_played'].sum())})"
            if pistol < PISTOL_WEAK:
                practice = "Run pistol comps, the first duel, and the bonus as their own block."
            else:
                practice = "Pistols are stable. Keep the block only for the conversion round."
            items.append({"round": "Pistol", "result": result, "practice": practice})
    if not buys.empty and "is_us" in buys.columns:
        ours = buys[buys["is_us"] == True]  # noqa: E712
        full = ours[(ours["our_buy"] == "full") & (ours["opp_buy"] == "full")]
        anti = ours[(ours["our_buy"] == "full") & (ours["opp_buy"] == "eco")]
        full_rate = rate(full["won"].sum(), full["played"].sum()) if not full.empty else None
        anti_rate = rate(anti["won"].sum(), anti["played"].sum()) if not anti.empty else None
        if full_rate is not None:
            items.append(
                {
                    "round": "Full buy vs full buy",
                    "result": f"{_pct(full_rate)} ({int(full['won'].sum())}/{int(full['played'].sum())})",
                    "practice": (
                        "Gun-round block before any map-pool change."
                        if full_rate < FULL_BUY_WEAK
                        else "Gun rounds are in a playable range. Use this as the baseline, separate from eco swings."
                    ),
                }
            )
        if anti_rate is not None and anti["played"].sum() >= 8:
            items.append(
                {
                    "round": "Full buy vs eco",
                    "result": f"{_pct(anti_rate)} ({int(anti['won'].sum())}/{int(anti['played'].sum())})",
                    "practice": (
                        "VOD the force rounds before changing a ban."
                        if anti_rate < 0.8
                        else "Anti-ecos are being closed. Leave them off the priority list."
                    ),
                }
            )
    if not rounds.empty and "our_side" in rounds.columns:
        attack = rounds[rounds["our_side"] == "attack"]
        if len(attack) >= 20:
            lost = attack[attack["winner_is_us"] == False]  # noqa: E712
            defuses = int((lost["win_method"] == "defuse").sum())
            share = defuses / len(attack)
            items.append(
                {
                    "round": "Attack post-plant",
                    "result": f"Opponents defused {defuses} of {len(attack)} attack rounds ({share:.0%})",
                    "practice": (
                        "Pair the post-plant positions with the player who is winning opening duels."
                        if share >= 0.12
                        else "Post-plants are not the leak. Spend the review on the opening duel."
                    ),
                }
            )
    return items


def _side_stats(players: pd.DataFrame, player: str) -> dict[str, dict]:
    frame = players[(players["is_us"] == True) & (players["player"] == player) & (players["side"].isin(["attack", "defense"]))]  # noqa: E712
    found = {}
    for side, group in frame.groupby("side"):
        found[side] = {
            "rating": weighted_mean(group, "rating"),
            "fk_diff": int(group["fk_diff"].sum()) if group["fk_diff"].notna().any() else 0,
        }
    return found


def _agent_rows(group: pd.DataFrame) -> list[dict]:
    rows = []
    for agent, played in group.groupby("agent"):
        if not str(agent).strip():
            continue
        rating = weighted_mean(played, "rating")
        if rating is None:
            continue
        rows.append(
            {
                "agent": str(agent),
                "maps": len(played),
                "rating": rating,
                "fk_diff": int(played["fk_diff"].sum()) if played["fk_diff"].notna().any() else 0,
            }
        )
    return rows


def _agent_plan(group: pd.DataFrame) -> dict:
    """Default agent from volume plus rating. A small-sample spike does not replace the home agent."""
    rows = _agent_rows(group)
    floor = _agent_floor(len(group))
    qualified = [row for row in rows if row["maps"] >= floor]
    if not qualified:
        return {"role": _role_for(group["agent"]), "lines": []}
    best = max(qualified, key=lambda row: row["rating"])
    volume = max(qualified, key=lambda row: row["maps"])
    gap = best["rating"] - volume["rating"]
    if volume["agent"] == best["agent"] or gap <= 0.08 or (volume["maps"] >= 2 * best["maps"] and gap <= 0.15):
        home = volume if gap <= 0.15 else best
    else:
        home = best
    if volume["agent"] != best["agent"] and volume["maps"] >= 2 * best["maps"] and gap <= 0.15:
        home = volume
    role = ROLES.get(home["agent"].casefold(), _role_for(group["agent"]))
    lines = [f"Default {home['agent']} ({home['rating']:.2f} over {home['maps']} maps)."]
    if best["agent"] != home["agent"]:
        lines.append(
            f"{best['agent']} is higher on a smaller sample ({best['rating']:.2f} over {best['maps']} maps). "
            "Use it when the map wants that kit."
        )
    home_role = ROLES.get(home["agent"].casefold(), "")
    companion = [
        row
        for row in qualified
        if row["agent"] not in {home["agent"], best["agent"]}
        and home["rating"] - row["rating"] <= 0.08
        and row["fk_diff"] >= 0
        and ROLES.get(row["agent"].casefold(), "") == home_role
    ]
    if companion:
        next_agent = max(companion, key=lambda row: row["rating"])
        lines.append(f"{next_agent['agent']} stays with the default ({next_agent['rating']:.2f} over {next_agent['maps']} maps).")
    if volume["agent"] != home["agent"] and volume["rating"] + 0.05 < home["rating"]:
        lines.append(
            f"{volume['agent']} is the most played agent at a lower rating "
            f"({volume['rating']:.2f} over {volume['maps']} maps). Move those rounds onto {home['agent']}."
        )
    drops = []
    cautions = []
    for row in qualified:
        if row["agent"] in {home["agent"], best["agent"]}:
            continue
        if any(line.startswith(row["agent"]) for line in lines):
            continue
        short = home["rating"] - row["rating"]
        if short >= 0.15:
            drops.append(f"{row['agent']} ({row['rating']:.2f} over {row['maps']} maps)")
        elif short >= 0.08 and row["fk_diff"] <= -4:
            drops.append(f"{row['agent']} ({row['rating']:.2f}, first-duel differential {row['fk_diff']:+d})")
        elif row["fk_diff"] <= -3 and short > 0:
            cautions.append(f"{row['agent']} ({row['rating']:.2f}, first-duel differential {row['fk_diff']:+d})")
    if drops:
        listed = drops[0] if len(drops) == 1 else ", ".join(drops[:-1]) + " and " + drops[-1]
        lines.append(f"Drop {listed} until the rating is near {home['agent']}.")
    if cautions:
        lines.append("Not the default: " + ", ".join(cautions) + ".")
    return {"role": role, "lines": lines, "home": home["agent"]}


def player_assignments(players: pd.DataFrame, performance: pd.DataFrame) -> dict:
    """Roster plan: default agent, what to move off, the winning side, and the partner."""
    summary = player_summary(players)
    if summary.empty:
        return {"cards": [], "shape": ""}
    both = our_player_rows(players)
    floor = MIN_PLAYER_MAPS if summary["maps"].max() >= MIN_PLAYER_MAPS else 1
    regulars = summary[summary["maps"] >= floor]
    if regulars.empty:
        regulars = summary
    plants = {}
    if not performance.empty and "is_us" in performance.columns and "plants" in performance.columns:
        ours = performance[performance["is_us"] == True]  # noqa: E712
        plants = ours.groupby("player")["plants"].sum().to_dict()

    drafts = []
    for _, row in regulars.iterrows():
        name = row["player"]
        group = both[both["player"] == name]
        plan = _agent_plan(group)
        role = plan["role"]
        sides = _side_stats(players, name)
        attack = sides.get("attack", {})
        defense = sides.get("defense", {})
        attack_fk = attack.get("fk_diff", 0)
        defense_fk = defense.get("fk_diff", 0)
        if defense_fk >= attack_fk:
            strong = "defense"
            strong_fk = defense_fk
            weak_fk = attack_fk
        else:
            strong = "attack"
            strong_fk = attack_fk
            weak_fk = defense_fk
        drafts.append(
            {
                "player": name,
                "role": role,
                "rating": row["rating"],
                "maps": int(row["maps"]),
                "agent_lines": plan["lines"],
                "strong": strong,
                "strong_fk": strong_fk,
                "weak_fk": weak_fk,
                "attack_rating": attack.get("rating"),
                "defense_rating": defense.get("rating"),
                "plants": int(plants.get(name, 0)),
                "kast": row["kast"],
            }
        )

    duelists = [card for card in drafts if card["role"] == "duelist"]
    initiators = [card for card in drafts if card["role"] == "initiator"]
    attack_entry = (
        max(duelists, key=lambda card: card["strong_fk"] if card["strong"] == "attack" else card["weak_fk"])
        if duelists
        else None
    )
    info = max(initiators, key=lambda card: (card["plants"], card["rating"] or 0)) if initiators else None
    planter = max(drafts, key=lambda card: card["plants"]) if drafts else None

    cards = []
    for card in sorted(drafts, key=lambda item: item["rating"] or 0, reverse=True):
        side_line = (
            f"Wins the duel on {card['strong']}: first-duel differential {card['strong_fk']:+d} there, "
            f"{card['weak_fk']:+d} on the other side."
        )
        leak = ""
        if card["attack_rating"] is not None and card["defense_rating"] is not None:
            weak_side = "attack" if card["attack_rating"] + 0.08 < card["defense_rating"] else ""
            if card["defense_rating"] + 0.08 < card["attack_rating"]:
                weak_side = "defense"
            if weak_side:
                weak_rating = card["attack_rating"] if weak_side == "attack" else card["defense_rating"]
                other_rating = card["defense_rating"] if weak_side == "attack" else card["attack_rating"]
                leak = f"The leak is {weak_side} rating {weak_rating:.2f} against {other_rating:.2f}."
        info_name = info["player"] if info else ""
        entry_name = attack_entry["player"] if attack_entry else ""
        if card["role"] == "duelist" and card["strong"] == "defense" and card["weak_fk"] <= 0:
            pair = (
                f"On attack, only the committed fight after {info_name}'s info. Leave the lurk."
                if info_name
                else "On attack, only the committed fight. Leave the lurk."
            )
        elif card["role"] == "duelist" and card["strong"] == "defense":
            pair = (
                f"Defensive contact is the job. On attack, second body after {info_name}'s info, not a dry entry."
                if info_name
                else "Defensive contact is the job. On attack, be the second body, not the dry entry."
            )
        elif card["role"] == "duelist":
            pair = (
                f"This is the attack entry. {info_name}'s info goes to this contact."
                if info_name
                else "This is the attack entry. The info player should be on the same contact."
            )
        elif card["role"] == "initiator":
            pair = (
                f"Info into {entry_name}'s contact, then take the plant."
                if entry_name
                else "Info into the contact, then take the plant."
            )
            if card["plants"] and (planter is None or planter["player"] == card["player"]):
                pair += f" Plant count is {card['plants']}, the roster high."
        elif card["role"] == "controller":
            pair = (
                f"Smoke and play the post-plant with {planter['player']}. The first duel stays with the duelists."
                if planter and planter["player"] != card["player"]
                else "Smoke and play the post-plant. The first duel stays with the duelists."
            )
        else:
            names = [person for person in (entry_name, info_name) if person]
            pair = (
                f"Hold the site {' and '.join(names)} are not hitting. The 1v1 is the job, not the execute contact."
                if names
                else "Hold the site the entry is not hitting."
            )
        detail = " ".join(part for part in (*card["agent_lines"], side_line, leak, pair) if part)
        cards.append({"player": card["player"], "role": card["role"], "detail": detail})
    shape_bits = []
    if info and attack_entry:
        shape_bits.append(f"{info['player']} info into {attack_entry['player']}")
    if planter:
        shape_bits.append(f"{planter['player']} plants")
    controllers = [card["player"] for card in drafts if card["role"] == "controller"]
    sentinels = [card["player"] for card in drafts if card["role"] == "sentinel"]
    if controllers:
        shape_bits.append(f"{controllers[0]} plays the round out")
    if sentinels:
        shape_bits.append(f"{sentinels[0]} holds the other site")
    shape = ""
    if shape_bits:
        shape = "The contact is " + ", ".join(shape_bits) + "."
    return {"cards": cards, "shape": shape}


def attack_defense_frame(players: pd.DataFrame) -> pd.DataFrame:
    frame = players[(players["is_us"] == True) & (players["side"].isin(["attack", "defense"]))].copy()  # noqa: E712
    if frame.empty:
        return frame
    rows = []
    for (player_id, side), group in frame.groupby(["player_id", "side"]):
        rows.append(
            {
                "player_id": player_id,
                "player": group.sort_values("date")["player"].iloc[-1],
                "side": side,
                "rounds": group["rounds"].sum(),
                "rating": weighted_mean(group, "rating"),
                "acs": weighted_mean(group, "acs"),
                "kast": weighted_mean(group, "kast"),
                "fk_diff": group["fk_diff"].sum(),
            }
        )
    return pd.DataFrame(rows)
