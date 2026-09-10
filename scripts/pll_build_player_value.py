"""
Phase 6: player-value build.

Orchestrates the split the Phase 6 brief asks for -- statistical estimation in
Python, the value accounting in SQL:

  1. Python (scripts/pll_player_value_models.py) estimates the empirical event
     coefficients (bootstrap over a forward event scan) and validates the shot
     model by cross-validation. Neither is expressible as a clean aggregate
     query, so neither is forced into SQL.
  2. Those coefficients are written to a scratch CSV and read back by
     sql/player_value_baselines.sql, so the SQL layer has a single documented
     source for every number it multiplies by.
  3. DuckDB then computes every opportunity count, baseline and value
     component, and the results are exported.

Reads (Phase 1-5 outputs, none modified):
    games.csv, players.csv, events.csv, possessions.csv,
    player_game_stats.csv, team_game_stats.csv

Writes to data/processed/2026/:
    player_opportunities.csv
    player_value_baselines.csv
    player_value_components.csv
    player_value_shrinkage.csv
    shot_model_validation.csv
    ground_ball_context_values.csv
    player_value_metric_definitions.csv

Deterministic: fixed seeds throughout, explicit ORDER BY on every query.
"""
from __future__ import annotations

import csv
import shutil
import sys
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pll_player_value_models as models  # noqa: E402
from pll_player_value_definitions import (  # noqa: E402
    DEFINITIONS, DEFINITION_COLUMNS,
)

SQL_PIPELINE = [
    ("20_player_base_views.sql", None, None),
    ("player_value_baselines.sql", "player_value_baselines", "player_value_baselines.csv"),
    ("player_opportunities.sql", "player_opportunities", "player_opportunities.csv"),
    ("player_shooting_value.sql", "player_shooting_value", None),
    ("player_turnover_value.sql", "player_turnover_value", None),
    ("player_faceoff_value.sql", "player_faceoff_value", None),
    ("player_defensive_value.sql", "player_defensive_value", None),
    ("player_goalie_value.sql", "player_goalie_value", None),
    ("player_value_components.sql", "player_value_components", "player_value_components.csv"),
]

# The baselines query needs player_opportunities for the turnover/caused-turnover
# group rates, but player_opportunities does not depend on the baselines. The
# order above therefore builds baselines from player_game directly (see the SQL)
# rather than from player_opportunities.


def run_sql_file(con, path: Path, data_dir: Path, scratch_dir: Path):
    sql = (path.read_text()
           .replace("{data_dir}", str(data_dir))
           .replace("{scratch_dir}", str(scratch_dir)))
    con.execute(sql)


def write_metric_definitions(data_dir: Path) -> int:
    out = data_dir / "player_value_metric_definitions.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DEFINITION_COLUMNS)
        w.writeheader()
        for row in DEFINITIONS:
            w.writerow(row)
    return len(DEFINITIONS)


def build_shrinkage_table(opportunities: pd.DataFrame) -> pd.DataFrame:
    """Raw vs empirical-Bayes-shrunk versions of the four unstable rates.

    Published side by side and NOT substituted into player_value_components:
    the Phase 6 brief asks for the comparison first, and shrinking a rate that
    then gets multiplied by the player's own opportunity count would pull every
    player's VALUE toward zero in proportion to his sample, which is a
    different (and much stronger) claim than shrinking his RATE.
    """
    df = opportunities.copy()
    specs = [
        ("goals", "shots", "shooting_pct"),
        # one-point conversion is shrunk separately from overall shooting
        # percentage: the overall rate mixes two shot classes with very
        # different conversion probabilities, so shrinking it and then applying
        # it to one shot class would be a category error.
        ("one_point_goals", "one_point_attempts", "one_point_pct"),
        ("two_point_goals", "two_point_attempts", "two_point_pct"),
        ("faceoff_wins", "faceoffs", "faceoff_win_pct"),
        ("saves", "save_denominator", "save_pct"),
    ]
    df["save_denominator"] = df["saves"] + df["goals_allowed"]
    out = df[["player_id", "player_name", "primary_team_id", "position_code",
              "baseline_group", "games_played"]].copy()
    for succ, trials, name in specs:
        # Estimate the prior only on players who actually have the opportunity
        # type; including 200 field players with zero faceoffs would make the
        # faceoff prior meaningless.
        sub = df[df[trials] > 0]
        shrunk = models.empirical_bayes_rates(sub, succ, trials, name)
        cols = [c for c in shrunk.columns if c.startswith(name + "_")]
        out = out.merge(shrunk[["player_id", succ, trials] + cols], on="player_id", how="left")
        out = out.rename(columns={succ: f"{name}_successes", trials: f"{name}_trials"})
        out[f"{name}_shrinkage_shift"] = out[f"{name}_shrunk"] - out[f"{name}_raw"]
    return out.sort_values("player_id").reset_index(drop=True)


def main(data_dir: Path = None):
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    scratch = Path(tempfile.mkdtemp(prefix="pll_phase6_"))
    try:
        # ---- 1. Python estimation -------------------------------------------
        ev = models.load_eligible_events(data_dir)
        event_values = models.estimate_event_values(ev)
        event_values.to_csv(scratch / "event_value_coefficients.csv", index=False)

        cv, shot_baseline = models.fit_shot_models(ev, data_dir=data_dir)
        cv["selected_model"] = cv["model"] == "shot_class"  # actual SQL baseline
        cv.to_csv(data_dir / "shot_model_validation.csv", index=False)

        possessions = pd.read_csv(data_dir / "possessions.csv")
        gb_ctx = models.ground_ball_context_values(ev, possessions)
        overlap = models.faceoff_ground_ball_overlap(ev)
        for k, v in overlap.items():
            gb_ctx[k] = v
        gb_ctx.to_csv(data_dir / "ground_ball_context_values.csv", index=False)

        # ---- 2/3. SQL layer --------------------------------------------------
        con = duckdb.connect()
        exported = {}
        for sql_name, table, out_name in SQL_PIPELINE:
            run_sql_file(con, SQL_DIR / sql_name, data_dir, scratch)
            if out_name:
                df = con.execute(f"SELECT * FROM {table}").df()
                df.to_csv(data_dir / out_name, index=False)
                exported[out_name] = len(df)
                print(f"  {out_name:42s} {len(df):5d} rows")

        # ---- 4. Shrinkage comparison ----------------------------------------
        opportunities = con.execute("SELECT * FROM player_opportunities").df()
        shrink = build_shrinkage_table(opportunities)
        shrink.to_csv(data_dir / "player_value_shrinkage.csv", index=False)
        print(f"  {'player_value_shrinkage.csv':42s} {len(shrink):5d} rows")

        n = write_metric_definitions(data_dir)
        print(f"  {'player_value_metric_definitions.csv':42s} {n:5d} rows")
        print(f"  {'shot_model_validation.csv':42s} {len(cv):5d} rows")
        print(f"  {'ground_ball_context_values.csv':42s} {len(gb_ctx):5d} rows")

        coeff = con.execute("SELECT * FROM value_coefficients").df().iloc[0]
        print("\nCoefficients in use (PLL points):")
        for k in ["xp_per_one_point_attempt", "xp_per_two_point_attempt",
                  "xp_allowed_per_one_point_sog", "xp_allowed_per_two_point_sog",
                  "faceoff_win_probability", "points_per_marginal_faceoff_win",
                  "points_per_turnover", "points_per_caused_turnover"]:
            print(f"  {k:34s} {coeff[k]:+.5f}")
        print(f"\nShot model selected: "
              f"{'shot_class_plus_game_state' if cv.attrs['richer_model_helps'] else 'shot_class'}"
              f" (cross-validated Brier)")
        return con
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
