"""
Phase 3.5: validation with explicit raw-vs-cleaned semantics.

For every metric, in every completed game, computes BOTH a raw value
(computed directly from the raw event fields, no cleaning applied) and a
cleaned value (after applying the validation/dedup flags from
pll_pbp_clean.py), alongside the official PLL box-score value. See
VALIDATION_METHODOLOGY.md for the full rationale and status definitions.

Outputs data/processed/2026/validation_report.csv with columns:
game_slug, metric, raw_value, cleaned_value, official_value,
raw_difference, cleaned_difference, raw_status, cleaned_status,
final_status, notes

Status definitions (see VALIDATION_METHODOLOGY.md for the full writeup):
  raw_status / cleaned_status: PASS if that value matches official exactly,
    else MISMATCH.
  final_status:
    PASS             = cleaned_value matches official exactly.
    KNOWN_DATA_ISSUE  = cleaned still mismatches, but the discrepancy is
                        understood and attributable to a documented,
                        bounded PLL feed issue (never assigned merely
                        because the difference is small — see the
                        magnitude caps below, drawn from what was actually
                        observed and root-caused during investigation).
    UNRESOLVED        = cleaned still mismatches and we cannot confidently
                        explain why (or the mismatch exceeds the bound of
                        what's been investigated and documented).
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"

# Metrics with a DOCUMENTED, evidence-based dedup/validity mechanism (see
# FULL_SEASON_ANOMALIES.md), each with a magnitude cap drawn from what was
# actually observed and investigated. This cap is a SAFETY CEILING, not by
# itself sufficient evidence — see final_status() below: a per-game,
# per-metric mismatch is only ever called KNOWN_DATA_ISSUE if cleaning
# *actually found and excluded something in that specific game* (i.e.
# cleaned_value != raw_value) AND the residual is within the cap. A game
# where cleaning found nothing to exclude, yet a gap still exists, has NO
# evidence behind it for that game and is UNRESOLVED regardless of metric —
# this prevents one game's understood duplicate-logging incident from
# quietly absorbing a different, unexplained gap in another game that
# happens to share a metric name.
KNOWN_ISSUE_CAPS = {
    "caused_turnovers": None,     # unconditional structural issue, not evidence-dependent — see final_status()
    "ground_balls": 3,            # max observed residual, among games where a duplicate WAS found and excluded
    "turnovers": 3,
    "faceoff_wins": 2,
    "penalties": 5,               # covers the 2026-ev-38 chaotic-incident residual
}

NOTES = {
    "final_home_score": "",
    "final_away_score": "",
    "scoring_plays": "cleaned excludes any mislabeled saved-shot events (is_valid_goal).",
    "one_point_goals": "cleaned excludes any mislabeled saved-shot events (is_valid_goal).",
    "two_point_goals": "cleaned excludes any mislabeled saved-shot events (is_valid_goal).",
    "shots": "",
    "shots_on_goal": "",
    "saves": "No duplicate/mislabeling mechanism has been found for shot-save events; any residual is UNRESOLVED, not assumed-known.",
    "faceoff_wins": "cleaned excludes exact-duplicate faceoff events (is_duplicate_event). Residual >2 would be UNRESOLVED.",
    "turnovers": "cleaned excludes exact-duplicate turnover events (is_duplicate_event). Residual >3 would be UNRESOLVED.",
    "caused_turnovers": "causedTurnoverId is always null in the pbp feed; not attributable at all from play-by-play. Always a known miss.",
    "ground_balls": "cleaned excludes exact-duplicate groundball events (is_duplicate_event). Residual >3 would be UNRESOLVED.",
    "penalties": "cleaned excludes malformed (null-length) and exact-duplicate penalties. A chaotic multi-penalty incident (2026-ev-38) has duplicates interleaved with real distinct penalties that a conservative adjacency rule cannot fully separate — see FULL_SEASON_ANOMALIES.md.",
    "goals_with_pre_shot_pass": "DIAGNOSTIC ONLY — cross-checks how often a valid goal's shotAssistId/pre_shot_pass_player_id is populated against the official 'assists' box-score stat. shotAssistId is NOT a confirmed official assist (see DATASET_2026.md); this is not an assist statistic.",
    "shot_clock_expirations": "No duplicate/mislabeling mechanism has been found for this event type; any residual is UNRESOLVED, not assumed-known.",
    "team_stats_row_count": "teams_stats returned a phantom extra team row not part of this game (PLL backend bug, confirmed via game_meta cross-check); excluded from official sums.",
}


def final_status(metric: str, cleaned_diff: int, cleaning_found_something: bool) -> str:
    if cleaned_diff == 0:
        return "PASS"
    if metric == "caused_turnovers":
        return "KNOWN_DATA_ISSUE"  # unconditional: field is structurally always null, not evidence-dependent
    cap = KNOWN_ISSUE_CAPS.get(metric)
    if cap is not None and cleaning_found_something and abs(cleaned_diff) <= cap:
        return "KNOWN_DATA_ISSUE"
    return "UNRESOLVED"


def validate_game(slug: str, ev: pd.DataFrame, team_totals: dict, final_home: int, final_away: int) -> list[dict]:
    rows = []

    def add(metric, raw_value, cleaned_value, official_value):
        raw_diff = raw_value - official_value
        cleaned_diff = cleaned_value - official_value
        cleaning_found_something = cleaned_value != raw_value
        status = final_status(metric, cleaned_diff, cleaning_found_something)
        notes = NOTES.get(metric, "") if cleaned_diff != 0 else ""
        if status == "UNRESOLVED" and metric in KNOWN_ISSUE_CAPS and cleaned_diff != 0 and not cleaning_found_something:
            notes = (f"No {metric.replace('_', ' ')} were flagged/excluded by cleaning in THIS game specifically "
                     f"(cleaned_value == raw_value), so the gap vs. official has no supporting evidence here even "
                     f"though other games show a documented duplicate-logging mechanism for this metric type — "
                     f"genuinely unresolved for this game.")
        rows.append({
            "game_slug": slug,
            "metric": metric,
            "raw_value": raw_value,
            "cleaned_value": cleaned_value,
            "official_value": official_value,
            "raw_difference": raw_diff,
            "cleaned_difference": cleaned_diff,
            "raw_status": "PASS" if raw_diff == 0 else "MISMATCH",
            "cleaned_status": "PASS" if cleaned_diff == 0 else "MISMATCH",
            "final_status": status,
            "notes": notes,
        })

    if len(ev) == 0:
        add("event_count", 0, 0, -1)
        return rows

    not_dup = ev["is_duplicate_event"] != True  # noqa: E712
    valid_goal = ev["is_valid_goal"] == True  # noqa: E712
    valid_pen = ev["is_valid_penalty"] == True  # noqa: E712

    last = ev.iloc[-1]
    add("final_home_score", int(last["home_score_raw"]), int(last["home_score_corrected"]), int(final_home))
    add("final_away_score", int(last["away_score_raw"]), int(last["away_score_corrected"]), int(final_away))

    is_goal = ev["event_type"] == "goal"
    add("scoring_plays", int(is_goal.sum()), int((is_goal & valid_goal).sum()), team_totals["goals"])

    is_1pt = ev["shot_type"].isin(["1_PT", "MU"])
    is_2pt = ev["shot_type"].isin(["2_PT", "MU_2_PT"])
    add("one_point_goals", int((is_goal & is_1pt).sum()), int((is_goal & valid_goal & is_1pt).sum()), team_totals["onePointGoals"])
    add("two_point_goals", int((is_goal & is_2pt).sum()), int((is_goal & valid_goal & is_2pt).sum()), team_totals["twoPointGoals"])

    is_shot_or_goal = ev["event_type"].isin(["shot", "goal"])
    add("shots", int(is_shot_or_goal.sum()), int(ev["shot_outcome"].notna().sum()), team_totals["shots"])

    # raw shots_on_goal: naively trust shot_on_goal on 'shot' rows and trust
    # every raw 'goal' row as on-goal (i.e. without checking is_valid_goal)
    is_shot = ev["event_type"] == "shot"
    raw_sog = int((is_shot & (ev["shot_on_goal"] == True)).sum()) + int(is_goal.sum())  # noqa: E712
    cleaned_sog = int(ev["shot_outcome"].isin(["goal", "saved", "on_goal_no_save"]).sum())
    add("shots_on_goal", raw_sog, cleaned_sog, team_totals["shotsOnGoal"])

    raw_saves = int((is_shot & (ev["shot_saved"] == True)).sum())  # noqa: E712
    cleaned_saves = int((ev["shot_outcome"] == "saved").sum())
    add("saves", raw_saves, cleaned_saves, team_totals["saves"])

    is_fo = ev["event_type"] == "faceoff"
    add("faceoff_wins", int(is_fo.sum()), int((is_fo & not_dup).sum()), team_totals["faceoffsWon"])

    is_to = ev["event_type"] == "turnover"
    add("turnovers", int(is_to.sum()), int((is_to & not_dup).sum()), team_totals["turnovers"])
    add("caused_turnovers", 0, 0, team_totals["causedTurnovers"])

    is_gb = ev["event_type"] == "groundball"
    add("ground_balls", int(is_gb.sum()), int((is_gb & not_dup).sum()), team_totals["groundBalls"])

    is_pen = ev["event_type"] == "penalty"
    add("penalties", int(is_pen.sum()), int((is_pen & valid_pen & not_dup).sum()), team_totals["numPenalties"])

    has_pre_shot_pass = ev["secondary_player_id"].notna()
    add(
        "goals_with_pre_shot_pass",
        int((is_goal & has_pre_shot_pass).sum()),
        int((is_goal & valid_goal & has_pre_shot_pass).sum()),
        team_totals["assists"],
    )

    is_sce = ev["event_type"] == "shotclockexpired"
    add("shot_clock_expirations", int(is_sce.sum()), int((is_sce & not_dup).sum()), team_totals["shotClockExpirations"])

    return rows


def main():
    events = pd.read_csv(
        DATA_DIR / "events.csv",
        dtype={"player_id": str, "secondary_player_id": str, "team_id": str,
               "goalie_id": str, "gb_player_id": str},
        low_memory=False,
    )
    team_stats = pd.read_csv(DATA_DIR / "team_game_stats.csv")
    games = pd.read_csv(DATA_DIR / "games.csv")
    games = games[games["is_completed"]]

    stat_cols = ["goals", "onePointGoals", "twoPointGoals", "shots", "shotsOnGoal",
                 "saves", "faceoffsWon", "turnovers", "causedTurnovers",
                 "groundBalls", "numPenalties", "assists", "shotClockExpirations"]

    all_rows = []
    for _, game in games.iterrows():
        slug = game["game_slug"]
        ev = events[events["game_slug"] == slug]
        ts_raw = team_stats[team_stats["game_slug"] == slug]
        # teams_stats occasionally returns a phantom 3rd team's row for a
        # game (observed: 2026-ev-46, 2026-ev-47 — both involving WAT, same
        # week). Only sum rows for the two teams that actually played this
        # game per game_meta; see FULL_SEASON_ANOMALIES.md.
        expected_teams = {game["home_team_id"], game["away_team_id"]}
        ts = ts_raw[ts_raw["officialId"].isin(expected_teams)]
        if len(ts_raw) != len(ts):
            all_rows.append({
                "game_slug": slug, "metric": "team_stats_row_count",
                "raw_value": len(ts_raw), "cleaned_value": len(expected_teams), "official_value": 2,
                "raw_difference": len(ts_raw) - 2, "cleaned_difference": len(expected_teams) - 2,
                "raw_status": "MISMATCH", "cleaned_status": "PASS" if len(expected_teams) == 2 else "MISMATCH",
                "final_status": "KNOWN_DATA_ISSUE",
                "notes": f"teams_stats returned {len(ts_raw)} team rows ({sorted(ts_raw['officialId'].tolist())}) "
                         f"instead of the 2 that played ({sorted(expected_teams)}); phantom row(s) excluded from sums.",
            })
        if len(ts) == 0:
            all_rows.append({
                "game_slug": slug, "metric": "team_stats_present", "raw_value": 0, "cleaned_value": 0, "official_value": 1,
                "raw_difference": -1, "cleaned_difference": -1, "raw_status": "MISMATCH", "cleaned_status": "MISMATCH",
                "final_status": "UNRESOLVED", "notes": "No teams_stats rows found for this game.",
            })
            team_totals = {c: 0 for c in stat_cols}
        else:
            team_totals = {c: int(ts[c].sum()) for c in stat_cols}
        all_rows.extend(validate_game(slug, ev, team_totals, game["home_score"], game["away_score"]))

    report = pd.DataFrame(all_rows)
    out_path = DATA_DIR / "validation_report.csv"
    report.to_csv(out_path, index=False)
    print(f"Saved validation report ({len(report)} rows) to {out_path.relative_to(REPO_ROOT)}")
    print()
    print(report["final_status"].value_counts())
    print()
    unresolved = report[report["final_status"] == "UNRESOLVED"]
    print(f"UNRESOLVED rows: {len(unresolved)}")
    if len(unresolved):
        print(unresolved[["game_slug", "metric", "raw_value", "cleaned_value", "official_value", "cleaned_difference"]].to_string(index=False))
    return report


if __name__ == "__main__":
    main()
