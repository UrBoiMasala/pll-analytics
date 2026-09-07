"""
Phase 3: full-season raw data ingestion.

Discovers all 2026 games from the public schedule endpoint, classifies them
by status, and downloads the 4 per-game endpoints (play-by-play, game meta,
player stats, team stats) for every completed game, under:

    data/raw/2026/<slug>/{play_by_play,game_meta,players_stats,teams_stats}.json

Safely resumable and safe to rerun after the season progresses: the
schedule is always re-fetched fresh (so newly-completed games are detected
automatically — a game's eventStatus can change from 0 to 3 between runs),
but a given completed game's 4 raw files are only downloaded once — a game
is skipped (no network call) if all 4 already exist and parse as valid
non-empty JSON. Games with eventStatus==0 (not yet played) are never
queried beyond the schedule row itself — no play-by-play/box-score request
is made for them, since that data doesn't exist yet. Polite rate limiting
(sleep between requests) is applied. Failures are logged and do not stop
the run; a summary of failed games is printed and saved at the end so a
re-run can retry just those. Nothing here hard-codes a game count — the
schedule response is the sole source of truth for how many games exist and
which are complete.

Usage:
    python3 pll_ingest_season.py [--force] [--sleep 0.4]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "https://stats.premierlacrosseleague.com/api/v4"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_PATH = REPO_ROOT / "data" / "raw" / "2026" / "_schedule" / "games_2026.json"

ENDPOINTS = {
    "play_by_play": "games/{slug}/play-by-plays",
    "game_meta": "games/{slug}",
    "players_stats": "games/{slug}/players/stats",
    "teams_stats": "games/{slug}/teams/stats",
}


def referer_for(slug: str) -> str:
    return f"https://stats.premierlacrosseleague.com/games/2026/{slug}?tab=plays"


def fetch_json(url: str, slug: str) -> dict:
    headers = dict(HEADERS)
    headers["Referer"] = referer_for(slug)
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_schedule(offline: bool = False) -> dict:
    """
    The schedule is always re-fetched (it's one cheap request) so that
    reruns detect games that have newly completed since the last run —
    unlike per-game raw data, it is NOT treated as immutable/cached,
    because its content (eventStatus) changes over time for the same URL.
    Pass offline=True only to reuse the last-saved copy (e.g. for local
    testing without network access); this is not used in normal operation.
    """
    if offline:
        return json.loads(SCHEDULE_PATH.read_text())
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_json(f"{BASE_URL}/games?year=2026", "schedule")
    SCHEDULE_PATH.write_text(json.dumps(data, indent=2))
    return data


def classify_games(schedule: dict):
    items = schedule["data"]["items"]
    completed, upcoming, other = [], [], []
    for it in items:
        status = it.get("eventStatus")
        if status == 3:
            completed.append(it)
        elif status == 0:
            upcoming.append(it)
        else:
            other.append(it)
    return completed, upcoming, other


def raw_dir_for(slug: str) -> Path:
    return REPO_ROOT / "data" / "raw" / "2026" / slug


def already_cached(slug: str) -> bool:
    d = raw_dir_for(slug)
    for name in ENDPOINTS:
        p = d / f"{name}.json"
        if not p.exists():
            return False
        try:
            content = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        if not content:
            return False
    return True


def ingest_game(slug: str, sleep_sec: float) -> dict:
    d = raw_dir_for(slug)
    d.mkdir(parents=True, exist_ok=True)
    result = {"slug": slug, "ok": True, "errors": []}
    for name, path_tmpl in ENDPOINTS.items():
        out_path = d / f"{name}.json"
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text())
                if existing:
                    continue
            except (json.JSONDecodeError, OSError):
                pass
        url = f"{BASE_URL}/{path_tmpl.format(slug=slug)}"
        try:
            data = fetch_json(url, slug)
            out_path.write_text(json.dumps(data, indent=2))
        except Exception as e:  # noqa: BLE001
            result["ok"] = False
            result["errors"].append(f"{name}: {e}")
        time.sleep(sleep_sec)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-download game data even if cached")
    parser.add_argument("--offline", action="store_true", help="reuse the last-saved schedule instead of re-fetching")
    parser.add_argument("--sleep", type=float, default=0.4, help="seconds between requests")
    args = parser.parse_args()

    print("Fetching schedule ..." if not args.offline else "Loading cached schedule (--offline) ...")
    schedule = fetch_schedule(offline=args.offline)
    completed, upcoming, other = classify_games(schedule)
    print(f"Schedule: {len(schedule['data']['items'])} total games — "
          f"{len(completed)} completed, {len(upcoming)} upcoming/not-started, {len(other)} other-status")
    print(f"  never fetches play-by-play/box-score data for upcoming/not-started games — "
          f"those 3-endpoint calls are only made for eventStatus==3 games")
    if other:
        print("  other-status games:", [(g["slugname"], g.get("eventStatus")) for g in other])

    failures = []
    skipped = 0
    fetched = 0
    for i, g in enumerate(completed, 1):
        slug = g["slugname"]
        if not args.force and already_cached(slug):
            skipped += 1
            continue
        print(f"[{i}/{len(completed)}] fetching {slug} ...")
        result = ingest_game(slug, args.sleep)
        if result["ok"]:
            fetched += 1
        else:
            failures.append(result)
            print(f"  ERROR: {result['errors']}")

    print()
    print(f"Done. {fetched} games freshly fetched, {skipped} already cached (skipped), {len(failures)} failed.")
    if failures:
        print("Failed games:", [f["slug"] for f in failures])
        fail_path = REPO_ROOT / "data" / "raw" / "2026" / "_schedule" / "ingest_failures.json"
        fail_path.write_text(json.dumps(failures, indent=2))
        print(f"Saved failure details to {fail_path.relative_to(REPO_ROOT)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
