-- Phase 13: SQL exposure layer for defensive production (descriptive only).
-- Deliberately carries NO ORDER BY on a value column and NO combined score
-- -- sorted by games_played (an availability fact), matching
-- docs/DEFENSIVE_PRODUCTION_LIMITATIONS.md.
--
-- {data_dir} = data/processed/2026

CREATE OR REPLACE VIEW defensive_production_2026 AS
    SELECT * FROM read_csv_auto('{data_dir}/defensive_production_2026.csv');

CREATE OR REPLACE VIEW defensive_production_2026_by_availability AS
SELECT player_name, canonical_position, games_played, caused_turnovers,
       ground_balls, caused_turnovers_per_game, data_coverage
FROM defensive_production_2026
ORDER BY games_played DESC;
