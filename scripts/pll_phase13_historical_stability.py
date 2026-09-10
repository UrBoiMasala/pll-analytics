"""
Phase 13 Section N: historical backtest analysis.

The four Phase 13 leaderboards (offense/faceoff/goalie/defensive production)
are already run identically across 2022-2026 by pll_phase13_player_value_v1.py
-- this script does not rebuild them, it ANALYZES the pooled historical
output for year-to-year distribution, rank stability, extreme values, and
whether 2026 looks anomalous relative to 2022-2025, exactly as Section N
asks. No model is changed here.

Output: data/processed/history/player_value_historical_stability.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST = REPO_ROOT / "data" / "processed" / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]


def _rho(a, b):
    if len(a) < 10:
        return np.nan
    return float(np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1])


def year_to_year_rank_stability(df: pd.DataFrame, value_col: str, min_opp: int, opp_col: str) -> list:
    rows = []
    for s in SEASONS[:-1]:
        cur = df[(df["season"] == s) & (df[opp_col] >= min_opp)][["player_id", value_col]]
        nxt = df[(df["season"] == s + 1) & (df[opp_col] >= min_opp)][["player_id", value_col]]
        m = cur.merge(nxt, on="player_id", suffixes=("_t", "_t1"))
        rows.append({
            "season_pair": f"{s}-{s+1}", "value_col": value_col, "min_opportunity": min_opp,
            "n_pairs": len(m),
            "spearman_rho": _rho(m[f"{value_col}_t"], m[f"{value_col}_t1"]) if len(m) >= 10 else np.nan,
        })
    return rows


def distributional_summary(df: pd.DataFrame, value_col: str) -> list:
    rows = []
    for s in SEASONS:
        sub = df[df["season"] == s][value_col].dropna()
        if len(sub) == 0:
            continue
        rows.append({
            "season": s, "value_col": value_col, "n": len(sub),
            "mean": round(float(sub.mean()), 3), "sd": round(float(sub.std()), 3),
            "min": round(float(sub.min()), 3), "p25": round(float(sub.quantile(.25)), 3),
            "median": round(float(sub.median()), 3), "p75": round(float(sub.quantile(.75)), 3),
            "max": round(float(sub.max()), 3),
        })
    return rows


def is_2026_anomalous(dist_rows: pd.DataFrame, value_col: str) -> dict:
    sub = dist_rows[dist_rows["value_col"] == value_col]
    prior = sub[sub["season"] != 2026]
    y2026 = sub[sub["season"] == 2026]
    if prior.empty or y2026.empty:
        return {"value_col": value_col, "verdict": "NO_DATA"}
    prior_sd_of_means = prior["mean"].std()
    prior_mean_of_means = prior["mean"].mean()
    z = (y2026["mean"].iloc[0] - prior_mean_of_means) / prior_sd_of_means if prior_sd_of_means > 0 else np.nan
    return {
        "value_col": value_col,
        "2026_mean": round(float(y2026["mean"].iloc[0]), 3),
        "2022_2025_mean_of_means": round(float(prior_mean_of_means), 3),
        "2022_2025_sd_of_means": round(float(prior_sd_of_means), 3),
        "z_score_of_2026_vs_2022_2025": round(float(z), 2) if pd.notna(z) else np.nan,
        "verdict": "WITHIN_HISTORICAL_RANGE" if pd.notna(z) and abs(z) < 2 else
                  ("NOTABLE_BUT_NOT_DISQUALIFYING" if pd.notna(z) else "INSUFFICIENT_DATA"),
    }


def main():
    off = pd.read_csv(HIST / "offensive_value_2022_2026.csv", dtype={"player_id": str})
    fo = pd.read_csv(HIST / "faceoff_value_2022_2026.csv", dtype={"player_id": str})
    go = pd.read_csv(HIST / "goalie_value_2022_2026.csv", dtype={"player_id": str})

    rows = []
    rows += year_to_year_rank_stability(off, "offensive_value", 20, "shots")
    rows += year_to_year_rank_stability(fo, "faceoff_value_total", 20, "faceoffs")
    rows += year_to_year_rank_stability(go, "goalie_value_total", 40, "shots_on_goal_faced")
    stability_df = pd.DataFrame(rows)

    dist_rows = pd.DataFrame(
        distributional_summary(off, "offensive_value")
        + distributional_summary(fo, "faceoff_value_total")
        + distributional_summary(go, "goalie_value_total"))

    anomaly_rows = [is_2026_anomalous(dist_rows, c) for c in
                    ["offensive_value", "faceoff_value_total", "goalie_value_total"]]

    # extreme values, one row per role, all 5 seasons
    extremes = []
    for name, df, col in [("offense", off, "offensive_value"),
                          ("faceoff", fo, "faceoff_value_total"),
                          ("goalie", go, "goalie_value_total")]:
        for s in SEASONS:
            sub = df[df["season"] == s]
            if sub.empty:
                continue
            top = sub.loc[sub[col].idxmax()]
            bot = sub.loc[sub[col].idxmin()]
            extremes.append({"role": name, "season": s,
                            "max_value": round(float(top[col]), 2), "max_player": top["player_name"],
                            "min_value": round(float(bot[col]), 2), "min_player": bot["player_name"]})
    extremes_df = pd.DataFrame(extremes)

    out1 = HIST / "player_value_historical_stability.csv"
    stability_df.to_csv(out1, index=False)
    out2 = HIST / "player_value_historical_distribution.csv"
    dist_rows.to_csv(out2, index=False)
    out3 = HIST / "player_value_historical_extremes.csv"
    extremes_df.to_csv(out3, index=False)
    out4 = HIST / "player_value_2026_anomaly_check.csv"
    pd.DataFrame(anomaly_rows).to_csv(out4, index=False)

    print(f"Wrote {out1.name}, {out2.name}, {out3.name}, {out4.name}")
    print(stability_df.to_string(index=False))
    print()
    print(pd.DataFrame(anomaly_rows).to_string(index=False))


if __name__ == "__main__":
    main()
