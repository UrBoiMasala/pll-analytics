-- Phase 8: the canonical 2026 player statistical table.
--
-- One row per player (228). Two blocks, kept in this order and never mixed:
--
--   BLOCK A -- DESCRIPTIVE PRODUCTION. Counting stats and simple rates from the
--   official box score, plus the event-derived goalie shot split Phase 6
--   reconciled. Everything here answers "what is on the stat sheet". Appearing
--   in this block confers NO value: assists, ground balls and penalties are
--   carried because they are needed to interpret the advanced block, and are
--   explicitly unvalued in the Phase 6 accounting.
--
--   BLOCK B -- ADVANCED VALUE. Phase 6 components and Phase 7 usage /
--   reliability / normalization, selected unchanged. Phase 8 recomputes none of
--   it; a validation check asserts byte-identity of the Phase 6/7 source files
--   and an independent check re-adds the components to EPA_points_raw.
--
-- The only genuinely new columns are the two flagged NEW below, both of which
-- are rates whose numerator and denominator already exist but whose ratio was
-- never emitted at player level.

CREATE OR REPLACE TABLE player_stats_2026 AS
SELECT
    -- =====================================================================
    -- IDENTITY AND ROLE
    -- =====================================================================
    o.player_id,
    o.player_name,
    a.team_id,
    a.n_teams,
    a.raw_position                                AS roster_position_code,
    a.canonical_position,
    a.position_group,
    a.value_role,
    c.baseline_group,
    o.games_played,

    -- =====================================================================
    -- BLOCK A -- DESCRIPTIVE PRODUCTION (official box score)
    -- =====================================================================
    -- scoring
    o.goals,
    o.one_point_goals,
    o.two_point_goals,
    o.pll_points                                  AS scoring_points,
    o.official_assists,

    -- shooting
    o.shots,
    o.shots_on_goal,
    o.one_point_attempts,
    o.two_point_attempts,
    o.shooting_pct,
    -- NEW: share of a player's attempts that reached the cage. Numerator and
    -- denominator are both Phase 6 columns; the ratio is new at player level.
    CAST(o.shots_on_goal AS DOUBLE) / NULLIF(o.shots, 0)   AS shots_on_goal_pct,
    o.one_point_pct                               AS one_point_conversion_pct,
    o.two_point_pct                               AS two_point_conversion_pct,
    o.points_per_shot,

    -- possession security
    o.turnovers,
    o.touches,
    o.turnovers_per_touch,
    o.caused_turnovers,
    o.ground_balls,
    o.penalties,

    -- faceoff
    o.faceoffs,
    o.faceoff_wins,
    o.faceoff_losses,
    o.faceoff_win_pct,

    -- goalkeeping
    o.saves,
    o.goals_allowed,
    o.two_point_goals_allowed,
    o.pll_points_allowed,
    o.shots_on_goal_faced,
    o.one_point_shots_on_goal_faced,
    o.two_point_shots_on_goal_faced,
    o.save_pct,
    -- NEW: PLL points conceded per shot on goal faced. The goalie analogue of
    -- points_per_shot, and the denominator goalie_value is actually built on.
    CAST(o.pll_points_allowed AS DOUBLE) / NULLIF(o.shots_on_goal_faced, 0)
                                                  AS points_allowed_per_sog_faced,

    -- usage volume
    a.recorded_offensive_opportunities,
    a.offensive_opportunities_per_game,
    a.offensive_play_share,
    a.offensive_play_share_season,
    a.shot_share,
    a.touch_share,
    a.faceoff_team_share,
    a.caused_turnover_team_share,
    a.event_log_play_shares,
    a.event_log_play_share,

    -- =====================================================================
    -- BLOCK B -- ADVANCED VALUE (Phase 6 raw, Phase 7 adjusted; unchanged)
    -- =====================================================================
    -- component values, raw
    a.shooting_value_raw,
    a.shooting_value_one_point_raw,
    a.shooting_value_two_point_raw,
    a.turnover_value_raw,
    a.faceoff_value_raw,
    a.goalie_value_raw,
    a.defensive_value_partial_raw,
    a.offensive_EPA_points_raw,
    a.EPA_points_raw,
    a.components_supported,
    c.ground_ball_value_status,
    c.assist_value_status,
    a.defensive_value_scope,

    -- efficiency
    a.EPA_per_recorded_opportunity,
    a.shooting_EPA_per_shot,
    a.faceoff_EPA_per_faceoff,
    a.goalie_EPA_per_SOG,
    a.defensive_EPA_partial_per_game,
    a.EPA_points_per_game,

    -- usage-relative
    a.expected_EPA_given_usage,
    a.EPA_vs_usage_expectation,
    a.EPA_vs_usage_expectation_z,

    -- chance-relative (the one class-A standardization)
    a.EPA_points_null_sd,
    a.EPA_points_null_z,
    a.shooting_value_null_z,
    a.faceoff_value_null_z,
    a.goalie_value_null_z,

    -- raw vs shrunk rates, side by side, never substituted
    a.shooting_rate_raw,
    a.shooting_rate_shrunk,
    a.one_point_rate_raw,
    a.one_point_rate_shrunk,
    a.two_point_rate_raw,
    a.two_point_rate_shrunk,
    a.faceoff_rate_raw,
    a.faceoff_rate_shrunk,
    a.save_rate_raw,
    a.save_rate_shrunk,

    -- reliability
    a.shooting_reliability,
    a.one_point_reliability,
    a.two_point_reliability,
    a.faceoff_reliability,
    a.save_reliability,
    a.shooting_posterior_ci_width,
    a.faceoff_posterior_ci_width,
    a.save_posterior_ci_width,
    a.role_rate_name,
    a.role_rate_reliability,

    -- within-position standardization
    a.position_n_players,
    a.position_EPA_mean,
    a.position_EPA_sd,
    a.EPA_position_percentile,
    a.EPA_position_robust_z,
    a.EPA_position_z,
    a.usage_position_percentile,
    a.efficiency_position_percentile,

    -- value decomposition shares (absolute magnitudes -- signed shares are
    -- uninterpretable, see Phase 7 s14)
    a.faceoff_share_of_absolute_value,
    a.offensive_share_of_absolute_value,
    a.defensive_partial_share_of_absolute_value,

    -- eligibility and caveat flags
    a.descriptive_eligible,
    a.rate_ranking_eligible,
    a.offensive_rate_ranking_eligible,
    a.reliability_adjusted_eligible,
    a.future_award_input_eligible,
    a.small_sample,
    a.chance_variation_exceeds_peer_spread,
    a.defense_partial,
    a.usage_proxy_only,
    a.unsupported_components,
    a.role_interpretation_caveat,
    a.mapping_reason
FROM p8_opps o
JOIN p8_adjusted  a USING (player_id)
JOIN p8_components c USING (player_id)
ORDER BY o.player_id;
