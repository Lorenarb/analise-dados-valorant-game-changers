"""Team and season this project analyzes.

Change this file to point the same pipeline at another VLR team.
`TEAM_NAMES` and `TEAM_TAGS` are matched case-insensitively against the
names VLR prints on match pages (full name and short tag).
"""

TEAM_ID = "8050"
TEAM_SLUG = "mibr-gc"
TEAM_LABEL = "MIBR GC"
TEAM_NAMES = {"mibr gc", "mibr.gc"}
# Overview pages use MIBR.GC. The performance table shortens the tag to MIBR.
TEAM_TAGS = {"mibr.gc", "mibrgc", "mibr"}
YEAR = 2026

VLR_ORIGIN = "https://www.vlr.gg"
MATCH_LIST_URL = f"{VLR_ORIGIN}/team/matches/{TEAM_ID}/{TEAM_SLUG}/"

# Pause between uncached requests. Cached HTML is never requested again.
REQUEST_DELAY_SECONDS = 0.8
