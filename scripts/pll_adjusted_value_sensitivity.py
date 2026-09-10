"""
Phase 7: sensitivity analysis for the usage / normalization layer.

Every Phase 7 choice that could reasonably have gone another way is re-run
here and the rank consequences are reported. The published choice is always
`primary_method`. Nothing was selected because it produced a nicer leaderboard:
the usage model was chosen by cross-validated MSE and the reliability threshold
is a property of the estimator, both fixed before any player was inspected.

Five families of alternative:

  usage_definition        (shots + turnovers) / team, in games played
                          vs shots only, vs including assists, vs touches,
                          vs the Lacrosse Reference event-log play share,
                          vs a full-season denominator
  shrinkage_treatment     raw observed shooting production
                          vs production implied by empirical-Bayes shrunk rates
  normalization_scope     positional standardization vs league-wide
  standardization_method  ordinary z vs robust z vs percentile
  minimum_sample_policy   reliability >= 0.5 vs the Lacrosse Reference 1%
                          team play-share rule vs no minimum

Writes data/processed/2026/player_adjusted_value_sensitivity.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pll_adjusted_value_models as models  # noqa: E402

ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str}


def _rank_desc(values: pd.Series) -> pd.Series:
    """Competition rank, best (largest) first, NaNs left unranked."""
    return values.rank(ascending=False, method="min")


def _rows(av, family, metric, primary_method, alternative_method,
          primary, alternative, sample, sample_measure, population=None):
    """One comparison, as long-format rows.

    `population` restricts BOTH sides to the same players. Ranking 228 players
    on one side against 47 on the other manufactures enormous fake rank moves,
    so the primary and the alternative are always ranked over an identical set.
    """
    p = pd.Series(primary, index=av.index, dtype=float)
    a = pd.Series(alternative, index=av.index, dtype=float)
    if population is not None:
        mask = pd.Series(population, index=av.index).fillna(False).astype(bool)
        p = p.where(mask)
        a = a.where(mask)
    rp, ra = _rank_desc(p), _rank_desc(a)
    return pd.DataFrame({
        "family": family,
        "player_id": av["player_id"].values,
        "player_name": av["player_name"].values,
        "team_id": av["team_id"].values,
        "canonical_position": av["canonical_position"].values,
        "value_role": av["value_role"].values,
        "metric": metric,
        "primary_method": primary_method,
        "alternative_method": alternative_method,
        "sample_size": av[sample].values,
        "sample_measure": sample_measure,
        "primary_value": p.values,
        "alternative_value": a.values,
        "difference": (a - p).values,
        "relative_difference": ((a - p) / p.abs().replace(0, np.nan)).values,
        "rank_primary": rp.values,
        "rank_alternative": ra.values,
        "rank_change": (ra - rp).values,
    })


def main():
    av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
    usage = pd.read_csv(DATA_DIR / "player_play_shares.csv", dtype=ID_DTYPE)
    base = pd.read_csv(DATA_DIR / "player_value_baselines.csv")
    opp = pd.read_csv(DATA_DIR / "player_opportunities.csv", dtype=ID_DTYPE)
    shrink = pd.read_csv(DATA_DIR / "player_value_shrinkage.csv", dtype=ID_DTYPE)

    def bl(n):
        return float(base.loc[base["baseline_name"] == n, "baseline_value"].iloc[0])

    xp1, xp2 = (bl("expected_points_per_one_point_attempt"),
                bl("expected_points_per_two_point_attempt"))

    av = av.merge(usage[["player_id", "offensive_play_share_with_assists"]],
                  on="player_id", how="left")
    av = av.merge(opp[["player_id", "expected_points_from_shots"]]
                  if "expected_points_from_shots" in opp.columns
                  else pd.read_csv(DATA_DIR / "player_value_components.csv",
                                   dtype=ID_DTYPE)[["player_id",
                                                    "expected_points_from_shots"]],
                  on="player_id", how="left")
    av = av.merge(shrink[["player_id", "one_point_pct_shrunk", "two_point_pct_shrunk"]],
                  on="player_id", how="left")

    field = av["value_role"].isin(["offensive_field", "defensive_field"])
    has_opps = av["recorded_offensive_opportunities"] > 0
    out = []

    # ---- 1. usage definition -------------------------------------------------
    for label, col in [
        ("shots only / team shots (exact attribution, no turnovers)", "shot_share"),
        ("(shots + turnovers + assists) / team (assists double-count a shot)",
         "offensive_play_share_with_assists"),
        ("touches / team touches (includes defensive and clearing touches)", "touch_share"),
        ("event-log play shares / team (Lacrosse Reference definition)", "event_log_play_share"),
        ("full-season team denominator instead of games played",
         "offensive_play_share_season"),
    ]:
        out.append(_rows(av, "usage_definition", "offensive_play_share",
                         "(shots + turnovers) / team, over games played (published)",
                         label, av["offensive_play_share"], av[col],
                         "recorded_offensive_opportunities", "recorded offensive opportunities"))

    # ---- 2. usage-adjusted value under alternative usage definitions --------
    # The usage expectation is refitted on each alternative so the comparison is
    # of whole methods, not of one method's residual measured against another's
    # expectation.
    pop = field & has_opps
    for label, col in [
        ("usage measured by shot share", "shot_share"),
        ("usage measured by touch share", "touch_share"),
        ("usage measured by event-log play share", "event_log_play_share"),
    ]:
        sub = av[pop]
        cv, fitted, _, _ = models.fit_usage_model(
            sub[col].fillna(0).to_numpy(float),
            sub["offensive_EPA_points_raw"].to_numpy(float))
        alt = pd.Series(np.nan, index=av.index)
        alt.loc[sub.index] = sub["offensive_EPA_points_raw"].to_numpy() - fitted
        out.append(_rows(av, "usage_definition", "EPA_vs_usage_expectation",
                         "expectation fitted on offensive_play_share (published)",
                         label, av["EPA_vs_usage_expectation"], alt,
                         "recorded_offensive_opportunities", "recorded offensive opportunities",
                         population=pop))

    # ---- 3. raw vs shrunk shooting treatment --------------------------------
    # Production implied by the player's empirical-Bayes shrunk conversion rates
    # on his own actual attempt mix, against the same expectation. This is the
    # comparison Phase 6 found moved 219 of 228 shooting ranks; it is re-run
    # here because Phase 7 has to decide a raw-vs-shrunk POLICY, not just
    # observe the instability.
    shrunk_points = (av["one_point_attempts"] * av["one_point_pct_shrunk"].fillna(xp1)
                     + av["two_point_attempts"] * av["two_point_pct_shrunk"].fillna(xp2 / 2) * 2)
    alt_shoot = shrunk_points - av["expected_points_from_shots"]
    out.append(_rows(av, "shrinkage_treatment", "shooting_value_raw",
                     "raw observed conversion (published as observed_value)",
                     "empirical-Bayes shrunk conversion rates (estimated_skill)",
                     av["shooting_value_raw"], alt_shoot, "shots", "shot attempts",
                     population=av["shots"] > 0))

    alt_total = (av["EPA_points_raw"] - av["shooting_value_raw"].fillna(0)
                 + alt_shoot.fillna(0))
    out.append(_rows(av, "shrinkage_treatment", "EPA_points_raw",
                     "raw observed production (published)",
                     "shooting component replaced by shrunk-rate production",
                     av["EPA_points_raw"], alt_total, "shots", "shot attempts"))

    # ---- 4. positional vs league-wide normalization --------------------------
    league_mean = av["EPA_points_raw"].mean()
    league_sd = av["EPA_points_raw"].std()
    league_z = (av["EPA_points_raw"] - league_mean) / league_sd
    out.append(_rows(av, "normalization_scope", "EPA_position_z",
                     "standardized within position_group (published)",
                     "standardized against the whole league",
                     av["EPA_position_z"], league_z, "games_played", "games played"))

    league_pct = models.midrank_percentile(av["EPA_points_raw"].to_numpy())
    out.append(_rows(av, "normalization_scope", "EPA_position_percentile",
                     "percentile within position_group (published)",
                     "percentile against the whole league",
                     av["EPA_position_percentile"], league_pct,
                     "games_played", "games played"))

    # ---- 5. standardization method ------------------------------------------
    out.append(_rows(av, "standardization_method", "EPA_position_z",
                     "ordinary z within position_group",
                     "robust z within position_group (median / 1.4826 x MAD)",
                     av["EPA_position_z"], av["EPA_position_robust_z"],
                     "games_played", "games played"))
    # percentile rescaled to a z-like scale is not meaningful, so the
    # comparison is made on RANKS, which is what the percentile actually
    # determines
    out.append(_rows(av, "standardization_method", "EPA_position_percentile",
                     "ordinary z within position_group",
                     "percentile within position_group",
                     av["EPA_position_z"], av["EPA_position_percentile"],
                     "games_played", "games played"))

    # ---- 6. minimum-sample policy -------------------------------------------
    # Same metric, three eligibility gates. The VALUE never changes; what
    # changes is who is ranked, so rank_change is the whole point of this
    # family.
    eff = av["shooting_EPA_per_shot"]
    for label, mask in [
        ("Lacrosse Reference rule: >= 1% of team event-log play shares",
         av["future_award_input_eligible"].astype(bool)),
        ("no minimum sample at all", av["shots"] > 0),
    ]:
        out.append(_rows(av, "minimum_sample_policy", "shooting_EPA_per_shot",
                         "reliability >= 0.5 on the role rate (published)",
                         label,
                         eff.where(av["rate_ranking_eligible"].astype(bool)),
                         eff.where(mask), "shots", "shot attempts"))

    result = pd.concat(out, ignore_index=True)
    result = result.sort_values(
        ["family", "metric", "alternative_method", "player_id"]).reset_index(drop=True)
    path = DATA_DIR / "player_adjusted_value_sensitivity.csv"
    result.to_csv(path, index=False)

    print(f"Wrote {len(result)} rows to {path.relative_to(REPO_ROOT)}\n")
    summary = (result.dropna(subset=["rank_primary", "rank_alternative"])
               .groupby(["family", "metric", "alternative_method"])
               .agg(players=("player_id", "size"),
                    mean_abs_diff=("difference", lambda x: x.abs().mean()),
                    max_abs_diff=("difference", lambda x: x.abs().max()),
                    n_rank_changed=("rank_change", lambda x: int((x != 0).sum())),
                    max_rank_move=("rank_change", lambda x: int(x.abs().max())))
               .round(4))
    # Rank correlation between the two orderings, per comparison. Computed on
    # the rank columns directly (a Pearson correlation of ranks IS Spearman's
    # rho), which keeps it to one numpy call and no groupby-apply.
    ranked = result.dropna(subset=["rank_primary", "rank_alternative"])
    sp = (ranked.groupby(["family", "metric", "alternative_method"])[
              ["rank_primary", "rank_alternative"]]
          .corr().unstack().iloc[:, 1])
    summary["rank_correlation"] = sp.round(4)
    print(summary.to_string())
    return result


if __name__ == "__main__":
    main()
