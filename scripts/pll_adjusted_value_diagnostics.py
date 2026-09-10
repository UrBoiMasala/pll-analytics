"""
Phase 7: diagnostics.

THESE ARE DIAGNOSTICS, NOT AN AWARD LEADERBOARD. There is no cross-position
board here and no composite of any kind. Every table is either within a single
role, or is explicitly about one measured dimension (volume, usage, efficiency,
reliability) with its sample size beside it.

The Phase 7 brief is explicit that Phase 7 must not answer "who is the MVP".
Nothing in this file combines usage with value, weights a component, or ranks a
goalie against an attackman.

Writes data/processed/2026/player_adjusted_value_diagnostics.csv (long format)
and prints the tables.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
ID_DTYPE = {"player_id": str, "team_id": str}

TOP_N = 10

# (board name, value column, sample column, ascending?, role filter, gate)
# `gate` is a column name, optionally prefixed "not:" to require it be FALSE.
BOARDS = [
    ("highest_raw_EPA_points", "EPA_points_raw", "games_played", False, None, None),
    ("highest_offensive_play_share", "offensive_play_share",
     "recorded_offensive_opportunities", False, None, None),
    ("highest_EPA_per_recorded_opportunity_adequately_sampled",
     "EPA_per_recorded_opportunity", "recorded_offensive_opportunities", False,
     None, "offensive_rate_ranking_eligible"),
    ("highest_usage_adjusted_EPA_vs_expectation", "EPA_vs_usage_expectation",
     "recorded_offensive_opportunities", False, None, None),
    ("strongest_positive_EPA_vs_usage_residual", "EPA_vs_usage_expectation_z",
     "recorded_offensive_opportunities", False, None, None),
    ("strongest_negative_EPA_vs_usage_residual", "EPA_vs_usage_expectation_z",
     "recorded_offensive_opportunities", True, None, None),
    ("highest_positional_EPA_percentile", "EPA_position_percentile",
     "games_played", False, None, None),
    ("top_faceoff_positional_value", "faceoff_value_raw", "faceoffs", False,
     "faceoff", None),
    ("top_faceoff_positional_percentile", "EPA_position_percentile", "faceoffs",
     False, "faceoff", None),
    ("top_goalie_positional_value", "goalie_value_raw", "shots_on_goal_faced",
     False, "goalie", None),
    ("top_goalie_positional_percentile", "EPA_position_percentile",
     "shots_on_goal_faced", False, "goalie", None),
    ("top_partial_defensive_value", "defensive_value_partial_raw", "games_played",
     False, "defensive_field", None),
    ("least_reliable_apparent_high_performers", "EPA_points_raw",
     "recorded_offensive_opportunities", False, None, "not:rate_ranking_eligible"),
    ("highest_value_whose_chance_spread_covers_the_peer_group", "EPA_points_raw",
     "recorded_offensive_opportunities", False, None,
     "chance_variation_exceeds_peer_spread"),
]


def _board(av, name, col, sample_col, asc, role, gate):
    sub = av.dropna(subset=[col]).copy()
    if role:
        sub = sub[sub["value_role"] == role]
    if gate:
        col_name = gate[4:] if gate.startswith("not:") else gate
        keep = sub[col_name].astype(bool)
        sub = sub[~keep if gate.startswith("not:") else keep]
    sub = sub.sort_values([col, "player_id"], ascending=[asc, True]).head(TOP_N)
    rows = []
    for rank, r in enumerate(sub.itertuples(), start=1):
        rows.append({
            "board": name,
            "rank": rank,
            "player_id": r.player_id,
            "player_name": r.player_name,
            "team_id": r.team_id,
            "canonical_position": r.canonical_position,
            "value_role": r.value_role,
            "games_played": r.games_played,
            "metric": col,
            "value": getattr(r, col),
            "sample_size_metric": sample_col,
            "sample_size": getattr(r, sample_col),
            "role_filter": role or "none",
            "eligibility_gate": gate or "none",
            "reliability": r.role_rate_reliability,
            "small_sample": r.small_sample,
        })
    return rows


def main():
    av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
    sens = pd.read_csv(DATA_DIR / "player_adjusted_value_sensitivity.csv", dtype=ID_DTYPE)

    rows = []
    for name, col, sample_col, asc, role, gate in BOARDS:
        rows += _board(av, name, col, sample_col, asc, role, gate)

    # ---- who moves most under each Phase 7 transformation -------------------
    def movers(family, metric, label):
        s = sens[(sens["family"] == family) & (sens["metric"] == metric)].copy()
        s = s.dropna(subset=["rank_change"])
        if s.empty:
            return []
        agg = (s.groupby(["player_id", "player_name", "team_id", "value_role"])
                 .agg(max_abs_rank_change=("rank_change", lambda x: x.abs().max()),
                      max_abs_value_change=("difference", lambda x: x.abs().max()),
                      sample_size=("sample_size", "first"))
                 .reset_index()
                 .sort_values(["max_abs_rank_change", "max_abs_value_change"],
                              ascending=False).head(TOP_N))
        out = []
        for rank, r in enumerate(agg.itertuples(), start=1):
            out.append({
                "board": label, "rank": rank, "player_id": r.player_id,
                "player_name": r.player_name, "team_id": r.team_id,
                "canonical_position": "", "value_role": r.value_role,
                "games_played": np.nan, "metric": metric,
                "value": r.max_abs_rank_change,
                "sample_size_metric": "sensitivity sample", "sample_size": r.sample_size,
                "role_filter": "none", "eligibility_gate": "none",
                "reliability": np.nan, "small_sample": np.nan,
            })
        return out

    rows += movers("shrinkage_treatment", "shooting_value_raw",
                   "most_affected_by_shrinkage_rank_change")
    rows += movers("normalization_scope", "EPA_position_z",
                   "most_affected_by_positional_normalization_rank_change")
    rows += movers("usage_definition", "offensive_play_share",
                   "most_affected_by_usage_definition_rank_change")

    # ---- conclusions that materially change after positional normalization --
    flip = av.dropna(subset=["EPA_position_percentile"]).copy()
    league_pct = (flip["EPA_points_raw"].rank(method="average") - 0.5) / len(flip) * 100
    flip["league_percentile"] = league_pct
    flip["percentile_shift"] = flip["EPA_position_percentile"] - flip["league_percentile"]
    flip = flip.reindex(flip["percentile_shift"].abs().sort_values(ascending=False).index)
    for rank, r in enumerate(flip.head(TOP_N).itertuples(), start=1):
        rows.append({
            "board": "conclusion_changes_most_under_positional_normalization",
            "rank": rank, "player_id": r.player_id, "player_name": r.player_name,
            "team_id": r.team_id, "canonical_position": r.canonical_position,
            "value_role": r.value_role, "games_played": r.games_played,
            "metric": "EPA_position_percentile - league_percentile",
            "value": r.percentile_shift,
            "sample_size_metric": "recorded_offensive_opportunities",
            "sample_size": r.recorded_offensive_opportunities,
            "role_filter": "none", "eligibility_gate": "none",
            "reliability": r.role_rate_reliability, "small_sample": r.small_sample,
        })

    out = pd.DataFrame(rows)
    path = DATA_DIR / "player_adjusted_value_diagnostics.csv"
    out.to_csv(path, index=False)

    for board in out["board"].unique():
        sub = out[out["board"] == board].head(6)
        print(f"\n=== {board} ===")
        print(sub[["rank", "player_name", "team_id", "canonical_position", "value_role",
                   "value", "sample_size", "reliability"]]
              .round(3).to_string(index=False))
    print(f"\nWrote {len(out)} rows to {path.relative_to(REPO_ROOT)}")
    return out


if __name__ == "__main__":
    main()
