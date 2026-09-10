"""
Phase 13 Section S: SQL analytics layer.

Executes the phase13_*.sql files against DuckDB, substituting {data_dir}/
{team_dir}/{hist_dir} exactly as pll_build_team_metrics.py and
pll_build_player_value.py already do for earlier phases. OWNERSHIP is
explicit and one-directional: Python (pll_phase13_player_value_v1.py,
pll_phase13_team_accounting.py, pll_phase13_historical_stability.py) is the
SOURCE of every statistical estimate; every phase13_*.sql file only exposes
and queries those already-published CSVs -- no value formula, baseline, or
uncertainty calculation is duplicated in SQL.

This module also PROVES the two layers agree (Section U check 17): it reads
the leaderboard back out of DuckDB and diffs it, row for row, against the
CSV pandas already validated.

Run: python3 scripts/pll_phase13_sql_layer.py
"""
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SQL_DIR = REPO_ROOT / "sql"

SQL_FILES = [
    "phase13_offensive_leaderboard.sql",
    "phase13_faceoff_leaderboard.sql",
    "phase13_goalie_leaderboard.sql",
    "phase13_defensive_production.sql",
    "phase13_team_accounting.sql",
    "phase13_historical_player_value.sql",
]

AGREEMENT_CHECKS = [
    ("offensive_value_2026", "offensive_value_2026.csv", PROC / "2026"),
    ("faceoff_value_2026", "faceoff_value_2026.csv", PROC / "2026"),
    ("goalie_value_2026", "goalie_value_2026.csv", PROC / "2026"),
    ("defensive_production_2026", "defensive_production_2026.csv", PROC / "2026"),
    ("player_value_team_accounting", "player_value_team_accounting.csv", PROC / "2026"),
]


def run_sql_layer(con: duckdb.DuckDBPyConnection):
    for fname in SQL_FILES:
        text = (SQL_DIR / fname).read_text()
        text = text.replace("{data_dir}", str(PROC / "2026")).replace(
            "{team_dir}", str(PROC / "2026")).replace("{hist_dir}", str(HIST))
        con.execute(text)


def _column_mismatches(sql_col: pd.Series, csv_col: pd.Series) -> int:
    """Numeric columns compared with a floating-point tolerance (DuckDB and
    pandas render the same double with different trailing digits); every
    other column compared exactly as strings."""
    if pd.api.types.is_numeric_dtype(csv_col):
        a = pd.to_numeric(sql_col, errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(csv_col, errors="coerce").to_numpy(dtype=float)
        both_nan = np.isnan(a) & np.isnan(b)
        close = np.isclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=False)
        return int((~(close | both_nan)).sum())
    mismatch = sql_col.astype(str).reset_index(drop=True) != csv_col.astype(str).reset_index(drop=True)
    return int(mismatch.sum())


def verify_agreement(con: duckdb.DuckDBPyConnection) -> list:
    results = []
    for view_name, csv_name, csv_dir in AGREEMENT_CHECKS:
        sql_df = con.execute(f"SELECT * FROM {view_name}").fetchdf().reset_index(drop=True)
        csv_df = pd.read_csv(csv_dir / csv_name).reset_index(drop=True)
        n_mismatch = sum(_column_mismatches(sql_df[c], csv_df[c]) for c in csv_df.columns)
        results.append({
            "view": view_name, "csv": csv_name, "n_rows": len(csv_df),
            "n_cols": len(csv_df.columns), "n_cell_mismatches": n_mismatch,
            "result": "PASS" if n_mismatch == 0 else "FAIL",
        })
    return results


def main():
    con = duckdb.connect(database=":memory:")
    run_sql_layer(con)
    agreement = verify_agreement(con)
    df = pd.DataFrame(agreement)
    out = HIST / "phase13_sql_python_agreement.csv"
    df.to_csv(out, index=False)
    print(df.to_string(index=False))

    print("\nSample query -- offensive_value_2026_readable top 5:")
    print(con.execute("SELECT rank, player_name, team_name, offensive_value FROM "
                      "offensive_value_2026_readable ORDER BY rank LIMIT 5").fetchdf().to_string(index=False))
    print("\nfaceoff_workload_vs_skill_summary:")
    print(con.execute("SELECT * FROM faceoff_workload_vs_skill_summary").fetchdf().to_string(index=False))
    print("\nteam_accounting_league_summary:")
    print(con.execute("SELECT * FROM team_accounting_league_summary").fetchdf().to_string(index=False))

    n_fail = int((df["result"] == "FAIL").sum())
    if n_fail:
        print(f"\n{n_fail} SQL/Python agreement FAILURES", file=sys.stderr)
        sys.exit(1)
    con.close()


if __name__ == "__main__":
    main()
