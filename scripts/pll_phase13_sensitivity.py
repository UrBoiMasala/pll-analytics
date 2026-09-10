"""
Phase 13 Section P: sensitivity analysis.

Tests reasonable ALTERNATIVE assumptions against the frozen v1 model and
reports how much the ranking moves -- never selects the alternative that
looks best. Every alternative reuses already-published columns
(shooting_rate_shrunk, EPA_points_null_z, one/two-point shots-on-goal-faced)
rather than re-deriving a new baseline from raw events.

Output: data/processed/history/player_value_sensitivity.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASON = 2026


def _rho(a, b):
    a, b = pd.Series(a).reset_index(drop=True), pd.Series(b).reset_index(drop=True)
    mask = a.notna() & b.notna()
    if mask.sum() < 5:
        return np.nan
    return float(np.corrcoef(a[mask].rank(), b[mask].rank())[0, 1])


def offense_sensitivity(players: pd.DataFrame) -> list:
    rows = []
    off = players[(players["season"] == SEASON) &
                  (players["position_group"].isin(["attack", "midfield"]))].copy()
    off["offensive_value"] = off["shooting_value_raw"].fillna(0) + off["turnover_value_raw"].fillna(0)

    # S1: raw observed value vs REJECTED shrunk-rate-times-season-opportunity
    # (Phase 12 model candidate MF4_shrunk_rate_x_season_opportunity) --
    # computed here ONLY to quantify how much it would move rankings, not
    # adopted.
    league_shooting_rate = off["shooting_rate_shrunk"]
    baseline_rate = (off["one_point_goals"].fillna(0) + off["two_point_goals"].fillna(0)).sum() / \
        off["shots"].sum()
    alt_shooting_value = (off["shooting_rate_shrunk"] - baseline_rate) * off["shots"]
    alt_offensive_value = alt_shooting_value + off["turnover_value_raw"].fillna(0)
    rho1 = _rho(off["offensive_value"], alt_offensive_value)
    top10_orig = set(off.nlargest(10, "offensive_value")["player_id"])
    top10_alt = set(off.nlargest(10, "offensive_value").index) if False else \
        set(pd.Series(alt_offensive_value.values, index=off["player_id"]).nlargest(10).index)
    rows.append({
        "sensitivity_id": "S1_raw_vs_shrunk_rate_x_opportunity", "role": "offense",
        "assumption_varied": "raw observed shooting rate (adopted) vs career-shrunk rate x season shots "
                             "(Phase 12 REJECTED model MF4_shrunk_rate_x_season_opportunity)",
        "n_players": len(off), "rank_correlation": round(rho1, 3) if pd.notna(rho1) else np.nan,
        "top10_overlap": len(top10_orig & top10_alt),
        "finding": f"rank correlation {rho1:.3f}, top-10 overlap {len(top10_orig & top10_alt)}/10 -- "
                  "quantifies exactly how much adopting the REJECTED alternative would move the board; "
                  "this number is reported to justify the rejection with evidence, the alternative is not adopted",
    })

    # S2: raw value vs EPA_points_null_z (an existing, published alternative
    # standardization -- Phase 10/12's M10, VIABLE_WITH_CAVEAT for
    # "unusualness" only)
    off_full = players[(players["season"] == SEASON) &
                       (players["position_group"].isin(["attack", "midfield"]))]
    rho2 = _rho(off_full["offensive_value"] if "offensive_value" in off_full.columns else off["offensive_value"],
               off_full["EPA_points_null_z"])
    top10_null = set(off_full.nlargest(10, "EPA_points_null_z")["player_id"])
    rows.append({
        "sensitivity_id": "S2_raw_value_vs_null_standardized", "role": "offense",
        "assumption_varied": "raw PLL-point value (adopted) vs null-standardized unusualness "
                             "EPA_points_null_z (Phase 10 M10)",
        "n_players": len(off), "rank_correlation": round(rho2, 3) if pd.notna(rho2) else np.nan,
        "top10_overlap": len(top10_orig & top10_null),
        "finding": f"rank correlation {rho2:.3f}, top-10 overlap {len(top10_orig & top10_null)}/10 -- "
                  "null-standardization changes who is 'most unusual' vs 'most productive'; consistent "
                  "with both being legitimate but different questions (PLAYER_VALUE_DEFINITION.md)",
    })

    # S3: inclusion vs exclusion of small-sample / descriptive-only players
    off["_opp"] = off["shots"]
    qual_only = off[(off["role_rate_reliability"] >= 0.5) & (off["offensive_rate_ranking_eligible"] == True)]  # noqa: E712
    top10_all = off.nlargest(10, "offensive_value")["player_name"].tolist()
    top10_qual = qual_only.nlargest(10, "offensive_value")["player_name"].tolist() if len(qual_only) >= 10 else qual_only.nlargest(len(qual_only), "offensive_value")["player_name"].tolist()
    overlap3 = len(set(top10_all) & set(top10_qual))
    rows.append({
        "sensitivity_id": "S3_all_players_vs_qualified_only", "role": "offense",
        "assumption_varied": f"all {len(off)} attack/midfield players (adopted, with a qualification flag "
                             f"shown) vs restricting the top-10 to the {len(qual_only)} QUALIFIED players only",
        "n_players": len(off), "rank_correlation": np.nan, "top10_overlap": overlap3,
        "finding": f"{overlap3}/10 of the unrestricted top-10 are also in the qualified-only top-10 -- "
                  "shows how much the unrestricted board is carried by small-sample players "
                  f"({len(off) - len(qual_only)} of {len(off)} do not clear reliability >=0.5)",
    })
    return rows


def goalie_sensitivity(players: pd.DataFrame) -> list:
    rows = []
    go = players[(players["season"] == SEASON) & (players["position_group"] == "goalie")].copy()
    go["goalie_value_total"] = go["goalie_value_raw"]
    go["expected_points_allowed"] = go["pll_points_allowed"].fillna(0) + go["goalie_value_raw"].fillna(0)

    # S4: separate 1PT/2PT baseline (adopted) vs a single pooled baseline
    league_pooled_rate = go["pll_points_allowed"].sum() / (
        go["one_point_shots_on_goal_faced"].sum() + 2 * go["two_point_shots_on_goal_faced"].sum()
        - go["two_point_shots_on_goal_faced"].sum())  # placeholder avoided below; use points-per-SOG directly
    # points-allowed-per-SOG-faced, pooled across shot classes (points, not goals)
    league_pts_per_sog = go["pll_points_allowed"].sum() / go["shots_on_goal_faced"].sum()
    alt_expected = go["shots_on_goal_faced"] * league_pts_per_sog
    alt_goalie_value = alt_expected - go["pll_points_allowed"].fillna(0)
    rho4 = _rho(go["goalie_value_total"], alt_goalie_value)
    top10_orig = set(go.nlargest(min(10, len(go)), "goalie_value_total")["player_id"])
    top10_alt = set(pd.Series(alt_goalie_value.values, index=go["player_id"]).nlargest(min(10, len(go))).index)
    rows.append({
        "sensitivity_id": "S4_separate_1pt_2pt_baseline_vs_pooled", "role": "goalie",
        "assumption_varied": "separate one-point/two-point expected-points-allowed baseline (adopted, "
                             "PLAYER_VALUE_ACCOUNTING.md sec 4G) vs a single pooled points-per-SOG-faced baseline",
        "n_players": len(go), "rank_correlation": round(rho4, 3) if pd.notna(rho4) else np.nan,
        "top10_overlap": len(top10_orig & top10_alt),
        "finding": f"rank correlation {rho4:.3f} -- {'small' if rho4 > 0.9 else 'material'} sensitivity to "
                  "the 1PT/2PT split, informative about whether shot-mix matters as much as the accounting "
                  "doc's stated rationale (nearly identical expected points per SOG, 0.461 vs 0.482) implies",
    })

    # S5: inclusion of small-sample goalies in the top of the board
    qual_go = go[(go["role_rate_reliability"] >= 0.5) & (go["future_award_input_eligible"] == True)]  # noqa: E712
    top10_all_go = go.nlargest(min(10, len(go)), "goalie_value_total")["player_name"].tolist()
    top10_qual_go = qual_go.nlargest(min(10, len(qual_go)), "goalie_value_total")["player_name"].tolist()
    overlap5 = len(set(top10_all_go) & set(top10_qual_go))
    rows.append({
        "sensitivity_id": "S5_all_goalies_vs_qualified_only", "role": "goalie",
        "assumption_varied": f"all {len(go)} goalies (adopted) vs restricting to the {len(qual_go)} QUALIFIED",
        "n_players": len(go), "rank_correlation": np.nan, "top10_overlap": overlap5,
        "finding": f"only {len(qual_go)} of {len(go)} goalies clear reliability >=0.5 in a single season "
                  f"(consistent with Phase 8's finding of ~1/16-27); {overlap5}/{min(10,len(qual_go)) if qual_go.shape[0] else 0} "
                  "top-ranked goalies are qualified -- most of the goalie board is small-sample.",
    })
    return rows


def faceoff_sensitivity(players: pd.DataFrame) -> list:
    rows = []
    fo = players[(players["season"] == SEASON) & (players["position_group"] == "faceoff")].copy()
    fo["faceoff_value_total"] = fo["faceoff_value_raw"]
    league_mean_faceoffs = fo.loc[fo["faceoffs"] > 0, "faceoffs"].mean()
    fo["faceoff_rate_value"] = fo["faceoff_value_total"] * (league_mean_faceoffs / fo["faceoffs"])

    rho6 = _rho(fo["faceoff_value_total"], fo["faceoff_rate_value"])
    top10_total = set(fo.nlargest(min(10, len(fo)), "faceoff_value_total")["player_id"])
    top10_rate = set(fo.nlargest(min(10, len(fo)), "faceoff_rate_value")["player_id"])
    rows.append({
        "sensitivity_id": "S6_total_value_vs_rate_only_ranking", "role": "faceoff",
        "assumption_varied": "faceoff_value_total (adopted, rewards volume) vs faceoff_rate_value only "
                             "(a per-opportunity ranking that holds volume at league-average)",
        "n_players": len(fo), "rank_correlation": round(rho6, 3) if pd.notna(rho6) else np.nan,
        "top10_overlap": len(top10_total & top10_rate),
        "finding": f"rank correlation {rho6:.3f}, top-10 overlap {len(top10_total & top10_rate)}/{min(10,len(fo))} -- "
                  "quantifies the workload confound directly: how much the total-value board would change "
                  "if volume were held constant at league-average for every player",
    })
    return rows


def main():
    players = pd.read_csv(HIST / "player_stats_2022_2026.csv", dtype={"player_id": str, "team_id": str})
    rows = offense_sensitivity(players) + goalie_sensitivity(players) + faceoff_sensitivity(players)
    df = pd.DataFrame(rows)
    out = HIST / "player_value_sensitivity.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(REPO_ROOT)}: {len(df)} sensitivity checks")
    print(df[["sensitivity_id", "role", "rank_correlation", "top10_overlap"]].to_string(index=False))


if __name__ == "__main__":
    main()
