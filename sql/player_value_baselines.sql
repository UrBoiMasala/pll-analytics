-- Phase 6: league baselines.
--
-- Every number a value component compares a player against lives here, with
-- its numerator, denominator, sample size, source and standard error. A reader
-- who disagrees with a coefficient can see exactly what it was estimated from.
--
-- Two kinds of baseline:
--
--   CONVERSION baselines (computed here, in SQL) -- league-average outcome per
--   opportunity: expected points per one-point attempt, per two-point attempt,
--   per shot on goal faced, faceoff win probability, turnovers per touch,
--   caused turnovers per game by position.
--
--   EVENT-VALUE coefficients (estimated in Python, read from
--   event_value_coefficients.csv) -- the net PLL points associated with an
--   event over the following 60 seconds of play. These need a forward scan of
--   the event log and a bootstrap, which is Python's job, not SQL's.
--
-- Standard errors are binomial where the quantity is a proportion and
-- bootstrap percentiles where it is not.

CREATE OR REPLACE VIEW event_value_coefficients AS
SELECT * FROM read_csv_auto('{scratch_dir}/event_value_coefficients.csv');

CREATE OR REPLACE TABLE player_value_baselines AS

WITH shot_baselines AS (
    SELECT
        CASE WHEN is_two_point THEN 'expected_points_per_two_point_attempt'
             ELSE 'expected_points_per_one_point_attempt' END          AS baseline_name,
        'shooting'                                                      AS component,
        CASE WHEN is_two_point THEN 'two-point shot attempts'
             ELSE 'one-point shot attempts' END                         AS denominator_desc,
        COUNT(*)                                                        AS sample_size,
        SUM(CASE WHEN is_goal THEN 1 ELSE 0 END)                        AS numerator_events,
        SUM(pll_points)                                                 AS numerator_points,
        SUM(CASE WHEN is_goal THEN 1 ELSE 0 END) / CAST(COUNT(*) AS DOUBLE) AS conversion_rate,
        SUM(pll_points) / CAST(COUNT(*) AS DOUBLE)                      AS baseline_value
    FROM eligible_shot_events
    GROUP BY is_two_point
),

goalie_baselines AS (
    SELECT
        CASE WHEN is_two_point THEN 'expected_points_allowed_per_two_point_shot_on_goal'
             ELSE 'expected_points_allowed_per_one_point_shot_on_goal' END AS baseline_name,
        'goalie'                                                        AS component,
        CASE WHEN is_two_point THEN 'two-point shots on goal faced'
             ELSE 'one-point shots on goal faced' END                   AS denominator_desc,
        COUNT(*)                                                        AS sample_size,
        SUM(CASE WHEN is_goal THEN 1 ELSE 0 END)                        AS numerator_events,
        SUM(pll_points)                                                 AS numerator_points,
        SUM(CASE WHEN is_goal THEN 1 ELSE 0 END) / CAST(COUNT(*) AS DOUBLE) AS conversion_rate,
        SUM(pll_points) / CAST(COUNT(*) AS DOUBLE)                      AS baseline_value
    FROM eligible_shot_events
    WHERE is_shot_on_goal
    GROUP BY is_two_point
),

-- Faceoff win probability. Nearly, but NOT exactly, 0.5: each draw credits a
-- faceoff to both participants and a win to one, so the ratio would be exactly
-- 0.5 if every draw had a recorded winner. 18 of the season's 1,309 draws do
-- not (the Phase 5 finding that faceoffsWon + faceoffsLost falls 1-2 short of
-- faceoffs in 8 games -- violations and redraws PLL counts as contested but
-- awards to nobody). The empirical rate is 1,300/2,618 = 0.49656, and it is
-- the empirical rate that must be used: the faceoff residuals sum to exactly
-- zero against it and would not against an assumed 0.5.
faceoff_baseline AS (
    SELECT
        'faceoff_win_probability'                       AS baseline_name,
        'faceoff'                                       AS component,
        'faceoffs contested (league)'                   AS denominator_desc,
        SUM(faceoffs)                                   AS sample_size,
        SUM(faceoff_wins)                               AS numerator_events,
        CAST(NULL AS DOUBLE)                            AS numerator_points,
        SUM(faceoff_wins) / CAST(SUM(faceoffs) AS DOUBLE) AS conversion_rate,
        SUM(faceoff_wins) / CAST(SUM(faceoffs) AS DOUBLE) AS baseline_value
    FROM player_game
),

-- Turnovers per touch, by baseline group. Position groups are used rather
-- than one league rate because the rate is genuinely role-dependent (faceoff
-- specialists turn the ball over roughly twice as often per touch as field
-- players, because their touches are overwhelmingly contested scrum
-- recoveries). Charging a FOGO against an attackman's rate would penalise the
-- role, not the player.
turnover_baseline AS (
    SELECT
        'turnovers_per_touch__' || baseline_group       AS baseline_name,
        'turnover'                                      AS component,
        'recorded touches (' || baseline_group || ')'   AS denominator_desc,
        SUM(touches)                                    AS sample_size,
        SUM(turnovers)                                  AS numerator_events,
        CAST(NULL AS DOUBLE)                            AS numerator_points,
        SUM(turnovers) / CAST(SUM(touches) AS DOUBLE)   AS conversion_rate,
        SUM(turnovers) / CAST(SUM(touches) AS DOUBLE)   AS baseline_value
    FROM player_game
    GROUP BY baseline_group
),

-- Caused turnovers per game, by baseline group. Games played is a crude
-- denominator -- it does not adjust for minutes, which the feed does not
-- provide -- and that limitation is carried on every defensive-value row.
caused_turnover_baseline AS (
    SELECT
        'caused_turnovers_per_game__' || baseline_group AS baseline_name,
        'defense'                                       AS component,
        'games played (' || baseline_group || ')'       AS denominator_desc,
        COUNT(*)                                        AS sample_size,
        SUM(caused_turnovers)                           AS numerator_events,
        CAST(NULL AS DOUBLE)                            AS numerator_points,
        SUM(caused_turnovers) / CAST(COUNT(*) AS DOUBLE) AS conversion_rate,
        SUM(caused_turnovers) / CAST(COUNT(*) AS DOUBLE) AS baseline_value
    FROM player_game
    GROUP BY baseline_group
),

-- Team-level context baselines, for reference and for the sensitivity
-- analysis (an alternative faceoff coefficient is built from the possession
-- value of a faceoff-started possession).
possession_baselines AS (
    SELECT 'points_per_possession_league' AS baseline_name, 'context' AS component,
           'all eligible possessions' AS denominator_desc,
           COUNT(*) AS sample_size, SUM(points_scored) AS numerator_events,
           SUM(points_scored) AS numerator_points,
           CAST(NULL AS DOUBLE) AS conversion_rate,
           SUM(points_scored) / CAST(COUNT(*) AS DOUBLE) AS baseline_value
    FROM possessions_raw
    UNION ALL
    SELECT 'points_per_faceoff_started_possession', 'context',
           'possessions starting on a faceoff win',
           COUNT(*), SUM(points_scored), SUM(points_scored), NULL,
           SUM(points_scored) / CAST(COUNT(*) AS DOUBLE)
    FROM possessions_raw WHERE start_reason = 'faceoff_win'
    UNION ALL
    SELECT 'points_per_opponent_turnover_possession', 'context',
           'possessions starting on an opponent turnover',
           COUNT(*), SUM(points_scored), SUM(points_scored), NULL,
           SUM(points_scored) / CAST(COUNT(*) AS DOUBLE)
    FROM possessions_raw WHERE start_reason = 'opponent_turnover'
),

sql_baselines AS (
    SELECT * FROM shot_baselines
    UNION ALL SELECT * FROM goalie_baselines
    UNION ALL SELECT * FROM faceoff_baseline
    UNION ALL SELECT * FROM turnover_baseline
    UNION ALL SELECT * FROM caused_turnover_baseline
    UNION ALL SELECT * FROM possession_baselines
),

sql_rows AS (
    SELECT
        baseline_name,
        component,
        baseline_value,
        conversion_rate,
        sample_size,
        numerator_events,
        denominator_desc,
        -- binomial standard error where the baseline is a proportion (or a
        -- proportion scaled by a fixed point value); NULL where it is not
        CASE WHEN conversion_rate IS NOT NULL AND sample_size > 0
             THEN SQRT(conversion_rate * (1 - conversion_rate) / sample_size)
                  * (baseline_value / NULLIF(conversion_rate, 0))
        END AS standard_error,
        'binomial' AS uncertainty_method,
        CASE component
            WHEN 'shooting' THEN 'events.csv (shot/goal events, is_analysis_eligible_event)'
            WHEN 'goalie'   THEN 'events.csv (shots on goal, is_analysis_eligible_event)'
            WHEN 'context'  THEN 'possessions.csv'
            ELSE 'player_game_stats.csv'
        END AS source_table,
        'league-analytics-eligible games only; all-star excluded' AS eligibility
    FROM sql_baselines
),

-- Coefficients estimated in Python by the forward-window method.
python_rows AS (
    SELECT
        'event_value__' || event_class      AS baseline_name,
        'event_value'                       AS component,
        value_vs_neutral                    AS baseline_value,
        CAST(NULL AS DOUBLE)                AS conversion_rate,
        n_events                            AS sample_size,
        CAST(NULL AS BIGINT)                AS numerator_events,
        'occurrences of this event class'   AS denominator_desc,
        se_net_points                       AS standard_error,
        'bootstrap (2000 resamples) + neutral-reference adjustment' AS uncertainty_method,
        'events.csv forward 60s window'     AS source_table,
        'league-analytics-eligible games only; all-star excluded' AS eligibility
    FROM event_value_coefficients
)

SELECT * FROM sql_rows
UNION ALL
SELECT * FROM python_rows
ORDER BY component, baseline_name;


-- ---------------------------------------------------------------------------
-- Named scalar coefficients, pivoted out of the baseline table so every
-- component query reads them from a single source rather than restating a
-- number. Changing a baseline changes every component that uses it.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW value_coefficients AS
SELECT
    MAX(baseline_value) FILTER (WHERE baseline_name = 'expected_points_per_one_point_attempt')
        AS xp_per_one_point_attempt,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'expected_points_per_two_point_attempt')
        AS xp_per_two_point_attempt,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'expected_points_allowed_per_one_point_shot_on_goal')
        AS xp_allowed_per_one_point_sog,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'expected_points_allowed_per_two_point_shot_on_goal')
        AS xp_allowed_per_two_point_sog,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'faceoff_win_probability')
        AS faceoff_win_probability,
    -- A faceoff win is worth its own event value; a loss hands that same value
    -- to the opponent. The swing from losing to winning is therefore twice the
    -- event value, and that is what a marginal win above expectation is worth.
    2 * MAX(baseline_value) FILTER (WHERE baseline_name = 'event_value__faceoff_win')
        AS points_per_marginal_faceoff_win,
    -- Cost of a turnover: the (negative) net-points swing the event is
    -- empirically associated with, taken as a positive magnitude.
    -1 * MAX(baseline_value) FILTER (WHERE baseline_name = 'event_value__turnover')
        AS points_per_turnover,
    -- A caused turnover is the same physical event seen from the defending
    -- side, so it carries the same magnitude with the opposite sign. See
    -- docs/PLAYER_VALUE_ACCOUNTING.md scenario E.
    -1 * MAX(baseline_value) FILTER (WHERE baseline_name = 'event_value__turnover')
        AS points_per_caused_turnover,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'event_value__ground_ball')
        AS points_per_ground_ball_event,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'points_per_possession_league')
        AS points_per_possession_league,
    MAX(baseline_value) FILTER (WHERE baseline_name = 'points_per_faceoff_started_possession')
        AS points_per_faceoff_started_possession
FROM player_value_baselines;
