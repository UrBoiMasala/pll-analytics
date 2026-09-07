"""
PLL play-by-play extractor (originated as a Phase 1 proof of concept;
`normalize_play_by_play` is still active, load-bearing code).

Pulls play-by-play, game metadata, and player-stats JSON directly from the
PLL stats site's public REST API (api/v4), saves the raw responses, and
normalizes the play-by-play into a flat per-event pandas DataFrame.

`normalize_play_by_play` (and `build_player_lookup`/`build_team_lookup`) are
imported directly by `pll_build_tables.py` and used for every game in the
season-wide pipeline — this module is NOT legacy/archived code even though
its own `main()`/CLI below (fetch one game, write it standalone to
`data/processed/<slug>_play_by_play.csv`) has been superseded by the
season builder and is kept only for ad hoc single-game debugging. The
Phase 1/2 per-game CSVs this `main()` used to produce for 6 sample games
have been archived; see `archive/legacy_phase1_2/README.md`.

Usage:
    python3 pll_pbp_extractor.py 2026-ev-1
"""
import json
import sys
from pathlib import Path

import pandas as pd
import requests

from pll_pbp_clean import clean

BASE_URL = "https://stats.premierlacrosseleague.com/api/v4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

REPO_ROOT = Path(__file__).resolve().parent.parent


def referer_for(slug: str) -> str:
    return f"https://stats.premierlacrosseleague.com/games/{slug.split('-')[0]}/{slug}?tab=plays"


def fetch_json(url: str, slug: str) -> dict:
    headers = dict(HEADERS)
    headers["Referer"] = referer_for(slug)
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_game_raw(slug: str, year: int) -> dict:
    """Fetch play-by-play, game meta, and player stats; save raw JSON to disk."""
    raw_dir = REPO_ROOT / "data" / "raw" / str(year) / slug
    raw_dir.mkdir(parents=True, exist_ok=True)

    endpoints = {
        "play_by_play": f"{BASE_URL}/games/{slug}/play-by-plays",
        "game_meta": f"{BASE_URL}/games/{slug}",
        "players_stats": f"{BASE_URL}/games/{slug}/players/stats",
        "teams_stats": f"{BASE_URL}/games/{slug}/teams/stats",
    }

    raw = {}
    for name, url in endpoints.items():
        data = fetch_json(url, slug)
        raw[name] = data
        out_path = raw_dir / f"{name}.json"
        out_path.write_text(json.dumps(data, indent=2))
        print(f"  saved {out_path.relative_to(REPO_ROOT)}")

    return raw


def build_player_lookup(players_stats_json: dict) -> dict:
    """Map officialId -> {'name': ..., 'team': ...}."""
    items = players_stats_json["data"]["items"]
    lookup = {}
    for p in items:
        lookup[p["officialId"]] = {
            "name": f"{p['firstName']} {p['lastName']}",
            "team": p["teamId"],
        }
    return lookup


def build_team_lookup(game_meta_json: dict) -> dict:
    """Map team code (officialId) -> full team name."""
    data = game_meta_json["data"]
    lookup = {}
    for side in ("homeTeam", "awayTeam"):
        t = data[side]
        lookup[t["officialId"]] = f"{t['location']} {t['fullName']}"
    return lookup


def player_name(player_lookup: dict, pid):
    if not pid:
        return None
    return player_lookup.get(pid, {}).get("name")


def normalize_play_by_play(slug: str, raw: dict) -> pd.DataFrame:
    items = raw["play_by_play"]["data"]["items"]
    player_lookup = build_player_lookup(raw["players_stats"])
    team_lookup = build_team_lookup(raw["game_meta"])

    rows = []
    for i, it in enumerate(items):
        event_type = it.get("eventType")
        team_id = it.get("teamId") or None

        # Primary actor / secondary actor depend on event type.
        player_id = None
        secondary_player_id = None

        if event_type in ("shot", "goal"):
            player_id = it.get("shooterId")
            secondary_player_id = it.get("shotAssistId")
        elif event_type == "faceoff":
            player_id = it.get("faceoffWinnerId")
            secondary_player_id = it.get("faceoffLoserId")
        elif event_type == "groundball":
            player_id = it.get("gbPlayerId")
        elif event_type == "penalty":
            player_id = it.get("commitedPenaltyId")

        details = it.get("details") or {}

        rows.append({
            "game_id": slug,
            "event_id": it.get("markerId"),
            "event_number": i,
            "period": it.get("period"),
            "clock": f"{it.get('minutes', 0):02d}:{it.get('seconds', 0):02d}",
            "seconds_passed": it.get("secondsPassed"),
            "team_id": team_id,
            "team": team_lookup.get(team_id) if team_id else None,
            "player_id": player_id,
            "player": player_name(player_lookup, player_id),
            "secondary_player_id": secondary_player_id,
            "secondary_player": player_name(player_lookup, secondary_player_id),
            "event_type": event_type,
            "shot_type": it.get("shotType") or None,
            "description": it.get("description"),
            "home_score_raw": it.get("homeScore"),
            "away_score_raw": it.get("visitorScore"),
            "gb_player_id": it.get("gbPlayerId") if event_type == "faceoff" else None,
            "goalie_id": it.get("goalieId"),
            "goalie": player_name(player_lookup, it.get("goalieId")),
            "shot_on_goal": details.get("shotOnGoal"),
            "shot_saved": details.get("shotSaved"),
            "save_type": details.get("saveType"),
            "penalty_length_sec": it.get("penaltyLength"),
            "penalty_description": it.get("penaltyDescription"),
            "away_win_prob": it.get("awayTeamWinProbability"),
            "home_win_prob": it.get("homeTeamWinProbability"),
        })

    return pd.DataFrame(rows)


def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "2026-ev-1"
    year = int(slug.split("-")[0])

    print(f"Fetching raw data for {slug} ...")
    raw = fetch_game_raw(slug, year)

    print("Normalizing play-by-play ...")
    df = normalize_play_by_play(slug, raw)

    print("Applying cleaning/validation rules ...")
    df = clean(df)

    processed_dir = REPO_ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_dir / f"{slug}_play_by_play.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path.relative_to(REPO_ROOT)}")

    return df


if __name__ == "__main__":
    main()
