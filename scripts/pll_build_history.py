"""
Phase 9: historical pipeline driver for 2022-2025.

Runs the EXISTING, validated Phase 1-4 pipeline against a historical season by
pointing its season state at that year. Nothing about the cleaning rules, the
table construction or the possession reconstruction is re-implemented or tuned
per season -- that is the whole point. If a historical season produces a
different possession profile, that has to be a fact about the season rather
than a fact about a rule someone adjusted to make it look tidy.

Per season it produces, under data/processed/<year>/:
    games.csv, teams.csv, players.csv, events.csv,
    player_game_stats.csv, team_game_stats.csv,
    team_game_stats_exceptions.csv, unresolved_player_ids.csv,
    unresolved_team_ids.csv, possessions.csv

and appends to data/processed/history/historical_ingestion_report.csv.

Usage:
    python3 pll_build_history.py                # 2022-2025
    python3 pll_build_history.py --years 2023   # one season
"""
import argparse
import io
import json
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pll_build_tables as bt            # noqa: E402
import pll_build_possessions as bp       # noqa: E402
import pll_validate_season as vseason    # noqa: E402
import pll_validate_possessions as vposs # noqa: E402

HISTORY_SEASONS = [2022, 2023, 2024, 2025]
OUT_DIR = REPO_ROOT / "data" / "processed" / "history"

# validate_season writes validation_report.csv, which the Phase 5 layer reads;
# validate_possessions writes possession_validation_report.csv. Both are part of
# building a season, not an afterthought, so they run in the pipeline.
STAGES = ["build_tables", "build_possessions", "validate_season", "validate_possessions"]


def raw_meta_for(season: int, slug: str) -> dict:
    p = REPO_ROOT / "data" / "raw" / str(season) / slug / "_meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def run_season(season: int) -> list:
    """Run every pipeline stage for one season. Restartable and idempotent:
    each stage rewrites its own outputs from the raw corpus, so re-running is
    safe and produces identical files."""
    rows = []
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = REPO_ROOT / "data" / "processed" / str(season)
    out.mkdir(parents=True, exist_ok=True)

    for stage in STAGES:
        buf = io.StringIO()
        status, detail = "ok", ""
        try:
            with redirect_stdout(buf):
                mod = {"build_tables": bt, "build_possessions": bp,
                       "validate_season": vseason,
                       "validate_possessions": vposs}[stage]
                mod.set_season(season)
                mod.main()
        except Exception:  # noqa: BLE001
            status = "failed"
            detail = traceback.format_exc().strip().splitlines()[-1]
        log = buf.getvalue()
        rows.append({
            "season": season, "stage": stage, "status": status,
            "detail": detail or log.strip().splitlines()[-1] if log.strip() else detail,
            "run_at_utc": ts,
            "log": log.replace("\n", " | ")[:2000],
        })
        print(f"  [{season}] {stage:20s} {status}")
        if status == "failed":
            print("      " + detail)
            break
    return rows


def game_inventory(seasons) -> pd.DataFrame:
    """One row per scheduled game across every season, from the schedule
    response plus what actually landed on disk. This is the completeness
    ledger: every scheduled game appears, whether or not it was ingested."""
    rows = []
    for season in seasons:
        sched_p = (REPO_ROOT / "data" / "raw" / str(season) / "_schedule"
                   / f"games_{season}.json")
        if not sched_p.exists():
            continue
        for g in json.loads(sched_p.read_text())["data"]["items"]:
            slug = g["slugname"]
            gdir = REPO_ROOT / "data" / "raw" / str(season) / slug
            pbp_p = gdir / "play_by_play.json"
            n_events = None
            pbp_status = "absent"
            if pbp_p.exists():
                try:
                    items = json.loads(pbp_p.read_text())["data"]["items"]
                    n_events = len(items)
                    pbp_status = "present" if n_events else "empty"
                except (json.JSONDecodeError, OSError, KeyError):
                    pbp_status = "malformed"
            seg = g.get("seasonSegment")
            completed = bt.is_completed(g)
            game_type = bt.classify_game_type(seg)
            meta = raw_meta_for(season, slug)
            rows.append({
                "season": season,
                "game_slug": slug,
                "season_segment": seg,
                "game_type": game_type,
                "event_status": g.get("eventStatus"),
                "is_completed": completed,
                "is_competitive": game_type in ("regular_season", "playoffs"),
                "include_in_league_analytics": game_type in ("regular_season", "playoffs"),
                "home_team_id": (g.get("homeTeam") or {}).get("officialId"),
                "away_team_id": (g.get("awayTeam") or {}).get("officialId"),
                "home_score": g.get("homeScore"),
                "away_score": g.get("visitorScore"),
                "pbp_status": pbp_status,
                "n_raw_events": n_events,
                "raw_endpoints_on_disk": sum(
                    (gdir / f"{n}.json").exists()
                    for n in ("play_by_play", "game_meta", "players_stats", "teams_stats")),
                "retrieved_at_utc": (meta.get("play_by_play") or {}).get("retrieved_at"),
                "source_url": (meta.get("play_by_play") or {}).get("url"),
                "raw_content_hash": (meta.get("play_by_play") or {}).get("content_hash"),
            })
    df = pd.DataFrame(rows)

    def exception_reason(r):
        if not r["is_competitive"]:
            return f"excluded_by_design: seasonSegment={r['season_segment']}"
        if not r["is_completed"]:
            return "not_completed"
        if r["pbp_status"] == "present" and r["n_raw_events"] and r["n_raw_events"] >= 50:
            return ""
        if r["pbp_status"] == "present":
            return f"suspiciously_short_pbp: only {r['n_raw_events']} events"
        return f"missing_pbp: {r['pbp_status']}"

    df["exception_reason"] = df.apply(exception_reason, axis=1)
    df["admitted_to_analytics"] = (df["is_competitive"] & df["is_completed"]
                                   & (df["exception_reason"] == ""))
    return df.sort_values(["season", "game_slug"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=str, default=None,
                    help="comma-separated seasons (default 2022,2023,2024,2025)")
    args = ap.parse_args()
    seasons = ([int(y) for y in args.years.split(",")] if args.years
               else list(HISTORY_SEASONS))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report = []
    for season in seasons:
        print(f"=== {season} ===")
        report.extend(run_season(season))

    rep = pd.DataFrame(report)
    rep_path = OUT_DIR / "historical_ingestion_report.csv"
    rep.to_csv(rep_path, index=False)
    print(f"\nWrote {rep_path.relative_to(REPO_ROOT)} ({len(rep)} stage rows)")

    # Phase 11 fix: this always included 2026 in the completeness ledger
    # (regardless of --years) so the ledger stays a full 2022-2026 picture
    # even when --years only rebuilds a subset -- but it appended 2026
    # unconditionally, so explicitly passing 2026 in --years (as Phase 11's
    # rebuild does) silently doubled every 2026 row. Dedup instead.
    inv = game_inventory(sorted(set(seasons) | {2026}))
    inv_path = OUT_DIR / "historical_game_inventory.csv"
    inv.to_csv(inv_path, index=False)
    print(f"Wrote {inv_path.relative_to(REPO_ROOT)} ({len(inv)} scheduled games)")

    summary = inv.groupby("season").agg(
        scheduled=("game_slug", "size"),
        completed=("is_completed", "sum"),
        competitive=("is_competitive", "sum"),
        admitted=("admitted_to_analytics", "sum"),
        exceptions=("exception_reason", lambda s: (s != "").sum()),
    )
    print("\n" + summary.to_string())
    exc = inv[(inv["exception_reason"] != "") & inv["is_competitive"]]
    if len(exc):
        print("\nCompetitive games NOT admitted:")
        print(exc[["season", "game_slug", "exception_reason"]].to_string(index=False))
    else:
        print("\nEvery completed competitive game in every season was admitted.")
    return rep, inv


if __name__ == "__main__":
    main()
