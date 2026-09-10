"""
Phase 6: player-value sensitivity analysis.

Every coefficient in the framework is an estimate, and several rest on a
convention (a 60-second forward window) rather than on something the data
forces. This re-runs the affected components under defensible alternatives and
reports how much each player's value and rank moves.

Four comparisons:

  shooting_model    simple two-class conversion baseline (published)
                    vs the rejected logistic model with game state
  shooting_rates    raw player rates (published) vs empirical-Bayes shrunk rates
  turnover_cost     forward-window event value 0.20046 (published)
                    vs league points per possession 0.27120
                    vs 30-second and 120-second forward windows
  faceoff_value     forward-window coefficient 0.34643 (published)
                    vs the possession-native alternative 2 x the points a
                    faceoff-started possession is worth (0.49040)

The published choice is always the `baseline_method`. No alternative was
selected because it produced a nicer-looking leaderboard; the shot model was
chosen on cross-validated Brier score before any player total was inspected.

Writes data/processed/2026/player_value_sensitivity.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pll_player_value_models as models  # noqa: E402


def _rank_desc(values: pd.Series) -> pd.Series:
    """Competition rank, best (largest) first, NaNs left unranked."""
    return values.rank(ascending=False, method="min")


def _rows(component, baseline_method, alternative_method, base, alt, opportunities,
          players, opportunity_col):
    base_rank, alt_rank = _rank_desc(base), _rank_desc(alt)
    return pd.DataFrame({
        "player_id": players["player_id"].values,
        "player_name": players["player_name"].values,
        "team_id": players["team_id"].values,
        "position_code": players["position_code"].values,
        "component": component,
        "baseline_method": baseline_method,
        "alternative_method": alternative_method,
        "opportunities": opportunities.values,
        "opportunity_measure": opportunity_col,
        "baseline_value": base.values,
        "alternative_value": alt.values,
        "value_difference": (alt - base).values,
        "relative_difference": ((alt - base) / base.abs().replace(0, np.nan)).values,
        "rank_baseline": base_rank.values,
        "rank_alternative": alt_rank.values,
        "rank_difference": (alt_rank - base_rank).values,
    })


# player_id is a zero-padded 6-character string throughout this repo
# ("000221"). Reading it without an explicit dtype makes pandas infer int64 and
# silently drop the padding, which then fails to join against events.csv.
ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str}


def main():
    comp = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
    shrink = pd.read_csv(DATA_DIR / "player_value_shrinkage.csv", dtype=ID_DTYPE)
    baselines = pd.read_csv(DATA_DIR / "player_value_baselines.csv")
    ev = models.load_eligible_events()

    def bl(name):
        return float(baselines.loc[baselines["baseline_name"] == name, "baseline_value"].iloc[0])

    xp1 = bl("expected_points_per_one_point_attempt")
    xp2 = bl("expected_points_per_two_point_attempt")
    ppp_league = bl("points_per_possession_league")
    ppp_faceoff = bl("points_per_faceoff_started_possession")
    fo_prob = bl("faceoff_win_probability")
    published_turnover_cost = -bl("event_value__turnover")
    published_faceoff_coef = 2 * bl("event_value__faceoff_win")

    players = comp[["player_id", "player_name", "team_id", "position_code"]]
    out = []

    # ---- 1. shot model: published two-class baseline vs rejected logistic ----
    shots = models._shot_feature_frame(ev)
    feats = ["is_two_point", "score_margin", "period_late", "game_progress"]
    X = np.column_stack([np.ones(len(shots))] + [shots[f].to_numpy(float) for f in feats])
    beta = models._irls_logistic(X, shots["y"].to_numpy(float))
    shots["p_hat"] = models._predict(X, beta)
    shots["xp_points_rich"] = shots["p_hat"] * np.where(shots["is_two_point"] > 0, 2, 1)
    rich = (shots.groupby(shots["player_id"].astype(str).str.zfill(6))["xp_points_rich"]
            .sum().rename("expected_points_rich"))
    m = comp.merge(rich, left_on="player_id", right_index=True, how="left")
    m["expected_points_rich"] = m["expected_points_rich"].fillna(0.0)
    alt_shooting = m["pll_points"] - m["expected_points_rich"]
    out.append(_rows("shooting_value",
                     "empirical two-class conversion baseline (published)",
                     "logistic model with game state (rejected on cross-validated Brier)",
                     m["shooting_value"], alt_shooting, m["shots"], players, "shots"))

    # ---- 2. raw vs empirical-Bayes shrunk shooting rates --------------------
    s = comp.merge(
        shrink[["player_id", "one_point_pct_shrunk", "two_point_pct_shrunk"]],
        on="player_id", how="left")
    # A shrunk-rate version of observed production: replace the player's own
    # realised conversion with his shrunk rate, keeping his actual attempt mix.
    # Each shot class is shrunk against its own prior -- a player's one-point
    # and two-point conversion are different quantities with very different
    # league means, and a player with no attempts of a class falls back to that
    # class's league rate.
    shrunk_points = (s["one_point_attempts"] * s["one_point_pct_shrunk"].fillna(xp1)
                     + s["two_point_attempts"] * s["two_point_pct_shrunk"].fillna(xp2 / 2) * 2)
    alt_shrunk = shrunk_points - s["expected_points_from_shots"]
    out.append(_rows("shooting_value",
                     "raw observed conversion (published)",
                     "empirical-Bayes shrunk conversion rates",
                     s["shooting_value"], alt_shrunk, s["shots"], players, "shots"))

    # ---- 3. turnover cost alternatives --------------------------------------
    for label, cost in [
        ("league points per possession (0.27120)", ppp_league),
        ("30-second forward window", None),
        ("120-second forward window", None),
    ]:
        if cost is None:
            window = 30 if "30-" in label else 120
            vals = models.estimate_event_values(ev, window=window, n_boot=200)
            cost = -float(vals.loc[vals["event_class"] == "turnover", "value_vs_neutral"].iloc[0])
            label = f"{label} (cost {cost:.5f})"
        alt = -comp["turnovers_above_expected"] * cost
        out.append(_rows("turnover_value",
                         f"60-second forward window (published, cost {published_turnover_cost:.5f})",
                         label, comp["turnover_value"], alt, comp["touches"],
                         players, "touches"))

    # ---- 4. faceoff coefficient alternative ---------------------------------
    alt_fo = comp["faceoff_wins_above_expected"] * (2 * ppp_faceoff)
    out.append(_rows("faceoff_value",
                     f"forward-window coefficient (published, {published_faceoff_coef:.5f})",
                     f"possession-native: 2 x points per faceoff-started possession "
                     f"({2 * ppp_faceoff:.5f})",
                     comp["faceoff_value"], alt_fo, comp["faceoffs"], players, "faceoffs"))

    # ---- 5. faceoff baseline alternative ------------------------------------
    # NULL where the published component is NULL, so both sides rank the same
    # 47 players. Leaving non-faceoff players at 0 in the alternative would rank
    # 228 against 47 and manufacture enormous fake rank moves.
    alt_fo_half = ((comp["faceoff_wins"] - comp["faceoffs"] * 0.5)
                   * published_faceoff_coef).where(comp["faceoffs"] > 0)
    out.append(_rows("faceoff_value",
                     f"empirical league win probability (published, {fo_prob:.5f})",
                     "assumed 0.5 win probability",
                     comp["faceoff_value"], alt_fo_half, comp["faceoffs"], players, "faceoffs"))

    result = pd.concat(out, ignore_index=True)
    result = result.sort_values(
        ["component", "alternative_method", "player_id"]).reset_index(drop=True)
    path = DATA_DIR / "player_value_sensitivity.csv"
    result.to_csv(path, index=False)

    print(f"Wrote {len(result)} rows to {path.relative_to(REPO_ROOT)}\n")
    summary = (result.dropna(subset=["value_difference"])
               .groupby(["component", "alternative_method"])
               .agg(players=("player_id", "size"),
                    mean_abs_diff=("value_difference", lambda x: x.abs().mean()),
                    max_abs_diff=("value_difference", lambda x: x.abs().max()),
                    n_rank_changed=("rank_difference", lambda x: int((x != 0).sum())),
                    max_rank_move=("rank_difference", lambda x: int(x.abs().max())))
               .round(4))
    print(summary.to_string())
    return result


if __name__ == "__main__":
    main()
