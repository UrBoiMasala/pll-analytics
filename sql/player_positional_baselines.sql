-- Phase 7: positional and league-wide baselines.
--
-- One row per (scope, group, metric). Two scopes are always produced for every
-- metric so a reader can see what the positional adjustment actually did:
--
--   league   -- all 228 players, no positional partition
--   position -- partitioned by `position_group` (attack, midfield,
--               defensive_field, faceoff, goalie, unknown)
--   role     -- partitioned by `value_role` (offensive_field, defensive_field,
--               faceoff, goalie, unclassified_field)
--
-- `position_group` is the ROSTER partition and `value_role` is the MEASURED-
-- ROLE partition; they differ for the 13 faceoff specialists only in name but
-- would differ substantively for any player whose measured role diverged from
-- his label, so both are published rather than one being chosen for us.
--
-- ---------------------------------------------------------------------------
-- SUPPRESSION RULE, AND WHY IT IS 9
--
-- A positional baseline is only published for standardization when the group
-- has at least 9 players with the metric defined. The relative standard error
-- of an estimated standard deviation is 1 / sqrt(2(n-1)); at n = 9 that is
-- 25%, and below it the denominator of a z-score is more uncertain than the
-- numerator it is meant to scale. Groups under the rule keep their mean,
-- median and count -- those are still informative -- but carry
-- `sd_is_publishable = false`, and every standardized measure built on them
-- falls back to the league scope with `baseline_fallback_reason` recording it.
--
-- In 2026 exactly one group is suppressed: `unknown`, 2 players, both of whom
-- played 1-2 games. The faceoff (13) and goalie (17) groups clear the rule,
-- which is the whole reason Phase 7 can standardize them within role at all.
--
-- ---------------------------------------------------------------------------
-- WHAT IS REPORTED
--
-- n_players, n_opportunities, mean, median, sd, MAD, standard error of the
-- mean, quartiles and range -- so a reader can see the shape of the group's
-- distribution and not just its centre. MAD is carried because several of
-- these distributions are visibly skewed (offensive_field EPA_points skew
-- +0.75, defensive_field shooting-value excess kurtosis +3.4) and the robust
-- standardization needs a scale that a single 8-point outlier cannot set.

CREATE OR REPLACE TABLE player_positional_baselines AS

WITH metric_long AS (
    -- UNPIVOT rather than one hand-written aggregate per metric: adding a
    -- metric to the list below is then the only edit needed, and no metric can
    -- silently get a different filter from its neighbours.
    SELECT player_id, position_group, value_role, games_played,
           metric_name, metric_value, opportunity_count
    FROM (
        SELECT
            player_id, position_group, value_role, games_played,
            EPA_points_raw, offensive_EPA_points_raw, shooting_value_raw,
            turnover_value_raw, faceoff_value_raw, goalie_value_raw,
            defensive_value_partial_raw,
            EPA_per_recorded_opportunity, shooting_EPA_per_shot,
            faceoff_EPA_per_faceoff, goalie_EPA_per_SOG,
            defensive_EPA_partial_per_game, EPA_points_per_game,
            offensive_play_share, touch_share, event_log_play_share,
            offensive_opportunities_per_game,
            shooting_rate_raw, faceoff_rate_raw, save_rate_raw,
            shooting_rate_shrunk, faceoff_rate_shrunk, save_rate_shrunk,
            -- the opportunity count that goes with each metric, matched by
            -- position in the two UNPIVOT lists
            CAST(recorded_offensive_opportunities AS DOUBLE) AS o_epa_total,
            CAST(recorded_offensive_opportunities AS DOUBLE) AS o_off_epa,
            CAST(shots AS DOUBLE)                            AS o_shooting,
            CAST(touches AS DOUBLE)                          AS o_turnover,
            CAST(faceoffs AS DOUBLE)                         AS o_faceoff,
            CAST(shots_on_goal_faced AS DOUBLE)              AS o_goalie,
            CAST(games_played AS DOUBLE)                     AS o_defense,
            CAST(recorded_offensive_opportunities AS DOUBLE) AS o_epa_per_opp,
            CAST(shots AS DOUBLE)                            AS o_shoot_per_shot,
            CAST(faceoffs AS DOUBLE)                         AS o_fo_per_fo,
            CAST(shots_on_goal_faced AS DOUBLE)              AS o_gk_per_sog,
            CAST(games_played AS DOUBLE)                     AS o_def_per_game,
            CAST(games_played AS DOUBLE)                     AS o_epa_per_game,
            CAST(recorded_offensive_opportunities AS DOUBLE) AS o_play_share,
            CAST(touches AS DOUBLE)                          AS o_touch_share,
            CAST(event_log_play_shares AS DOUBLE)            AS o_log_share,
            CAST(games_played AS DOUBLE)                     AS o_opp_per_game,
            CAST(shots AS DOUBLE)                            AS o_shoot_rate,
            CAST(faceoffs AS DOUBLE)                         AS o_fo_rate,
            CAST(shots_on_goal_faced AS DOUBLE)              AS o_save_rate
        FROM player_adjusted_core
    )
    UNPIVOT (
        (metric_value, opportunity_count) FOR metric_name IN (
            (EPA_points_raw, o_epa_total)                        AS 'EPA_points_raw',
            (offensive_EPA_points_raw, o_off_epa)                AS 'offensive_EPA_points_raw',
            (shooting_value_raw, o_shooting)                     AS 'shooting_value_raw',
            (turnover_value_raw, o_turnover)                     AS 'turnover_value_raw',
            (faceoff_value_raw, o_faceoff)                       AS 'faceoff_value_raw',
            (goalie_value_raw, o_goalie)                         AS 'goalie_value_raw',
            (defensive_value_partial_raw, o_defense)             AS 'defensive_value_partial_raw',
            (EPA_per_recorded_opportunity, o_epa_per_opp)        AS 'EPA_per_recorded_opportunity',
            (shooting_EPA_per_shot, o_shoot_per_shot)            AS 'shooting_EPA_per_shot',
            (faceoff_EPA_per_faceoff, o_fo_per_fo)               AS 'faceoff_EPA_per_faceoff',
            (goalie_EPA_per_SOG, o_gk_per_sog)                   AS 'goalie_EPA_per_SOG',
            (defensive_EPA_partial_per_game, o_def_per_game)     AS 'defensive_EPA_partial_per_game',
            (EPA_points_per_game, o_epa_per_game)                AS 'EPA_points_per_game',
            (offensive_play_share, o_play_share)                 AS 'offensive_play_share',
            (touch_share, o_touch_share)                         AS 'touch_share',
            (event_log_play_share, o_log_share)                  AS 'event_log_play_share',
            (offensive_opportunities_per_game, o_opp_per_game)   AS 'offensive_opportunities_per_game',
            (shooting_rate_raw, o_shoot_rate)                    AS 'shooting_rate_raw',
            (faceoff_rate_raw, o_fo_rate)                        AS 'faceoff_rate_raw',
            (save_rate_raw, o_save_rate)                         AS 'save_rate_raw',
            (shooting_rate_shrunk, o_shoot_rate)                 AS 'shooting_rate_shrunk',
            (faceoff_rate_shrunk, o_fo_rate)                     AS 'faceoff_rate_shrunk',
            (save_rate_shrunk, o_save_rate)                      AS 'save_rate_shrunk'
        )
    )
),

scoped AS (
    SELECT 'league' AS baseline_scope, 'ALL' AS baseline_group,
           metric_name, metric_value, opportunity_count
    FROM metric_long
    UNION ALL
    SELECT 'position', position_group, metric_name, metric_value, opportunity_count
    FROM metric_long
    UNION ALL
    SELECT 'role', value_role, metric_name, metric_value, opportunity_count
    FROM metric_long
),

-- median absolute deviation needs the group median first
with_median AS (
    SELECT s.*,
           MEDIAN(metric_value) OVER (PARTITION BY baseline_scope, baseline_group, metric_name)
               AS group_median
    FROM scoped s
    WHERE metric_value IS NOT NULL
)

-- ROUND(..., 12) on every aggregate is a DETERMINISM measure, not a precision
-- claim. This query aggregates over the output of an UNPIVOT feeding a
-- windowed MEDIAN, and DuckDB does not guarantee a fixed row order into the
-- group aggregate through that pipeline; floating-point addition is not
-- associative, so AVG and STDDEV_SAMP came back differing in the 16th
-- significant figure between two runs of the identical query (caught by
-- validation check 25's SHA-256 rebuild). Twelve decimal places is roughly
-- four orders of magnitude finer than the smallest quantity here and ten
-- orders coarser than the jitter, so it fixes the byte-level reproducibility
-- without touching anything a reader could care about.
SELECT
    baseline_scope,
    baseline_group,
    metric_name,
    COUNT(*)                                            AS n_players,
    SUM(opportunity_count)                              AS n_opportunities,
    ROUND(AVG(metric_value), 12)                        AS mean,
    ROUND(MEDIAN(metric_value), 12)                     AS median,
    ROUND(STDDEV_SAMP(metric_value), 12)                AS sd,
    ROUND(MEDIAN(ABS(metric_value - group_median)), 12) AS mad,
    ROUND(1.4826 * MEDIAN(ABS(metric_value - group_median)), 12) AS robust_sd,
    ROUND(STDDEV_SAMP(metric_value) / NULLIF(SQRT(CAST(COUNT(*) AS DOUBLE)), 0), 12)
                                                        AS se_mean,
    ROUND(QUANTILE_CONT(metric_value, 0.25), 12)        AS p25,
    ROUND(QUANTILE_CONT(metric_value, 0.75), 12)        AS p75,
    ROUND(MIN(metric_value), 12)                        AS min_value,
    ROUND(MAX(metric_value), 12)                        AS max_value,
    -- the >= 9 rule, stated on the row rather than applied invisibly
    (COUNT(*) >= 9)                                     AS sd_is_publishable,
    CASE WHEN COUNT(*) >= 9 THEN NULL
         ELSE 'group has ' || COUNT(*) || ' players with this metric; the relative standard '
              || 'error of an estimated sd is 1/sqrt(2(n-1)) > 25% below n=9, so the '
              || 'positional sd is suppressed and standardization falls back to the league scope'
    END                                                 AS baseline_suppression_reason,
    ROUND(1.0 / SQRT(2.0 * (COUNT(*) - 1)), 12)         AS relative_se_of_sd
FROM with_median
GROUP BY baseline_scope, baseline_group, metric_name
ORDER BY metric_name, baseline_scope, baseline_group;
