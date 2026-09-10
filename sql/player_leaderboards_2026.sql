-- Phase 8: player leaderboards, long/tidy.
--
-- One row per (category, metric, scope, player). Two scopes per metric:
--
--   scope = 'ALL'        every player for whom the metric is defined, ranked.
--                        This is the descriptive record. A player who went 3
--                        for 3 appears here at rank 1 with attempts = 3 on the
--                        same row, which is exactly why the denominator is
--                        mandatory rather than optional.
--   scope = 'QUALIFIED'  only players who clear the metric's evidence gate,
--                        re-ranked among themselves. Absent for a metric whose
--                        gate nobody can clear -- and for two-point rates that
--                        absence IS the finding, not an omission.
--
-- NO THRESHOLD HERE IS A ROUND NUMBER CHOSEN FOR CONVENIENCE. Every gate is
-- either (a) empirical-Bayes reliability >= 0.5 -- the point at which the
-- posterior puts more weight on the player's own record than on the league
-- prior, with the implied trial count set separately by each rate's own prior
-- strength (15.9 draws / 70.8 shots / 75.3 one-point attempts / 108.8 touches /
-- 300.3 save-percentage trials) -- or (b) a Phase 7 eligibility flag built on
-- the same rule, or (c) "none: this is a counting statistic and a count needs
-- no evidence gate". The turnovers-per-touch prior strength is the one number
-- estimated in Phase 8; it uses Phase 6's own beta_prior_by_moments estimator,
-- imported and not reimplemented, and arrives through p8_derived_thresholds.
--
-- ON THE GOALIE TRIAL BASE. save_pct is saves / (saves + goals_allowed) -- the
-- official definition -- and Phase 7 estimated its prior on exactly that base
-- (2,412 league trials, max 309). shots_on_goal_faced is a DIFFERENT and
-- larger count (2,567): the event log records shots on goal that the official
-- box score resolves as neither a save nor a goal. Every save-rate row here
-- therefore carries saves+goals_allowed as its denominator, and only the
-- genuinely per-shot goalie value metrics carry shots_on_goal_faced.
--
-- Raw and shrunk are separate rows, never one column that silently switched.
-- Where a shrunk counterpart exists it also travels on the raw row (and vice
-- versa) as companion_metric_name / companion_metric_value, so a consumer
-- cannot see one without seeing the other.
--
-- EVERY ROW CARRIES A POSITION RANK as well as an overall rank. EPA_points_raw
-- is class C -- not cross-position comparable -- so an overall rank on it is a
-- record of the season, not a ranking of players. position_rank is the reading
-- that is defensible, and it sits on the same row so a consumer cannot take one
-- without seeing the other.

CREATE OR REPLACE TABLE player_leaderboards_2026 AS

WITH thr AS (SELECT * FROM p8_derived_thresholds),

-- The opportunity base an all-components value total is actually earned on.
-- EPA_points_raw has no single denominator -- that is the whole reason it is
-- class C -- so rather than emitting NULL and leaving the sample size off the
-- leaderboard, each player carries the count of the opportunities his own role
-- supplies, NAMED, so a goalie's 332 shots faced is never read as commensurate
-- with an attackman's 214 offensive opportunities.
role_base AS (
    SELECT
        player_id,
        CASE value_role
            WHEN 'goalie'  THEN 'shots_on_goal_faced (goalie role base)'
            WHEN 'faceoff' THEN 'faceoffs (faceoff role base)'
            ELSE 'recorded_offensive_opportunities (field role base)'
        END AS role_denominator_name,
        CAST(CASE value_role
            WHEN 'goalie'  THEN shots_on_goal_faced
            WHEN 'faceoff' THEN faceoffs
            ELSE recorded_offensive_opportunities
        END AS DOUBLE) AS role_denominator_value
    FROM player_stats_2026
),

metrics AS (
    SELECT
        p.player_id, p.player_name, p.team_id,
        p.canonical_position, p.position_group, p.value_role, p.games_played,
        m.*
    FROM player_stats_2026 p
    JOIN role_base rb USING (player_id)
    CROSS JOIN thr
    CROSS JOIN LATERAL (
        VALUES
        -- =============== SCORING (counting stats: no evidence gate) ===============
        ('scoring', 'scoring_points',        p.scoring_points,       TRUE,  'games_played', CAST(p.games_played AS DOUBLE), TRUE,  'NONE_COUNTING', 'raw',   NULL, NULL::DOUBLE, NULL::DOUBLE, NULL::VARCHAR),
        ('scoring', 'goals',                 CAST(p.goals AS DOUBLE),TRUE,  'games_played', CAST(p.games_played AS DOUBLE), TRUE,  'NONE_COUNTING', 'raw',   NULL, NULL, NULL, NULL),
        ('scoring', 'one_point_goals',       CAST(p.one_point_goals AS DOUBLE), TRUE, 'one_point_attempts', CAST(p.one_point_attempts AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('scoring', 'two_point_goals',       CAST(p.two_point_goals AS DOUBLE), TRUE, 'two_point_attempts', CAST(p.two_point_attempts AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('scoring', 'official_assists',      CAST(p.official_assists AS DOUBLE), TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('scoring', 'scoring_points_per_game', CAST(p.scoring_points AS DOUBLE) / NULLIF(p.games_played,0), TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),

        -- =============== SHOOTING ===============
        ('shooting', 'shots',                CAST(p.shots AS DOUBLE), TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('shooting', 'shooting_pct',         p.shooting_pct,          TRUE, 'shots', CAST(p.shots AS DOUBLE),
             p.shooting_reliability >= 0.5, 'SHOOTING_RELIABILITY_HALF', 'raw',
             'shooting_rate_shrunk', p.shooting_rate_shrunk, p.shooting_reliability, 'shooting_reliability'),
        ('shooting', 'shooting_rate_shrunk', p.shooting_rate_shrunk,  TRUE, 'shots', CAST(p.shots AS DOUBLE),
             p.shots > 0, 'ANY_TRIAL_SHRUNK', 'shrunk',
             'shooting_pct', p.shooting_pct, p.shooting_reliability, 'shooting_reliability'),
        ('shooting', 'one_point_conversion_pct', p.one_point_conversion_pct, TRUE, 'one_point_attempts', CAST(p.one_point_attempts AS DOUBLE),
             p.one_point_reliability >= 0.5, 'ONE_POINT_RELIABILITY_HALF', 'raw',
             'one_point_rate_shrunk', p.one_point_rate_shrunk, p.one_point_reliability, 'one_point_reliability'),
        ('shooting', 'points_per_shot',      p.points_per_shot,       TRUE, 'shots', CAST(p.shots AS DOUBLE),
             p.shooting_reliability >= 0.5, 'SHOOTING_RELIABILITY_HALF', 'raw', NULL, NULL, p.shooting_reliability, 'shooting_reliability'),
        ('shooting', 'shots_on_goal_pct',    p.shots_on_goal_pct,     TRUE, 'shots', CAST(p.shots AS DOUBLE),
             p.shooting_reliability >= 0.5, 'SHOOTING_RELIABILITY_HALF', 'raw', NULL, NULL, p.shooting_reliability, 'shooting_reliability'),

        -- =============== TWO-POINT: DESCRIPTIVE ONLY, NEVER QUALIFIED ===============
        -- Phase 6/7 established the 2026 between-player two-point variance is
        -- SMALLER than binomial noise alone predicts. The prior strength is
        -- capped at 1e6, every shrunk rate is the league mean and every
        -- reliability is < 0.001. There is therefore no evidence gate any
        -- player can clear, and no QUALIFIED scope is emitted for this rate.
        ('two_point_descriptive', 'two_point_conversion_pct', p.two_point_conversion_pct, TRUE,
             'two_point_attempts', CAST(p.two_point_attempts AS DOUBLE),
             FALSE, 'NOT_QUALIFIABLE_TWO_POINT', 'raw', NULL, NULL, p.two_point_reliability, 'two_point_reliability'),
        ('two_point_descriptive', 'two_point_attempts', CAST(p.two_point_attempts AS DOUBLE), TRUE,
             'shots', CAST(p.shots AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),

        -- =============== OFFENSIVE EFFICIENCY (Phase 7 gate) ===============
        ('offensive_efficiency', 'EPA_per_recorded_opportunity', p.EPA_per_recorded_opportunity, TRUE,
             'recorded_offensive_opportunities', CAST(p.recorded_offensive_opportunities AS DOUBLE),
             p.offensive_rate_ranking_eligible, 'OFFENSIVE_RATE_RANKING_ELIGIBLE', 'raw', NULL, NULL,
             p.shooting_reliability, 'shooting_reliability'),
        ('offensive_efficiency', 'shooting_EPA_per_shot', p.shooting_EPA_per_shot, TRUE,
             'shots', CAST(p.shots AS DOUBLE),
             p.offensive_rate_ranking_eligible, 'OFFENSIVE_RATE_RANKING_ELIGIBLE', 'raw', NULL, NULL,
             p.shooting_reliability, 'shooting_reliability'),

        -- =============== OFFENSIVE VALUE (totals: volume, not a rate) ===============
        ('offensive_value', 'shooting_value_raw',        p.shooting_value_raw,        TRUE, 'shots', CAST(p.shots AS DOUBLE), p.shots > 0, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, p.shooting_reliability, 'shooting_reliability'),
        ('offensive_value', 'offensive_EPA_points_raw',  p.offensive_EPA_points_raw,  TRUE, 'recorded_offensive_opportunities', CAST(p.recorded_offensive_opportunities AS DOUBLE), TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, NULL, NULL),
        ('offensive_value', 'shooting_value_null_z',     p.shooting_value_null_z,     TRUE, 'shots', CAST(p.shots AS DOUBLE), p.shots > 0, 'DESCRIPTIVE_VALUE_TOTAL', 'chance_standardized', NULL, NULL, NULL, NULL),

        -- =============== USAGE (a volume measure; never a value) ===============
        ('usage', 'offensive_play_share',              p.offensive_play_share,             TRUE, 'team_recorded_offensive_opportunities_in_games_played', CAST(p.recorded_offensive_opportunities AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('usage', 'recorded_offensive_opportunities',  CAST(p.recorded_offensive_opportunities AS DOUBLE), TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('usage', 'EPA_vs_usage_expectation',          p.EPA_vs_usage_expectation,         TRUE, 'recorded_offensive_opportunities', CAST(p.recorded_offensive_opportunities AS DOUBLE), TRUE, 'USAGE_MODEL_POPULATION', 'raw', NULL, NULL, NULL, NULL),

        -- =============== TURNOVERS ===============
        ('turnovers', 'turnovers',           CAST(p.turnovers AS DOUBLE), FALSE, 'touches', CAST(p.touches AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('turnovers', 'turnovers_per_touch', p.turnovers_per_touch,       FALSE, 'touches', CAST(p.touches AS DOUBLE),
             CAST(p.touches AS DOUBLE) >= thr.turnover_rate_min_touches, 'TURNOVER_RATE_RELIABILITY_HALF', 'raw', NULL, NULL,
             CAST(p.touches AS DOUBLE) / NULLIF(CAST(p.touches AS DOUBLE) + thr.turnover_rate_kappa, 0), 'turnover_rate_reliability'),
        ('turnovers', 'turnover_value_raw',  p.turnover_value_raw,        TRUE,  'touches', CAST(p.touches AS DOUBLE), TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, NULL, NULL),

        -- =============== FACEOFF ===============
        ('faceoff', 'faceoff_win_pct',       p.faceoff_win_pct,       TRUE, 'faceoffs', CAST(p.faceoffs AS DOUBLE),
             p.faceoff_reliability >= 0.5, 'FACEOFF_RELIABILITY_HALF', 'raw',
             'faceoff_rate_shrunk', p.faceoff_rate_shrunk, p.faceoff_reliability, 'faceoff_reliability'),
        ('faceoff', 'faceoff_rate_shrunk',   p.faceoff_rate_shrunk,   TRUE, 'faceoffs', CAST(p.faceoffs AS DOUBLE),
             p.faceoffs > 0, 'ANY_TRIAL_SHRUNK', 'shrunk',
             'faceoff_win_pct', p.faceoff_win_pct, p.faceoff_reliability, 'faceoff_reliability'),
        ('faceoff', 'faceoff_value_raw',     p.faceoff_value_raw,     TRUE, 'faceoffs', CAST(p.faceoffs AS DOUBLE), p.faceoffs > 0, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, p.faceoff_reliability, 'faceoff_reliability'),
        ('faceoff', 'faceoff_EPA_per_faceoff', p.faceoff_EPA_per_faceoff, TRUE, 'faceoffs', CAST(p.faceoffs AS DOUBLE),
             p.faceoff_reliability >= 0.5, 'FACEOFF_RELIABILITY_HALF', 'raw', NULL, NULL, p.faceoff_reliability, 'faceoff_reliability'),

        -- =============== GOALIE ===============
        -- The QUALIFIED save-percentage leaderboard has exactly ONE eligible
        -- goalie in 2026. That is the correct output of the rule, not a bug:
        -- the busiest keeper in the league faced 332 shots on goal against a
        -- prior strength of 300. It is documented rather than worked around.
        ('goalie', 'save_pct',               p.save_pct,              TRUE, 'saves+goals_allowed', CAST(p.saves + p.goals_allowed AS DOUBLE),
             p.save_reliability >= 0.5, 'SAVE_RELIABILITY_HALF', 'raw',
             'save_rate_shrunk', p.save_rate_shrunk, p.save_reliability, 'save_reliability'),
        ('goalie', 'save_rate_shrunk',       p.save_rate_shrunk,      TRUE, 'saves+goals_allowed', CAST(p.saves + p.goals_allowed AS DOUBLE),
             p.saves + p.goals_allowed > 0, 'ANY_TRIAL_SHRUNK', 'shrunk',
             'save_pct', p.save_pct, p.save_reliability, 'save_reliability'),
        ('goalie', 'goalie_value_raw',       p.goalie_value_raw,      TRUE, 'shots_on_goal_faced', CAST(p.shots_on_goal_faced AS DOUBLE), p.shots_on_goal_faced > 0, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, p.save_reliability, 'save_reliability'),
        ('goalie', 'goalie_EPA_per_SOG',     p.goalie_EPA_per_SOG,    TRUE, 'shots_on_goal_faced', CAST(p.shots_on_goal_faced AS DOUBLE),
             p.save_reliability >= 0.5, 'SAVE_RELIABILITY_HALF', 'raw', NULL, NULL, p.save_reliability, 'save_reliability'),
        ('goalie', 'goalie_value_null_z',    p.goalie_value_null_z,   TRUE, 'shots_on_goal_faced', CAST(p.shots_on_goal_faced AS DOUBLE), p.shots_on_goal_faced > 0, 'DESCRIPTIVE_VALUE_TOTAL', 'chance_standardized', NULL, NULL, NULL, NULL),

        -- =============== PARTIAL DEFENCE ===============
        -- "partial" is in every name on purpose. A value near zero means
        -- "caused turnovers at the position group's per-game rate", NOT
        -- "an average defender".
        ('partial_defense', 'caused_turnovers', CAST(p.caused_turnovers AS DOUBLE), TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'NONE_COUNTING', 'raw', NULL, NULL, NULL, NULL),
        ('partial_defense', 'defensive_value_partial_raw', p.defensive_value_partial_raw, TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, NULL, NULL),
        ('partial_defense', 'defensive_EPA_partial_per_game', p.defensive_EPA_partial_per_game, TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, NULL, NULL),

        -- =============== WITHIN-POSITION ADVANCED VALUE ===============
        -- EPA_points_raw is class C: NOT cross-position comparable. It is
        -- emitted because it is the retrospective record of 2026, and every row
        -- carries canonical_position so a consumer partitions before reading.
        ('within_position_value', 'EPA_points_raw',          p.EPA_points_raw,          TRUE, rb.role_denominator_name, rb.role_denominator_value, TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, p.role_rate_reliability, 'role_rate_reliability'),
        ('within_position_value', 'EPA_points_null_z',       p.EPA_points_null_z,       TRUE, rb.role_denominator_name, rb.role_denominator_value, TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'chance_standardized', NULL, NULL, NULL, NULL),
        ('within_position_value', 'EPA_position_percentile', p.EPA_position_percentile, TRUE, 'position_n_players', CAST(p.position_n_players AS DOUBLE), TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'within_position', NULL, NULL, NULL, NULL),
        ('within_position_value', 'EPA_points_per_game',     p.EPA_points_per_game,     TRUE, 'games_played', CAST(p.games_played AS DOUBLE), TRUE, 'DESCRIPTIVE_VALUE_TOTAL', 'raw', NULL, NULL, NULL, NULL)
    ) AS m(category, metric_name, metric_value, higher_is_better,
           denominator_name, denominator_value,
           qualifies, qualification_rule, raw_or_shrunk,
           companion_metric_name, companion_metric_value,
           reliability_value, reliability_name)
    WHERE m.metric_value IS NOT NULL
),

scoped AS (
    SELECT *, 'ALL' AS scope FROM metrics
    UNION ALL
    SELECT *, 'QUALIFIED' AS scope FROM metrics WHERE qualifies
),

-- RANKING IS DONE ON THE VALUE ROUNDED TO 12 DECIMALS, and the reason is a real
-- defect that ranking on the raw double produced. Phase 7 computes a per-game
-- value as (rate * games) / games, so two players who caused zero turnovers in
-- different numbers of games get values that are equal in every meaningful
-- sense and differ in the last unit in the last place. Ranking the raw doubles
-- split 40 identical defensive values into a group of 8 at rank 128 and a group
-- of 32 at rank 136, asserting that eight players were strictly better than
-- thirty-two others on a difference of 1e-17. metric_value is published at full
-- precision; only the ORDER BY key is rounded, and 1e-12 is far below the
-- resolution of any real difference in this system (the finest is a rate over a
-- denominator in the hundreds).
ranked AS (
    SELECT
        s.*,
        RANK() OVER (PARTITION BY s.scope, s.metric_name
                     ORDER BY ROUND(CASE WHEN s.higher_is_better THEN -s.metric_value ELSE s.metric_value END, 12)
                    ) AS rank_value,
        COUNT(*)              OVER (PARTITION BY s.scope, s.metric_name) AS n_ranked,
        AVG(s.metric_value)   OVER (PARTITION BY s.scope, s.metric_name) AS scope_mean,
        MEDIAN(s.metric_value) OVER (PARTITION BY s.scope, s.metric_name) AS scope_median,
        -- the within-position reading, on the same row as the overall one
        RANK() OVER (PARTITION BY s.scope, s.metric_name, s.canonical_position
                     ORDER BY ROUND(CASE WHEN s.higher_is_better THEN -s.metric_value ELSE s.metric_value END, 12)
                    ) AS position_rank_value,
        COUNT(*) OVER (PARTITION BY s.scope, s.metric_name, s.canonical_position)
                     AS position_n_ranked
    FROM scoped s
)

SELECT
    r.category,
    r.metric_name,
    r.scope,
    r.higher_is_better,
    r.raw_or_shrunk,
    r.rank_value                    AS rank,
    r.n_ranked,
    r.position_rank_value           AS position_rank,
    r.position_n_ranked,
    r.player_id,
    r.player_name,
    r.team_id,
    r.canonical_position,
    r.position_group,
    r.value_role,
    r.games_played,
    r.metric_value,
    r.denominator_name,
    r.denominator_value,
    r.scope_mean,
    r.scope_median,
    r.reliability_name,
    r.reliability_value,
    r.qualifies                     AS is_qualified,
    r.qualification_rule,
    q.qualification_reason,
    r.companion_metric_name,
    r.companion_metric_value
FROM ranked r
LEFT JOIN p8_qualification_rules q ON q.qualification_rule = r.qualification_rule
ORDER BY r.category, r.metric_name, r.scope, r.rank_value, r.player_id;
