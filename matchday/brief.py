"""Match-day reads on top of the tables main already builds."""

from __future__ import annotations

import pandas as pd

from mibrgc import config
from mibrgc.config import YEAR
from mibrgc.insights import map_decisions, player_assignments, round_plan
from mibrgc.metrics import map_pool, our_map_rows, player_summary, side_rates


BRAZIL = "brazil"
INTERNATIONAL = "international"

SCOPES = (
    {
        "id": BRAZIL,
        "name": {"en": "Brazil", "pt": "Brasil"},
        "note": {
            "en": "Brazil circuit only: Kickoff, Stage 1, Stage 2, and Finals. Championship, AMER Last Chance, and VCL are not in this veto.",
            "pt": "Só o circuito do Brasil: Kickoff, Stage 1, Stage 2 e Finals. Championship, AMER Last Chance e VCL ficam fora deste veto.",
        },
    },
    {
        "id": INTERNATIONAL,
        "name": {"en": "International", "pt": "Internacional"},
        "note": {
            "en": "Championship and AMER Last Chance only. The sample is small. Use it as a check beside the Brazil veto.",
            "pt": "Só Championship e AMER Last Chance. A amostra é pequena. Use como checagem ao lado do veto do Brasil.",
        },
    },
)


def competition_scope(event: str) -> str:
    """Brazil stages, or Championship plus AMER. VCL and anything else stay out."""
    name = str(event)
    if "VCL" in name:
        return ""
    if "Championship" in name or "AMER" in name or "Last Chance" in name:
        return INTERNATIONAL
    if "Brazil" in name:
        return BRAZIL
    return ""


def filter_scope(frames: dict[str, pd.DataFrame], scope: str) -> dict[str, pd.DataFrame]:
    matches = frames["matches"]
    chosen = matches["event"].map(competition_scope).eq(scope)
    ids = set(matches.loc[chosen, "match_id"].astype(str))
    scoped = {}
    for key, frame in frames.items():
        if frame.empty or "match_id" not in getattr(frame, "columns", []):
            scoped[key] = frame
            continue
        scoped[key] = frame[frame["match_id"].astype(str).isin(ids)].copy()
    return scoped


_ECONOMY_ORDER = ("pistol", "bonus", "full_full", "full_half", "full_eco", "half_half", "eco_full")


def economy_rows(opening: pd.DataFrame, buys: pd.DataFrame) -> list[dict]:
    """Buy win rates with enough rounds to read. Empty matchups are left out."""
    found: dict[str, dict] = {}
    if not opening.empty and "is_us" in opening.columns:
        ours = opening[opening["is_us"] == True]  # noqa: E712
        for key, won_col, played_col in (
            ("pistol", "pistol_won", "pistol_played"),
            ("bonus", "bonus_won", "bonus_played"),
        ):
            played = int(ours[played_col].sum())
            won = int(ours[won_col].sum())
            if played >= 8:
                found[key] = {"key": key, "won": won, "played": played, "rate": round(won / played, 4)}
    if not buys.empty and "is_us" in buys.columns:
        ours = buys[buys["is_us"] == True]  # noqa: E712
        pairs = {
            "full_full": ("full", "full"),
            "full_half": ("full", "half"),
            "full_eco": ("full", "eco"),
            "half_half": ("half", "half"),
            "eco_full": ("eco", "full"),
        }
        for key, (our_buy, opp_buy) in pairs.items():
            group = ours[(ours["our_buy"] == our_buy) & (ours["opp_buy"] == opp_buy)]
            played = int(group["played"].sum()) if not group.empty else 0
            won = int(group["won"].sum()) if not group.empty else 0
            if played >= 8:
                found[key] = {"key": key, "won": won, "played": played, "rate": round(won / played, 4)}
    return [found[key] for key in _ECONOMY_ORDER if key in found]


def economy_strategies(opening: pd.DataFrame, buys: pd.DataFrame, lang: str = "en") -> list[dict]:
    """The buy states lost most often, each with one round plan."""
    rows = economy_rows(opening, buys)
    ranked = sorted((row for row in rows if row["played"] >= 20), key=lambda row: row["rate"])[:3]
    plans = []
    for row in ranked:
        lost = row["played"] - row["won"]
        plans.append(
            {
                "key": row["key"],
                "won": row["won"],
                "played": row["played"],
                "rate": row["rate"],
                "title": _economy_title(row["key"], lang),
                "line": _economy_line(row["key"], lang),
                "why": _economy_why(row["key"], lost, row["played"], opening, buys, lang),
            }
        )
    return plans


def _economy_title(key: str, lang: str) -> str:
    titles = {
        "en": {
            "eco_full": "Eco vs their rifles",
            "half_half": "Half vs their half",
            "bonus": "Bonus round",
            "pistol": "Pistol",
            "full_eco": "Full vs their eco",
            "full_half": "Full vs their half",
            "full_full": "Full vs their full",
        },
        "pt": {
            "eco_full": "Eco contra os rifles delas",
            "half_half": "Half contra o half delas",
            "bonus": "Rodada de bônus",
            "pistol": "Pistola",
            "full_eco": "Full contra o eco delas",
            "full_half": "Full contra o half delas",
            "full_full": "Full contra o full delas",
        },
    }
    return titles.get(lang, titles["en"]).get(key, key)


def _economy_line(key: str, lang: str) -> str:
    if lang == "pt":
        lines = {
            "eco_full": "Jogue o save. Um exit ou o plant, e saia do duelo de rifle.",
            "half_half": "Não entre em cinco duelos separados num half buy. Salve para um full, ou jogue só o contato combinado.",
            "bonus": "Segure as armas que sobraram e jogue devagar. Sem caçada.",
            "full_eco": "Feche o anti-eco do jeito treinado. Sem pressa depois da pistola.",
            "full_full": "Trate o full contra full como a linha de base. Não misture com o eco.",
        }
        return lines.get(key, "Revise essas rodadas antes de mudar o veto.")
    lines = {
        "eco_full": "Play the save. Take one exit or the plant, then leave the rifle duel.",
        "half_half": "Do not take five separate duels on a half buy. Save into a full, or play only the named contact.",
        "bonus": "Keep the leftover guns in a slow round. Do not hunt.",
        "full_eco": "Close the anti-eco the way you practiced it. No rush after the pistol.",
        "full_full": "Treat full vs full as the baseline. Keep it apart from the eco rounds.",
    }
    return lines.get(key, "Review these rounds before changing a veto.")


def _economy_why(key: str, lost: int, played: int, opening: pd.DataFrame, buys: pd.DataFrame, lang: str) -> str:
    share = lost / played if played else 0
    record = f"{share:.0%} ({lost}/{played})"
    extra = ""
    if key == "half_half" and not buys.empty and "is_us" in buys.columns:
        group = buys[(buys["is_us"] == True) & (buys["our_buy"] == "half") & (buys["opp_buy"] == "half")]  # noqa: E712
        if not group.empty:
            by_opp = group.groupby("opponent")[["won", "played"]].sum().sort_values("played", ascending=False)
            top = by_opp.iloc[0]
            if int(top["played"]) >= 0.25 * played:
                top_rate = int(top["won"]) / int(top["played"]) if int(top["played"]) else 0
                opponent = by_opp.index[0]
                extra = (
                    f" {int(top['played'])} dessas rodadas são contra {opponent}, ganhas a {top_rate:.0%}."
                    if lang == "pt"
                    else f" {int(top['played'])} of those rounds are against {opponent}, won at {top_rate:.0%}."
                )
    if key == "bonus" and not opening.empty and "is_us" in opening.columns:
        ours = opening[opening["is_us"] == True]  # noqa: E712
        converted = int(ours["conversion_won"].sum())
        conversion_played = int(ours["conversion_played"].sum())
        if conversion_played:
            conversion = converted / conversion_played
            extra = (
                f" A conversão da pistola é {conversion:.0%} ({converted}/{conversion_played}), então o vazamento é o bônus."
                if lang == "pt"
                else f" Pistol conversion is {conversion:.0%} ({converted}/{conversion_played}), so the leak is the bonus."
            )
    if lang == "pt":
        if key == "eco_full":
            return f"Perderam {record}. Um save deve perder. Essa rodada existe para o próximo full buy estar vivo."
        if key == "half_half":
            return f"Perderam {record}. É a compra equilibrada que desmonta contra o campo.{extra}"
        return f"Perderam {record}.{extra}"
    if key == "eco_full":
        return f"Lost {record}. A save is supposed to lose. This round exists so the next full buy is alive."
    if key == "half_half":
        return f"Lost {record}. This is the even buy that falls apart against the field.{extra}"
    return f"Lost {record}.{extra}"


def economy_note(rows: list[dict], lang: str = "en") -> str:
    by_key = {row["key"]: row for row in rows}
    half = by_key.get("half_half")
    anti = by_key.get("full_eco")
    save = by_key.get("eco_full")
    if lang == "pt":
        if half and half["rate"] < 0.45:
            text = f"A compra para revisar é half contra half: {half['rate']:.0%} ({half['won']}/{half['played']})."
        elif anti and anti["rate"] < 0.8:
            text = f"A compra para revisar é full contra eco: {anti['rate']:.0%} ({anti['won']}/{anti['played']})."
        else:
            text = "As compras de full estão na faixa jogável."
        if save:
            text += " Eco contra full baixo é a rodada de save, não um problema separado."
        return text
    if half and half["rate"] < 0.45:
        text = f"The buy to review is half vs half: {half['rate']:.0%} ({half['won']}/{half['played']})."
    elif anti and anti["rate"] < 0.8:
        text = f"The buy to review is full vs eco: {anti['rate']:.0%} ({anti['won']}/{anti['played']})."
    else:
        text = "Full buys are in a playable range."
    if save:
        text += " A low eco vs full rate is the save round, not a separate problem."
    return text


def season_headline(matches: pd.DataFrame, maps: pd.DataFrame) -> dict:
    map_rows = our_map_rows(maps)
    wins = int(matches["result"].eq("win").sum()) if not matches.empty else 0
    losses = int(matches["result"].eq("loss").sum()) if not matches.empty else 0
    map_wins = int(map_rows["win"].sum()) if not map_rows.empty else 0
    map_count = len(map_rows)
    round_diff = int(map_rows["our_score"].sum() - map_rows["opp_score"].sum()) if not map_rows.empty else 0
    sides = side_rates(maps)
    return {
        "team": config.TEAM_LABEL,
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
        f"{config.TEAM_LABEL} está {wins}-{losses} contra {label} em {YEAR}."
        if lang == "pt"
        else f"{config.TEAM_LABEL} is {wins}-{losses} against {label} in {YEAR}."
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
