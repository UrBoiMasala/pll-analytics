-- Phase 5 base views.
--
-- Loads the Phase 1-4.25 canonical tables into DuckDB and derives the shared
-- building blocks every downstream Phase 5 query joins against. Nothing here
-- invents a new eligibility rule: it reuses games.include_in_league_analytics
-- and events.is_analysis_eligible_event exactly as Phases 3.5/4 defined them
-- (see DATASET_2026.md "Metric-specific eligibility").
--
-- {data_dir} is substituted by scripts/pll_build_team_metrics.py.

CREATE OR REPLACE VIEW games_raw       AS SELECT * FROM read_csv_auto('{data_dir}/games.csv');
CREATE OR REPLACE VIEW teams_raw       AS SELECT * FROM read_csv_auto('{data_dir}/teams.csv');
CREATE OR REPLACE VIEW events_raw      AS SELECT * FROM read_csv_auto('{data_dir}/events.csv');
CREATE OR REPLACE VIEW possessions_raw AS SELECT * FROM read_csv_auto('{data_dir}/possessions.csv');
CREATE OR REPLACE VIEW team_game_stats AS SELECT * FROM read_csv_auto('{data_dir}/team_game_stats.csv');
CREATE OR REPLACE VIEW validation_raw  AS SELECT * FROM read_csv_auto('{data_dir}/validation_report.csv');


-- ---------------------------------------------------------------------------
-- Eligible games. The all-star game is excluded here, once, and every Phase 5
-- table inherits that exclusion by joining through this view.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW eligible_games AS
SELECT
    game_id,
    game_slug,
    week,
    game_type,
    is_playoff,
    start_date_utc,
    home_team_id,
    away_team_id,
    home_score,
    away_score
FROM games_raw
WHERE is_completed
  AND include_in_league_analytics
  AND NOT is_all_star;


-- ---------------------------------------------------------------------------
-- One row per (game, participating team), with that team's opponent and the
-- official final score from games.csv. This is the spine of the team-game
-- table: exactly 2 rows per eligible game, by construction.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW game_participants AS
SELECT g.game_id, g.game_slug, g.week, g.game_type, g.is_playoff, g.start_date_utc,
       g.home_team_id AS team_id, g.away_team_id AS opponent_team_id,
       TRUE           AS is_home,
       g.home_score   AS team_score_official,
       g.away_score   AS opponent_score_official
FROM eligible_games g
UNION ALL
SELECT g.game_id, g.game_slug, g.week, g.game_type, g.is_playoff, g.start_date_utc,
       g.away_team_id, g.home_team_id,
       FALSE,
       g.away_score,
       g.home_score
FROM eligible_games g;


-- ---------------------------------------------------------------------------
-- Analysis-eligible events restricted to eligible games, with the two derived
-- scoring quantities Phase 5 needs everywhere:
--   points_scored -- PLL scoring: a two-point goal is 1 goal worth 2 points.
--   is_shot_on_goal -- the shot_outcome classes Phase 3 defined as on-goal.
-- Verified against the official box score: summing shots / shots_on_goal /
-- goals / two-point shots / two-point goals from this view reproduces
-- team_game_stats exactly in all 100 team-games (see TEAM_ADVANCED_METRICS.md
-- "Source selection").
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW eligible_events AS
SELECT e.*
FROM events_raw e
JOIN eligible_games g USING (game_id)
WHERE e.is_analysis_eligible_event;

CREATE OR REPLACE VIEW eligible_shots AS
SELECT
    game_id,
    game_slug,
    team_id,
    event_id,
    shot_type,
    shot_outcome,
    is_valid_goal,
    COALESCE(is_two_point_attempt, FALSE) AS is_two_point_attempt,
    COALESCE(is_man_up_shot,       FALSE) AS is_man_up_shot,
    shot_outcome IN ('goal', 'saved', 'on_goal_no_save') AS is_shot_on_goal,
    CASE WHEN is_valid_goal AND COALESCE(is_two_point_attempt, FALSE) THEN 2
         WHEN is_valid_goal                                          THEN 1
         ELSE 0 END AS points_scored
FROM eligible_events
WHERE event_type IN ('shot', 'goal')
  AND shot_outcome IS NOT NULL;


-- ---------------------------------------------------------------------------
-- Possessions, restricted to eligible games (they already are, by Phase 4
-- construction -- the join is a guard, not a filter) and tagged with the
-- confidence subsets the sensitivity analysis needs.
--
-- is_measurable_span: the possession's duration_seconds is a span between two
-- DISTINCT logged events, is not truncated by a period/game boundary, and the
-- possession's own boundaries are unambiguous. Possessions failing this are
-- not "bad" -- they are simply not duration measurements (871 season-wide are
-- opened and closed by the same single event, so their span is 0 by
-- construction). See TEAM_ADVANCED_METRICS.md "Possession length".
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW possessions AS
SELECT p.*,
       NOT p.is_ambiguous                                     AS is_unambiguous,
       (NOT p.is_ambiguous AND NOT p.is_truncated)             AS is_high_confidence,
       (NOT p.is_ambiguous AND NOT p.is_truncated
            AND p.start_event_id <> p.end_event_id)                            AS is_measurable_span,
       CASE WHEN p.end_reason = 'turnover' THEN 1 ELSE 0 END   AS ended_in_turnover,
       CASE WHEN p.end_reason = 'goal'     THEN 1 ELSE 0 END   AS ended_in_goal,
       CASE WHEN p.start_reason = 'faceoff_win' THEN 1 ELSE 0 END AS started_on_faceoff
FROM possessions_raw p
JOIN eligible_games g USING (game_id);


-- ---------------------------------------------------------------------------
-- Uncertainty propagation.
--
-- Two independent kinds of evidence are carried onto every team-game row:
--
-- (a) game_validation_flags -- the GAME-level status from validation_report.csv
--     for the 5 metrics Phase 4.25 left with unresolved residuals. This is the
--     evidence the validation table actually provides, at the grain it
--     provides it (per game, not per team).
--
-- (b) team_stat_residuals -- a TEAM-level residual computed here by comparing
--     the play-by-play event count against that team's own official box-score
--     value. validation_report.csv only reports whole-game totals, so this
--     recovers which of the two teams in an affected game actually carries the
--     discrepancy. Nothing is corrected: the residual is reported alongside
--     both source values so a consumer can see exactly what the disagreement
--     is.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW game_validation_flags AS
SELECT
    g.game_id,
    MAX(CASE WHEN v.metric = 'turnovers'              THEN v.final_status END) AS turnover_validation_status,
    MAX(CASE WHEN v.metric = 'ground_balls'           THEN v.final_status END) AS ground_ball_validation_status,
    MAX(CASE WHEN v.metric = 'shot_clock_expirations' THEN v.final_status END) AS shot_clock_validation_status,
    MAX(CASE WHEN v.metric = 'saves'                  THEN v.final_status END) AS save_validation_status,
    MAX(CASE WHEN v.metric = 'penalties'              THEN v.final_status END) AS penalty_validation_status
FROM eligible_games g
LEFT JOIN validation_raw v ON v.game_slug = g.game_slug
GROUP BY g.game_id;

CREATE OR REPLACE VIEW team_pbp_counts AS
SELECT
    game_id,
    team_id,
    COUNT(*) FILTER (WHERE event_type = 'turnover')         AS turnovers_pbp,
    COUNT(*) FILTER (WHERE event_type = 'groundball')       AS ground_balls_pbp,
    COUNT(*) FILTER (WHERE event_type = 'shotclockexpired') AS shot_clock_expirations_pbp,
    COUNT(*) FILTER (WHERE event_type = 'faceoff')          AS faceoff_wins_pbp,
    COUNT(*) FILTER (WHERE event_type = 'penalty' AND is_valid_penalty) AS penalties_pbp
FROM eligible_events
WHERE team_id IS NOT NULL
GROUP BY game_id, team_id;

-- Saves are credited to the DEFENDING team, so a team's saves come from the
-- opponent's saved shots. Computed as (all saved shots in the game) minus
-- (this team's own saved shots) rather than by a self-join on opponent id.
CREATE OR REPLACE VIEW team_saves_pbp AS
SELECT
    p.game_id,
    p.team_id,
    COALESCE(SUM(CASE WHEN s.team_id = p.opponent_team_id THEN 1 ELSE 0 END), 0) AS saves_pbp
FROM game_participants p
LEFT JOIN eligible_shots s
       ON s.game_id = p.game_id
      AND s.shot_outcome = 'saved'
GROUP BY p.game_id, p.team_id;
