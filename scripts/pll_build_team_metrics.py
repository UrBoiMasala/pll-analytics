"""
Phase 5: team advanced-metrics build.

Orchestrates the DuckDB SQL analytics layer in sql/ and exports the resulting
tables to data/processed/2026/. Python here does loading, ordering, export and
reporting only -- every metric definition lives in the .sql files, so the
analytics logic is reviewable as SQL rather than buried in dataframe code.

Reads (all Phase 1-4.25 outputs, none of them modified):
    data/processed/2026/games.csv
    data/processed/2026/teams.csv
    data/processed/2026/events.csv
    data/processed/2026/possessions.csv
    data/processed/2026/team_game_stats.csv
    data/processed/2026/validation_report.csv

Writes:
    data/processed/2026/team_game_advanced.csv
    data/processed/2026/team_season_advanced.csv
    data/processed/2026/team_rankings.csv
    data/processed/2026/possession_length_splits.csv
    data/processed/2026/team_metric_sensitivity.csv
    data/processed/2026/metric_definitions.csv

Deterministic: every query carries an explicit ORDER BY and no metric depends
on row order, so reruns produce byte-identical CSVs.
"""
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_metric_definitions import DEFINITIONS, DEFINITION_COLUMNS  # noqa: E402

# (sql file, table it creates, exported csv name or None)
PIPELINE = [
    ("00_base_views.sql", None, None),
    ("team_game_advanced.sql", "team_game_advanced", "team_game_advanced.csv"),
    ("team_season_advanced.sql", "team_season_advanced", "team_season_advanced.csv"),
    ("possession_length_splits.sql", "possession_length_splits", "possession_length_splits.csv"),
    ("team_rankings.sql", "team_rankings", "team_rankings.csv"),
    ("team_metric_sensitivity.sql", "team_metric_sensitivity", "team_metric_sensitivity.csv"),
]


def run_sql_file(con, path: Path, data_dir: Path):
    """Execute a .sql file, substituting the {data_dir} placeholder. DuckDB
    executes a multi-statement script in one call, so no statement splitting
    (and no fragile semicolon parsing) is needed here."""
    con.execute(path.read_text().replace("{data_dir}", str(data_dir)))


def export(con, table: str, out_name: str) -> int:
    out = DATA_DIR / out_name
    df = con.execute(f"SELECT * FROM {table}").df()
    df.to_csv(out, index=False)
    return len(df)


def write_metric_definitions() -> int:
    import csv

    out = DATA_DIR / "metric_definitions.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=DEFINITION_COLUMNS)
        w.writeheader()
        for row in DEFINITIONS:
            w.writerow(row)
    return len(DEFINITIONS)


def main():
    con = duckdb.connect()
    for sql_name, table, out_name in PIPELINE:
        run_sql_file(con, SQL_DIR / sql_name, DATA_DIR)
        if out_name:
            n = export(con, table, out_name)
            print(f"  {out_name:34s} {n:5d} rows")

    n = write_metric_definitions()
    print(f"  {'metric_definitions.csv':34s} {n:5d} rows")

    n_games = con.execute("SELECT COUNT(*) FROM eligible_games").fetchone()[0]
    n_poss = con.execute("SELECT COUNT(*) FROM possessions").fetchone()[0]
    print(f"\nBuilt from {n_games} league-analytics-eligible games / {n_poss} possessions.")
    return con


if __name__ == "__main__":
    main()
