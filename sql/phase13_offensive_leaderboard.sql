-- Phase 13: SQL exposure layer for the offensive value leaderboard.
--
-- OWNERSHIP: Python (pll_phase13_player_value_v1.py) owns every statistical
-- estimate here -- the value formula, the bootstrap uncertainty, and the
-- qualification classification. This file NEVER recomputes any of them; it
-- only exposes the already-validated CSV as queryable relations and
-- provides a few illustrative joins/aggregations, so no business logic is
-- duplicated inconsistently between the two layers.
--
-- {data_dir} = data/processed/2026, {team_dir} = data/processed/2026 (teams.csv)

CREATE OR REPLACE VIEW offensive_value_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/offensive_value_2026.csv');

CREATE OR REPLACE VIEW offensive_value_components_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/offensive_value_components.csv');

CREATE OR REPLACE VIEW teams_2026 AS
    SELECT * FROM read_csv_auto('{team_dir}/teams.csv');

-- Leaderboard with team names resolved, for human-readable output.
CREATE OR REPLACE VIEW offensive_value_2026_readable AS
SELECT
    v.rank,
    v.player_name,
    t.full_name AS team_name,
    v.canonical_position,
    v.games_played,
    v.shots,
    v.offensive_value,
    v.value_ci_lo,
    v.value_ci_hi,
    v.top10_inclusion_frequency,
    v.qualification_state
FROM offensive_value_2026 v
LEFT JOIN teams_2026 t ON v.team_id = t.team_id
ORDER BY v.rank;

-- Accounting spot-check: every component row's shooting_value_raw +
-- turnover_value_raw must equal offensive_value (re-verifies, in SQL, the
-- identity Python already asserts before writing the CSV).
CREATE OR REPLACE VIEW offensive_value_accounting_check AS
SELECT
    player_id, player_name,
    shooting_value_raw + turnover_value_raw AS reconstructed_value,
    offensive_value,
    ABS(shooting_value_raw + turnover_value_raw - offensive_value) AS residual
FROM offensive_value_components_2026
ORDER BY residual DESC;

-- Qualification breakdown -- how much of the board is small-sample.
CREATE OR REPLACE VIEW offensive_value_qualification_summary AS
SELECT
    qualification_state,
    COUNT(*) AS n_players,
    ROUND(AVG(offensive_value), 3) AS mean_value,
    ROUND(AVG(top10_inclusion_frequency), 3) AS mean_top10_inclusion_frequency
FROM offensive_value_2026
GROUP BY qualification_state
ORDER BY n_players DESC;
