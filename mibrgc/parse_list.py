from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from mibrgc import config
from mibrgc.config import VLR_ORIGIN, YEAR


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _is_us(name: str = "", tag: str = "") -> bool:
    return name.casefold() in config.TEAM_NAMES or tag.casefold() in config.TEAM_TAGS


def parse_match_list(html: str) -> list[dict]:
    """Series rows for the configured year from a team matches page."""
    soup = BeautifulSoup(html, "html.parser")
    series: list[dict] = []
    seen: set[str] = set()

    for card in soup.select("a.m-item"):
        href = card.get("href") or ""
        match = re.match(r"/(\d+)/", href.split("?")[0])
        if not match:
            continue
        match_id = match.group(1)
        if match_id in seen:
            continue

        event_node = card.select_one(".m-item-event")
        event = ""
        stage = ""
        if event_node is not None:
            bold = event_node.find("div")
            event = _clean(bold.get_text(" ", strip=True) if bold else "")
            stage = _clean(event_node.get_text(" ", strip=True).replace(event, "", 1))

        teams = card.select(".m-item-team")
        if len(teams) < 2:
            continue
        left_name = _clean(teams[0].select_one(".m-item-team-name").get_text()) if teams[0].select_one(".m-item-team-name") else ""
        left_tag = _clean(teams[0].select_one(".m-item-team-tag").get_text()) if teams[0].select_one(".m-item-team-tag") else ""
        right_name = _clean(teams[1].select_one(".m-item-team-name").get_text()) if teams[1].select_one(".m-item-team-name") else ""
        right_tag = _clean(teams[1].select_one(".m-item-team-tag").get_text()) if teams[1].select_one(".m-item-team-tag") else ""

        digits = [int(piece) for piece in card.select_one(".m-item-result").stripped_strings if piece.isdigit()] if card.select_one(".m-item-result") else []
        if len(digits) < 2:
            continue
        left_score, right_score = digits[0], digits[1]

        date_node = card.select_one(".m-item-date")
        date_parts = list(date_node.stripped_strings) if date_node else []
        date_text = date_parts[0].strip() if date_parts else ""
        time_text = date_parts[1].strip() if len(date_parts) > 1 else ""
        try:
            played_on = datetime.strptime(date_text, "%Y/%m/%d").date()
        except ValueError:
            continue
        if played_on.year != YEAR:
            continue

        if _is_us(left_name, left_tag):
            our_score, opp_score = left_score, right_score
            opponent, opponent_tag = right_name, right_tag
        elif _is_us(right_name, right_tag):
            our_score, opp_score = right_score, left_score
            opponent, opponent_tag = left_name, left_tag
        else:
            continue

        if our_score == opp_score:
            result = "draw"
        elif our_score > opp_score:
            result = "win"
        else:
            result = "loss"

        vod = card.select_one(".m-item-vods") is not None
        path = href.split("?")[0]
        seen.add(match_id)
        series.append(
            {
                "match_id": match_id,
                "url": f"{VLR_ORIGIN}{path}",
                "date": played_on.isoformat(),
                "time": time_text,
                "event": event,
                "stage": stage,
                "team": config.TEAM_LABEL,
                "opponent": opponent,
                "opponent_tag": opponent_tag,
                "our_score": our_score,
                "opp_score": opp_score,
                "result": result,
                "vod": vod,
            }
        )
    return series
