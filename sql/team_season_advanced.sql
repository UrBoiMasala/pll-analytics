-- Phase 5: team-season advanced metrics.
--
-- One row per team over the 2026 league-analytics-eligible season (8 teams;
-- the all-star squads never appear because team_game_advanced is built from
-- eligible_games, which excludes the all-star game).
--
-- Every rate is recomputed from SEASON TOTALS -- sum(numerator) over
-- sum(denominator) -- never as the mean of the per-game rates. Those two are
-- not the same number when games have different possession counts, and the
-- totals-based version is the one that answers "how efficient was this team
-- this season". Validation check 6 asserts that the season COUNT columns are
-- exactly the sum of their team-game counterparts.

CREATE OR REPLACE TABLE team_season_advanced AS

WITH totals AS (
    SELECT
        team_id,
        ANY_VALUE(team_name)                          AS team_name,
        COUNT(*)                                      AS games_played,
        SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) AS losses,
        SUM(CASE WHEN result = 'T' THEN 1 ELSE 0 END) AS ties,
        SUM(is_playoff::INTEGER)                      AS playoff_games,

        SUM(offensive_possessions)  AS offensive_possessions,
        SUM(defensive_possessions)  AS defensive_possessions,
        SUM(total_game_possessions) AS total_game_possessions,
        SUM(points_scored)          AS points_scored,
        SUM(points_allowed)         AS points_allowed,
        SUM(team_score_official)    AS points_scored_official,
        SUM(opponent_score_official) AS points_allowed_official,

        SUM(shots)          AS shots,
        SUM(shots_on_goal)  AS shots_on_goal,
        SUM(goals)          AS goals,
        SUM(points)         AS points,

        SUM(two_point_attempts)                 AS two_point_attempts,
        SUM(two_point_shots_on_goal)            AS two_point_shots_on_goal,
        SUM(two_point_goals)                    AS two_point_goals,
        SUM(two_point_points)                   AS two_point_points,
        SUM(one_point_attempts)                 AS one_point_attempts,
        SUM(one_point_goals)                    AS one_point_goals,
        SUM(one_point_points)                   AS one_point_points,
        SUM(possessions_with_two_point_attempt) AS possessions_with_two_point_attempt,

        SUM(turnovers)                   AS turnovers,
        SUM(turnovers_pbp)               AS turnovers_pbp,
        SUM(possession_ending_turnovers) AS possession_ending_turnovers,
        SUM(caused_turnovers_official)   AS caused_turnovers_official,
        SUM(turnovers_forced)            AS turnovers_forced,

        SUM(faceoffs)                  AS faceoffs,
        SUM(faceoff_wins)              AS faceoff_wins,
        SUM(faceoff_losses)            AS faceoff_losses,
        SUM(faceoff_start_possessions) AS faceoff_start_possessions,

        SUM(man_up_opportunities)   AS man_up_opportunities,
        SUM(man_up_shots)           AS man_up_shots,
        SUM(man_up_goals)           AS man_up_goals,
        SUM(man_up_goals_pbp)       AS man_up_goals_pbp,
        SUM(man_up_points)          AS man_up_points,
        SUM(man_down_opportunities)   AS man_down_opportunities,
        SUM(man_down_goals_allowed)   AS man_down_goals_allowed,

        SUM(ground_balls)     AS ground_balls,
        SUM(ground_balls_pbp) AS ground_balls_pbp,

        SUM(shots_allowed)                    AS shots_allowed,
        SUM(shots_on_goal_allowed)            AS shots_on_goal_allowed,
        SUM(goals_allowed)                    AS goals_allowed,
        SUM(two_point_goals_allowed) AS two_point_goals_allowed,
        SUM(two_point_attempts_allowed)       AS two_point_attempts_allowed,
        SUM(saves)                            AS saves,

        SUM(penalties)                      AS penalties,
        SUM(penalty_minutes)                AS penalty_minutes,
        SUM(shot_clock_expirations)         AS shot_clock_expirations,
        SUM(clears)                         AS clears,
        SUM(clear_attempts)                 AS clear_attempts,
        SUM(ride_attempts)                  AS ride_attempts,

        SUM(observed_possession_seconds)             AS observed_possession_seconds,
        SUM(complete_possession_seconds)             AS complete_possession_seconds,
        SUM(truncated_possessions)                   AS truncated_possessions,
        SUM(complete_possessions)                    AS complete_possessions,
        SUM(measurable_span_possessions)             AS measurable_span_possessions,
        SUM(time_of_possession_official_seconds)     AS time_of_possession_official_seconds,

        SUM(ambiguous_offensive_possessions) AS ambiguous_offensive_possessions,
        SUM(ambiguous_defensive_possessions) AS ambiguous_defensive_possessions,

        SUM(has_unresolved_validation_issue::INTEGER)   AS games_with_unresolved_validation_issue,
        SUM(has_turnover_validation_issue::INTEGER)     AS games_with_turnover_validation_issue,
        SUM(has_ground_ball_validation_issue::INTEGER)  AS games_with_ground_ball_validation_issue,
        SUM(has_shot_clock_validation_issue::INTEGER)   AS games_with_shot_clock_validation_issue,
        SUM(has_save_validation_issue::INTEGER)         AS games_with_save_validation_issue,
        SUM(has_penalty_validation_issue::INTEGER)      AS games_with_penalty_validation_issue,
        SUM(turnovers_pbp_minus_official)               AS turnovers_pbp_minus_official,
        SUM(ground_balls_pbp_minus_official)            AS ground_balls_pbp_minus_official,
        SUM(faceoff_wins_pbp_minus_official)            AS faceoff_wins_pbp_minus_official,
        SUM(saves_pbp_minus_official)                   AS saves_pbp_minus_official,
        SUM(shot_clock_expirations_pbp_minus_official)  AS shot_clock_expirations_pbp_minus_official
    FROM team_game_advanced
    GROUP BY team_id
),

-- Span statistics have to come from the possession rows themselves: a season
-- median is not the mean of 12-13 per-game medians.
span_stats AS (
    SELECT
        offense_team_id AS team_id,
        AVG(duration_seconds)    FILTER (WHERE NOT is_truncated)   AS mean_complete_possession_duration,
        MEDIAN(duration_seconds) FILTER (WHERE NOT is_truncated)   AS median_complete_possession_duration,
        AVG(duration_seconds)    FILTER (WHERE is_measurable_span) AS mean_measurable_span_seconds,
        MEDIAN(duration_seconds) FILTER (WHERE is_measurable_span) AS median_measurable_span_seconds
    FROM possessions
    GROUP BY offense_team_id
)

SELECT
    t.team_id,
    t.team_name,
    t.games_played, t.wins, t.losses, t.ties, t.playoff_games,

    -- ---- core possession metrics ---------------------------------------
    t.offensive_possessions, t.defensive_possessions, t.total_game_possessions,
    t.points_scored, t.points_allowed,
    t.points_scored  / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS points_per_possession,
    t.points_allowed / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0) AS points_allowed_per_possession,
    t.points_scored  / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS offensive_efficiency,
    t.points_allowed / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0) AS defensive_efficiency,
      t.points_scored  / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0)
    - t.points_allowed / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0) AS net_efficiency,
    100 * t.points_scored  / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS offensive_efficiency_per_100,
    100 * t.points_allowed / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0) AS defensive_efficiency_per_100,
    100 * (  t.points_scored  / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0)
           - t.points_allowed / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0)) AS net_efficiency_per_100,

    -- ---- pace (possession-count based; NOT duration based) -------------
    t.offensive_possessions / NULLIF(CAST(t.games_played AS DOUBLE), 0)  AS team_possessions_per_game,
    t.total_game_possessions / NULLIF(CAST(t.games_played AS DOUBLE), 0) AS combined_possessions_per_game,

    -- ---- shooting -------------------------------------------------------
    t.shots, t.shots_on_goal, t.goals, t.points,
    t.goals         / NULLIF(CAST(t.shots AS DOUBLE), 0)         AS shooting_pct,
    t.shots_on_goal / NULLIF(CAST(t.shots AS DOUBLE), 0)         AS shots_on_goal_pct,
    t.goals         / NULLIF(CAST(t.shots_on_goal AS DOUBLE), 0) AS goals_per_shot_on_goal,
    t.points        / NULLIF(CAST(t.shots AS DOUBLE), 0)         AS points_per_shot,
    t.goals         / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS goals_per_possession,
    t.shots         / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS shots_per_possession,
    t.shots_on_goal / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS shots_on_goal_per_possession,

    -- ---- PLL two-point --------------------------------------------------
    t.two_point_attempts, t.two_point_shots_on_goal, t.two_point_goals, t.two_point_points,
    t.one_point_attempts, t.one_point_goals, t.one_point_points,
    t.two_point_attempts / NULLIF(CAST(t.shots AS DOUBLE), 0)                 AS two_point_attempt_rate,
    t.two_point_goals    / NULLIF(CAST(t.two_point_attempts AS DOUBLE), 0)    AS two_point_conversion_pct,
    t.one_point_goals    / NULLIF(CAST(t.one_point_attempts AS DOUBLE), 0)    AS one_point_conversion_pct,
    t.two_point_points   / NULLIF(CAST(t.points AS DOUBLE), 0)                AS two_point_points_share,
    t.two_point_points   / NULLIF(CAST(t.two_point_attempts AS DOUBLE), 0)    AS points_per_two_point_attempt,
    t.possessions_with_two_point_attempt,
    t.possessions_with_two_point_attempt / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS two_point_possession_rate,

    -- ---- turnovers ------------------------------------------------------
    t.turnovers, t.turnovers_pbp, t.possession_ending_turnovers,
    t.caused_turnovers_official, t.turnovers_forced,
    t.turnovers / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS turnovers_per_possession,
    t.turnovers / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS turnover_rate,
    t.possession_ending_turnovers / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS possession_ending_turnover_rate,
    t.turnovers_forced / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0) AS turnovers_forced_per_defensive_possession,

    -- ---- faceoffs -------------------------------------------------------
    t.faceoffs, t.faceoff_wins, t.faceoff_losses,
    t.faceoff_wins / NULLIF(CAST(t.faceoffs AS DOUBLE), 0) AS faceoff_win_pct,
    t.faceoff_start_possessions,
    t.faceoff_start_possessions / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS faceoff_start_possession_share,

    -- ---- man-up (opportunity-denominated; see TEAM_ADVANCED_METRICS.md) --
    t.man_up_opportunities, t.man_up_shots, t.man_up_goals, t.man_up_goals_pbp, t.man_up_points,
    t.man_up_goals  / NULLIF(CAST(t.man_up_shots AS DOUBLE), 0)         AS man_up_shooting_pct,
    t.man_up_goals  / NULLIF(CAST(t.man_up_opportunities AS DOUBLE), 0) AS man_up_goals_per_opportunity,
    t.man_up_points / NULLIF(CAST(t.man_up_opportunities AS DOUBLE), 0) AS man_up_points_per_opportunity,
    t.man_up_shots  / NULLIF(CAST(t.man_up_opportunities AS DOUBLE), 0) AS man_up_shots_per_opportunity,
    t.man_down_opportunities, t.man_down_goals_allowed,
    t.man_down_goals_allowed / NULLIF(CAST(t.man_down_opportunities AS DOUBLE), 0) AS man_down_goals_allowed_per_opportunity,

    -- ---- ground balls ---------------------------------------------------
    t.ground_balls, t.ground_balls_pbp,
    t.ground_balls / NULLIF(CAST(t.total_game_possessions AS DOUBLE), 0) AS ground_balls_per_possession,

    -- ---- team goalkeeping ----------------------------------------------
    t.shots_allowed, t.shots_on_goal_allowed, t.goals_allowed,
    t.two_point_goals_allowed, t.two_point_attempts_allowed, t.saves,
    t.saves / NULLIF(CAST(t.saves + t.goals_allowed AS DOUBLE), 0)      AS save_pct_official,
    t.saves / NULLIF(CAST(t.shots_on_goal_allowed AS DOUBLE), 0)        AS save_pct_vs_shots_on_goal,
    t.goals_allowed / NULLIF(CAST(t.shots_on_goal_allowed AS DOUBLE), 0) AS opponent_shooting_pct_on_goal,
    t.goals_allowed / NULLIF(CAST(t.shots_allowed AS DOUBLE), 0)        AS opponent_shooting_pct,
    t.shots_allowed / NULLIF(CAST(t.defensive_possessions AS DOUBLE), 0) AS shots_allowed_per_possession,

    -- ---- penalties / shot clock / clearing ------------------------------
    t.penalties, t.penalty_minutes, t.shot_clock_expirations,
    t.shot_clock_expirations / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS shot_clock_expiration_rate,
    t.clears, t.clear_attempts, t.ride_attempts,

    -- ---- possession span / official time of possession ------------------
    t.observed_possession_seconds, t.complete_possession_seconds,
    t.truncated_possessions, t.complete_possessions, t.measurable_span_possessions,
    s.mean_complete_possession_duration,
    s.median_complete_possession_duration,
    s.mean_measurable_span_seconds,
    s.median_measurable_span_seconds,
    t.time_of_possession_official_seconds,
    t.time_of_possession_official_seconds / NULLIF(CAST(t.games_played AS DOUBLE), 0) AS time_of_possession_official_seconds_per_game,
    t.observed_possession_seconds / NULLIF(CAST(t.time_of_possession_official_seconds AS DOUBLE), 0) AS possession_span_coverage_ratio,

    -- ---- uncertainty ----------------------------------------------------
    t.ambiguous_offensive_possessions, t.ambiguous_defensive_possessions,
    t.ambiguous_offensive_possessions / NULLIF(CAST(t.offensive_possessions AS DOUBLE), 0) AS ambiguous_offensive_possession_share,
    t.games_with_unresolved_validation_issue,
    t.games_with_turnover_validation_issue,
    t.games_with_ground_ball_validation_issue,
    t.games_with_shot_clock_validation_issue,
    t.games_with_save_validation_issue,
    t.games_with_penalty_validation_issue,
    t.turnovers_pbp_minus_official,
    t.ground_balls_pbp_minus_official,
    t.faceoff_wins_pbp_minus_official,
    t.saves_pbp_minus_official,
    t.shot_clock_expirations_pbp_minus_official
FROM totals t
JOIN span_stats s USING (team_id)
ORDER BY t.team_id;
