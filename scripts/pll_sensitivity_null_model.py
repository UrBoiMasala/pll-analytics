"""
Phase 5: null model for the possession-ambiguity sensitivity analysis.

team_metric_sensitivity.csv shows that restricting to non-ambiguous possessions
moves team ranks by up to 4 places. That number on its own does not say whether
possession ambiguity BIASES a ranking, because the high-confidence subset is
also only ~61% the size of the full set -- and any smaller sample reshuffles a
close 8-team ranking on noise alone.

This script separates the two explanations by resampling. For each metric it
draws, 2,000 times, a RANDOM subset of each team's possessions of exactly the
same size as that team's high-confidence subset, recomputes the metric, and
re-ranks. That gives the distribution of rank churn attributable purely to
sample size. The observed churn is then read against it:

    p_rank_churn = P(random churn >= observed churn)

A small p means ambiguity moves ranks more than shrinking the sample does --
i.e. the ambiguous possessions are systematically different. A large p means
the observed reshuffling is what any subset of that size would produce, and the
honest conclusion is that these ranks are fragile at this sample size, not that
ambiguity specifically distorts them.

The metric LEVEL is tested separately and more simply: random subsampling is
unbiased by construction, so any consistent level shift is attributable to
ambiguity, and is reported as such.

Writes data/processed/2026/team_metric_sensitivity_null_model.csv.
Deterministic: fixed seed, fixed draw count.
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"

N_DRAWS = 2000
SEED = 20260907

# metric -> (side, per-possession value column or callable)
#   side 'off'  -- denominated on offensive possessions
#   side 'def'  -- denominated on defensive possessions
#   side 'net'  -- needs both
METRICS = {
    "offensive_efficiency": ("off", "points_scored"),
    "defensive_efficiency": ("def", "points_scored"),
    "net_efficiency": ("net", "points_scored"),
    "shots_per_possession": ("off", "shot_attempts"),
    "possession_ending_turnover_rate": ("off", "ended_in_turnover"),
    "two_point_possession_rate": ("off", "has_two_point_attempt_int"),
}
HIGHER_IS_BETTER = {
    "offensive_efficiency": True, "defensive_efficiency": False, "net_efficiency": True,
    "shots_per_possession": True, "possession_ending_turnover_rate": False,
    "two_point_possession_rate": True,
}
SUBSETS = {
    "non_ambiguous": lambda p: ~p["is_ambiguous"],
    "non_ambiguous_non_truncated": lambda p: ~p["is_ambiguous"] & ~p["is_truncated"],
}


def competition_rank(values: dict, higher_is_better: bool) -> dict:
    """1 + the number of teams strictly ahead. Same semantics as SQL RANK()."""
    out = {}
    for team, v in values.items():
        if higher_is_better:
            better = sum(1 for w in values.values() if w > v)
        else:
            better = sum(1 for w in values.values() if w < v)
        out[team] = better + 1
    return out


def main():
    poss = pd.read_csv(DATA_DIR / "possessions.csv")
    poss["ended_in_turnover"] = (poss["end_reason"] == "turnover").astype(int)
    poss["has_two_point_attempt_int"] = poss["has_two_point_attempt"].astype(int)
    teams = sorted(poss["offense_team_id"].unique())

    # Per-team arrays of per-possession values, offensive and defensive side.
    off_vals, def_vals = {}, {}
    for t in teams:
        o = poss[poss["offense_team_id"] == t]
        d = poss[poss["defense_team_id"] == t]
        off_vals[t] = {c: o[c].to_numpy(dtype=float)
                       for c in ["points_scored", "shot_attempts", "ended_in_turnover",
                                 "has_two_point_attempt_int"]}
        def_vals[t] = {"points_scored": d["points_scored"].to_numpy(dtype=float)}

    rows = []
    rng = np.random.default_rng(SEED)

    for subset_name, mask_fn in SUBSETS.items():
        mask = mask_fn(poss)
        sub = poss[mask]
        n_off_hc = {t: int((sub["offense_team_id"] == t).sum()) for t in teams}
        n_def_hc = {t: int((sub["defense_team_id"] == t).sum()) for t in teams}

        for metric, (side, col) in METRICS.items():
            hib = HIGHER_IS_BETTER[metric]

            def value_from(off_idx=None, def_idx=None, t=None):
                if side == "off":
                    v = off_vals[t][col][off_idx]
                    return v.mean()
                if side == "def":
                    return def_vals[t]["points_scored"][def_idx].mean()
                return (off_vals[t]["points_scored"][off_idx].mean()
                        - def_vals[t]["points_scored"][def_idx].mean())

            # ---- observed -------------------------------------------------
            full_vals, hc_vals = {}, {}
            for t in teams:
                o_all = np.arange(len(off_vals[t]["points_scored"]))
                d_all = np.arange(len(def_vals[t]["points_scored"]))
                # positions, within this team's own possession arrays, of the
                # possessions that survive the subset mask
                o_mask = mask.to_numpy()[(poss["offense_team_id"] == t).to_numpy()]
                d_mask = mask.to_numpy()[(poss["defense_team_id"] == t).to_numpy()]
                full_vals[t] = value_from(o_all, d_all, t)
                hc_vals[t] = value_from(np.flatnonzero(o_mask), np.flatnonzero(d_mask), t)

            rank_full = competition_rank(full_vals, hib)
            rank_hc = competition_rank(hc_vals, hib)
            observed_churn = sum(abs(rank_hc[t] - rank_full[t]) for t in teams)
            observed_max = max(abs(rank_hc[t] - rank_full[t]) for t in teams)
            observed_level_shift = float(np.mean([hc_vals[t] - full_vals[t] for t in teams]))

            # ---- null: random subsets of the same per-team size ------------
            null_churn = np.empty(N_DRAWS, dtype=int)
            null_level = np.empty(N_DRAWS, dtype=float)
            for i in range(N_DRAWS):
                draw = {}
                for t in teams:
                    n_o = len(off_vals[t]["points_scored"])
                    n_d = len(def_vals[t]["points_scored"])
                    o_idx = rng.choice(n_o, size=n_off_hc[t], replace=False)
                    d_idx = rng.choice(n_d, size=n_def_hc[t], replace=False)
                    draw[t] = value_from(o_idx, d_idx, t)
                r = competition_rank(draw, hib)
                null_churn[i] = sum(abs(r[t] - rank_full[t]) for t in teams)
                null_level[i] = float(np.mean([draw[t] - full_vals[t] for t in teams]))

            p_churn = float((null_churn >= observed_churn).mean())
            p_level = float((np.abs(null_level) >= abs(observed_level_shift)).mean())

            rows.append({
                "comparison_set": subset_name,
                "metric_name": metric,
                "observed_rank_churn": observed_churn,
                "observed_max_rank_change": observed_max,
                "null_rank_churn_mean": round(float(null_churn.mean()), 3),
                "null_rank_churn_p50": float(np.percentile(null_churn, 50)),
                "null_rank_churn_p95": float(np.percentile(null_churn, 95)),
                "p_rank_churn": p_churn,
                "rank_churn_exceeds_sampling_noise": p_churn < 0.05,
                "observed_level_shift": round(observed_level_shift, 6),
                "null_level_shift_p95_abs": round(float(np.percentile(np.abs(null_level), 95)), 6),
                "p_level_shift": p_level,
                "level_shift_exceeds_sampling_noise": p_level < 0.05,
                "n_draws": N_DRAWS,
            })

    out = pd.DataFrame(rows).sort_values(["comparison_set", "metric_name"])
    path = DATA_DIR / "team_metric_sensitivity_null_model.csv"
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print(f"\nSaved {len(out)} rows to {path.relative_to(REPO_ROOT)}")
    return out


if __name__ == "__main__":
    main()
