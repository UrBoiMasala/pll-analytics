-- Phase 13: SQL exposure layer for team-level value accounting.
-- {data_dir} = data/processed/2026

CREATE OR REPLACE VIEW player_value_team_accounting AS
    SELECT * FROM read_csv_auto('{data_dir}/player_value_team_accounting.csv');

CREATE OR REPLACE VIEW team_accounting_failures AS
SELECT * FROM player_value_team_accounting
WHERE unconditional_accounting_result != 'PASS';

CREATE OR REPLACE VIEW team_accounting_league_summary AS
SELECT season, team_sum_of_EPA_points_raw, sum_of_published_role_leaderboard_values,
       role_leaderboard_coverage_gap
FROM player_value_team_accounting
WHERE team_id = 'LEAGUE_TOTAL'
ORDER BY season;
