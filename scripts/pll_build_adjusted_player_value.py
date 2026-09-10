"""
Phase 7: usage-adjusted, positionally-normalized player value.

Keeps the Phase 5/6 split -- statistical estimation in Python, accounting and
normalization in SQL -- and runs in three passes because the usage model needs
a usage number that only SQL produces:

  Pass 1 (SQL)     position mapping and every usage/play-share measure.
  Pass 2 (Python)  the closed-form sampling variance of each Phase 6 component,
                   empirical-Bayes reliability with exact beta-posterior
                   intervals, and the cross-validated E[value | usage] fit.
  Pass 3 (SQL)     the analytic core, positional baselines, the usage-adjusted
                   table and the assembled player table.

READS (none modified): the Phase 1-5 canonical tables plus the Phase 6 outputs
player_value_components.csv, player_opportunities.csv, player_value_baselines.csv
and player_value_shrinkage.csv. Phase 6's raw EPA_points values are carried
through verbatim rather than recomputed.

WRITES to data/processed/2026/:
    player_position_map.csv
    player_play_shares.csv
    player_rate_reliability.csv
    player_rate_identification.csv
    player_value_null_variance.csv
    player_usage_model.csv
    player_positional_baselines.csv
    player_usage_adjusted_value.csv
    player_adjusted_value.csv
    player_adjusted_metric_definitions.csv

Deterministic: fixed seeds, explicit ORDER BY on every query.
"""
from __future__ import annotations

import csv
import shutil
import sys
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pll_adjusted_value_models as models  # noqa: E402
from pll_adjusted_value_definitions import (  # noqa: E402
    ADJUSTED_DEFINITIONS, ADJUSTED_DEFINITION_COLUMNS,
)

ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str}

# The population the usage model is fitted on. Restricted to field players who
# actually have offensive opportunities: fitting E[value | usage] over goalies
# and faceoff specialists as well would let two roles with an entirely
# different opportunity structure set the slope for attackmen.
USAGE_MODEL_POPULATION = "field players (value_role offensive_field or defensive_field) with at least one recorded offensive opportunity"

SQL_PASS_1 = [
    ("20_player_base_views.sql", None, None),
    ("30_player_adjusted_base_views.sql", None, None),
    ("player_position_mapping.sql", "player_position_map", "player_position_map.csv"),
    ("player_play_shares.sql", "player_usage", "player_play_shares.csv"),
]

SQL_PASS_3 = [
    ("player_adjusted_core.sql", "player_adjusted_core", None),
    ("player_positional_baselines.sql", "player_positional_baselines",
     "player_positional_baselines.csv"),
    ("player_usage_adjusted_value.sql", "player_usage_adjusted_value",
     "player_usage_adjusted_value.csv"),
    ("player_adjusted_value.sql", "player_adjusted_value", "player_adjusted_value.csv"),
]


def run_sql_file(con, path: Path, data_dir: Path, scratch_dir: Path):
    sql = (path.read_text()
           .replace("{data_dir}", str(data_dir))
           .replace("{scratch_dir}", str(scratch_dir)))
    con.execute(sql)


def write_metric_definitions(data_dir: Path) -> int:
    out = data_dir / "player_adjusted_metric_definitions.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ADJUSTED_DEFINITION_COLUMNS)
        w.writeheader()
        for row in ADJUSTED_DEFINITIONS:
            w.writerow(row)
    return len(ADJUSTED_DEFINITIONS)


def build_usage_expectation(usage: pd.DataFrame, components: pd.DataFrame,
                            position_map: pd.DataFrame,
                            nulls: pd.DataFrame) -> tuple:
    """Fit E[offensive EPA | offensive play share] and return the per-player
    expectation and residual, plus the model-comparison table.

    The expectation is only defined for the population it was fitted on. Every
    player outside it gets NULL, not zero: a goalie has no offensive-usage
    expectation, and writing 0 there would read as "his expectation was
    measured and came out at zero".
    """
    df = (components[["player_id", "shooting_value", "turnover_value"]]
          .merge(usage[["player_id", "offensive_play_share",
                        "recorded_offensive_opportunities"]], on="player_id")
          .merge(position_map[["player_id", "value_role"]], on="player_id")
          .merge(nulls[["player_id", "shooting_value_null_variance",
                        "turnover_value_null_variance"]], on="player_id"))
    df["offensive_EPA"] = df["shooting_value"].fillna(0) + df["turnover_value"].fillna(0)
    df["null_var"] = (df["shooting_value_null_variance"].fillna(0)
                      + df["turnover_value_null_variance"].fillna(0))

    pop = df[df["value_role"].isin(["offensive_field", "defensive_field"])
             & (df["recorded_offensive_opportunities"] > 0)].copy()

    cv, fitted, coeffs, degree = models.fit_usage_model(
        pop["offensive_play_share"].to_numpy(float),
        pop["offensive_EPA"].to_numpy(float))
    form = {0: "constant", 1: "linear", 2: "quadratic"}[degree]

    # the weighted alternative, reported but not published as the expectation
    w = 1.0 / np.clip(pop["null_var"].to_numpy(float), 1e-9, None)
    cv_w, _, coeffs_w, degree_w = models.fit_usage_model(
        pop["offensive_play_share"].to_numpy(float),
        pop["offensive_EPA"].to_numpy(float), weights=w)
    cv["weighting"] = "unweighted (published)"
    cv_w["weighting"] = "weighted by 1 / null variance (alternative)"
    cv_all = pd.concat([cv, cv_w], ignore_index=True)
    cv_all["population"] = USAGE_MODEL_POPULATION
    cv_all["n_population"] = len(pop)
    cv_all["response"] = "offensive_EPA_points_raw (shooting_value + turnover_value)"
    cv_all["predictor"] = "offensive_play_share"

    # correlation diagnostics, so the "usage does not predict value" finding is
    # a published number rather than an assertion in prose
    corr = {
        "pearson_r_usage_vs_offensive_EPA": float(np.corrcoef(
            pop["offensive_play_share"], pop["offensive_EPA"])[0, 1]),
        "pearson_r_opportunities_vs_offensive_EPA": float(np.corrcoef(
            pop["recorded_offensive_opportunities"], pop["offensive_EPA"])[0, 1]),
        "spearman_r_usage_vs_offensive_EPA": float(np.corrcoef(
            pop["offensive_play_share"].rank(), pop["offensive_EPA"].rank())[0, 1]),
    }
    for k, v in corr.items():
        cv_all[k] = v

    pop["expected_EPA_given_usage"] = fitted
    pop["EPA_vs_usage_expectation"] = pop["offensive_EPA"] - fitted
    out = df[["player_id"]].merge(
        pop[["player_id", "expected_EPA_given_usage", "EPA_vs_usage_expectation"]],
        on="player_id", how="left")
    out["usage_model_population"] = np.where(
        out["expected_EPA_given_usage"].notna(), USAGE_MODEL_POPULATION,
        "outside the fitted population; no offensive-usage expectation is defined")
    out["usage_model_form"] = np.where(
        out["expected_EPA_given_usage"].notna(),
        f"{form} in offensive_play_share, selected by 5-fold CV MSE", "not_applicable")
    return out.sort_values("player_id").reset_index(drop=True), cv_all


def build_usage_variance_profile(core_like: pd.DataFrame) -> pd.DataFrame:
    """Observed spread of offensive EPA by usage quintile, alongside the mean.

    This is the evidence behind the central Phase 7 finding: usage moves the
    VARIANCE of measured value, not its mean.
    """
    pop = core_like[core_like["recorded_offensive_opportunities"] > 0].copy()
    pop = pop[pop["value_role"].isin(["offensive_field", "defensive_field"])]
    pop["usage_quintile"] = pd.qcut(pop["offensive_play_share"], 5, labels=False,
                                    duplicates="drop") + 1
    g = pop.groupby("usage_quintile")
    return pd.DataFrame({
        "usage_quintile": g.size().index,
        "n_players": g.size().to_numpy(),
        "mean_offensive_play_share": g["offensive_play_share"].mean().to_numpy(),
        "mean_recorded_opportunities": g["recorded_offensive_opportunities"].mean().to_numpy(),
        "mean_offensive_EPA": g["offensive_EPA_points_raw"].mean().to_numpy(),
        "sd_offensive_EPA": g["offensive_EPA_points_raw"].std().to_numpy(),
        "mean_null_sd": g["offensive_EPA_null_sd"].mean().to_numpy(),
        "mean_EPA_per_opportunity": g["EPA_per_recorded_opportunity"].mean().to_numpy(),
    }).reset_index(drop=True)


def main(data_dir: Path = None):
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    scratch = Path(tempfile.mkdtemp(prefix="pll_phase7_"))
    exported = {}
    try:
        con = duckdb.connect()
        # Single-threaded on purpose. DuckDB's parallel aggregation sums
        # floating-point partials in whatever order the threads finish in, so
        # AVG and STDDEV_SAMP over the same rows can differ in the last bit
        # between runs. That is harmless numerically and fatal to a byte-for-
        # byte reproducibility check (validation check 25 caught it moving the
        # positional baselines by 1.8e-15). The tables here are a few hundred
        # rows; there is nothing to parallelise anyway.
        con.execute("PRAGMA threads=1")

        # ---- Pass 1: position map + usage -----------------------------------
        for sql_name, table, out_name in SQL_PASS_1:
            run_sql_file(con, SQL_DIR / sql_name, data_dir, scratch)
            if out_name:
                df = con.execute(f"SELECT * FROM {table} ORDER BY player_id").df()
                df.to_csv(data_dir / out_name, index=False)
                exported[out_name] = len(df)

        usage = con.execute("SELECT * FROM player_usage ORDER BY player_id").df()
        position_map = con.execute(
            "SELECT * FROM player_position_map ORDER BY player_id").df()

        # ---- Pass 2: Python estimation --------------------------------------
        comp = pd.read_csv(data_dir / "player_value_components.csv", dtype=ID_DTYPE)
        opp = pd.read_csv(data_dir / "player_opportunities.csv", dtype=ID_DTYPE)
        base = pd.read_csv(data_dir / "player_value_baselines.csv")

        nulls = models.null_variance_components(comp, base)
        nulls.to_csv(scratch / "player_null_variance.csv", index=False)
        nulls.to_csv(data_dir / "player_value_null_variance.csv", index=False)
        exported["player_value_null_variance.csv"] = len(nulls)

        reliability = models.reliability_table(opp)
        reliability.to_csv(scratch / "player_rate_reliability.csv", index=False)
        reliability.to_csv(data_dir / "player_rate_reliability.csv", index=False)
        exported["player_rate_reliability.csv"] = len(reliability)

        ident = models.rate_identification_summary(reliability)
        ident.to_csv(data_dir / "player_rate_identification.csv", index=False)
        exported["player_rate_identification.csv"] = len(ident)

        fit, cv_all = build_usage_expectation(usage, comp, position_map, nulls)
        fit.to_csv(scratch / "player_usage_expectation.csv", index=False)

        # ---- Pass 3: SQL assembly -------------------------------------------
        for sql_name, table, out_name in SQL_PASS_3:
            run_sql_file(con, SQL_DIR / sql_name, data_dir, scratch)
            if out_name:
                order = "player_id" if table != "player_positional_baselines" \
                    else "metric_name, baseline_scope, baseline_group"
                df = con.execute(f"SELECT * FROM {table} ORDER BY {order}").df()
                df.to_csv(data_dir / out_name, index=False)
                exported[out_name] = len(df)

        core = con.execute("SELECT * FROM player_adjusted_core ORDER BY player_id").df()

        # component-level identification, using the null variances
        sn_rows = []
        for value_col, var_col, opp_col in [
            ("shooting_value", "shooting_value_null_variance", "shots"),
            ("turnover_value", "turnover_value_null_variance", "touches"),
            ("faceoff_value", "faceoff_value_null_variance", "faceoffs"),
            ("goalie_value", "goalie_value_null_variance", "shots_on_goal_faced"),
            ("caused_turnover_value", "caused_turnover_value_null_variance", "games_played"),
        ]:
            sn_rows.append(models.null_signal_to_noise(comp, nulls, value_col,
                                                       var_col, opp_col))
        sn = pd.DataFrame(sn_rows)

        profile = build_usage_variance_profile(core)
        # the usage model table carries the fit, the correlations and the
        # quintile profile in one artefact
        cv_all.to_csv(data_dir / "player_usage_model.csv", index=False)
        exported["player_usage_model.csv"] = len(cv_all)
        profile.to_csv(data_dir / "player_usage_variance_profile.csv", index=False)
        exported["player_usage_variance_profile.csv"] = len(profile)
        sn.to_csv(data_dir / "player_component_identification.csv", index=False)
        exported["player_component_identification.csv"] = len(sn)

        n = write_metric_definitions(data_dir)
        exported["player_adjusted_metric_definitions.csv"] = n

        for k in sorted(exported):
            print(f"  {k:46s} {exported[k]:5d} rows")

        print("\nUsage model (cross-validated MSE, unweighted):")
        print(cv_all[cv_all["weighting"].str.startswith("unweighted")]
              [["model", "mse_cross_validated", "improvement_vs_constant",
                "selected_model"]].round(5).to_string(index=False))
        print(f"\n  Pearson r(usage, offensive EPA) = "
              f"{cv_all['pearson_r_usage_vs_offensive_EPA'].iloc[0]:+.4f}")

        print("\nComponent identification (sd of value / null sd; 1.0 = pure chance):")
        print(sn[["component", "n_players", "sd_of_null_standardized_value",
                  "implied_skill_share_of_variance"]].round(4).to_string(index=False))

        print("\nRate identification:")
        print(ident[["rate_name", "n_players_with_trials", "prior_strength_trials",
                     "n_players_reliability_ge_0_5", "identification"]]
              .round(2).to_string(index=False))
        return con
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
