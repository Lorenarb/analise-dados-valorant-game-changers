# Análise de Dados Valorant Game Changers

Season review for **MIBR GC** and **Team Liquid Brazil** in **2026**, built from the public match pages on [VLR](https://www.vlr.gg/team/matches/8050/mibr-gc/) and [VLR](https://www.vlr.gg/team/7055/team-liquid-brazil).

## What it answers

- Series record, map record, and round differential for one championship or the whole year
- Map pool, including attack and defense round win rate and who picked the map
- Players across the season and inside each championship: rating, ACS, KAST, ADR, HS%, first kills, agents
- Attack versus defense splits for those same player stats
- Pistols, pistol conversion, bonuses, and win rate by buy type (eco / half / full)
- How rounds were won (elimination, detonation, defuse, time)
- Short strategy notes a coach can take into a VOD review

## Match day

On the `match-day` branch, the brief a coach can read is separate from this lab:

```bash
streamlit run matchday/app.py
```

The iOS app opens on a roster choice: MIBR GC or Team Liquid Brazil. Each brief has the report, the series against the other roster, the veto card, and three rehearsal cues. English and Portuguese, and the Brazil circuit versus the international sheet, stay inside the roster you picked. The Brazil veto is Kickoff, Stage 1, Stage 2, and Finals. Championship and AMER Last Chance are the check, not part of that average. VCL stays out. The year stays 2026 because the rosters changed.

```bash
python -m mibrgc fetch --team team-liquid-brazil
python -m matchday.export_ios
```

MIBR GC tables stay in `data/processed`. Team Liquid Brazil tables stay in `data/team-liquid-brazil/processed`. `main` keeps the full MIBR GC dashboard.

The iOS app in `ios/MIBRGC.xcodeproj` draws those same reads as bars, score cards, and a veto list. Refresh the bundled numbers after a new fetch:

```bash
python -m matchday.export_ios
```

Open the project in Xcode and run it on a simulator. The EN / PT control is at the top of the screen.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m mibrgc fetch
streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501). The sidebar filters championships and switches sections: Strategy, Championships, Maps, Players, Economy.

`fetch` downloads every completed series in the configured year (overview, performance, and economy) and writes the tables. Cached HTML is not requested again. After the cache exists:

```bash
python -m mibrgc build          # reparse local HTML only
python -m mibrgc fetch --limit 2
python -m mibrgc fetch --refresh
```

`--limit` keeps the oldest N series, for a quick check. `--refresh` downloads again.

## Layout

| Path | Role |
| --- | --- |
| `mibrgc/config.py` | Season, and the roster list (id, names, tags). |
| `mibrgc/client.py` | Downloads VLR HTML and caches it in `data/raw/`. |
| `mibrgc/parse_list.py` | Reads the team match list into series. |
| `mibrgc/parse_match.py` | Reads overview, performance, and economy for each series. |
| `mibrgc/tables.py` | Turns the cache into CSV under `data/processed/`. |
| `mibrgc/metrics.py` | Win rates and round-weighted player averages. |
| `mibrgc/insights.py` | The coaching notes. Thresholds live at the top of this file. |
| `mibrgc/__main__.py` | `fetch` and `build` commands. |
| `dashboard/app.py` | Local dashboard. |

`data/` is gitignored. A fresh clone needs `python -m mibrgc fetch` before the dashboard has rows.

Processed tables:

| File | One row is |
| --- | --- |
| `matches.csv` | A series |
| `maps.csv` | A map |
| `players.csv` | A player on one map, once per side (both, attack, defense) |
| `performance.csv` | Multikills, clutches, plants, and defuses for a player on one map |
| `economy_opening.csv` | Pistol, conversion, and bonus for one team on one map |
| `economy_buys.csv` | A buy-type matchup (eco / half / full) |
| `rounds.csv` | A round, including which side won it and how |

## First change

Edit `mibrgc/config.py` when the question changes team or year. `TEAM_NAMES` and `TEAM_TAGS` must match the labels VLR prints: overview pages use `MIBR.GC`, the performance table shortens the tag to `MIBR`.

Edit the constants at the top of `mibrgc/insights.py` when a win-rate cutoff should move. Add a chart in `dashboard/app.py` only after those two still describe the read you want.

## Data notes

VLR is the source of record. Attack and defense use VLR’s attacker/defender round counts. Player rating, ACS, KAST, ADR, and HS% are round-weighted across maps so a 12–0 does not count the same as an overtime. Strategy notes are hypotheses from those aggregates. They are not a substitute for watching the rounds.
