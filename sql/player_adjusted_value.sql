-- Phase 7: the assembled player table.
--
-- Adds three things to the core: positional standardization, reliability-based
-- eligibility tiers, and the limitation flags that stop a number being read as
-- something it is not.
--
-- ===========================================================================
-- WHY THERE ARE THREE STANDARDIZED FORMS AND NOT ONE
-- ===========================================================================
--
-- The Phase 7 brief asks for standardization but forbids reaching for an
-- ordinary z-score if the distributions do not support it. They partly do not:
--
--   offensive_field EPA_points_raw    skew +0.75, excess kurtosis +1.7
--   defensive_field shooting_value    excess kurtosis +3.4
--   faceoff / goalie groups           n = 13 and n = 17
--
-- So all three are published and none is presented as the answer:
--
--   *_position_z          ordinary (x - group mean) / group sd. Familiar, and
--                         the right thing when the group is large and roughly
--                         symmetric. Suppressed to NULL when the group has
--                         fewer than 9 players with the metric.
--
--   *_position_robust_z   (x - group median) / (1.4826 x group MAD). The same
--                         scale as an ordinary z under normality, but a single
--                         +8 EPA outlier cannot set the denominator.
--
--   *_position_percentile empirical CDF within the group, ties at their mid-
--                         rank, on 0-100. Makes no distributional assumption
--                         at all and is the form to prefer when the group is
--                         small or skewed. It is also, deliberately, coarse in
--                         a small group -- a 13-player faceoff group has 7.7
--                         percentile points between adjacent players, and that
--                         coarseness is information, not a defect.
--
-- RECOMMENDED READING ORDER, documented rather than enforced: percentile
-- first, robust z second, ordinary z last. The recommendation is in
-- PLAYER_ADJUSTED_VALUE_METHODOLOGY.md; the data are all here either way.
--
-- A FOURTH, DIFFERENT STANDARDIZATION also travels on this table:
-- `EPA_points_null_z` divides a player's value by the sampling spread at his
-- own opportunity volume rather than by the spread of his positional group. It
-- answers a different question -- "is this distinguishable from chance?"
-- instead of "is this unusual among his peers?" -- and it is the only one of
-- the four that is not distorted by a group whose members have wildly
-- different opportunity counts.
--
-- ===========================================================================
-- ELIGIBILITY: FLAGS, NEVER DELETION
-- ===========================================================================
--
-- All 228 players stay in this table. Nobody is dropped for a small sample;
-- they are flagged out of the leaderboards their sample cannot support. The
-- thresholds are derived, not chosen:
--
--   descriptive_eligible        played at least one eligible game. All 228.
--                               What happened, happened.
--
--   rate_ranking_eligible       the player's reliability on the rate that
--                               drives his role's leaderboard is >= 0.5 --
--                               the point at which his own record outweighs
--                               the league prior in the posterior. The trial
--                               count this implies is different for every rate
--                               because each rate's prior strength is
--                               estimated separately: 16 draws, 71 shots, 300
--                               shots on goal.
--
--   reliability_adjusted_eligible  has at least one trial of the relevant
--                               rate, so a shrunk estimate exists at all.
--
--   future_award_input_eligible  Lacrosse Reference's own published cutoff:
--                               at least 1% of the team's play shares. Adopted
--                               because it is documented rather than invented,
--                               and applied to the event-log play share, which
--                               is the measure they define it on.
--
-- These are inputs to a later phase's eligibility decision, not an award
-- ranking. Nothing in this file weights, combines or scores anything.

CREATE OR REPLACE TABLE player_adjusted_value AS

WITH base AS (
    SELECT c.*,
           -- ordinary z, computed in-window per positional group
           AVG(EPA_points_raw)         OVER w_pos  AS pos_epa_mean,
           STDDEV_SAMP(EPA_points_raw) OVER w_pos  AS pos_epa_sd,
           COUNT(*)                    OVER w_pos  AS pos_n_players,
           AVG(offensive_play_share)         OVER w_pos AS pos_usage_mean,
           STDDEV_SAMP(offensive_play_share) OVER w_pos AS pos_usage_sd,
           AVG(EPA_per_recorded_opportunity)         OVER w_pos AS pos_eff_mean,
           STDDEV_SAMP(EPA_per_recorded_opportunity) OVER w_pos AS pos_eff_sd,
           -- mid-rank percentiles within the positional group. PERCENT_RANK
           -- would put the group minimum at exactly 0 and pin ties to the
           -- bottom of their run; CUME_DIST averaged with its complement gives
           -- the mid-rank convention used everywhere else in this phase.
           0.5 * 100 * (CUME_DIST() OVER (PARTITION BY position_group
                                          ORDER BY EPA_points_raw)
                      + 1 - CUME_DIST() OVER (PARTITION BY position_group
                                              ORDER BY EPA_points_raw DESC))
                                                   AS EPA_position_percentile,
           0.5 * 100 * (CUME_DIST() OVER (PARTITION BY position_group
                                          ORDER BY offensive_play_share)
                      + 1 - CUME_DIST() OVER (PARTITION BY position_group
                                              ORDER BY offensive_play_share DESC))
                                                   AS usage_position_percentile,
           0.5 * 100 * (CUME_DIST() OVER (PARTITION BY position_group
                                          ORDER BY EPA_per_recorded_opportunity)
                      + 1 - CUME_DIST() OVER (PARTITION BY position_group
                                              ORDER BY EPA_per_recorded_opportunity DESC))
                                                   AS efficiency_position_percentile
    FROM player_adjusted_core c
    WINDOW w_pos AS (PARTITION BY position_group)
),

-- robust scales come from the baseline table so there is exactly one published
-- median and MAD per (group, metric) and no chance of two queries disagreeing
robust AS (
    SELECT baseline_group AS position_group, metric_name, median, robust_sd, sd_is_publishable
    FROM player_positional_baselines
    WHERE baseline_scope = 'position'
)

SELECT
    -- ---------------------------------------------------------- IDENTITY
    b.player_id,
    b.player_name,
    b.team_id,
    b.n_teams,
    b.raw_position,
    b.canonical_position,
    b.position_group,
    b.value_role,
    b.mapping_reason,
    b.mapping_confidence,
    b.games_played,

    -- ------------------------------------------------------------ VOLUME
    b.recorded_offensive_opportunities,
    b.team_recorded_offensive_opportunities,
    b.offensive_opportunities_per_game,
    b.shots, b.one_point_attempts, b.two_point_attempts, b.shots_on_goal,
    b.turnovers, b.touches, b.ground_balls, b.official_assists,
    b.caused_turnovers, b.faceoffs, b.faceoff_wins,
    b.shots_on_goal_faced, b.one_point_shots_on_goal_faced,
    b.two_point_shots_on_goal_faced, b.saves, b.penalties,

    -- ------------------------------------------------------------- USAGE
    b.offensive_play_share,
    b.offensive_play_share_season,
    b.shot_share,
    b.touch_share,
    b.faceoff_team_share,
    b.caused_turnover_team_share,
    b.event_log_play_shares,
    b.event_log_play_share,

    -- --------------------------------------------- RAW VALUE (Phase 6, verbatim)
    b.shooting_value_raw,
    b.shooting_value_one_point_raw,
    b.shooting_value_two_point_raw,
    b.turnover_value_raw,
    b.faceoff_value_raw,
    b.goalie_value_raw,
    b.defensive_value_partial_raw,
    b.defensive_value_scope,
    b.offensive_EPA_points_raw,
    b.EPA_points_raw,
    b.components_supported,

    -- -------------------------------------------------------- EFFICIENCY
    b.EPA_per_recorded_opportunity,
    b.shooting_EPA_per_shot,
    b.faceoff_EPA_per_faceoff,
    b.goalie_EPA_per_SOG,
    b.defensive_EPA_partial_per_game,
    b.EPA_points_per_game,
    b.uaEPA_per_event_log_play_share,

    -- ------------------------------------------ USAGE-ADJUSTED (see own table)
    b.expected_EPA_given_usage,
    b.EPA_vs_usage_expectation,
    b.EPA_vs_usage_expectation / NULLIF(b.offensive_EPA_null_sd, 0)
                                                     AS EPA_vs_usage_expectation_z,

    -- ----------------------------------- SAMPLING NOISE AT THIS PLAYER'S VOLUME
    b.shooting_value_null_sd,
    b.faceoff_value_null_sd,
    b.goalie_value_null_sd,
    b.offensive_EPA_null_sd,
    b.EPA_points_null_sd,
    b.EPA_points_raw / NULLIF(b.EPA_points_null_sd, 0)          AS EPA_points_null_z,
    b.shooting_value_raw / NULLIF(b.shooting_value_null_sd, 0)  AS shooting_value_null_z,
    b.faceoff_value_raw / NULLIF(b.faceoff_value_null_sd, 0)    AS faceoff_value_null_z,
    b.goalie_value_raw / NULLIF(b.goalie_value_null_sd, 0)      AS goalie_value_null_z,

    -- ------------------------------------------------- SHRUNK / ESTIMATED SKILL
    b.shooting_rate_raw,   b.shooting_rate_shrunk,
    b.one_point_rate_raw,  b.one_point_rate_shrunk,
    b.two_point_rate_raw,  b.two_point_rate_shrunk,
    b.faceoff_rate_raw,    b.faceoff_rate_shrunk,
    b.save_rate_raw,       b.save_rate_shrunk,

    -- ------------------------------------------------------- RELIABILITY
    b.shooting_reliability,
    b.one_point_reliability,
    b.two_point_reliability,
    b.faceoff_reliability,
    b.save_reliability,
    b.shooting_posterior_ci_width,
    b.faceoff_posterior_ci_width,
    b.save_posterior_ci_width,

    -- ------------------------------------------------- POSITIONAL CONTEXT
    b.pos_n_players                                  AS position_n_players,
    b.pos_epa_mean                                   AS position_EPA_mean,
    CASE WHEN b.pos_n_players >= 9 THEN b.pos_epa_sd END AS position_EPA_sd,
    CASE WHEN b.pos_n_players >= 9 AND b.pos_epa_sd > 0
         THEN (b.EPA_points_raw - b.pos_epa_mean) / b.pos_epa_sd END
                                                     AS EPA_position_z,
    CASE WHEN r_epa.sd_is_publishable AND r_epa.robust_sd > 0
         THEN (b.EPA_points_raw - r_epa.median) / r_epa.robust_sd END
                                                     AS EPA_position_robust_z,
    b.EPA_position_percentile,

    CASE WHEN b.pos_n_players >= 9 AND b.pos_usage_sd > 0
         THEN (b.offensive_play_share - b.pos_usage_mean) / b.pos_usage_sd END
                                                     AS usage_position_z,
    b.usage_position_percentile,

    CASE WHEN b.pos_n_players >= 9 AND b.pos_eff_sd > 0
         THEN (b.EPA_per_recorded_opportunity - b.pos_eff_mean) / b.pos_eff_sd END
                                                     AS efficiency_position_z,
    b.efficiency_position_percentile,

    CASE WHEN b.pos_n_players >= 9 THEN NULL
         ELSE 'positional sd suppressed (n=' || b.pos_n_players
              || ' < 9); use the percentile column or the league scope'
    END                                              AS position_baseline_note,

    -- -------------------------------------------------------- ELIGIBILITY
    TRUE                                             AS descriptive_eligible,

    -- the rate that decides the player's own role leaderboard
    CASE b.value_role
        WHEN 'faceoff'         THEN b.faceoff_reliability
        WHEN 'goalie'          THEN b.save_reliability
        ELSE b.shooting_reliability
    END                                              AS role_rate_reliability,
    CASE b.value_role
        WHEN 'faceoff'         THEN 'faceoff_win_pct'
        WHEN 'goalie'          THEN 'save_pct'
        ELSE 'shooting_pct'
    END                                              AS role_rate_name,
    COALESCE(CASE b.value_role
        WHEN 'faceoff'         THEN b.faceoff_reliability
        WHEN 'goalie'          THEN b.save_reliability
        ELSE b.shooting_reliability
    END >= 0.5, FALSE)                               AS rate_ranking_eligible,
    COALESCE(CASE b.value_role
        WHEN 'faceoff'         THEN b.faceoff_rate_shrunk
        WHEN 'goalie'          THEN b.save_rate_shrunk
        ELSE b.shooting_rate_shrunk
    END IS NOT NULL, FALSE)                          AS reliability_adjusted_eligible,
    COALESCE(b.event_log_play_share >= 0.01, FALSE)  AS future_award_input_eligible,
    -- A separate gate for OFFENSIVE rate leaderboards, which every role can
    -- appear on. A faceoff specialist can clear rate_ranking_eligible on 353
    -- draws while having taken 6 offensive opportunities, so his faceoff
    -- reliability must not license him onto an efficiency-per-shot board.
    -- Shooting reliability is the gate because finishing is what drives
    -- offensive efficiency; it corresponds to 71 shot attempts in 2026.
    COALESCE(b.shooting_reliability >= 0.5, FALSE)   AS offensive_rate_ranking_eligible,

    -- --------------------------------------------------- LIMITATION FLAGS
    TRUE                                             AS defense_partial,
    TRUE                                             AS usage_proxy_only,
    -- TWO DIFFERENT SMALLNESS FLAGS, because they mean different things and
    -- collapsing them would hide one of them. Neither is a round-number cutoff.
    --
    -- small_sample: the empirical-Bayes posterior puts more weight on the
    -- league prior than on this player's own record for the rate that defines
    -- his role. The threshold is 0.5 reliability -- a property of the
    -- estimator -- and the trial count it implies is set by the data, not by
    -- us: 16 draws, 71 shots, 300 shots on goal.
    NOT COALESCE(CASE b.value_role
        WHEN 'faceoff'         THEN b.faceoff_reliability
        WHEN 'goalie'          THEN b.save_reliability
        ELSE b.shooting_reliability
    END >= 0.5, FALSE)                               AS small_sample,
    --
    -- chance_variation_exceeds_peer_spread: the player's own chance-alone
    -- standard deviation is at least as large as the whole observed spread of
    -- his positional group. That is the precise statement "luck alone could
    -- have put this player anywhere within his peer group", and it is the
    -- condition under which his positional percentile carries no information.
    -- It catches HIGH-volume players too -- a 96-attempt midfielder has a
    -- chance sd of about 4.5 EPA_points against a midfield group sd of 3.3 --
    -- which is exactly why it is not the same flag as small_sample.
    COALESCE(b.EPA_points_null_sd >= b.pos_epa_sd, TRUE)
                                                     AS chance_variation_exceeds_peer_spread,
    'ground_ball_value,assist_value,possession_participation,penalty_value'
                                                     AS unsupported_components,
    CASE WHEN b.value_role = 'goalie'  THEN 'goalie metrics are standardized only against '
              || 'other goalies; a goalie total is not comparable with a field player total'
         WHEN b.value_role = 'faceoff' THEN 'faceoff value dominates this role''s total; see '
              || 'the faceoff share-of-total column before comparing across roles'
         WHEN b.value_role = 'defensive_field' THEN 'defensive value is PARTIAL (caused '
              || 'turnovers only, on a games-played denominator); a value near zero does '
              || 'NOT mean an average defender'
         ELSE 'offensive value covers finishing and possession security only; shot creation, '
              || 'assists and off-ball work are not measured'
    END                                              AS role_interpretation_caveat,

    -- share of the player's own MEASURED value coming from each phase, so a
    -- reader can see what a role total is actually made of. Denominated in
    -- absolute magnitudes because the components are signed residuals: a share
    -- of a signed sum is not interpretable and can be negative or unbounded.
    (ABS(COALESCE(b.faceoff_value_raw, 0)))
      / NULLIF(ABS(COALESCE(b.shooting_value_raw, 0)) + ABS(COALESCE(b.turnover_value_raw, 0))
             + ABS(COALESCE(b.faceoff_value_raw, 0)) + ABS(COALESCE(b.goalie_value_raw, 0))
             + ABS(COALESCE(b.defensive_value_partial_raw, 0)), 0)
                                                     AS faceoff_share_of_absolute_value,
    (ABS(COALESCE(b.shooting_value_raw, 0)) + ABS(COALESCE(b.turnover_value_raw, 0)))
      / NULLIF(ABS(COALESCE(b.shooting_value_raw, 0)) + ABS(COALESCE(b.turnover_value_raw, 0))
             + ABS(COALESCE(b.faceoff_value_raw, 0)) + ABS(COALESCE(b.goalie_value_raw, 0))
             + ABS(COALESCE(b.defensive_value_partial_raw, 0)), 0)
                                                     AS offensive_share_of_absolute_value,
    (ABS(COALESCE(b.defensive_value_partial_raw, 0)))
      / NULLIF(ABS(COALESCE(b.shooting_value_raw, 0)) + ABS(COALESCE(b.turnover_value_raw, 0))
             + ABS(COALESCE(b.faceoff_value_raw, 0)) + ABS(COALESCE(b.goalie_value_raw, 0))
             + ABS(COALESCE(b.defensive_value_partial_raw, 0)), 0)
                                                     AS defensive_partial_share_of_absolute_value

FROM base b
LEFT JOIN robust r_epa
       ON r_epa.position_group = b.position_group
      AND r_epa.metric_name = 'EPA_points_raw'
ORDER BY b.player_id;
