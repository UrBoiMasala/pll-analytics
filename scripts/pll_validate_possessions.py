"""
Phase 4: possession-reconstruction validation.

Runs the 18 checks specified for Phase 4 against data/processed/2026/
possessions.csv, cross-referenced with events.csv/games.csv/teams.csv.
Outputs data/processed/2026/possession_validation_report.csv with columns:
check_id, check_name, status (PASS/FAIL), n_failures, detail

Does not modify possessions.csv. A FAIL here means the possession dataset
has a genuine structural problem needing investigation — not a stylistic
nitpick.
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"


def set_season(year: int) -> None:
    """Phase 9: point this validator at a season. Default stays 2026."""
    global DATA_DIR
    DATA_DIR = REPO_ROOT / "data" / "processed" / str(year)


def main():
    poss = pd.read_csv(DATA_DIR / "possessions.csv")
    events = pd.read_csv(
        DATA_DIR / "events.csv", low_memory=False,
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str, "event_id": str},
    )
    games = pd.read_csv(DATA_DIR / "games.csv")
    teams = pd.read_csv(DATA_DIR / "teams.csv")

    eligible_games = games[games["is_completed"] & games["include_in_league_analytics"]]
    eligible_game_ids = set(eligible_games["game_id"])
    elig_events = events[events["is_analysis_eligible_event"] == True]  # noqa: E712

    results = []

    def check(check_id, name, fail_mask_or_count, detail=""):
        if isinstance(fail_mask_or_count, pd.Series):
            n_fail = int(fail_mask_or_count.sum())
        else:
            n_fail = int(fail_mask_or_count)
        results.append({
            "check_id": check_id, "check_name": name,
            "status": "PASS" if n_fail == 0 else "FAIL",
            "n_failures": n_fail, "detail": detail,
        })

    # 1. Every possession belongs to exactly one eligible completed game.
    bad = ~poss["game_id"].isin(eligible_game_ids)
    check(1, "possession_belongs_to_eligible_completed_game", bad,
          f"{bad.sum()} possessions reference a game_id not in the eligible completed set")

    # 2. Every possession has exactly one offense team (non-null, single value).
    bad = poss["offense_team_id"].isna()
    check(2, "possession_has_one_offense_team", bad, f"{bad.sum()} possessions have null offense_team_id")

    # 3. offense_team_id != defense_team_id.
    bad = poss["offense_team_id"] == poss["defense_team_id"]
    check(3, "offense_defense_distinct", bad, f"{bad.sum()} possessions have offense==defense")

    # 4. Both offense and defense teams are participants in that game.
    g_teams = eligible_games.set_index("game_id")[["home_team_id", "away_team_id"]]
    merged = poss.merge(g_teams, on="game_id", how="left")
    bad = ~(
        ((merged["offense_team_id"] == merged["home_team_id"]) | (merged["offense_team_id"] == merged["away_team_id"]))
        & ((merged["defense_team_id"] == merged["home_team_id"]) | (merged["defense_team_id"] == merged["away_team_id"]))
    )
    check(4, "teams_are_game_participants", bad, f"{bad.sum()} possessions have a team not in that game's home/away pair")

    # 5. possession_number is sequential within each game (1..N, no gaps/dupes).
    bad_games = []
    for slug, g in poss.groupby("game_slug"):
        nums = sorted(g["possession_number"].tolist())
        if nums != list(range(1, len(nums) + 1)):
            bad_games.append(slug)
    check(5, "possession_number_sequential_per_game", len(bad_games), f"games with non-sequential numbering: {bad_games}")

    # 6. No possession crosses a period boundary — verify every event in
    # [start_event_number, end_event_number] for that game shares the same period.
    bad_rows = 0
    bad_examples = []
    ev_by_game = {slug: g.sort_values("event_number").set_index("event_number") for slug, g in elig_events.groupby("game_slug")}
    for row in poss.itertuples():
        g = ev_by_game.get(row.game_slug)
        if g is None:
            continue
        window = g[(g.index >= row.start_event_number) & (g.index <= row.end_event_number)]
        if window["period"].nunique() > 1:
            bad_rows += 1
            if len(bad_examples) < 10:
                bad_examples.append(row.possession_id)
    check(6, "possession_within_single_period", bad_rows, f"examples: {bad_examples}")

    # 7. duration_seconds is never negative.
    bad = poss["duration_seconds"] < 0
    check(7, "duration_non_negative", bad, f"{bad.sum()} possessions have negative duration")

    # 8. Every valid goal is assigned to exactly one possession (or documented anomaly).
    # event_id markers (e.g. "shot-800") recur across DIFFERENT games — every
    # comparison here must use the (game_slug, event_id) composite key, never
    # the bare marker string.
    valid_goal_keys = set(zip(
        elig_events.loc[(elig_events["event_type"] == "goal") & (elig_events["is_valid_goal"] == True), "game_slug"],  # noqa: E712
        elig_events.loc[(elig_events["event_type"] == "goal") & (elig_events["is_valid_goal"] == True), "event_id"],  # noqa: E712
    ))
    goal_ends = poss.loc[poss["end_reason"] == "goal", ["game_slug", "end_event_id"]]
    goal_end_keys = list(zip(goal_ends["game_slug"], goal_ends["end_event_id"]))
    seen, dup_goal_ends = set(), []
    for k in goal_end_keys:
        if k in seen:
            dup_goal_ends.append(k)
        seen.add(k)
    missing_goals = valid_goal_keys - set(goal_end_keys)
    check(8, "every_valid_goal_in_exactly_one_possession", len(dup_goal_ends) + len(missing_goals),
          f"duplicated goal (game,end_event_id) keys: {dup_goal_ends}; valid goals missing from any possession: {sorted(missing_goals)[:10]}")

    # 9. Points summed from possessions reconcile with final game scores.
    pts = poss.groupby(["game_slug", "offense_team_id"])["points_scored"].sum().reset_index()
    mismatches = []
    for _, g in eligible_games.iterrows():
        slug = g["game_slug"]
        home_pts = pts[(pts["game_slug"] == slug) & (pts["offense_team_id"] == g["home_team_id"])]["points_scored"].sum()
        away_pts = pts[(pts["game_slug"] == slug) & (pts["offense_team_id"] == g["away_team_id"])]["points_scored"].sum()
        if home_pts != g["home_score"] or away_pts != g["away_score"]:
            mismatches.append((slug, home_pts, g["home_score"], away_pts, g["away_score"]))
    check(9, "points_reconcile_with_final_score", len(mismatches), f"{mismatches}")

    # event_id is only unique WITHIN a game (e.g. "faceoff-100" recurs every
    # game) — key lookups by (game_slug, event_id) throughout.
    ev_team_by_key = elig_events.set_index(["game_slug", "event_id"])["team_id"]

    def team_for(game_slug_series, event_id_series):
        return pd.Series(
            [ev_team_by_key.get((g, e)) for g, e in zip(game_slug_series, event_id_series)],
            index=game_slug_series.index,
        )

    # 10. A possession cannot contain scoring by both teams — by construction
    # goals only accrue to the offense team; verify no possession's goal
    # count could include a wrong-team goal by checking end_event's team
    # matches offense_team_id whenever end_reason == 'goal'.
    goal_rows = poss[poss["end_reason"] == "goal"]
    mismatched_team = team_for(goal_rows["game_slug"], goal_rows["end_event_id"]) != goal_rows["offense_team_id"]
    check(10, "no_possession_scored_by_both_teams", mismatched_team, f"{int(mismatched_team.sum())} goal-ending possessions where the goal's team != offense_team_id")

    # 11. Exact duplicate events cannot create duplicate possession boundaries
    # — verify no duplicate-flagged event_id appears as any possession's
    # start/end event (they were excluded from the eligible-event input).
    dup_keys = set(zip(events.loc[events["is_duplicate_event"] == True, "game_slug"],  # noqa: E712
                       events.loc[events["is_duplicate_event"] == True, "event_id"]))  # noqa: E712
    bad = pd.Series(
        [(g, s) in dup_keys or (g, e) in dup_keys for g, s, e in zip(poss["game_slug"], poss["start_event_id"], poss["end_event_id"])],
        index=poss.index,
    )
    check(11, "duplicates_excluded_from_boundaries", bad, f"{int(bad.sum())} possessions reference a duplicate-flagged event as a boundary")

    # 12. Consecutive possessions should normally alternate teams (diagnostic,
    # not a hard failure) — report the rate, not a pass/fail threshold.
    same_team_streak = 0
    total_consec = 0
    for slug, g in poss.sort_values(["game_slug", "possession_number"]).groupby("game_slug"):
        offs = g["offense_team_id"].tolist()
        for i in range(1, len(offs)):
            total_consec += 1
            if offs[i] == offs[i - 1]:
                same_team_streak += 1
    rate = same_team_streak / total_consec if total_consec else 0
    results.append({
        "check_id": 12, "check_name": "consecutive_possessions_alternate_teams_rate",
        "status": "INFO", "n_failures": same_team_streak,
        "detail": f"{same_team_streak}/{total_consec} ({100*rate:.1f}%) consecutive possessions share the same offense team; "
                  f"expected to be non-zero (transient turnover-evidenced possessions, ambiguous-conflict re-opens) — diagnostic only, not a hard failure",
    })

    # 13. A goal cannot accidentally generate two possessions — same check as #8's dup component.
    check(13, "goal_generates_exactly_one_possession", len(dup_goal_ends), f"duplicated goal (game,end_event_id) keys: {dup_goal_ends}")

    # 14. turnover + shotclockexpired redundancy cannot generate two possession
    # changes for the same real transition — verify no two possessions in the
    # same game/period have end_seconds_passed equal AND consecutive
    # possession_number with both end_reason in {turnover, shot_clock_expiration}
    # for the SAME team （which would indicate the redundant-pair suppression failed).
    bad = 0
    examples = []
    for slug, g in poss.sort_values(["game_slug", "possession_number"]).groupby("game_slug"):
        g = g.reset_index(drop=True)
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if (a["end_reason"] in ("turnover", "shot_clock_expiration") and b["end_reason"] in ("turnover", "shot_clock_expiration")
                    and a["offense_team_id"] == b["offense_team_id"] and a["end_seconds_passed"] == b["end_seconds_passed"]):
                bad += 1
                if len(examples) < 10:
                    examples.append((slug, a["possession_id"], b["possession_id"]))
    check(14, "turnover_shotclock_redundancy_collapsed", bad, f"examples: {examples}")

    # 15. Offensive ground-ball recovery after a shot must not automatically
    # create a new possession — verify no possession boundary (end_event) is
    # a groundball event whose team matches the possession's own offense_team_id
    # (that should be a continuation, not a boundary).
    gb_ends = poss[poss["end_reason"] == "defensive_ground_ball"]
    end_team = team_for(gb_ends["game_slug"], gb_ends["end_event_id"])
    bad = end_team == gb_ends["offense_team_id"]
    check(15, "offensive_rebound_does_not_end_possession", bad, f"{int(bad.sum())} 'defensive_ground_ball' ends where the recovering team matches the possession's own offense team")

    # 16. Defensive recovery after a loose-ball sequence should create the
    # appropriate possession change — verify every 'defensive_ground_ball'
    # end is immediately followed (same game) by a possession whose offense
    # team equals the recovering (groundball) team.
    bad = 0
    for slug, g in poss.sort_values(["game_slug", "possession_number"]).groupby("game_slug"):
        g = g.reset_index(drop=True)
        for i in range(len(g) - 1):
            if g.loc[i, "end_reason"] == "defensive_ground_ball":
                end_ev_team = ev_team_by_key.get((slug, g.loc[i, "end_event_id"]))
                if g.loc[i + 1, "offense_team_id"] != end_ev_team:
                    bad += 1
    check(16, "defensive_recovery_starts_new_possession_for_recovering_team", bad)

    # 17. No possession should have an impossible or unknown team when
    # sufficient event evidence exists — report count of start_reason=='unknown'.
    bad = (poss["start_reason"] == "unknown").sum()
    check(17, "no_unknown_team_possessions", bad, f"{bad} possessions used the 'unknown' start_reason (should be 0 — every opening event type carries a team_id)")

    # 18. All-Star games must not contaminate normal league analytical output.
    all_star_ids = set(games.loc[games["game_type"] == "all_star", "game_id"])
    bad = poss["game_id"].isin(all_star_ids)
    check(18, "no_all_star_possessions", bad, f"{int(bad.sum())} possessions belong to an all-star game")

    report = pd.DataFrame(results)
    out_path = DATA_DIR / "possession_validation_report.csv"
    report.to_csv(out_path, index=False)
    print(f"Saved possession validation report ({len(report)} rows) to {out_path.relative_to(REPO_ROOT)}")
    print()
    print(report[["check_id", "check_name", "status", "n_failures"]].to_string(index=False))
    fails = report[report["status"] == "FAIL"]
    if len(fails):
        print()
        print("=== FAIL details ===")
        for _, r in fails.iterrows():
            print(f"[{r['check_id']}] {r['check_name']}: {r['detail']}")
    return report


if __name__ == "__main__":
    main()
