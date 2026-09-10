-- Phase 13: SQL exposure layer for the goalie value leaderboard.
-- OWNERSHIP: Python owns the value/decomposition/bootstrap; this file only
-- exposes and joins the already-validated CSV.
--
-- {data_dir} = data/processed/2026, {team_dir} = data/processed/2026

CREATE OR REPLACE VIEW goalie_value_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/goalie_value_2026.csv');

CREATE OR REPLACE VIEW goalie_value_components_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/goalie_value_components.csv');

CREATE OR REPLACE VIEW teams_2026 AS
    SELECT * FROM read_csv_auto('{team_dir}/teams.csv');

CREATE OR REPLACE VIEW goalie_value_2026_readable AS
SELECT
    v.rank, v.player_name, t.full_name AS team_name, v.shots_on_goal_faced, v.save_pct,
    v.goalie_value_total, v.goalie_rate_value, v.goalie_workload_value,
    v.workload_vs_skill, v.top10_inclusion_frequency, v.qualification_state
FROM goalie_value_2026 v
LEFT JOIN teams_2026 t ON v.team_id = t.team_id
ORDER BY v.rank;

CREATE OR REPLACE VIEW goalie_value_decomposition_check AS
SELECT
    player_id, player_name,
    goalie_rate_value + goalie_workload_value AS reconstructed_total,
    goalie_value_total,
    ABS(goalie_rate_value + goalie_workload_value - goalie_value_total) AS residual
FROM goalie_value_components_2026
ORDER BY residual DESC;

CREATE OR REPLACE VIEW goalie_workload_vs_skill_summary AS
SELECT workload_vs_skill, COUNT(*) AS n_goalies,
       ROUND(AVG(goalie_value_total), 2) AS mean_value
FROM goalie_value_2026
GROUP BY workload_vs_skill;
