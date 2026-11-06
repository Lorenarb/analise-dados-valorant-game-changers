from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mibrgc.config import TEAM_LABEL, YEAR  # noqa: E402
from mibrgc.insights import (  # noqa: E402
    attack_defense_frame,
    championship_reports,
    map_decisions,
    player_assignments,
    round_plan,
)
from mibrgc.metrics import (  # noqa: E402
    event_summary,
    map_pool,
    our_map_rows,
    player_by_event,
    player_summary,
    side_rates,
)
from mibrgc.tables import load_tables  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
st.set_page_config(page_title=f"{TEAM_LABEL} {YEAR}", layout="wide")


def pct(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.0%}"


def show_table(frame: pd.DataFrame, percent_columns: tuple[str, ...] = ()) -> None:
    if frame.empty:
        st.info("No rows for this filter.")
        return
    display = frame.copy()
    for column in percent_columns:
        if column in display.columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.1%}")
    for column in display.columns:
        if column in percent_columns:
            continue
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.2f}")
    st.dataframe(display, use_container_width=True, hide_index=True)


def filter_frames(frames: dict[str, pd.DataFrame], events: list[str]) -> dict[str, pd.DataFrame]:
    filtered = {}
    for name, frame in frames.items():
        if "event" in frame.columns:
            filtered[name] = frame[frame["event"].isin(events)].copy()
        else:
            filtered[name] = frame
    return filtered


def main() -> None:
    st.title(f"{TEAM_LABEL} · {YEAR}")
    st.caption("Public VLR stats for series, maps, and players. Strategy notes are reads from those numbers, not a VOD review.")

    if not (PROCESSED / "matches.csv").exists():
        st.warning("No tables yet. From the project folder run `python -m mibrgc fetch`, then reload this page.")
        st.stop()

    frames = load_tables(PROCESSED)
    events = sorted(frames["matches"]["event"].dropna().unique().tolist())
    with st.sidebar:
        st.header("Filter")
        chosen = st.multiselect("Championships", events, default=events)
        page = st.radio(
            "Section",
            ["Strategy", "Championships", "Maps", "Players", "Economy", "Official API"],
            label_visibility="collapsed",
        )
        st.caption("Another team later: edit `mibrgc/config.py` and fetch again.")

    data = filter_frames(frames, chosen)
    matches = data["matches"]
    maps = our_map_rows(data["maps"])

    if page == "Strategy":
        render_strategy(matches, maps, data)
    elif page == "Championships":
        render_events(data)
    elif page == "Maps":
        render_maps(maps, data["rounds"])
    elif page == "Players":
        render_players(data["players"], data["performance"])
    elif page == "Economy":
        render_economy(data["economy_opening"], data["economy_buys"])
    else:
        render_official_api()


def render_strategy(matches: pd.DataFrame, maps: pd.DataFrame, data: dict[str, pd.DataFrame]) -> None:
    wins = int(matches["result"].eq("win").sum()) if not matches.empty else 0
    losses = int(matches["result"].eq("loss").sum()) if not matches.empty else 0
    map_wins = int(maps["win"].sum()) if not maps.empty else 0
    map_count = len(maps)
    round_diff = int(maps["our_score"].sum() - maps["opp_score"].sum()) if not maps.empty else 0
    sides = side_rates(maps)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Series", f"{wins}-{losses}")
    c2.metric("Maps", f"{map_wins}-{map_count - map_wins}" if map_count else "0-0")
    c3.metric("Round diff", f"{round_diff:+d}")
    c4.metric("Attack", pct(sides["attack"]))
    c5.metric("Defense", pct(sides["defense"]))

    st.subheader("Map decisions")
    st.caption("Maps with at least four games. The call uses win rate and the attack/defense gap.")
    decisions = map_decisions(maps)
    if decisions.empty:
        st.info("Not enough maps in this filter for a ban or a keep.")
    else:
        show_table(decisions, percent_columns=("attack", "defense"))
        chart = decisions.copy()
        chart["attack_win_rate"] = chart["attack"]
        chart["defense_win_rate"] = chart["defense"]
        long = chart.melt(id_vars=["map"], value_vars=["attack_win_rate", "defense_win_rate"], var_name="side", value_name="side_win_rate")
        long["side"] = long["side"].str.replace("_win_rate", "", regex=False)
        st.plotly_chart(
            px.bar(long, x="map", y="side_win_rate", color="side", barmode="group", title="Attack vs defense on maps with a call"),
            use_container_width=True,
        )

    st.subheader("Round types")
    plan = round_plan(data["economy_opening"], data["economy_buys"], data["rounds"])
    if not plan:
        st.info("No pistol, buy, or round rows in this filter.")
    else:
        show_table(pd.DataFrame(plan))

    st.subheader("How to use this roster")
    st.caption("Default agent, what to move off, the side that wins the duel, and who stands on the same contact.")
    roster = player_assignments(data["players"], data["performance"])
    if not roster["cards"]:
        st.info("No player rows in this filter.")
    else:
        if roster["shape"]:
            st.markdown(f"**Contact.** {roster['shape']}")
        for card in roster["cards"]:
            st.markdown(f"**{card['player']} · {card['role']}.** {card['detail']}")


def render_events(data: dict[str, pd.DataFrame]) -> None:
    matches = data["matches"]
    maps = our_map_rows(data["maps"])
    st.subheader("One championship")
    reports = championship_reports(data)
    if not reports:
        st.info("No championships in this filter.")
    else:
        labels = [
            f"{report['event']}  ·  {report['series_wins']}-{report['series_losses']}"
            for report in reports
        ]
        picked = st.selectbox("Championship", labels)
        report = reports[labels.index(picked)]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Series", f"{report['series_wins']}-{report['series_losses']}")
        c2.metric("Maps", f"{report['map_wins']}-{report['map_losses']}")
        c3.metric("Round diff", f"{report['round_diff']:+d}")
        c4.metric("Attack", pct(report["attack"]))
        c5.metric("Defense", pct(report["defense"]))
        st.markdown(report["summary"])
        if report["player"]:
            st.markdown(f"**Most relevant player: {report['player']}.** {report['reason']}")
        event_matches = matches[matches["event"] == report["event"]]
        columns = ["date", "stage", "opponent", "our_score", "opp_score", "result"]
        show_table(event_matches[columns].sort_values("date", ascending=False))
        event_players = data["players"][data["players"]["event"] == report["event"]]
        roster = player_summary(event_players)
        if not roster.empty:
            st.caption("Roster in this championship, weighted by rounds.")
            show_table(
                roster.drop(columns=["player_id"], errors="ignore"),
                percent_columns=("kast", "hs"),
            )

    st.subheader("All championships")
    summary = event_summary(matches, maps)
    show_table(summary, percent_columns=("map_win_rate",))
    if not summary.empty and "round_diff" in summary.columns:
        st.plotly_chart(
            px.bar(summary, x="event", y="round_diff", title="Round differential by event"),
            use_container_width=True,
        )


def render_maps(maps: pd.DataFrame, rounds: pd.DataFrame) -> None:
    st.subheader("By map")
    pool = map_pool(maps)
    show_table(pool, percent_columns=("win_rate", "attack_win_rate", "defense_win_rate"))
    if not pool.empty:
        long = pool.melt(
            id_vars=["map_name"],
            value_vars=["attack_win_rate", "defense_win_rate"],
            var_name="side",
            value_name="side_win_rate",
        )
        long["side"] = long["side"].str.replace("_win_rate", "", regex=False)
        st.plotly_chart(
            px.bar(long, x="map_name", y="side_win_rate", color="side", barmode="group", title="Attack vs defense by map"),
            use_container_width=True,
        )
    if rounds.empty:
        return
    st.subheader("How rounds end")
    ours = rounds[rounds["winner_is_us"] == True]  # noqa: E712
    if ours.empty:
        return
    mix = ours.groupby(["our_side", "win_method"]).size().reset_index(name="rounds")
    st.plotly_chart(
        px.bar(mix, x="our_side", y="rounds", color="win_method", title="Our winning rounds by method"),
        use_container_width=True,
    )


def render_players(players: pd.DataFrame, performance: pd.DataFrame) -> None:
    st.subheader("Roster, weighted by rounds")
    summary = player_summary(players)
    show_table(summary.drop(columns=["player_id"], errors="ignore"), percent_columns=("kast", "hs"))
    if not summary.empty:
        st.plotly_chart(
            px.bar(summary, x="player", y="rating", hover_data=["acs", "maps", "agents"], title="Rating"),
            use_container_width=True,
        )
    st.subheader("Attack vs defense")
    sides = attack_defense_frame(players)
    if not sides.empty:
        st.plotly_chart(
            px.bar(sides, x="player", y="rating", color="side", barmode="group", title="Rating by side"),
            use_container_width=True,
        )
    st.subheader("By championship")
    by_event = player_by_event(players)
    show_table(by_event.drop(columns=["player_id"], errors="ignore"), percent_columns=("kast",))
    if not performance.empty:
        st.subheader("Multikills and clutches")
        ours = performance[performance["is_us"] == True]  # noqa: E712
        if not ours.empty:
            grouped = (
                ours.groupby("player", as_index=False)[["k2", "k3", "k4", "k5", "clutch_1v1", "clutch_1v2", "clutch_1v3", "plants", "defuses"]]
                .sum()
                .sort_values("k3", ascending=False)
            )
            show_table(grouped)


def render_economy(opening: pd.DataFrame, buys: pd.DataFrame) -> None:
    st.subheader("Pistols and the next round")
    if opening.empty:
        st.info("No economy pages cached.")
        return
    ours = opening[opening["is_us"] == True].copy()  # noqa: E712
    if ours.empty:
        st.info("No MIBR rows in the economy tables.")
        return
    pistol = ours["pistol_won"].sum() / ours["pistol_played"].sum() if ours["pistol_played"].sum() else None
    conv = ours["conversion_won"].sum() / ours["conversion_played"].sum() if ours["conversion_played"].sum() else None
    bonus = ours["bonus_won"].sum() / ours["bonus_played"].sum() if ours["bonus_played"].sum() else None
    c1, c2, c3 = st.columns(3)
    c1.metric("Pistol", pct(pistol), f"{int(ours['pistol_won'].sum())}/{int(ours['pistol_played'].sum())}")
    c2.metric("Conversion", pct(conv))
    c3.metric("Bonus", pct(bonus))
    by_map = (
        ours.groupby("map_name", as_index=False)[["pistol_won", "pistol_played", "conversion_won", "conversion_played"]]
        .sum()
    )
    by_map["pistol"] = by_map["pistol_won"] / by_map["pistol_played"].replace(0, pd.NA)
    show_table(by_map, percent_columns=("pistol",))

    st.subheader("Buy vs buy")
    if buys.empty:
        return
    our_buys = buys[buys["is_us"] == True].copy()  # noqa: E712
    grouped = our_buys.groupby(["our_buy", "opp_buy"], as_index=False)[["won", "played"]].sum()
    grouped["win_rate"] = grouped["won"] / grouped["played"].replace(0, pd.NA)
    show_table(grouped, percent_columns=("win_rate",))
    heat = grouped.pivot(index="our_buy", columns="opp_buy", values="win_rate")
    st.plotly_chart(
        px.imshow(
            heat,
            text_auto=".0%",
            aspect="auto",
            title="Our win rate by buy type",
            labels={"x": "Opponent buy", "y": "Our buy", "color": "Win rate"},
        ),
        use_container_width=True,
    )


def render_official_api() -> None:
    st.subheader("What the official match feed would add")
    st.caption(
        "This app reads public VLR pages: series scores, map totals, and player averages. "
        "Riot's VAL-MATCH-V1 payload, and the replay a team exports from the client, is a round log. "
        "Every kill, plant, defuse, credit spend, and ability cast has a timestamp and a coordinate."
    )

    st.markdown(
        "A public developer key returns a player's live-queue history. "
        "Game Changers series are custom lobbies, and those often never appear on that key. "
        "The same JSON is what a team gets from the client replay or from Riot's esports partner feed. "
        "The notes below describe that payload."
    )

    gaps = pd.DataFrame(
        [
            {
                "question": "Who won the first duel",
                "from_vlr": "First kills and first deaths, summed across the map",
                "from_api": "The killer, weapon, headshot flag, both coordinates, and whether that round was won",
            },
            {
                "question": "Did the team trade",
                "from_vlr": "KAST is the only proxy for dying alone",
                "from_api": "A kill within a few seconds of a teammate's death, with both positions",
            },
            {
                "question": "Who should plant",
                "from_vlr": "Plant and defuse counts for the map",
                "from_api": "Site, plant clock, who was alive, and where each player stood",
            },
            {
                "question": "Which buy lost the gun round",
                "from_vlr": "Eco, half, and full buckets",
                "from_api": "Weapon, armor, credits spent, and credits left on that round",
            },
            {
                "question": "Did the utility do the job",
                "from_vlr": "Agent name only",
                "from_api": "Smoke, flash, recon, and ultimate casts on that round",
            },
            {
                "question": "Where the map pool actually breaks",
                "from_vlr": "Attack and defense round win rate",
                "from_api": "The choke or site of the entry death, and which site was hit",
            },
        ]
    )
    gaps.columns = ["Question this app already asks", "What VLR can say", "What the match feed adds"]
    show_table(gaps)

    st.subheader("How the current roster notes get sharper")
    st.markdown(
        """
- **bstrdd, attack entry.** VLR says the first-duel differential is +10 on attack and +73 on defense, and Neon is the most played agent at a lower rating than Yoru or Jett. The round log shows the coordinate of those attack deaths, the weapon, and whether a teammate traded within a few seconds. That separates a lost dry entry from a contact that the team failed to trade.
- **waved, Phoenix versus Waylay.** Phoenix is the strong agent and Waylay is the weak one. Ability casts and the clock of the first kill show whether Phoenix rounds are a committed flash-and-fight, and whether Waylay rounds die before a dash is even used.
- **melissa, plant and Tejo.** She has the plant count, and Tejo is the low-rating agent. Plant site, plant time, and her position when she dies tell you if the leak is the attack opener or the post-plant. Tejo's recon casts per round say whether the agent is being used or only picked.
- **conir, late round.** Rating and KAST are flat on both sides. Smoke casts per round, plus deaths while the bomb is down versus deaths on the anchor, show if he is closing rounds or taking first contact he should not take.
- **mizzy, defense rating.** The sentinel rating is lower on defense than on attack. Kill and death coordinates relative to the bomb split a lost site hold from a lost retake. Trip and camera casts mark whether the sentinel setup was placed.
- **Pistols and anti-eco.** VLR buckets the buy. The feed names the pistol, the armor, and the force weapon, so a lost anti-eco can be tied to a specific save instead of a generic eco rate.
        """
    )

    st.subheader("What to build once that feed exists")
    st.markdown(
        """
- A round table: side, weapon buy, first-blood player, traded or not, plant site, plant clock, round winner.
- Two columns on each player card: attack-entry survival, and trade rate after that player dies.
- A map view of entry deaths and plant sites, so a ban note can name a site instead of only a win rate.
        """
    )

    st.subheader("What stays a VOD either way")
    st.markdown(
        "Comms, the midround call, lineup quality, and whether a player lurked on purpose are not in the payload. "
        "Positions and casts tell you what happened. They do not tell you what was called."
    )


main()
