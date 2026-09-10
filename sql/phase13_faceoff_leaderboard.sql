-- Phase 13: SQL exposure layer for the faceoff value leaderboard.
-- OWNERSHIP: Python owns the value/decomposition/bootstrap; this file only
-- exposes and joins the already-validated CSV.
--
-- {data_dir} = data/processed/2026, {team_dir} = data/processed/2026

CREATE OR REPLACE VIEW faceoff_value_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/faceoff_value_2026.csv');

CREATE OR REPLACE VIEW faceoff_value_components_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/faceoff_value_components.csv');

CREATE OR REPLACE VIEW teams_2026 AS
    SELECT * FROM read_csv_auto('{team_dir}/teams.csv');

CREATE OR REPLACE VIEW faceoff_value_2026_readable AS
SELECT
    v.rank, v.player_name, t.full_name AS team_name, v.faceoffs, v.faceoff_win_pct,
    v.faceoff_value_total, v.faceoff_rate_value, v.faceoff_volume_value,
    v.workload_vs_skill, v.top10_inclusion_frequency, v.qualification_state
FROM faceoff_value_2026 v
LEFT JOIN teams_2026 t ON v.team_id = t.team_id
ORDER BY v.rank;

-- Rate/volume decomposition accounting check (must sum exactly).
CREATE OR REPLACE VIEW faceoff_value_decomposition_check AS
SELECT
    player_id, player_name,
    faceoff_rate_value + faceoff_volume_value AS reconstructed_total,
    faceoff_value_total,
    ABS(faceoff_rate_value + faceoff_volume_value - faceoff_value_total) AS residual
FROM faceoff_value_components_2026
ORDER BY residual DESC;

-- How much of the leaderboard is workload-driven vs rate-driven.
CREATE OR REPLACE VIEW faceoff_workload_vs_skill_summary AS
SELECT workload_vs_skill, COUNT(*) AS n_players,
       ROUND(AVG(faceoff_value_total), 2) AS mean_value
FROM faceoff_value_2026
GROUP BY workload_vs_skill;
