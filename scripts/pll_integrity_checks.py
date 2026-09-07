"""
Phase 3.5: season-level dataset integrity checks (final hardening pass).

Reads the built tables under data/processed/2026/ and the raw JSON under
data/raw/2026/, and reports the full set of counts/checks requested for the
Phase 3.5 hardening report. Prints a plain-text summary.
"""
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "2026"
PROC_DIR = REPO_ROOT / "data" / "processed" / "2026"


def main():
    games = pd.read_csv(PROC_DIR / "games.csv")
    teams = pd.read_csv(PROC_DIR / "teams.csv")
    players = pd.read_csv(PROC_DIR / "players.csv", dtype={"player_id": str})
    events = pd.read_csv(PROC_DIR / "events.csv", low_memory=False,
                          dtype={"player_id": str, "secondary_player_id": str, "team_id": str})
    unresolved_players = pd.read_csv(PROC_DIR / "unresolved_player_ids.csv")
    unresolved_teams = pd.read_csv(PROC_DIR / "unresolved_team_ids.csv")
    validation = pd.read_csv(PROC_DIR / "validation_report.csv")

    print("=== Schedule / game classification ===")
    print(f"Total scheduled games: {len(games)}")
    print(f"Completed games: {int(games['is_completed'].sum())}")
    print(f"Future/unplayed games: {int((~games['is_completed']).sum())}")
    gt = games.groupby(["game_type", "is_completed"]).size()
    print(gt)

    print()
    print("=== Table sizes ===")
    print(f"games.csv: {len(games)} | teams.csv: {len(teams)} | players.csv: {len(players)}")
    print(f"events.csv: {len(events)}")

    print()
    print("=== Event totals ===")
    print(events["event_type"].value_counts())
    print()
    print("total raw events:", len(events))
    print("total events flagged is_duplicate_event:", int(events["is_duplicate_event"].sum()))
    print("  by event_type:", dict(events.groupby("event_type")["is_duplicate_event"].sum()))
    print("total invalid goals (is_valid_goal==False):", int((events["is_valid_goal"] == False).sum()))  # noqa: E712
    print("total invalid penalties (is_valid_penalty==False):", int((events["is_valid_penalty"] == False).sum()))  # noqa: E712
    print("unique players:", len(players))
    print("unique teams:", len(teams), f"({int(teams['is_all_star_team'].sum())} all-star squads)")

    print()
    print("=== Player/team ID integrity (from raw JSON fields directly, not the normalized columns) ===")
    print(f"unresolved player IDs (build-time check, events.csv normalized columns): {len(unresolved_players)}")
    print(f"unresolved team IDs (build-time check): {len(unresolved_teams)}")

    known_players = set(players["player_id"])
    raw_id_fields = [
        "shooterId", "goalieId", "shotAssistId", "faceoffWinnerId", "faceoffLoserId",
        "gbPlayerId", "commitedPenaltyId", "offenseGoalieId", "assistOpportunityPlayerId",
        "closestDefenderId", "commitedTurnoverId", "causedTurnoverId",
    ]
    completed_slugs_for_ids = games.loc[games["is_completed"], "game_slug"].tolist()
    field_totals = {f: {"populated": 0, "resolved": 0, "unresolved": set()} for f in raw_id_fields}
    for slug in completed_slugs_for_ids:
        items = json.loads((RAW_DIR / slug / "play_by_play.json").read_text())["data"]["items"]
        for it in items:
            for f in raw_id_fields:
                v = it.get(f)
                if v not in (None, ""):
                    field_totals[f]["populated"] += 1
                    if v in known_players:
                        field_totals[f]["resolved"] += 1
                    else:
                        field_totals[f]["unresolved"].add(v)

    print(f"{'field':28s} {'populated':>10s} {'resolved':>10s} {'unresolved':>11s}")
    for f in raw_id_fields:
        t = field_totals[f]
        print(f"{f:28s} {t['populated']:10d} {t['resolved']:10d} {len(t['unresolved']):11d}")

    print()
    print("=== Analysis eligibility (league-analytics-scoped events) ===")
    print(events["is_analysis_eligible_event"].value_counts())
    print("events by game_type:", dict(events["game_type"].value_counts()))

    print()
    print("=== Validation report (Phase 3.5 raw/cleaned/final schema) ===")
    total = len(validation)
    counts = validation["final_status"].value_counts()
    print(counts)
    for status in ("PASS", "KNOWN_DATA_ISSUE", "UNRESOLVED"):
        n = counts.get(status, 0)
        print(f"  {status}: {n}/{total} = {100*n/total:.1f}%")

    print()
    print("=== Duplicate/malformed detail ===")
    dup_by_type = events.groupby("event_type")["is_duplicate_event"].sum()
    print("is_duplicate_event by type:")
    print(dup_by_type[dup_by_type > 0])

    print()
    print("=== Structural integrity checks ===")
    dup_game_ids = games["game_id"][games["game_id"].duplicated()].tolist()
    print(f"Duplicate game_id: {dup_game_ids if dup_game_ids else 'none'}")

    completed_events = events[events["game_slug"].isin(games.loc[games["is_completed"], "game_slug"])]
    dup_events = completed_events.groupby("game_slug")["event_id"].apply(lambda s: s[s.duplicated()].tolist())
    dup_events = {k: v for k, v in dup_events.items() if v}
    print(f"Duplicate event_id within a game: {dup_events if dup_events else 'none'}")

    bad_progression = []
    for slug, g in events.groupby("game_slug"):
        h, a = g["home_score_corrected"].values, g["away_score_corrected"].values
        if any(h[i] > h[i + 1] for i in range(len(h) - 1)) or any(a[i] > a[i + 1] for i in range(len(a) - 1)):
            bad_progression.append(slug)
    print(f"Non-monotonic corrected score progression: {bad_progression if bad_progression else 'none'}")

    completed_slugs = set(games.loc[games["is_completed"], "game_slug"])
    events_slugs = set(events["game_slug"])
    print(f"Completed games with no events at all: {sorted(completed_slugs - events_slugs) or 'none'}")


if __name__ == "__main__":
    main()
