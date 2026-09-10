-- Phase 13: SQL exposure layer for the 2022-2026 historical backtest.
-- {hist_dir} = data/processed/history

CREATE OR REPLACE VIEW offensive_value_2022_2026 AS
    SELECT * FROM read_csv_auto('{hist_dir}/offensive_value_2022_2026.csv');
CREATE OR REPLACE VIEW faceoff_value_2022_2026 AS
    SELECT * FROM read_csv_auto('{hist_dir}/faceoff_value_2022_2026.csv');
CREATE OR REPLACE VIEW goalie_value_2022_2026 AS
    SELECT * FROM read_csv_auto('{hist_dir}/goalie_value_2022_2026.csv');
CREATE OR REPLACE VIEW defensive_production_2022_2026 AS
    SELECT * FROM read_csv_auto('{hist_dir}/defensive_production_2022_2026.csv');
CREATE OR REPLACE VIEW player_value_historical_stability AS
    SELECT * FROM read_csv_auto('{hist_dir}/player_value_historical_stability.csv');

-- Season-by-season distribution of offensive value, for a quick historical
-- sanity check without leaving SQL.
CREATE OR REPLACE VIEW offensive_value_by_season AS
SELECT season, COUNT(*) AS n_players,
       ROUND(AVG(offensive_value), 3) AS mean_value,
       ROUND(STDDEV(offensive_value), 3) AS sd_value,
       ROUND(MAX(offensive_value), 2) AS max_value,
       ROUND(MIN(offensive_value), 2) AS min_value
FROM offensive_value_2022_2026
GROUP BY season
ORDER BY season;

-- Year-to-year rank stability, read straight from the Python-computed file
-- (SQL does not recompute Spearman correlation here -- it exposes it).
CREATE OR REPLACE VIEW year_to_year_rank_stability AS
SELECT * FROM player_value_historical_stability
ORDER BY value_col, season_pair;
