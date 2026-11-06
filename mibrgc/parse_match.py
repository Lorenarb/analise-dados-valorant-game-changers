from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from mibrgc import config

WIN_METHODS = {
    "elim": "elimination",
    "defuse": "defuse",
    "boom": "detonation",
    "time": "time",
}


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _num(value: str | None) -> float | int | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace("+", "").replace("–", "-").replace(",", "")
    if text in {"", "-", "—"}:
        return None
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return None


def _is_us(name: str = "", tag: str = "") -> bool:
    return name.casefold() in config.TEAM_NAMES or tag.casefold() in config.TEAM_TAGS


def _side_map(cell: Tag, percent: bool = False) -> dict[str, float | int | None]:
    found: dict[str, float | int | None] = {}
    for span in cell.select("span.side"):
        classes = span.get("class") or []
        if "mod-both" in classes:
            key = "both"
        elif "mod-t" in classes:
            key = "attack"
        elif "mod-ct" in classes:
            key = "defense"
        else:
            continue
        value = _num(span.get_text())
        if percent and isinstance(value, (int, float)):
            value = value / 100
        found[key] = value
    if "both" not in found:
        value = _num(cell.get_text(" ", strip=True))
        if percent and isinstance(value, (int, float)):
            value = value / 100
        found["both"] = value
    return found


def _fraction(text: str) -> tuple[int, int]:
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _map_name(header: Tag) -> str:
    name_el = header.select_one(".map-name")
    if name_el is None:
        return ""
    for piece in name_el.stripped_strings:
        if piece.strip().upper() != "PICK":
            return _clean(piece)
    return ""


def _pick_side(header: Tag) -> str | None:
    picked = header.select_one(".picked")
    if picked is None:
        return None
    classes = picked.get("class") or []
    if "mod-1" in classes:
        return "left"
    if "mod-2" in classes:
        return "right"
    return None


def _header_teams(header: Tag) -> list[dict]:
    blocks = [
        child
        for child in header.find_all("div", recursive=False)
        if "team" in (child.get("class") or [])
    ]
    teams = []
    for index, block in enumerate(blocks[:2]):
        name = _clean(block.select_one(".team-name").get_text()) if block.select_one(".team-name") else ""
        score_el = block.select_one(".score")
        attack_el = block.select_one("span.mod-t")
        defense_el = block.select_one("span.mod-ct")
        teams.append(
            {
                "slot": "left" if index == 0 else "right",
                "name": name,
                "is_us": _is_us(name),
                "score": _num(score_el.get_text()) if score_el else None,
                "attack_rounds": _num(attack_el.get_text()) if attack_el else None,
                "defense_rounds": _num(defense_el.get_text()) if defense_el else None,
            }
        )
    return teams


def _game_blocks(soup: BeautifulSoup) -> dict[str, Tag]:
    blocks: dict[str, Tag] = {}
    for game in soup.select("div.vm-stats-game"):
        game_id = game.get("data-game-id") or ""
        if not game_id or game_id == "all":
            continue
        blocks[game_id] = game
    return blocks


def _played_order(soup: BeautifulSoup) -> list[str]:
    order = []
    for item in soup.select(".vm-stats-gamesnav-item"):
        game_id = item.get("data-game-id") or ""
        if not game_id or game_id == "all":
            continue
        if item.get("data-disabled") == "1" or "mod-disabled" in (item.get("class") or []):
            continue
        order.append(game_id)
    return order


def _agents(node: Tag) -> str:
    names = []
    for image in node.select("img"):
        src = image.get("src") or ""
        title = _clean(image.get("title") or image.get("alt") or "")
        if not title and "/agents/" in src:
            title = src.rsplit("/", 1)[-1].split(".", 1)[0].replace("-", " ")
        if title:
            names.append(title.title() if title.islower() else title)
    return " / ".join(names)


def _stat_count(cell: Tag) -> int:
    """Visible count in a performance cell. Hover text lists the rounds, not the total."""
    square = cell.select_one(".stats-sq")
    if square is None:
        return 0
    for popup in square.select(".wf-popable-contents"):
        popup.extract()
    number = _num(square.get_text(" ", strip=True))
    if number is None:
        return 0
    return int(number)


def _player_link(node: Tag) -> tuple[str, str]:
    anchor = node.select_one("a[href*='/player/']")
    if anchor is None:
        return "", ""
    parts = [part for part in (anchor.get("href") or "").split("/") if part]
    # /player/<id>/<slug>
    if len(parts) >= 2 and parts[0] == "player":
        return parts[1], parts[2] if len(parts) > 2 else ""
    return "", ""


def parse_overview(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = _game_blocks(soup)
    order = _played_order(soup) or list(blocks)
    maps = []
    for index, game_id in enumerate(order, start=1):
        game = blocks.get(game_id)
        if game is None:
            continue
        header = game.select_one(".vm-stats-game-header")
        if header is None:
            continue
        teams = _header_teams(header)
        if len(teams) < 2 or teams[0]["score"] is None or teams[1]["score"] is None:
            continue
        us = next((team for team in teams if team["is_us"]), None)
        them = next((team for team in teams if not team["is_us"]), None)
        if us is None or them is None:
            continue
        our_score = int(us["score"])
        opp_score = int(them["score"])
        if our_score == opp_score:
            result = "draw"
        elif our_score > opp_score:
            result = "win"
        else:
            result = "loss"
        pick_slot = _pick_side(header)
        if pick_slot is None:
            picked_by = ""
        elif pick_slot == us["slot"]:
            picked_by = "us"
        else:
            picked_by = "opponent"
        duration = _clean(header.select_one(".map-duration").get_text()) if header.select_one(".map-duration") else ""
        maps.append(
            {
                "game_id": game_id,
                "map_number": index,
                "map_name": _map_name(header),
                "our_score": our_score,
                "opp_score": opp_score,
                "result": result,
                "our_attack_rounds": us["attack_rounds"],
                "our_defense_rounds": us["defense_rounds"],
                "opp_attack_rounds": them["attack_rounds"],
                "opp_defense_rounds": them["defense_rounds"],
                "duration": duration,
                "picked_by": picked_by,
                "opponent": them["name"],
                "players": _players(game),
                "rounds": _rounds(game, us["slot"]),
            }
        )
    return maps


def _players(game: Tag) -> list[dict]:
    rows = []
    for row in game.select(".ovw-row"):
        player_cell = row.select_one(".mod-player")
        if player_cell is None:
            continue
        name_el = player_cell.select_one(".ovw-player-name")
        tag_el = player_cell.select_one(".ovw-player-tag")
        name = _clean(name_el.get_text()) if name_el else ""
        tag = _clean(tag_el.get_text()) if tag_el else ""
        player_id, _slug = _player_link(player_cell)
        flag = player_cell.select_one("i.flag")
        country = (flag.get("title") or "") if flag else ""
        agent = _agents(row.select_one(".mod-agents") or row)
        cells = {cell.get("data-col"): cell for cell in row.select(".ovw-cell[data-col]")}
        kda = row.select_one(".mod-kda")
        kda_cells = {span.get("data-col"): span for span in (kda.select("[data-col]") if kda else [])}
        stats = {
            "rating": _side_map(cells["rating2"]) if "rating2" in cells else {},
            "acs": _side_map(cells["acs"]) if "acs" in cells else {},
            "kills": _side_map(kda_cells["kills"]) if "kills" in kda_cells else {},
            "deaths": _side_map(kda_cells["deaths"]) if "deaths" in kda_cells else {},
            "assists": _side_map(kda_cells["assists"]) if "assists" in kda_cells else {},
            "kd_diff": _side_map(cells["kd-diff"]) if "kd-diff" in cells else {},
            "kast": _side_map(cells["kast"], percent=True) if "kast" in cells else {},
            "adr": _side_map(cells["adr"]) if "adr" in cells else {},
            "hs": _side_map(cells["hsp"], percent=True) if "hsp" in cells else {},
            "fk": _side_map(cells["fb"]) if "fb" in cells else {},
            "fd": _side_map(cells["fd"]) if "fd" in cells else {},
            "fk_diff": _side_map(cells["fk-diff"]) if "fk-diff" in cells else {},
        }
        for side in ("both", "attack", "defense"):
            rows.append(
                {
                    "player": name,
                    "player_id": player_id,
                    "team_tag": tag,
                    "is_us": _is_us(tag=tag) or _is_us(name),
                    "country": country,
                    "agent": agent,
                    "side": side,
                    "rating": stats["rating"].get(side),
                    "acs": stats["acs"].get(side),
                    "kills": stats["kills"].get(side),
                    "deaths": stats["deaths"].get(side),
                    "assists": stats["assists"].get(side),
                    "kd_diff": stats["kd_diff"].get(side),
                    "kast": stats["kast"].get(side),
                    "adr": stats["adr"].get(side),
                    "hs": stats["hs"].get(side),
                    "fk": stats["fk"].get(side),
                    "fd": stats["fd"].get(side),
                    "fk_diff": stats["fk_diff"].get(side),
                }
            )
    return rows


def _rounds(game: Tag, our_slot: str) -> list[dict]:
    root = game.select_one(".vlr-rounds")
    if root is None:
        return []
    tags = [_clean(node.get_text()) for node in root.select(".vlr-rounds-tag")]
    # The rounds graphic lists the left/header team first, then the other team.
    top_is_us = our_slot == "left"
    parsed = []
    for column in root.select(".vlr-rounds-row-col"):
        number_el = column.select_one(".rnd-num")
        if number_el is None:
            continue
        number = _num(number_el.get_text())
        squares = column.select(".rnd-sq")
        if len(squares) < 2 or number is None:
            continue
        winner_index = next((i for i, square in enumerate(squares[:2]) if "mod-win" in (square.get("class") or [])), None)
        if winner_index is None:
            continue
        winner_square = squares[winner_index]
        classes = winner_square.get("class") or []
        if "mod-t" in classes:
            winner_side = "attack"
        elif "mod-ct" in classes:
            winner_side = "defense"
        else:
            winner_side = ""
        image = winner_square.select_one("img")
        method = ""
        if image and image.get("src"):
            stem = image["src"].rsplit("/", 1)[-1].split(".", 1)[0]
            method = WIN_METHODS.get(stem, stem)
        winner_is_us = (winner_index == 0) == top_is_us
        if winner_is_us:
            our_side = winner_side
        elif winner_side == "attack":
            our_side = "defense"
        elif winner_side == "defense":
            our_side = "attack"
        else:
            our_side = ""
        winner_tag = tags[winner_index] if winner_index < len(tags) else ""
        parsed.append(
            {
                "round_number": int(number),
                "winner_tag": winner_tag,
                "winner_is_us": winner_is_us,
                "winner_side": winner_side,
                "our_side": our_side,
                "win_method": method,
            }
        )
    return parsed


def parse_performance(html: str | None) -> dict[str, list[dict]]:
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    parsed: dict[str, list[dict]] = {}
    for game_id, game in _game_blocks(soup).items():
        rows = []
        for tr in game.select("table.mod-adv-stats tr"):
            cells = tr.find_all("td")
            if len(cells) < 14:
                continue
            tag_el = cells[0].select_one(".team-tag")
            tag = _clean(tag_el.get_text()) if tag_el else ""
            name = _clean(cells[0].get_text(" ", strip=True).replace(tag, "", 1))
            player_id, _slug = _player_link(cells[0])
            values = [_stat_count(cell) for cell in cells[2:14]]
            rows.append(
                {
                    "player": name,
                    "player_id": player_id,
                    "team_tag": tag,
                    "is_us": _is_us(tag=tag) or _is_us(name),
                    "agent": _agents(cells[1]),
                    "k2": values[0],
                    "k3": values[1],
                    "k4": values[2],
                    "k5": values[3],
                    "clutch_1v1": values[4],
                    "clutch_1v2": values[5],
                    "clutch_1v3": values[6],
                    "clutch_1v4": values[7],
                    "clutch_1v5": values[8],
                    "econ": values[9],
                    "plants": values[10],
                    "defuses": values[11],
                }
            )
        if rows:
            parsed[game_id] = rows
    return parsed


def _buy_key(label: str) -> str:
    text = label.casefold()
    if "eco" in text:
        return "eco"
    if "half" in text:
        return "half"
    if "full" in text:
        return "full"
    return _clean(label).casefold() or "unknown"


def parse_economy(html: str | None) -> dict[str, dict]:
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    parsed: dict[str, dict] = {}
    for game_id, game in _game_blocks(soup).items():
        tables = game.select("table.ecm")
        if not tables:
            continue
        opening = []
        for tr in tables[0].select("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            label = tr.select_one("th")
            name = (label.get("title") if label else "") or _clean(tr.get_text(" ", strip=True))
            name = _clean(name)
            pistol, conv, bonus = (_fraction(cell.get_text(" ", strip=True)) for cell in cells[:3])
            opening.append(
                {
                    "team": name,
                    "is_us": _is_us(name) or _is_us(tag=name),
                    "pistol_won": pistol[0],
                    "pistol_played": pistol[1],
                    "conversion_won": conv[0],
                    "conversion_played": conv[1],
                    "bonus_won": bonus[0],
                    "bonus_played": bonus[1],
                }
            )
        buys = []
        team_order = opening
        for table in tables[1:]:
            title_el = table.select_one(".ecm-gt-t")
            our_buy = _buy_key(title_el.get_text(" ", strip=True) if title_el else "")
            data_rows = [tr for tr in table.select("tr") if tr.find("td")]
            footer = [_buy_key(th.get_text(" ", strip=True)) for th in table.select("tr")[-1].find_all("th")]
            if not footer:
                footer = ["eco", "half", "full"]
            for row_index, tr in enumerate(data_rows):
                if row_index >= len(team_order):
                    break
                team = team_order[row_index]
                for cell, opp_buy in zip(tr.find_all("td"), footer):
                    won, played = _fraction(cell.get_text(" ", strip=True))
                    buys.append(
                        {
                            "team": team["team"],
                            "is_us": team["is_us"],
                            "our_buy": our_buy,
                            "opp_buy": opp_buy,
                            "won": won,
                            "played": played,
                        }
                    )
        if opening or buys:
            parsed[game_id] = {"opening": opening, "buys": buys}
    return parsed


def parse_match(overview_html: str, performance_html: str | None = None, economy_html: str | None = None) -> list[dict]:
    performance = parse_performance(performance_html)
    economy = parse_economy(economy_html)
    maps = parse_overview(overview_html)
    for game in maps:
        game["performance"] = performance.get(game["game_id"], [])
        econ = economy.get(game["game_id"], {})
        game["economy_opening"] = econ.get("opening", [])
        game["economy_buys"] = econ.get("buys", [])
    return maps
