-- Phase 5: efficiency by possession length.
--
-- Eligibility (deliberately stricter than "all possessions"):
--   is_measurable_span = unambiguous AND not truncated AND event_count > 1.
-- A possession opened and closed by the SAME single logged event has a span of
-- 0 by construction (871 of 4,388 season-wide). That is not a short
-- possession, it is the absence of a duration measurement, so those are
-- excluded outright. 2,096 of 4,388 possessions (47.8%) qualify.
--
-- Bucket scheme: 0s / 01-09s / 10-19s / 20-29s / 30-44s / 45-59s / 60s+,
-- chosen AFTER inspecting the empirical distribution of qualifying spans
-- (deciles at 0/5/12/19/25/30/35/41/52s). The 10s-wide interior edges keep
-- every league-level cell at n>=115, and 30s/45s straddle the two PLL
-- shot-clock lengths (32s after a faceoff, 52s on a change of possession),
-- which is what shapes the upper tail. Cell counts are on every row so a thin
-- team-level bucket is visible rather than implied.
--
-- Same-second possessions (span exactly 0 across two or more distinct logged
-- events) get their OWN bucket rather than being folded into 0-9s. They behave
-- nothing like the rest of that range: 251 possessions with a 76% goal rate
-- and 0.81 points per possession, against 0.43 for genuine 1-9 second
-- possessions. Merging them would have made the fastest bucket read as
-- 0.60 points per possession and invented a "fast offence is hyper-efficient"
-- effect that is really just the feed logging a possession's start and its
-- goal in the same second.
--
-- Buckets are LENGTH ONLY. No row here is labelled "transition" or "settled"
-- -- span is measured, playing style is not.

CREATE OR REPLACE TABLE possession_length_splits AS

WITH bucketed AS (
    SELECT
        offense_team_id AS team_id,
        duration_seconds,
        points_scored,
        goals,
        shot_attempts,
        shots_on_goal,
        ended_in_turnover,
        CASE WHEN duration_seconds =   0 THEN '0s'
             WHEN duration_seconds <  10 THEN '01-09s'
             WHEN duration_seconds <  20 THEN '10-19s'
             WHEN duration_seconds <  30 THEN '20-29s'
             WHEN duration_seconds <  45 THEN '30-44s'
             WHEN duration_seconds <  60 THEN '45-59s'
             ELSE                              '60s+'
        END AS length_bucket
    FROM possessions
    WHERE is_measurable_span
),

-- League row and per-team rows are the same aggregation over two groupings.
scoped AS (
    SELECT 'LEAGUE' AS scope, length_bucket, duration_seconds, points_scored, goals,
           shot_attempts, shots_on_goal, ended_in_turnover
    FROM bucketed
    UNION ALL
    SELECT team_id, length_bucket, duration_seconds, points_scored, goals,
           shot_attempts, shots_on_goal, ended_in_turnover
    FROM bucketed
),

agg AS (
    SELECT
        scope,
        length_bucket,
        COUNT(*)                                        AS possessions,
        COUNT(*) FILTER (WHERE duration_seconds = 0)    AS zero_span_possessions,
        SUM(points_scored)                              AS points,
        SUM(goals)                                      AS goals,
        SUM(shot_attempts)                              AS shots,
        SUM(shots_on_goal)                              AS shots_on_goal,
        SUM(ended_in_turnover)                          AS turnovers,
        AVG(duration_seconds)                           AS mean_span_seconds,
        MEDIAN(duration_seconds)                        AS median_span_seconds
    FROM scoped
    GROUP BY scope, length_bucket
)

SELECT
    scope,
    length_bucket,
    CASE length_bucket WHEN '0s'     THEN 1 WHEN '01-09s' THEN 2 WHEN '10-19s' THEN 3
                       WHEN '20-29s' THEN 4 WHEN '30-44s' THEN 5 WHEN '45-59s' THEN 6
                       ELSE 7 END AS bucket_order,
    possessions,
    zero_span_possessions,
    -- Window function: each bucket's share of that scope's qualifying
    -- possessions, so a thin cell is obvious without a second query.
    possessions / CAST(SUM(possessions) OVER (PARTITION BY scope) AS DOUBLE) AS share_of_possessions,
    mean_span_seconds,
    median_span_seconds,
    points,
    goals,
    points / CAST(possessions AS DOUBLE) AS points_per_possession,
    goals  / CAST(possessions AS DOUBLE) AS goals_per_possession,
    shots,
    shots_on_goal,
    shots         / CAST(possessions AS DOUBLE) AS shots_per_possession,
    shots_on_goal / CAST(possessions AS DOUBLE) AS shots_on_goal_per_possession,
    points / NULLIF(CAST(shots AS DOUBLE), 0)   AS points_per_shot,
    turnovers,
    turnovers / CAST(possessions AS DOUBLE) AS turnover_rate
FROM agg
ORDER BY (scope = 'LEAGUE') DESC, scope, bucket_order;
