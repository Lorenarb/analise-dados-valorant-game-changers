"""Match-day brief. The lab dashboard stays at dashboard/app.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matchday.brief import (  # noqa: E402
    BRAZIL,
    SCOPES,
    filter_scope,
    opponent_pack,
    opponent_read,
    preparation_cues,
    season_headline,
    veto_steps,
)
from matchday.copy import COPY, ROLES  # noqa: E402
from mibrgc.config import TEAMS, YEAR, team_dirs, use_team  # noqa: E402
from mibrgc.insights import map_decisions, player_assignments  # noqa: E402
from mibrgc.tables import load_tables  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
st.set_page_config(page_title=f"Game Changers {YEAR}", layout="centered")

PAGES = ["report", "liquid", "veto", "cues"]


def pct(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.0%}"


def show_table(frame: pd.DataFrame, text: dict, percent_columns: tuple[str, ...] = ()) -> None:
    if frame.empty:
        st.info(text["no_rows"])
        return
    display = frame.copy()
    for column in percent_columns:
        if column in display.columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.0%}")
    for column in display.columns:
        if column in percent_columns:
            continue
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    st.dataframe(display, use_container_width=True, hide_index=True)


def label_frame(frame: pd.DataFrame, text: dict, columns: list[str]) -> pd.DataFrame:
    display = frame[columns].copy()
    if "result" in display.columns:
        display["result"] = display["result"].map({"win": text["win"], "loss": text["loss"]}).fillna(display["result"])
    rename = {column: text[column] for column in columns if column in text and text[column] != column}
    if "maps" in columns:
        rename["maps"] = text["map_count"]
    return display.rename(columns=rename)


def main() -> None:
    with st.sidebar:
        lang = st.radio(
            "Language",
            ["en", "pt"],
            format_func=lambda code: "English" if code == "en" else "Português",
            horizontal=True,
            label_visibility="collapsed",
        )
    with st.sidebar:
        team = st.radio(
            "Team",
            [item["slug"] for item in TEAMS],
            format_func=lambda slug: next(item["label"] for item in TEAMS if item["slug"] == slug),
            horizontal=True,
        )
    active = use_team(team)
    text = dict(COPY[lang])
    text["title"] = f"{active['label']} · {'dia de jogo' if lang == 'pt' else 'match day'}"
    text["liquid"] = active["rival_tab"][lang]
    text["opponent"] = active["rival_label"]
    st.title(text["title"])
    st.caption(text["caption"])

    if not (PROCESSED / "matches.csv").exists():
        st.warning(text["missing"])
        st.stop()

    with st.sidebar:
        scope = st.radio(
            "Circuit",
            [item["id"] for item in SCOPES],
            index=0,
            format_func=lambda code: next(item["name"][lang] for item in SCOPES if item["id"] == code),
            horizontal=True,
        )
    _, processed = team_dirs(active["slug"], ROOT)
    if not (processed / "matches.csv").exists():
        st.warning(text["missing"])
        st.stop()
    frames = filter_scope(load_tables(processed), scope or BRAZIL)
    note = next(item["note"][lang] for item in SCOPES if item["id"] == scope)
    st.caption(note)
    decisions = map_decisions(frames["maps"])
    roster = player_assignments(frames["players"], frames["performance"], lang=lang)
    cues = preparation_cues(frames, roster, lang=lang)
    steps = veto_steps(decisions, lang=lang)

    with st.sidebar:
        st.header(text["sidebar"])
        page = st.radio(text["section"], PAGES, format_func=lambda key: text[key], label_visibility="collapsed")
        st.caption(text["lab"])

    if page == "report":
        render_report(frames, steps, cues, roster, text, lang)
    elif page == "liquid":
        render_liquid(frames, text, lang, active["rival_query"])
    elif page == "veto":
        render_veto(steps, text)
    else:
        render_cues(cues, text)


def render_report(frames, steps, cues, roster, text, lang) -> None:
    head = season_headline(frames["matches"], frames["maps"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(text["series"], head["series"])
    c2.metric(text["maps"], head["maps"])
    c3.metric(text["round_diff"], f"{head['round_diff']:+d}")
    c4.metric(text["attack"], pct(head["attack"]))
    c5.metric(text["defense"], pct(head["defense"]))

    st.subheader(text["call"])
    for step in steps:
        if step["key"] in {"ban", "first", "attack", "defense"}:
            st.markdown(f"**{step['title']}.** {step['detail']}")
    if roster.get("shape"):
        st.markdown(f"**{text['contact']}.** {roster['shape']}")

    st.subheader(text["say"])
    for cue in cues:
        st.markdown(f"**{cue['title']}.** {cue['line']}")

    roles = ROLES[lang]
    with st.expander(text["roster"]):
        for card in roster.get("cards", []):
            role = roles.get(card["role"], card["role"])
            st.markdown(f"**{card['player']} · {role}.** {card['detail']}")


def render_liquid(frames, text, lang, rival_query: str) -> None:
    st.subheader(text["opponent"])
    pack = opponent_pack(frames, rival_query)
    st.markdown(opponent_read(pack, lang=lang))
    if pack["series"].empty:
        return
    head = pack["headline"]
    c1, c2, c3 = st.columns(3)
    c1.metric(text["series"], head["series"])
    c2.metric(text["maps"], head["maps"])
    c3.metric(text["round_diff"], f"{head['round_diff']:+d}")

    st.subheader(text["series_heading"])
    columns = ["date", "event", "stage", "our_score", "opp_score", "result", "url"]
    show_table(label_frame(pack["series"].sort_values("date", ascending=False), text, columns), text)

    st.subheader(text["maps_heading"])
    pool = pack["pool"]
    if not pool.empty:
        map_columns = ["map_name", "maps", "wins", "win_rate", "attack_win_rate", "defense_win_rate", "round_diff"]
        show_table(
            label_frame(pool, text, map_columns),
            text,
            percent_columns=(text["win_rate"], text["attack_win_rate"], text["defense_win_rate"]),
        )

    st.subheader(text["roster_heading"])
    players = pack["players"]
    if not players.empty:
        player_columns = [column for column in players.columns if column != "player_id"]
        show_table(
            label_frame(players, text, player_columns),
            text,
            percent_columns=("kast", "hs"),
        )


def render_veto(steps, text) -> None:
    st.subheader(text["veto_heading"])
    st.caption(text["veto_caption"])
    if not steps:
        st.info(text["veto_empty"])
        return
    for index, step in enumerate(steps, start=1):
        st.markdown(f"**{index}. {step['title']}.** {step['detail']}")


def render_cues(cues, text) -> None:
    st.subheader(text["cues_heading"])
    st.caption(text["cues_caption"])
    if not cues:
        st.info(text["cues_empty"])
        return
    for cue in cues:
        st.markdown(f"**{cue['title']}**")
        st.markdown(cue["line"])
        st.caption(cue["why"])


main()
