-- Phase 7: the analytic core -- one row per player, every quantity Phase 7
-- normalizes, standardizes or ranks, assembled in one place.
--
-- STRICT SEPARATION OF THE FOUR DIMENSIONS (Phase 7 brief section 4). They are
-- named apart and never blended:
--
--   VOLUME      recorded_offensive_opportunities, shots, faceoffs,
--               shots_on_goal_faced, games_played
--   USAGE       offensive_play_share and the alternative shares
--   TOTAL VALUE the Phase 6 EPA_points components, taken from disk unchanged
--   EFFICIENCY  EPA per opportunity of the matching class
--
-- No column here is a weighted combination of two of them, and none is a
-- composite of any kind. A high-usage player gets a high usage number and
-- nothing else; whether that usage produced value is a separate column.
--
-- RAW VALUE IS PHASE 6'S, BYTE FOR BYTE. Every `*_raw` value column below is
-- selected straight out of player_value_components.csv. Nothing is recomputed,
-- rescaled or re-baselined, so `EPA_points_raw` reconciles to Phase 6 exactly
-- (validation checks 8 and 9).

CREATE OR REPLACE TABLE player_adjusted_core AS

WITH nulls AS (
    SELECT * FROM read_csv_auto('{scratch_dir}/player_null_variance.csv',
                                types={'player_id': 'VARCHAR'})
),
usage_fit AS (
    SELECT * FROM read_csv_auto('{scratch_dir}/player_usage_expectation.csv',
                                types={'player_id': 'VARCHAR'})
),
rel AS (
    -- one column per rate, pivoted out of the long reliability table
    SELECT
        player_id,
        MAX(rate_raw)            FILTER (WHERE rate_name = 'shooting_pct')    AS shooting_rate_raw,
        MAX(rate_shrunk)         FILTER (WHERE rate_name = 'shooting_pct')    AS shooting_rate_shrunk,
        MAX(reliability)         FILTER (WHERE rate_name = 'shooting_pct')    AS shooting_reliability,
        MAX(posterior_ci_width)  FILTER (WHERE rate_name = 'shooting_pct')    AS shooting_posterior_ci_width,
        MAX(rate_raw)            FILTER (WHERE rate_name = 'one_point_pct')   AS one_point_rate_raw,
        MAX(rate_shrunk)         FILTER (WHERE rate_name = 'one_point_pct')   AS one_point_rate_shrunk,
        MAX(reliability)         FILTER (WHERE rate_name = 'one_point_pct')   AS one_point_reliability,
        MAX(rate_raw)            FILTER (WHERE rate_name = 'two_point_pct')   AS two_point_rate_raw,
        MAX(rate_shrunk)         FILTER (WHERE rate_name = 'two_point_pct')   AS two_point_rate_shrunk,
        MAX(reliability)         FILTER (WHERE rate_name = 'two_point_pct')   AS two_point_reliability,
        MAX(rate_raw)            FILTER (WHERE rate_name = 'faceoff_win_pct') AS faceoff_rate_raw,
        MAX(rate_shrunk)         FILTER (WHERE rate_name = 'faceoff_win_pct') AS faceoff_rate_shrunk,
        MAX(reliability)         FILTER (WHERE rate_name = 'faceoff_win_pct') AS faceoff_reliability,
        MAX(posterior_ci_width)  FILTER (WHERE rate_name = 'faceoff_win_pct') AS faceoff_posterior_ci_width,
        MAX(rate_raw)            FILTER (WHERE rate_name = 'save_pct')        AS save_rate_raw,
        MAX(rate_shrunk)         FILTER (WHERE rate_name = 'save_pct')        AS save_rate_shrunk,
        MAX(reliability)         FILTER (WHERE rate_name = 'save_pct')        AS save_reliability,
        MAX(posterior_ci_width)  FILTER (WHERE rate_name = 'save_pct')        AS save_posterior_ci_width
    FROM read_csv_auto('{scratch_dir}/player_rate_reliability.csv',
                       types={'player_id': 'VARCHAR'})
    GROUP BY player_id
)

SELECT
    -- ------------------------------------------------------------ IDENTITY
    c.player_id,
    c.player_name,
    c.team_id,
    c.n_teams,
    m.raw_position,
    m.canonical_position,
    m.position_group,
    m.phase6_baseline_group,
    m.value_role,
    m.mapping_reason,
    m.mapping_confidence,
    c.games_played,

    -- -------------------------------------------------------------- VOLUME
    u.recorded_offensive_opportunities,
    u.team_recorded_offensive_opportunities,
    u.offensive_opportunities_per_game,
    c.shots,
    c.one_point_attempts,
    c.two_point_attempts,
    c.shots_on_goal,
    c.turnovers,
    c.touches,
    c.ground_balls,
    c.official_assists,
    c.caused_turnovers,
    c.faceoffs,
    c.faceoff_wins,
    c.shots_on_goal_faced,
    c.one_point_shots_on_goal_faced,
    c.two_point_shots_on_goal_faced,
    c.saves,
    c.penalties,

    -- --------------------------------------------------------------- USAGE
    u.offensive_play_share,
    u.offensive_play_share_season,
    u.offensive_play_share_with_assists,
    u.shot_share,
    u.touch_share,
    u.faceoff_team_share,
    u.caused_turnover_team_share,
    u.event_log_play_shares,
    u.event_log_play_share,
    c.play_shares                                    AS phase6_play_shares,

    -- ----------------------------------------------- RAW VALUE (Phase 6, unchanged)
    c.shooting_value                                 AS shooting_value_raw,
    c.shooting_value_one_point                       AS shooting_value_one_point_raw,
    c.shooting_value_two_point                       AS shooting_value_two_point_raw,
    c.turnover_value                                 AS turnover_value_raw,
    c.faceoff_value                                  AS faceoff_value_raw,
    c.goalie_value                                   AS goalie_value_raw,
    c.caused_turnover_value                          AS defensive_value_partial_raw,
    c.defensive_value_scope,
    c.total_player_value                             AS EPA_points_raw,
    COALESCE(c.shooting_value, 0) + COALESCE(c.turnover_value, 0)
                                                     AS offensive_EPA_points_raw,
    c.ground_ball_value,
    c.ground_ball_value_status,
    c.assist_value,
    c.assist_value_status,
    c.components_supported,

    -- ---------------------------------------------------------- EFFICIENCY
    -- Every efficiency column divides a component by the opportunity class it
    -- was actually measured over. NULLIF everywhere: an efficiency with no
    -- opportunities is undefined, never zero.
    (COALESCE(c.shooting_value, 0) + COALESCE(c.turnover_value, 0))
      / NULLIF(CAST(u.recorded_offensive_opportunities AS DOUBLE), 0)
                                                     AS EPA_per_recorded_opportunity,
    c.shooting_value_per_shot                        AS shooting_EPA_per_shot,
    c.faceoff_value_per_faceoff                      AS faceoff_EPA_per_faceoff,
    c.goalie_value_per_shot_on_goal_faced            AS goalie_EPA_per_SOG,
    c.caused_turnover_value_per_game                 AS defensive_EPA_partial_per_game,
    c.total_player_value / NULLIF(CAST(c.games_played AS DOUBLE), 0)
                                                     AS EPA_points_per_game,
    -- Lacrosse Reference's uaEGA operation, reproduced exactly on this
    -- project's estimand: total value divided by event-log play shares. Named
    -- so that nobody can mistake it for this project's own usage adjustment.
    c.total_player_value / NULLIF(CAST(u.event_log_play_shares AS DOUBLE), 0)
                                                     AS uaEPA_per_event_log_play_share,

    -- ----------------------------------------- SAMPLING NOISE AT THIS VOLUME
    n.shooting_value_null_sd,
    n.turnover_value_null_sd,
    n.faceoff_value_null_sd,
    n.goalie_value_null_sd,
    n.caused_turnover_value_null_sd,
    SQRT(COALESCE(n.shooting_value_null_variance, 0)
       + COALESCE(n.turnover_value_null_variance, 0)) AS offensive_EPA_null_sd,
    SQRT(COALESCE(n.shooting_value_null_variance, 0)
       + COALESCE(n.turnover_value_null_variance, 0)
       + COALESCE(n.faceoff_value_null_variance, 0)
       + COALESCE(n.goalie_value_null_variance, 0)
       + COALESCE(n.caused_turnover_value_null_variance, 0))
                                                     AS EPA_points_null_sd,

    -- ------------------------------------------------- USAGE EXPECTATION FIT
    f.expected_EPA_given_usage,
    f.EPA_vs_usage_expectation,
    f.usage_model_population,
    f.usage_model_form,

    -- ------------------------------------------- SHRUNK RATES / RELIABILITY
    r.shooting_rate_raw,
    r.shooting_rate_shrunk,
    r.shooting_reliability,
    r.shooting_posterior_ci_width,
    r.one_point_rate_raw,
    r.one_point_rate_shrunk,
    r.one_point_reliability,
    r.two_point_rate_raw,
    r.two_point_rate_shrunk,
    r.two_point_reliability,
    r.faceoff_rate_raw,
    r.faceoff_rate_shrunk,
    r.faceoff_reliability,
    r.faceoff_posterior_ci_width,
    r.save_rate_raw,
    r.save_rate_shrunk,
    r.save_reliability,
    r.save_posterior_ci_width

FROM phase6_components c
JOIN player_position_map m USING (player_id)
JOIN player_usage        u USING (player_id)
LEFT JOIN nulls          n USING (player_id)
LEFT JOIN usage_fit      f USING (player_id)
LEFT JOIN rel            r USING (player_id)
ORDER BY c.player_id;
