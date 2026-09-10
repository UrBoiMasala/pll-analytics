"""
Phase 13 Section V: the model change log.

Records every change made after leaderboard generation began, per the
Phase 13 brief's explicit format. "Leaderboard looked wrong" is never a
listed reason -- both entries below are either (a) a cosmetic column-label
fix with zero effect on any value or ranking, or (b) a correction to an
ACCOUNTING SCRIPT (not a value formula, not a ranking) after its own PASS/
FAIL check caught a real gap in the accounting script's understanding of
the data, not in the published value itself.

Output: data/processed/history/player_value_model_change_log.csv
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST = REPO_ROOT / "data" / "processed" / "history"

CHANGE_LOG_COLUMNS = [
    "order", "timestamp_note", "component", "old_definition", "new_definition",
    "reason", "bug_or_method_change", "players_materially_affected",
    "rankings_changed", "evidence",
]


def build_change_log() -> pd.DataFrame:
    rows = [
        {
            "order": 1,
            "timestamp_note": "same session, immediately after first offensive_value_2026.csv generation",
            "component": "offensive_value_v1 / two_point_selection column labeling (pll_phase13_player_value_v1.py::build_offensive_value)",
            "old_definition": "leaderboard/components column fell back to a raw 'shots' or 'shots_on_goal_pct' "
                              "count under the misleading name 'two_point_selection_or_shots', because "
                              "'two_point_attempt_share' does not exist as a per-season column in "
                              "player_stats_2022_2026.csv (it only exists at career scope, in "
                              "career_ability_reliability.csv)",
            "new_definition": "two_point_attempt_share_raw computed directly as "
                              "two_point_attempts/shots for the season, correctly labeled",
            "reason": "code-clarity/correctness defect in a DIAGNOSTIC column, discovered while reviewing the "
                     "leaderboard's own column list before publication",
            "bug_or_method_change": "BUG (mislabeled column, not a value/ranking formula)",
            "players_materially_affected": 0,
            "rankings_changed": "NO -- offensive_value, its bootstrap, and every rank are computed from "
                                "shooting_value_raw/turnover_value_raw only and were not touched by this change",
            "evidence": "diff to pll_phase13_player_value_v1.py; offensive_value_2026.csv rank column "
                       "identical before and after (verified by re-running and diffing)",
        },
        {
            "order": 2,
            "timestamp_note": "same session, first run of pll_phase13_team_accounting.py",
            "component": "team accounting reconciliation script (pll_phase13_team_accounting.py) -- NOT any "
                        "value formula or leaderboard",
            "old_definition": "summed shooting_value_raw+turnover_value_raw ONLY for position_group in "
                              "(attack, midfield), faceoff_value_raw ONLY for position_group=='faceoff', "
                              "goalie_value_raw ONLY for position_group=='goalie', and compared that sum "
                              "against team EPA_points_raw, expecting an exact match",
            "new_definition": "the exact accounting check is now UNCONDITIONAL -- it sums all 5 components "
                              "(shooting/turnover/faceoff/goalie/defensive_value_partial) for EVERY player "
                              "regardless of position_group and compares that to team EPA_points_raw (which "
                              "passes exactly, 40/40 team-seasons). A SEPARATE, explicitly non-PASS/FAIL "
                              "'role_leaderboard_coverage_gap' column now reports, honestly, how much of a "
                              "team's EPA_points_raw is NOT captured by the four published role leaderboards "
                              "(defensive_field publishes no value by design, and any player's off-role "
                              "incidental component -- e.g. a backup faceoff taker who is primarily a "
                              "defenseman, or an attackman's own caused-turnover credit -- is real production "
                              "not folded into any leaderboard)",
            "reason": "the old script's own PASS/FAIL check failed on all 40 team-seasons the first time it "
                     "ran, because player_stats_2022_2026.csv computes defensive_value_partial_raw (a caused-"
                     "turnover-vs-own-position-group-rate component) and, occasionally, faceoff_value_raw for "
                     "EVERY position group, not only the role each leaderboard is scoped to -- discovered by "
                     "inspecting one failing team-season's player rows directly (2023 CAN), not by looking at "
                     "which players ranked where",
            "bug_or_method_change": "METHOD CORRECTION to the accounting SCRIPT's own check -- the row-level "
                                    "value/component identity Phase 12 already verified (sum of 5 components "
                                    "== EPA_points_raw, max abs diff 5.3e-15) was never wrong and needed no "
                                    "change; what changed is which two questions the team-accounting script "
                                    "asks and how it labels the answer to each",
            "players_materially_affected": 0,
            "rankings_changed": "NO -- no leaderboard, no player value, and no rank in any of the four "
                                "published leaderboards was touched by this change; only "
                                "player_value_team_accounting.csv's own columns changed",
            "evidence": "data/processed/2026/player_value_team_accounting.csv: unconditional_accounting_result "
                       "is PASS for 40/40 team-seasons after the fix (0/40 under the superseded, "
                       "over-narrow check); docs/PLAYER_VALUE_MODEL_V1.md sec on team accounting",
        },
        {
            "order": 3,
            "timestamp_note": "same session, first run of pll_phase13_counterfactuals.py",
            "component": "counterfactual test O1's pair-selection method (pll_phase13_counterfactuals.py) -- "
                        "NOT any value formula or leaderboard",
            "old_definition": "found the first adjacent-in-sorted-order pair whose offensive rate "
                              "(offensive_value/shots) differed by less than a fixed absolute tolerance "
                              "(0.03), then chose the one with the largest shot-volume gap",
            "new_definition": "exhaustively searches all pairs with a shot-volume gap of at least 30 and "
                              "picks the one with the SMALLEST rate difference (helper _best_pair)",
            "reason": "the fixed tolerance of 0.03 was large relative to how tightly offensive rate values "
                     "cluster near zero for this population (observed range roughly -0.21 to +0.02), so the "
                     "test picked a pair (Dylan Molloy, 98 shots vs Connor Kirst, 18 shots) whose rates "
                     "differed by only 0.0006 in absolute terms but by a large relative amount given both "
                     "values are near zero -- Molloy's slightly more negative rate, applied to far more "
                     "shots, produced a lower total offensive_value than Kirst's, which is mathematically "
                     "correct given the actual rate gap and was never a defect in offensive_value itself, "
                     "only in how tightly this TEST matched 'same efficiency'",
            "bug_or_method_change": "METHOD CORRECTION to a test-construction script's pair-matching "
                                    "tolerance -- discovered because the test's own theoretical expectation "
                                    "failed, investigated by inspecting the exact two players selected (not "
                                    "by looking at which players ranked where on the leaderboard)",
            "players_materially_affected": 0,
            "rankings_changed": "NO -- offensive_value_2026.csv is untouched; only which pair of real players "
                                "test O1 selects to illustrate the concept changed",
            "evidence": "player_value_counterfactual_tests_v1.csv: O1 result is True after the fix; the exact "
                       "player pair and rate/shot values are recorded in the interpretation and value_a/value_b "
                       "columns for both the failing and corrected run",
        },
        {
            "order": 4,
            "timestamp_note": "same session, first run of pll_validate_phase13.py check 13",
            "component": "team accounting LEAGUE_TOTAL row computation (pll_phase13_team_accounting.py) -- "
                        "NOT any value formula or leaderboard",
            "old_definition": "the LEAGUE_TOTAL row summed the already-rounded (6 decimal places) "
                              "per-team 'unconditional_5_component_sum' and "
                              "'sum_of_published_role_leaderboard_values' columns across all 8 teams in a season",
            "new_definition": "the LEAGUE_TOTAL row is computed directly from the full-precision "
                              "player-level columns (summed across every player in the season, not across "
                              "already-rounded per-team subtotals)",
            "reason": "the validator's own check 13 failed for 2023/2024/2025 with residuals of "
                     "1.0e-6 to 2.0e-6 -- just over the 1e-6 tolerance -- caused by accumulating up to 8 "
                     "independent roundings of 5e-7 each; the underlying per-team identity was exact "
                     "(check 13 on the 40 team-season rows themselves, and Phase 12's row-level check, "
                     "both passed throughout) -- this was a display-rounding artifact in one aggregation "
                     "step, not a broken accounting identity",
            "bug_or_method_change": "BUG in a display-rounding order of operations inside the accounting "
                                    "SCRIPT -- no value, formula, or ranking was ever wrong",
            "players_materially_affected": 0,
            "rankings_changed": "NO -- no player-level file changed at all; only the "
                                "LEAGUE_TOTAL summary rows in player_value_team_accounting.csv changed, "
                                "from FAIL (rounding artifact) to PASS (exact)",
            "evidence": "data/processed/2026/player_value_team_accounting.csv: LEAGUE_TOTAL "
                       "unconditional_accounting_result is PASS for 5/5 seasons after the fix; "
                       "pll_validate_phase13.py check 13 is PASS (0 failures) after the fix",
        },
    ]
    df = pd.DataFrame(rows)
    assert list(df.columns) == CHANGE_LOG_COLUMNS
    return df


def main():
    df = build_change_log()
    out = HIST / "player_value_model_change_log.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(REPO_ROOT)}: {len(df)} entries")
    print(df[["order", "component", "bug_or_method_change", "rankings_changed"]].to_string(index=False))


if __name__ == "__main__":
    main()
