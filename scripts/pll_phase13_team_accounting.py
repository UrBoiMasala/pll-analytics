"""
ARCHIVED RESEARCH: excluded from the final product. Known audit defects are
retired with these features, not corrected here. See docs/AUDIT_REMEDIATION.md.

Phase 13 Section M: team-level accounting reconciliation.

Two DIFFERENT questions, kept separate on purpose (an early version of this
script conflated them and reported a spurious "FAIL" -- see
player_value_model_change_log.csv for the correction, which changed no
formula and no ranking):

1. UNCONDITIONAL ACCOUNTING IDENTITY (must be exact everywhere). Every
   player's EPA_points_raw is EXACTLY the sum of all 5 components
   (shooting_value_raw + turnover_value_raw + faceoff_value_raw +
   goalie_value_raw + defensive_value_partial_raw), regardless of the
   player's position_group -- Phase 12 verified this at the ROW level to
   1e-15; this script re-verifies it at the TEAM and LEAGUE level, which
   follows by linearity but is checked independently rather than assumed.

2. ROLE-LEADERBOARD COVERAGE (expected to be INCOMPLETE, and this is not a
   defect). The four published Phase 13 role leaderboards each expose only
   the THEMATICALLY relevant component(s) for that role (offense:
   shooting+turnover; faceoff: faceoff_value; goalie: goalie_value;
   defense: production only, no value). But the canonical data computes
   defensive_value_partial_raw (caused turnovers vs. the player's OWN
   position group's rate) and, occasionally, faceoff_value_raw for EVERY
   player regardless of role (e.g., an attackman credited for causing a
   turnover, or a backup faceoff taker who is primarily a defenseman).
   That incidental production is real, part of EPA_points_raw, and
   deliberately NOT folded into any role leaderboard's value (doing so
   would require crediting, e.g., an attackman's "defensive value" inside
   an offensive leaderboard, which Phase 12's MF3_offense_above_baseline
   specification does not do). The gap between team EPA_points_raw and the
   sum of published role-leaderboard values is measured and reported here,
   not hidden.

Output: data/processed/2026/player_value_team_accounting.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]
TOLERANCE = 1e-6

ALL_COMPONENTS = ["shooting_value_raw", "turnover_value_raw", "faceoff_value_raw",
                  "goalie_value_raw", "defensive_value_partial_raw"]


def _published_role_value(row) -> float:
    """The value a player receives on ITS OWN role leaderboard -- exactly the
    thematic component(s) player_value_model_spec_v1.csv assigns that role,
    never the player's incidental off-role components."""
    pg = row["position_group"]
    if pg in ("attack", "midfield"):
        return np.nansum([row["shooting_value_raw"], row["turnover_value_raw"]])
    if pg == "faceoff":
        return np.nan_to_num(row["faceoff_value_raw"])
    if pg == "goalie":
        return np.nan_to_num(row["goalie_value_raw"])
    # defensive_field and unknown: no VALUE is published (production only)
    return 0.0


def build_team_accounting() -> pd.DataFrame:
    players = pd.read_csv(HIST / "player_stats_2022_2026.csv",
                          dtype={"player_id": str, "team_id": str})
    players["unconditional_component_sum"] = players[ALL_COMPONENTS].fillna(0).sum(axis=1)
    players["published_role_value"] = players.apply(_published_role_value, axis=1)

    rows = []
    for season in SEASONS:
        p = players[players["season"] == season]
        for team_id, g in p.groupby("team_id"):
            epa_sum = float(g["EPA_points_raw"].sum())
            unconditional_sum = float(g["unconditional_component_sum"].sum())
            role_value_sum = float(g["published_role_value"].sum())
            rows.append({
                "season": season, "team_id": team_id, "n_players": len(g),
                "team_sum_of_EPA_points_raw": round(epa_sum, 6),
                "unconditional_5_component_sum": round(unconditional_sum, 6),
                "unconditional_accounting_residual": round(unconditional_sum - epa_sum, 9),
                "sum_of_published_role_leaderboard_values": round(role_value_sum, 6),
                "role_leaderboard_coverage_gap": round(epa_sum - role_value_sum, 6),
                "pct_of_team_EPA_covered_by_role_leaderboards":
                    round(100.0 * role_value_sum / epa_sum, 1) if abs(epa_sum) > 1e-6 else np.nan,
                "unconditional_accounting_result":
                    "PASS" if abs(unconditional_sum - epa_sum) < TOLERANCE else "FAIL",
                "tolerance": TOLERANCE,
            })
    df = pd.DataFrame(rows)

    league_rows = []
    for season in SEASONS:
        st = df[df["season"] == season]
        p = players[players["season"] == season]
        # recomputed from full-precision player-level columns, NOT by summing
        # the per-team rows above (which round to 6 decimals for display --
        # summing 8 already-rounded team values can accumulate a residual
        # just over a 1e-6 tolerance, a rounding-DISPLAY artifact rather than
        # a real accounting failure; see player_value_model_change_log.csv)
        epa_sum = float(p["EPA_points_raw"].sum())
        unconditional_sum_league = float(p["unconditional_component_sum"].sum())
        role_value_sum_league = float(p["published_role_value"].sum())
        league_rows.append({
            "season": season, "team_id": "LEAGUE_TOTAL",
            "n_players": int(st["n_players"].sum()),
            "team_sum_of_EPA_points_raw": round(epa_sum, 6),
            "unconditional_5_component_sum": round(unconditional_sum_league, 6),
            "unconditional_accounting_residual": round(unconditional_sum_league - epa_sum, 9),
            "sum_of_published_role_leaderboard_values": round(role_value_sum_league, 6),
            "role_leaderboard_coverage_gap": round(epa_sum - role_value_sum_league, 6),
            "pct_of_team_EPA_covered_by_role_leaderboards": np.nan,
            "unconditional_accounting_result":
                "PASS" if abs(unconditional_sum_league - epa_sum) < TOLERANCE
                else "FAIL",
            "tolerance": TOLERANCE,
        })
    df = pd.concat([df, pd.DataFrame(league_rows)], ignore_index=True)
    return df


def main():
    df = build_team_accounting()
    out = PROC / "2026" / "player_value_team_accounting.csv"
    df.to_csv(out, index=False)
    team_rows = df[df["team_id"] != "LEAGUE_TOTAL"]
    n_fail = int((team_rows["unconditional_accounting_result"] == "FAIL").sum())
    print(f"Wrote {out.relative_to(REPO_ROOT)}: {len(df)} rows")
    print(f"Unconditional accounting identity PASS: {len(team_rows) - n_fail}/{len(team_rows)} team-seasons")
    if n_fail:
        print(team_rows[team_rows["unconditional_accounting_result"] == "FAIL"].to_string())
    print()
    print("Role-leaderboard coverage (informational, expected < 100%):")
    print(df[df["team_id"] == "LEAGUE_TOTAL"][
        ["season", "team_sum_of_EPA_points_raw", "sum_of_published_role_leaderboard_values",
         "role_leaderboard_coverage_gap"]].to_string(index=False))


if __name__ == "__main__":
    main()
