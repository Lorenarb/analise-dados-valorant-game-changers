"""Match-day reads on top of the tables main already builds."""

from __future__ import annotations

import pandas as pd

from mibrgc.config import TEAM_LABEL, YEAR
from mibrgc.insights import map_decisions, player_assignments, round_plan
from mibrgc.metrics import map_pool, our_map_rows, player_summary, side_rates


def season_headline(matches: pd.DataFrame, maps: pd.DataFrame) -> dict:
    map_rows = our_map_rows(maps)
    wins = int(matches["result"].eq("win").sum()) if not matches.empty else 0
    losses = int(matches["result"].eq("loss").sum()) if not matches.empty else 0
    map_wins = int(map_rows["win"].sum()) if not map_rows.empty else 0
    map_count = len(map_rows)
    round_diff = int(map_rows["our_score"].sum() - map_rows["opp_score"].sum()) if not map_rows.empty else 0
    sides = side_rates(maps)
    return {
        "team": TEAM_LABEL,
        "year": YEAR,
        "series": f"{wins}-{losses}",
        "maps": f"{map_wins}-{map_count - map_wins}" if map_count else "0-0",
        "round_diff": round_diff,
        "attack": sides["attack"],
        "defense": sides["defense"],
    }


def _record_rate(record: str) -> float:
    won, lost = (int(part) for part in str(record).split("-"))
    played = won + lost
    return won / played if played else 0.0


_STEP_TITLES = {
    "en": {
        "ban": "Ban",
        "first": "First pick",
        "also": "Also play",
        "attack": "Attack side",
        "defense": "Defense side",
        "available": "Available",
    },
    "pt": {
        "ban": "Ban",
        "first": "Primeira escolha",
        "also": "Também joga",
        "attack": "Lado ataque",
        "defense": "Lado defesa",
        "available": "Disponível",
    },
}

_NOTES = {
    "Leave it in only when the opponent's stronger side is the one you can avoid.": "Deixe no pool só quando o lado forte da adversária for o que vocês conseguem evitar.",
    "Defense is the leak. Take it when the veto lets you start on attack.": "A defesa é o vazamento. Pegue quando o veto deixar vocês começarem no ataque.",
    "Attack is the leak. Review the execute before this stays in the pool.": "O ataque é o vazamento. Revise o execute antes de manter este mapa no pool.",
    "First map to take away from the opponent.": "Primeiro mapa para tirar da adversária.",
    "The map is playable, and the rounds are won on attack.": "O mapa é jogável, e as rodadas são ganhas no ataque.",
    "The map is playable, and the rounds are won on defense.": "O mapa é jogável, e as rodadas são ganhas na defesa.",
    "Win rate and both sides sit in the middle. Not a ban and not a permaban.": "A taxa de vitória e os dois lados ficam no meio. Não é ban nem primeira escolha.",
}


def veto_steps(decisions: pd.DataFrame, lang: str = "en") -> list[dict[str, str]]:
    """Ban, first pick, side-specific maps, then the maps that are simply available."""
    if decisions.empty:
        return []
    frame = decisions.copy()
    frame["rate"] = frame["record"].map(_record_rate)
    titles = _STEP_TITLES[lang]
    steps: list[dict[str, str]] = []

    def add(key: str, row: pd.Series) -> None:
        attack = row["attack"]
        defense = row["defense"]
        if pd.notna(attack) and pd.notna(defense):
            sides = (
                f" Ataque {attack:.0%}, defesa {defense:.0%}."
                if lang == "pt"
                else f" Attack {attack:.0%}, defense {defense:.0%}."
            )
        else:
            sides = ""
        if key == "also":
            note = "Mantenha no pool, atrás da primeira escolha." if lang == "pt" else "Keep it in the pool behind the first pick."
        elif key == "available":
            note = "Jogue quando o ban e a escolha já estiverem definidos." if lang == "pt" else "Play it once the ban and the pick are settled."
        else:
            note = _NOTES.get(row["note"], row["note"]) if lang == "pt" else row["note"]
        steps.append({"key": key, "title": titles[key], "detail": f"{row['map']} {row['record']}.{sides} {note}"})

    for _, row in frame[frame["decision"] == "Ban"].sort_values("rate").iterrows():
        add("ban", row)
    keeps = frame[frame["decision"] == "Keep"].sort_values(["rate", "maps"], ascending=[False, False])
    if not keeps.empty:
        add("first", keeps.iloc[0])
        for _, row in keeps.iloc[1:].iterrows():
            add("also", row)
    for _, row in frame[frame["decision"] == "Attack side"].sort_values("rate").iterrows():
        add("attack", row)
    for _, row in frame[frame["decision"] == "Defense side"].sort_values("rate").iterrows():
        add("defense", row)
    for _, row in frame[frame["decision"] == "Playable"].sort_values("rate", ascending=False).iterrows():
        add("available", row)
    return steps


def _contact_why(card: dict, lang: str) -> str:
    markers = (
        ("Ganha o duelo", "O contato defensivo", "segundo corpo")
        if lang == "pt"
        else ("Wins the duel", "Defensive contact", "second body")
    )
    sentences = [part.strip() for part in card["detail"].split(".") if part.strip()]
    picked = [
        sentence
        for sentence in sentences
        if sentence.startswith(markers[0]) or sentence.startswith(markers[1]) or markers[2] in sentence
    ]
    return ". ".join(picked) + "." if picked else card["detail"]


def preparation_cues(frames: dict[str, pd.DataFrame], roster: dict, lang: str = "en") -> list[dict[str, str]]:
    """Three rehearsal lines. They describe round habits, not anyone's state of mind."""
    plan = {
        item["round"]: item
        for item in round_plan(frames["economy_opening"], frames["economy_buys"], frames["rounds"], lang=lang)
    }
    cues: list[dict[str, str]] = []
    round_names = {
        "en": {"Pistol": "Pistol", "Full buy vs eco": "Full buy vs eco", "Attack post-plant": "Attack post-plant"},
        "pt": {"Pistol": "Pistola", "Full buy vs eco": "Full buy contra eco", "Attack post-plant": "Pós-plant no ataque"},
    }[lang]

    pistol = plan.get("Pistol")
    anti = plan.get("Full buy vs eco")
    if pistol or anti:
        why = " ".join(f"{round_names[item['round']]}: {item['result']}." for item in (pistol, anti) if item)
        cues.append(
            {
                "title": "Depois da pistola ganha, desacelera" if lang == "pt" else "After a won pistol, slow down",
                "line": "Jogue o bônus do jeito que vocês treinaram." if lang == "pt" else "Play the bonus the way you practiced it.",
                "why": why.strip(),
            }
        )

    shape = roster.get("shape") or ""
    marker = "segundo corpo" if lang == "pt" else "second body"
    second = next((card for card in roster.get("cards", []) if marker in card["detail"]), None)
    if second or shape:
        if shape:
            line = shape
        elif lang == "pt":
            line = f"Nomeie o contato antes da rodada. {second['player']} é o segundo corpo no ataque."
        else:
            line = f"Name the contact before the round. {second['player']} is the second body on attack."
        if second:
            why = _contact_why(second, lang)
        elif lang == "pt":
            why = "As rodadas de ataque da duelista vazam quando a entry entra sozinha."
        else:
            why = "The duelist's attack rounds are the ones that leak when the entry is dry."
        cues.append(
            {
                "title": "Nomeie o contato" if lang == "pt" else "Name the contact",
                "line": line,
                "why": why,
            }
        )

    post = plan.get("Attack post-plant")
    if post:
        cues.append(
            {
                "title": "Fica no pós-plant" if lang == "pt" else "Stay for the post-plant",
                "line": "Uma jogadora fica." if lang == "pt" else "One player stays.",
                "why": post["result"] + ".",
            }
        )
    return cues


def _opponent_mask(matches: pd.DataFrame, name: str) -> pd.Series:
    return matches["opponent"].fillna("").str.contains(name, case=False, regex=False)


def opponent_pack(frames: dict[str, pd.DataFrame], name: str = "Liquid") -> dict:
    matches = frames["matches"]
    series = matches[_opponent_mask(matches, name)].sort_values("date")
    if series.empty:
        return {"series": series, "maps": frames["maps"].iloc[0:0], "players": frames["players"].iloc[0:0], "pool": frames["maps"].iloc[0:0]}
    ids = set(series["match_id"].astype(str))
    maps = frames["maps"][frames["maps"]["match_id"].astype(str).isin(ids)].copy()
    players = frames["players"][frames["players"]["match_id"].astype(str).isin(ids)].copy()
    return {
        "series": series,
        "maps": maps,
        "players": player_summary(players),
        "pool": map_pool(maps),
        "headline": season_headline(series, maps),
    }


def opponent_read(pack: dict, lang: str = "en") -> str:
    series = pack["series"]
    if series.empty:
        return (
            "Nenhuma série contra essa adversária no ano em cache."
            if lang == "pt"
            else "No series against this opponent in the cached year."
        )
    label = series["opponent"].iloc[-1]
    wins = int(series["result"].eq("win").sum())
    losses = int(series["result"].eq("loss").sum())
    sweeps = series[(series["our_score"] == 0) & (series["opp_score"] >= 2)]
    long_wins = series[(series["result"] == "win") & (series["our_score"] + series["opp_score"] >= 3)]
    text = (
        f"{TEAM_LABEL} está {wins}-{losses} contra {label} em {YEAR}."
        if lang == "pt"
        else f"{TEAM_LABEL} is {wins}-{losses} against {label} in {YEAR}."
    )
    if not sweeps.empty:
        listed = ", ".join(
            f"{row.date.date().isoformat()} {row.event} {int(row.our_score)}-{int(row.opp_score)}"
            for row in sweeps.itertuples(index=False)
        )
        text += (
            f" A prioridade do VOD é o sweep: {listed}."
            if lang == "pt"
            else f" The VOD priority is the sweep: {listed}."
        )
    if not long_wins.empty:
        text += (
            " As séries que foram longe mostram que o jogo é vencível quando o primeiro mapa não acaba com ele."
            if lang == "pt"
            else " The series that went long are the ones that show the match is winnable when map one does not end it."
        )
    text += (
        " Prepare o primeiro mapa. Isso é familiaridade com uma rival, não uma história sobre nervosismo."
        if lang == "pt"
        else " Prep the first map. This is familiarity with a rival, not a story about nerve."
    )
    return text
