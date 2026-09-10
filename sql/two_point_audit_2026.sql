-- Phase 8: the two-point audit.
--
-- PLL's two-point arc is the single most important thing that makes a PLL
-- statistical system different from an NCAA one, so it gets its own long/tidy
-- table rather than being scattered across the team and player files.
--
-- One row per (scope, scope_key). Every row carries both point classes so the
-- comparison the league actually cares about -- is the long shot worth taking
-- at these conversion rates -- can be read off a single row.
--
-- WHAT THIS TABLE IS NOT. `two_point_minus_one_point_return` is a realized
-- return difference at 2026 conversion rates. It is NOT a shot-selection
-- finding. Phases 1-6 verified that shot events in this feed carry no location,
-- no distance and no defender, so the counterfactual "what would this two-point
-- attempt have returned as a one-point attempt" is unobservable. A team whose
-- two-point return is negative may be taking bad long shots, taking good long
-- shots and missing, or facing defences that concede them. Nothing here
-- separates those.
--
-- GAME STATE IS LAGGED. The pre-shot margin subtracts the shot's own points
-- from the score columns, because Phase 6 established that PLL's score columns
-- on a goal event already include that goal. Without the lag every goal would
-- arrive pre-labelled with a score swing a miss at the same instant does not
-- have -- the exact leak that made an earlier expected-shot model look good.

-- ---------------------------------------------------------------------------
-- Shot-level spine, with a leak-free pre-shot game state.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW p8_shot_spine AS
WITH s AS (
    SELECT
        e.game_id,
        e.event_id,
        e.team_id,
        e.player_id,
        e.period,
        COALESCE(e.is_two_point_attempt, FALSE)                    AS is_two_point,
        e.is_valid_goal                                            AS is_goal,
        CASE WHEN e.is_valid_goal AND COALESCE(e.is_two_point_attempt, FALSE) THEN 2
             WHEN e.is_valid_goal                                             THEN 1
             ELSE 0 END                                            AS points_scored,
        e.home_score_corrected,
        e.away_score_corrected,
        g.home_team_id,
        g.away_team_id
    FROM p8_events e
    JOIN p8_eligible_games g USING (game_id)
    WHERE e.is_analysis_eligible_event
      AND e.event_type IN ('shot', 'goal')
      AND e.shot_outcome IS NOT NULL
)
SELECT
    s.*,
    -- Shooting team's margin BEFORE the shot: strip this row's own points off
    -- the shooting team's running score.
    CASE WHEN s.team_id = s.home_team_id
         THEN (s.home_score_corrected - s.points_scored) - s.away_score_corrected
         ELSE (s.away_score_corrected - s.points_scored) - s.home_score_corrected
    END AS pre_shot_margin
FROM s;

CREATE OR REPLACE VIEW p8_shot_spine_bucketed AS
SELECT *,
    CASE WHEN pre_shot_margin <= -4 THEN 'trailing_4_plus'
         WHEN pre_shot_margin <= -1 THEN 'trailing_1_to_3'
         WHEN pre_shot_margin  =  0 THEN 'tied'
         WHEN pre_shot_margin <=  3 THEN 'leading_1_to_3'
         ELSE                            'leading_4_plus' END AS margin_bucket,
    CASE WHEN period >= 4 THEN 'period_4_or_OT' ELSE 'period_1_to_3' END AS period_bucket
FROM p8_shot_spine;


-- ---------------------------------------------------------------------------
-- The audit table. One row per (scope, scope_key).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE two_point_audit_2026 AS

WITH agg AS (
    -- scope = LEAGUE
    SELECT 'LEAGUE' AS scope, 'ALL' AS scope_key, 'League 2026' AS scope_label,
           NULL::VARCHAR AS scope_detail, *
    FROM (
        SELECT COUNT(*) FILTER (WHERE NOT is_two_point)                AS one_point_attempts,
               COUNT(*) FILTER (WHERE NOT is_two_point AND is_goal)    AS one_point_goals,
               COUNT(*) FILTER (WHERE is_two_point)                    AS two_point_attempts,
               COUNT(*) FILTER (WHERE is_two_point AND is_goal)        AS two_point_goals
        FROM p8_shot_spine_bucketed
    )

    UNION ALL
    -- scope = TEAM
    SELECT 'TEAM', b.team_id, t.full_name, NULL,
           COUNT(*) FILTER (WHERE NOT b.is_two_point),
           COUNT(*) FILTER (WHERE NOT b.is_two_point AND b.is_goal),
           COUNT(*) FILTER (WHERE b.is_two_point),
           COUNT(*) FILTER (WHERE b.is_two_point AND b.is_goal)
    FROM p8_shot_spine_bucketed b
    JOIN p8_teams t ON t.team_id = b.team_id
    GROUP BY b.team_id, t.full_name

    UNION ALL
    -- scope = GAME_STATE (pre-shot margin, lagged)
    SELECT 'GAME_STATE', b.margin_bucket, b.margin_bucket, 'pre-shot score margin of shooting team',
           COUNT(*) FILTER (WHERE NOT b.is_two_point),
           COUNT(*) FILTER (WHERE NOT b.is_two_point AND b.is_goal),
           COUNT(*) FILTER (WHERE b.is_two_point),
           COUNT(*) FILTER (WHERE b.is_two_point AND b.is_goal)
    FROM p8_shot_spine_bucketed b
    GROUP BY b.margin_bucket

    UNION ALL
    -- scope = PERIOD
    SELECT 'PERIOD', b.period_bucket, b.period_bucket, NULL,
           COUNT(*) FILTER (WHERE NOT b.is_two_point),
           COUNT(*) FILTER (WHERE NOT b.is_two_point AND b.is_goal),
           COUNT(*) FILTER (WHERE b.is_two_point),
           COUNT(*) FILTER (WHERE b.is_two_point AND b.is_goal)
    FROM p8_shot_spine_bucketed b
    GROUP BY b.period_bucket

    UNION ALL
    -- scope = VOLUME_GROUP: players grouped by two-point attempt volume.
    -- Edges are the observed quartile-ish structure of a heavily zero-inflated
    -- count, stated as counts rather than as "high/low volume" labels.
    SELECT 'VOLUME_GROUP', v.volume_bucket, v.volume_bucket, 'player two-point attempt volume',
           SUM(v.one_point_attempts), SUM(v.one_point_goals),
           SUM(v.two_point_attempts), SUM(v.two_point_goals)
    FROM (
        SELECT o.player_id,
               o.one_point_attempts, o.one_point_goals,
               o.two_point_attempts, o.two_point_goals,
               CASE WHEN o.two_point_attempts = 0            THEN '00_attempts'
                    WHEN o.two_point_attempts <= 2           THEN '01_02_attempts'
                    WHEN o.two_point_attempts <= 5           THEN '03_05_attempts'
                    WHEN o.two_point_attempts <= 10          THEN '06_10_attempts'
                    ELSE                                          '11_plus_attempts' END AS volume_bucket
        FROM p8_opps o
    ) v
    GROUP BY v.volume_bucket

    UNION ALL
    -- scope = PLAYER, descriptive only. Every player who attempted at least one
    -- two-pointer. This is production, NOT an ability ranking -- Phase 7
    -- established two-point shooting ability is not identifiable in 2026.
    SELECT 'PLAYER', CAST(o.player_id AS VARCHAR), o.player_name, a.canonical_position,
           o.one_point_attempts, o.one_point_goals,
           o.two_point_attempts, o.two_point_goals
    FROM p8_opps o
    JOIN p8_adjusted a USING (player_id)
    WHERE o.two_point_attempts > 0
)

SELECT
    scope,
    scope_key,
    scope_label,
    scope_detail,
    one_point_attempts,
    one_point_goals,
    two_point_attempts,
    two_point_goals,
    one_point_attempts + two_point_attempts                              AS total_attempts,
    one_point_goals + two_point_goals                                    AS total_goals,
    one_point_goals + 2 * two_point_goals                                AS total_points,
    2 * two_point_goals                                                  AS two_point_points,
    CAST(one_point_goals AS DOUBLE) / NULLIF(one_point_attempts, 0)       AS one_point_conversion_pct,
    CAST(two_point_goals AS DOUBLE) / NULLIF(two_point_attempts, 0)       AS two_point_conversion_pct,
    CAST(two_point_attempts AS DOUBLE)
        / NULLIF(one_point_attempts + two_point_attempts, 0)              AS two_point_attempt_share,
    CAST(2 * two_point_goals AS DOUBLE)
        / NULLIF(one_point_goals + 2 * two_point_goals, 0)                AS two_point_points_share,
    -- expected return per attempt, by class
    CAST(one_point_goals AS DOUBLE) / NULLIF(one_point_attempts, 0)       AS points_per_one_point_attempt,
    CAST(2 * two_point_goals AS DOUBLE) / NULLIF(two_point_attempts, 0)   AS points_per_two_point_attempt,
    CAST(2 * two_point_goals AS DOUBLE) / NULLIF(two_point_attempts, 0)
        - CAST(one_point_goals AS DOUBLE) / NULLIF(one_point_attempts, 0) AS two_point_minus_one_point_return,
    -- Binomial standard error on the two-point return, so a thin cell is
    -- visibly thin. Return = 2 * p, so se(return) = 2 * sqrt(p(1-p)/n).
    2 * SQRT(
        (CAST(two_point_goals AS DOUBLE) / NULLIF(two_point_attempts, 0))
        * (1 - CAST(two_point_goals AS DOUBLE) / NULLIF(two_point_attempts, 0))
        / NULLIF(two_point_attempts, 0)
    )                                                                    AS points_per_two_point_attempt_se,
    -- The Wald SE above COLLAPSES TO EXACTLY ZERO whenever a cell went 0-for-n
    -- or n-for-n, which is the single most misleading number this table could
    -- publish: 0 for 14 would advertise a conversion rate of 0.000 with a
    -- standard error of 0.000. The Wilson score interval does not degenerate at
    -- the boundary, so it is emitted alongside and is the interval to quote.
    -- Written out in closed form (z = 1.96) rather than via a UDF so the
    -- arithmetic stays visible in the SQL.
    CASE WHEN two_point_attempts > 0 THEN
        ((CAST(two_point_goals AS DOUBLE) + 1.9208)
          - 1.96 * SQRT(
              CAST(two_point_goals AS DOUBLE)
              * (1 - CAST(two_point_goals AS DOUBLE) / two_point_attempts)
              + 0.9604))
        / (two_point_attempts + 3.8416)
    END                                                                  AS two_point_conversion_wilson_low,
    CASE WHEN two_point_attempts > 0 THEN
        ((CAST(two_point_goals AS DOUBLE) + 1.9208)
          + 1.96 * SQRT(
              CAST(two_point_goals AS DOUBLE)
              * (1 - CAST(two_point_goals AS DOUBLE) / two_point_attempts)
              + 0.9604))
        / (two_point_attempts + 3.8416)
    END                                                                  AS two_point_conversion_wilson_high,
    CASE WHEN two_point_attempts >= 30 THEN 'adequate_for_a_group_estimate'
         WHEN two_point_attempts >= 10 THEN 'thin'
         ELSE                               'descriptive_only' END       AS two_point_sample_status
FROM agg
ORDER BY
    CASE scope WHEN 'LEAGUE' THEN 0 WHEN 'TEAM' THEN 1 WHEN 'GAME_STATE' THEN 2
               WHEN 'PERIOD' THEN 3 WHEN 'VOLUME_GROUP' THEN 4 ELSE 5 END,
    scope_key;
