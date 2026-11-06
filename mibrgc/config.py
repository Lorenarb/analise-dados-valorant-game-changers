"""Teams and season this project analyzes.

`use_team` points the same pipeline at one roster. Names and tags are matched
case-insensitively against the text VLR prints on match pages.
"""

from __future__ import annotations

# 2026 only. The rosters changed, so earlier seasons are different teams.
YEAR = 2026

VLR_ORIGIN = "https://www.vlr.gg"

TEAMS = (
    {
        "slug": "mibr-gc",
        "id": "8050",
        "label": "MIBR GC",
        "names": {"mibr gc", "mibr.gc"},
        # Overview pages use MIBR.GC. The performance table shortens the tag to MIBR.
        "tags": {"mibr.gc", "mibrgc", "mibr"},
        "rival_query": "Liquid",
        "rival_label": "Team Liquid Brazil",
        "rival_tab": {"en": "Liquid", "pt": "Liquid"},
    },
    {
        "slug": "team-liquid-brazil",
        "id": "7055",
        "label": "Team Liquid Brazil",
        "names": {"team liquid brazil", "liquid brazil"},
        "tags": {"tl", "tlv", "liquid", "tl br", "tlb"},
        "rival_query": "MIBR",
        "rival_label": "MIBR GC",
        "rival_tab": {"en": "MIBR", "pt": "MIBR"},
    },
)

TEAM_ID = TEAMS[0]["id"]
TEAM_SLUG = TEAMS[0]["slug"]
TEAM_LABEL = TEAMS[0]["label"]
TEAM_NAMES = set(TEAMS[0]["names"])
TEAM_TAGS = set(TEAMS[0]["tags"])
MATCH_LIST_URL = f"{VLR_ORIGIN}/team/matches/{TEAM_ID}/{TEAM_SLUG}/"


def use_team(slug: str) -> dict:
    """Point every parser at one roster. The name and tag sets are updated in place."""
    global TEAM_ID, TEAM_SLUG, TEAM_LABEL, MATCH_LIST_URL
    team = next(item for item in TEAMS if item["slug"] == slug)
    TEAM_ID = team["id"]
    TEAM_SLUG = team["slug"]
    TEAM_LABEL = team["label"]
    TEAM_NAMES.clear()
    TEAM_NAMES.update(team["names"])
    TEAM_TAGS.clear()
    TEAM_TAGS.update(team["tags"])
    MATCH_LIST_URL = f"{VLR_ORIGIN}/team/matches/{TEAM_ID}/{TEAM_SLUG}/"
    return team


def team_dirs(slug: str, root) -> tuple:
    """MIBR GC keeps the original cache. Every other roster gets its own folder."""
    from pathlib import Path

    root = Path(root)
    if slug == "mibr-gc":
        return root / "data" / "raw", root / "data" / "processed"
    base = root / "data" / slug
    return base / "raw", base / "processed"

# Pause between uncached requests. Cached HTML is never requested again.
REQUEST_DELAY_SECONDS = 0.8
