-- Phase 8 base views.
--
-- Phase 8 is a CONSOLIDATION layer. It does not re-derive any Phase 5/6/7
-- metric: it loads the validated outputs of those phases from disk and joins
-- them into publication-ready statistical tables. The one thing it is allowed
-- to compute is arithmetic that is genuinely new at this level (per-game
-- context, differentials, a handful of rates whose components already exist),
-- and every such column is registered in the Phase 8 metric catalog.
--
-- The rule that makes this safe: a metric formula lives in exactly one place.
-- If a number already exists in a Phase 5/6/7 output it is SELECTed, never
-- recomputed. Phase 8 validation check "phase_output_immutability" fails if any
-- Phase 5/6/7 file changes.
--
-- {data_dir} is substituted by scripts/pll_build_phase8_stats.py.

-- ---------------------------------------------------------------------------
-- Canonical Phase 1-4.25 tables
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_games        AS SELECT * FROM read_csv_auto('{data_dir}/games.csv');
CREATE OR REPLACE VIEW p8_teams        AS SELECT * FROM read_csv_auto('{data_dir}/teams.csv');
CREATE OR REPLACE VIEW p8_players      AS SELECT * FROM read_csv_auto('{data_dir}/players.csv');
CREATE OR REPLACE VIEW p8_events       AS SELECT * FROM read_csv_auto('{data_dir}/events.csv');
CREATE OR REPLACE VIEW p8_possessions  AS SELECT * FROM read_csv_auto('{data_dir}/possessions.csv');
CREATE OR REPLACE VIEW p8_pgs          AS SELECT * FROM read_csv_auto('{data_dir}/player_game_stats.csv');
CREATE OR REPLACE VIEW p8_tgs          AS SELECT * FROM read_csv_auto('{data_dir}/team_game_stats.csv');

-- ---------------------------------------------------------------------------
-- Phase 5 outputs (team advanced)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_team_season  AS SELECT * FROM read_csv_auto('{data_dir}/team_season_advanced.csv');
CREATE OR REPLACE VIEW p8_team_game    AS SELECT * FROM read_csv_auto('{data_dir}/team_game_advanced.csv');
CREATE OR REPLACE VIEW p8_team_rank5   AS SELECT * FROM read_csv_auto('{data_dir}/team_rankings.csv');
CREATE OR REPLACE VIEW p8_len_splits   AS SELECT * FROM read_csv_auto('{data_dir}/possession_length_splits.csv');
CREATE OR REPLACE VIEW p8_sensitivity  AS SELECT * FROM read_csv_auto('{data_dir}/team_metric_sensitivity.csv');

-- ---------------------------------------------------------------------------
-- Phase 6 outputs (player value)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_opps         AS SELECT * FROM read_csv_auto('{data_dir}/player_opportunities.csv');
CREATE OR REPLACE VIEW p8_components   AS SELECT * FROM read_csv_auto('{data_dir}/player_value_components.csv');
CREATE OR REPLACE VIEW p8_baselines    AS SELECT * FROM read_csv_auto('{data_dir}/player_value_baselines.csv');

-- ---------------------------------------------------------------------------
-- Phase 7 outputs (usage / reliability / positional normalization)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_adjusted     AS SELECT * FROM read_csv_auto('{data_dir}/player_adjusted_value.csv');
CREATE OR REPLACE VIEW p8_usage        AS SELECT * FROM read_csv_auto('{data_dir}/player_usage_adjusted_value.csv');
CREATE OR REPLACE VIEW p8_posmap       AS SELECT * FROM read_csv_auto('{data_dir}/player_position_map.csv');
CREATE OR REPLACE VIEW p8_posbase      AS SELECT * FROM read_csv_auto('{data_dir}/player_positional_baselines.csv');


-- ---------------------------------------------------------------------------
-- Eligibility, inherited unchanged from Phase 5's eligible_games. Phase 8 does
-- not define a new scope: the 50 league-analytics-eligible completed games
-- (regular season + 2 quarterfinals), all-star game and ASE/ASW excluded.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_eligible_games AS
SELECT game_id, game_slug, week, game_type, is_playoff, start_date_utc,
       home_team_id, away_team_id, home_score, away_score
FROM p8_games
WHERE is_completed AND include_in_league_analytics AND NOT is_all_star;

CREATE OR REPLACE VIEW p8_eligible_pgs AS
SELECT s.* FROM p8_pgs s JOIN p8_eligible_games g USING (game_id);

CREATE OR REPLACE VIEW p8_eligible_tgs AS
SELECT s.* FROM p8_tgs s JOIN p8_eligible_games g USING (game_id);


-- ---------------------------------------------------------------------------
-- League totals. Used by the two-point audit and by the internal-consistency
-- checks; computed once here so the same numbers are not re-derived in three
-- places.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_league_totals AS
SELECT
    SUM(games_played)          AS team_games,
    SUM(points_scored)         AS points_scored,
    SUM(points_allowed)        AS points_allowed,
    SUM(offensive_possessions) AS offensive_possessions,
    SUM(defensive_possessions) AS defensive_possessions,
    SUM(shots)                 AS shots,
    SUM(shots_on_goal)         AS shots_on_goal,
    SUM(goals)                 AS goals,
    SUM(one_point_attempts)    AS one_point_attempts,
    SUM(one_point_goals)       AS one_point_goals,
    SUM(two_point_attempts)    AS two_point_attempts,
    SUM(two_point_goals)       AS two_point_goals,
    SUM(turnovers)             AS turnovers,
    SUM(ground_balls)          AS ground_balls,
    SUM(faceoffs)              AS faceoffs,
    SUM(faceoff_wins)          AS faceoff_wins,
    SUM(saves)                 AS saves,
    SUM(goals_allowed)         AS goals_allowed
FROM p8_team_season;
