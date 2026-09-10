-- Phase 8: the canonical 2026 team statistical table.
--
-- One row per team. This is the PUBLICATION view of Phase 5: every column here
-- either comes straight out of team_season_advanced.csv (Phase 5's validated
-- output, unmodified) or is arithmetic that is new at the season-publication
-- level and registered in the Phase 8 metric catalog.
--
-- What Phase 8 adds, and why each addition is not a re-derivation:
--   * record context      win_pct, point_differential, per-game scoring rates.
--                         Phase 5 emitted totals; a per-game figure needs the
--                         games denominator and Phase 5 did not publish one.
--   * possession context  possessions_per_game already exists as
--                         team_possessions_per_game and is carried under that
--                         name; possession_differential is new.
--   * two-point economics points_per_one_point_attempt, and the difference
--                         against points_per_two_point_attempt. This is the
--                         PLL-specific comparison Phase 5 documented in prose
--                         but never emitted as a column.
--
-- Deliberately NOT carried into the published table (all remain available in
-- team_season_advanced.csv, and are catalogued as DIAGNOSTIC or UNSUPPORTED):
--   * observed_possession_seconds / complete_possession_seconds / the mean and
--     median span columns -- possession SPAN is not time of possession
--     (Phase 5: r=0.58 vs official, 0.54-1.00 coverage). The official ToP
--     figure and the coverage ratio are carried so the gap stays visible.
--   * every *_pbp column and every *_pbp_minus_official residual -- these are
--     source-disagreement diagnostics, not statistics about a team.
--   * man_up_possessions -- never existed; PLL's man-up tag is on goals only.

CREATE OR REPLACE TABLE team_stats_2026 AS
SELECT
    -- ---------- identity ----------
    s.team_id,
    s.team_name,

    -- ---------- record / scoring context ----------
    s.games_played,
    s.wins,
    s.losses,
    s.ties,
    s.playoff_games,
    CAST(s.wins AS DOUBLE) / NULLIF(s.games_played, 0)              AS win_pct,
    s.points_scored,
    s.points_allowed,
    s.points_scored - s.points_allowed                              AS point_differential,
    s.points_scored  / NULLIF(s.games_played, 0)                    AS points_per_game,
    s.points_allowed / NULLIF(s.games_played, 0)                    AS points_allowed_per_game,
    (s.points_scored - s.points_allowed) / NULLIF(s.games_played, 0) AS point_differential_per_game,

    -- ---------- possession ----------
    s.offensive_possessions,
    s.defensive_possessions,
    s.offensive_possessions - s.defensive_possessions               AS possession_differential,
    s.total_game_possessions,
    s.team_possessions_per_game,
    s.combined_possessions_per_game,
    s.faceoff_start_possessions,
    s.faceoff_start_possession_share,

    -- ---------- efficiency ----------
    s.offensive_efficiency,
    s.defensive_efficiency,
    s.net_efficiency,
    s.offensive_efficiency_per_100,
    s.defensive_efficiency_per_100,
    s.net_efficiency_per_100,
    s.goals_per_possession,
    s.shots_per_possession,
    s.shots_on_goal_per_possession,
    s.turnovers_per_possession,
    s.turnover_rate,
    s.possession_ending_turnover_rate,

    -- ---------- shooting ----------
    s.shots,
    s.shots_on_goal,
    s.goals,
    s.points,
    s.shooting_pct,
    s.shots_on_goal_pct,
    s.goals_per_shot_on_goal,
    s.points_per_shot,

    -- ---------- two-point (PLL-specific) ----------
    s.one_point_attempts,
    s.one_point_goals,
    s.one_point_points,
    s.one_point_conversion_pct,
    s.two_point_attempts,
    s.two_point_shots_on_goal,
    s.two_point_goals,
    s.two_point_points,
    s.two_point_conversion_pct,
    s.two_point_attempt_rate,
    s.two_point_points_share,
    s.points_per_two_point_attempt,
    s.two_point_possession_rate,
    -- Points per one-point attempt. Numerically identical to
    -- one_point_conversion_pct because a one-point goal is worth exactly one
    -- point; it is emitted under its own name so the two-point comparison below
    -- is stated in matching units rather than requiring the reader to know they
    -- coincide. Catalogued as ALGEBRAICALLY REDUNDANT with an explicit alias.
    CAST(s.one_point_points AS DOUBLE) / NULLIF(s.one_point_attempts, 0)
                                                                    AS points_per_one_point_attempt,
    s.points_per_two_point_attempt
        - CAST(s.one_point_points AS DOUBLE) / NULLIF(s.one_point_attempts, 0)
                                                                    AS two_point_minus_one_point_return,

    -- ---------- faceoff ----------
    s.faceoffs,
    s.faceoff_wins,
    s.faceoff_losses,
    s.faceoff_win_pct,

    -- ---------- turnovers / ground balls ----------
    s.turnovers,
    s.possession_ending_turnovers,
    s.turnovers_forced,
    s.turnovers_forced_per_defensive_possession,
    s.caused_turnovers_official,
    s.ground_balls,
    s.ground_balls_per_possession,

    -- ---------- goalkeeping / defence ----------
    s.shots_allowed,
    s.shots_on_goal_allowed,
    s.goals_allowed,
    s.two_point_goals_allowed,
    s.two_point_attempts_allowed,
    s.saves,
    s.save_pct_official,
    s.save_pct_vs_shots_on_goal,
    s.opponent_shooting_pct,
    s.opponent_shooting_pct_on_goal,
    s.shots_allowed_per_possession,

    -- ---------- discipline / shot clock ----------
    s.penalties,
    s.penalty_minutes,
    s.shot_clock_expirations,
    s.shot_clock_expiration_rate,

    -- ---------- extra man (opportunity-denominated only) ----------
    s.man_up_opportunities,
    s.man_up_shots,
    s.man_up_goals,
    s.man_up_points,
    s.man_up_shooting_pct,
    s.man_up_goals_per_opportunity,
    s.man_up_points_per_opportunity,
    s.man_up_shots_per_opportunity,
    s.man_down_opportunities,
    s.man_down_goals_allowed,
    s.man_down_goals_allowed_per_opportunity,

    -- ---------- clearing / riding: raw counts only, no efficiency ----------
    s.clears,
    s.clear_attempts,
    s.ride_attempts,

    -- ---------- time of possession: OFFICIAL only ----------
    s.time_of_possession_official_seconds,
    s.time_of_possession_official_seconds_per_game,
    s.possession_span_coverage_ratio,

    -- ---------- uncertainty carried onto every row ----------
    s.ambiguous_offensive_possessions,
    s.ambiguous_offensive_possession_share,
    s.truncated_possessions,
    s.complete_possessions,
    s.measurable_span_possessions,
    s.games_with_unresolved_validation_issue
FROM p8_team_season s
ORDER BY s.team_id;
