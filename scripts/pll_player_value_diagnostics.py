"""
Phase 6: player-value diagnostics.

Leaderboards for each value component, with the sample size beside every rate
so a small-sample artefact is visible rather than buried.

THESE ARE DIAGNOSTICS, NOT AN AWARD RANKING. No Statistical Tewaaraton, MVP
model or cross-position composite is built in Phase 6, and total_player_value
is deliberately NOT comparable across roles: a goalie faces 150-330 shots on
goal in a season while an attackman takes 80 shots, so the goalie's component
has a far larger opportunity base and therefore a far larger spread. Comparing
those totals directly would rank by opportunity volume, not by quality.

Writes data/processed/2026/player_value_diagnostics.csv (long format, one row
per leaderboard entry) and prints the tables.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str}

TOP_N = 10
MIN_SHOTS_FOR_RATE = 30
MIN_FACEOFFS_FOR_RATE = 50
MIN_SOG_FOR_RATE = 50

# (leaderboard, value column, sample-size column, ascending?, minimum sample)
BOARDS = [
    ("highest_total_shooting_value", "shooting_value", "shots", False, 0),
    ("lowest_total_shooting_value", "shooting_value", "shots", True, 0),
    ("highest_shooting_value_per_shot", "shooting_value_per_shot", "shots",
     False, MIN_SHOTS_FOR_RATE),
    ("highest_turnover_cost", "turnover_value", "touches", True, 0),
    ("best_possession_security", "turnover_value", "touches", False, 0),
    ("highest_faceoff_value", "faceoff_value", "faceoffs", False, 0),
    ("highest_faceoff_value_per_faceoff", "faceoff_value_per_faceoff", "faceoffs",
     False, MIN_FACEOFFS_FOR_RATE),
    ("highest_goalie_value", "goalie_value", "shots_on_goal_faced", False, 0),
    ("highest_goalie_value_per_shot_faced", "goalie_value_per_shot_on_goal_faced",
     "shots_on_goal_faced", False, MIN_SOG_FOR_RATE),
    ("highest_measured_defensive_value", "caused_turnover_value", "games_played", False, 0),
    ("highest_total_player_value", "total_player_value", "games_played", False, 0),
]


def main():
    comp = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
    rows = []
    for board, col, sample_col, asc, min_sample in BOARDS:
        sub = comp.dropna(subset=[col])
        if min_sample:
            sub = sub[sub[sample_col] >= min_sample]
        sub = sub.sort_values([col, "player_id"], ascending=[asc, True]).head(TOP_N)
        for rank, r in enumerate(sub.itertuples(), start=1):
            rows.append({
                "leaderboard": board,
                "rank": rank,
                "player_id": r.player_id,
                "player_name": r.player_name,
                "team_id": r.team_id,
                "position_code": r.position_code,
                "games_played": r.games_played,
                "value_metric": col,
                "value": getattr(r, col),
                "sample_size_metric": sample_col,
                "sample_size": getattr(r, sample_col),
                "minimum_sample_applied": min_sample,
            })
    out = pd.DataFrame(rows)
    path = DATA_DIR / "player_value_diagnostics.csv"
    out.to_csv(path, index=False)

    for board, col, sample_col, asc, min_sample in BOARDS:
        sub = out[out["leaderboard"] == board].head(6)
        gate = f"  (min {min_sample} {sample_col})" if min_sample else ""
        print(f"\n=== {board}{gate} ===")
        print(sub[["rank", "player_name", "team_id", "position_code",
                   "games_played", "value", "sample_size"]]
              .rename(columns={"sample_size": sample_col})
              .round(3).to_string(index=False))
    print(f"\nWrote {len(out)} rows to {path.relative_to(REPO_ROOT)}")
    return out


if __name__ == "__main__":
    main()
