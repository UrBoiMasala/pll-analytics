-- Phase 8: team leaderboards, long/tidy.
--
-- One row per (category, metric, team). Long rather than a pile of wide CSVs so
-- a consumer filters instead of joining, and so the direction convention, the
-- denominator and the sample size all travel as DATA on every row rather than
-- living in documentation that a chart can be built without reading.
--
-- Differences from Phase 5's team_rankings.csv, which is NOT replaced:
--   * every row carries its DENOMINATOR by name and value, which is the single
--     rule the Phase 8 brief makes non-negotiable for leaderboards;
--   * a category, so the eight logical leaderboards are addressable;
--   * league median as well as mean, because 8-team distributions are small
--     enough for one team to move the mean visibly;
--   * the gap to the next-ranked team and an explicit tie flag, because the
--     Phase 5 null model established that small rank gaps over 12-13 games are
--     not meaningful and a leaderboard that hides the gap invites reading them
--     as if they were;
--   * rank_stability, joined from Phase 5's possession sensitivity analysis, so
--     a possession-denominated ranking says out loud whether it survived the
--     high-confidence-possession subset.
--
-- RANK() (competition ranking), matching Phase 5: with 8 teams, if two tie for
-- 1st there is no 2nd, and rank reads as "teams ahead of you, plus one".

CREATE OR REPLACE TABLE team_leaderboards_2026 AS

WITH metrics AS (
    SELECT
        t.team_id, t.team_name, t.games_played,
        m.category, m.metric_name, m.metric_value, m.higher_is_better,
        m.denominator_name, m.denominator_value
    FROM team_stats_2026 t
    CROSS JOIN LATERAL (
        VALUES
        -- ---------------- OFFENSE ----------------
        ('offense', 'offensive_efficiency',            offensive_efficiency,            TRUE,  'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),
        ('offense', 'points_per_game',                 points_per_game,                 TRUE,  'games_played',          CAST(games_played AS DOUBLE)),
        ('offense', 'goals_per_possession',            goals_per_possession,            TRUE,  'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),
        ('offense', 'net_efficiency',                  net_efficiency,                  TRUE,  'offensive+defensive_possessions', CAST(offensive_possessions + defensive_possessions AS DOUBLE)),
        ('offense', 'point_differential_per_game',     point_differential_per_game,     TRUE,  'games_played',          CAST(games_played AS DOUBLE)),

        -- ---------------- DEFENSE ----------------
        ('defense', 'defensive_efficiency',            defensive_efficiency,            FALSE, 'defensive_possessions', CAST(defensive_possessions AS DOUBLE)),
        ('defense', 'points_allowed_per_game',         points_allowed_per_game,         FALSE, 'games_played',          CAST(games_played AS DOUBLE)),
        ('defense', 'shots_allowed_per_possession',    shots_allowed_per_possession,    FALSE, 'defensive_possessions', CAST(defensive_possessions AS DOUBLE)),
        ('defense', 'opponent_shooting_pct',           opponent_shooting_pct,           FALSE, 'shots_allowed',         CAST(shots_allowed AS DOUBLE)),
        ('defense', 'turnovers_forced_per_defensive_possession', turnovers_forced_per_defensive_possession, TRUE, 'defensive_possessions', CAST(defensive_possessions AS DOUBLE)),

        -- ---------------- SHOOTING ----------------
        ('shooting', 'shooting_pct',                   shooting_pct,                    TRUE,  'shots',                 CAST(shots AS DOUBLE)),
        ('shooting', 'points_per_shot',                points_per_shot,                 TRUE,  'shots',                 CAST(shots AS DOUBLE)),
        ('shooting', 'shots_on_goal_pct',              shots_on_goal_pct,               TRUE,  'shots',                 CAST(shots AS DOUBLE)),
        ('shooting', 'goals_per_shot_on_goal',         goals_per_shot_on_goal,          TRUE,  'shots_on_goal',         CAST(shots_on_goal AS DOUBLE)),
        ('shooting', 'shots_per_possession',           shots_per_possession,            TRUE,  'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),

        -- ---------------- POSSESSION ----------------
        ('possession', 'team_possessions_per_game',    team_possessions_per_game,       TRUE,  'games_played',          CAST(games_played AS DOUBLE)),
        ('possession', 'turnover_rate',                turnover_rate,                   FALSE, 'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),
        ('possession', 'possession_ending_turnover_rate', possession_ending_turnover_rate, FALSE, 'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),
        ('possession', 'shot_clock_expiration_rate',   shot_clock_expiration_rate,      FALSE, 'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),
        ('possession', 'ground_balls_per_possession',  ground_balls_per_possession,     TRUE,  'offensive+defensive_possessions', CAST(offensive_possessions + defensive_possessions AS DOUBLE)),
        ('possession', 'faceoff_start_possession_share', faceoff_start_possession_share, TRUE, 'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),

        -- ---------------- FACEOFF ----------------
        ('faceoff', 'faceoff_win_pct',                 faceoff_win_pct,                 TRUE,  'faceoffs',              CAST(faceoffs AS DOUBLE)),

        -- ---------------- GOALIE / TEAM DEFENCE ----------------
        ('goalie_defense', 'save_pct_official',        save_pct_official,               TRUE,  'saves+goals_allowed',   CAST(saves + goals_allowed AS DOUBLE)),
        ('goalie_defense', 'save_pct_vs_shots_on_goal', save_pct_vs_shots_on_goal,      TRUE,  'shots_on_goal_allowed', CAST(shots_on_goal_allowed AS DOUBLE)),
        ('goalie_defense', 'opponent_shooting_pct_on_goal', opponent_shooting_pct_on_goal, FALSE, 'shots_on_goal_allowed', CAST(shots_on_goal_allowed AS DOUBLE)),

        -- ---------------- TWO-POINT (PLL-specific) ----------------
        ('two_point', 'two_point_attempt_rate',        two_point_attempt_rate,          TRUE,  'shots',                 CAST(shots AS DOUBLE)),
        ('two_point', 'two_point_conversion_pct',      two_point_conversion_pct,        TRUE,  'two_point_attempts',    CAST(two_point_attempts AS DOUBLE)),
        ('two_point', 'points_per_two_point_attempt', points_per_two_point_attempt,     TRUE,  'two_point_attempts',    CAST(two_point_attempts AS DOUBLE)),
        ('two_point', 'two_point_points_share',        two_point_points_share,          TRUE,  'points',                CAST(points AS DOUBLE)),
        ('two_point', 'two_point_minus_one_point_return', two_point_minus_one_point_return, TRUE, 'two_point_attempts', CAST(two_point_attempts AS DOUBLE)),
        ('two_point', 'two_point_possession_rate',     two_point_possession_rate,       TRUE,  'offensive_possessions', CAST(offensive_possessions AS DOUBLE)),

        -- ---------------- EXTRA MAN (opportunity-denominated only) ----------------
        ('extra_man', 'man_up_points_per_opportunity', man_up_points_per_opportunity,   TRUE,  'man_up_opportunities',  CAST(man_up_opportunities AS DOUBLE)),
        ('extra_man', 'man_up_goals_per_opportunity',  man_up_goals_per_opportunity,    TRUE,  'man_up_opportunities',  CAST(man_up_opportunities AS DOUBLE)),
        ('extra_man', 'man_up_shooting_pct',           man_up_shooting_pct,             TRUE,  'man_up_shots',          CAST(man_up_shots AS DOUBLE)),
        ('extra_man', 'man_down_goals_allowed_per_opportunity', man_down_goals_allowed_per_opportunity, FALSE, 'man_down_opportunities', CAST(man_down_opportunities AS DOUBLE))
    ) AS m(category, metric_name, metric_value, higher_is_better, denominator_name, denominator_value)
),

ranked AS (
    SELECT
        category, metric_name, higher_is_better,
        team_id, team_name, games_played,
        metric_value, denominator_name, denominator_value,
        -- Rounded to 12 decimals before ranking, matching the player
        -- leaderboards: a difference below 1e-12 is floating-point residue from
        -- a division, not a difference between two teams. metric_value itself is
        -- published at full precision.
        RANK() OVER (PARTITION BY metric_name
                     ORDER BY ROUND(CASE WHEN higher_is_better THEN -metric_value ELSE metric_value END, 12)
                    ) AS rank_value,
        COUNT(*)          OVER (PARTITION BY metric_name) AS n_teams,
        AVG(metric_value) OVER (PARTITION BY metric_name) AS league_mean,
        MEDIAN(metric_value) OVER (PARTITION BY metric_name) AS league_median,
        STDDEV_POP(metric_value) OVER (PARTITION BY metric_name) AS league_sd,
        MIN(metric_value) OVER (PARTITION BY metric_name) AS league_min,
        MAX(metric_value) OVER (PARTITION BY metric_name) AS league_max,
        -- next team in leaderboard order, for the adjacent-rank gap
        LEAD(metric_value) OVER (
            PARTITION BY metric_name
            ORDER BY ROUND(CASE WHEN higher_is_better THEN -metric_value ELSE metric_value END, 12), team_id
        ) AS next_team_value
    FROM metrics
),

-- Phase 5's possession-sensitivity result, at metric grain: did restricting to
-- high-confidence possessions move any team's rank? Joined, not recomputed.
stability AS (
    SELECT metric_name,
           MAX(ABS(rank_change))       AS max_rank_change_high_confidence,
           SUM(CASE WHEN rank_change <> 0 THEN 1 ELSE 0 END) AS teams_changing_rank_high_confidence
    FROM p8_sensitivity
    WHERE comparison_set = 'non_ambiguous_non_truncated'
    GROUP BY metric_name
)

SELECT
    r.category,
    r.metric_name,
    r.higher_is_better,
    r.rank_value                                     AS rank,
    r.n_teams,
    r.team_id,
    r.team_name,
    r.games_played,
    r.metric_value,
    r.denominator_name,
    r.denominator_value,
    r.league_mean,
    r.league_median,
    r.league_sd,
    r.league_min,
    r.league_max,
    CASE WHEN r.league_sd = 0 THEN NULL
         ELSE (r.metric_value - r.league_mean) / r.league_sd END AS z_score,
    ABS(r.metric_value - r.next_team_value)          AS gap_to_next_rank,
    COUNT(*) OVER (PARTITION BY r.metric_name, ROUND(r.metric_value, 12)) > 1 AS is_tie,
    s.teams_changing_rank_high_confidence,
    s.max_rank_change_high_confidence,
    CASE
        WHEN s.metric_name IS NULL THEN 'not_covered_by_the_possession_sensitivity_analysis'
        ELSE 'possession-ambiguity rank churn was tested by the Phase 5 null model and was not '
             || 'significant for any metric (p 0.135-0.922); levels ARE subset-dependent'
    END                                              AS rank_stability_note
FROM ranked r
LEFT JOIN stability s USING (metric_name)
ORDER BY r.category, r.metric_name, r.rank_value, r.team_id;
