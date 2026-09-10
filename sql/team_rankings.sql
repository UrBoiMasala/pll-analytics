-- Phase 5: season team rankings.
--
-- Long format: one row per (metric, team). Long rather than wide so a new
-- metric is one UNPIVOT entry rather than three new columns, and so the
-- direction convention is stored as data on every row instead of living only
-- in documentation.
--
-- RANK() (not DENSE_RANK) is used deliberately: with 8 teams, competition
-- ranking is the right semantics -- if two teams tie for 1st there is no 2nd,
-- and rank_value still reads directly as "how many teams are ahead of you,
-- plus one". DENSE_RANK would compress the scale and make "3rd of 8" mean
-- different things depending on how many ties happened above.
--
-- higher_is_better = FALSE metrics (defensive_efficiency, turnover_rate) are
-- ranked ascending, so rank 1 is always the best team on every row.
--
-- No composite "best team" rating is produced -- that is explicitly deferred.

CREATE OR REPLACE TABLE team_rankings AS

WITH metrics AS (
    SELECT team_id, team_name, games_played, m.metric_name, m.metric_value, m.higher_is_better
    FROM team_season_advanced
    CROSS JOIN LATERAL (
        VALUES
            ('offensive_efficiency',                offensive_efficiency,                TRUE),
            ('defensive_efficiency',                defensive_efficiency,                FALSE),
            ('net_efficiency',                      net_efficiency,                      TRUE),
            ('turnover_rate',                       turnover_rate,                       FALSE),
            ('possession_ending_turnover_rate',     possession_ending_turnover_rate,     FALSE),
            ('shooting_pct',                        shooting_pct,                        TRUE),
            ('points_per_shot',                     points_per_shot,                     TRUE),
            ('shots_per_possession',                shots_per_possession,                TRUE),
            ('two_point_attempt_rate',              two_point_attempt_rate,              TRUE),
            ('two_point_conversion_pct',            two_point_conversion_pct,            TRUE),
            ('points_per_two_point_attempt',        points_per_two_point_attempt,        TRUE),
            ('two_point_possession_rate',           two_point_possession_rate,           TRUE),
            ('faceoff_win_pct',                     faceoff_win_pct,                     TRUE),
            ('faceoff_start_possession_share',      faceoff_start_possession_share,      TRUE),
            -- The Phase 5 brief asks for man_up_points_per_possession. The feed
            -- cannot identify which possessions were played man-up (its man-up
            -- tag lands on goals only), so the extra-man OPPORTUNITY is used as
            -- the denominator instead -- the closest supportable analogue.
            ('man_up_points_per_opportunity',       man_up_points_per_opportunity,       TRUE),
            ('man_up_goals_per_opportunity',        man_up_goals_per_opportunity,        TRUE),
            ('man_up_shooting_pct',                 man_up_shooting_pct,                 TRUE),
            ('team_possessions_per_game',           team_possessions_per_game,           TRUE),
            ('ground_balls_per_possession',         ground_balls_per_possession,         TRUE),
            ('save_pct_official',                   save_pct_official,                   TRUE),
            ('turnovers_forced_per_defensive_possession', turnovers_forced_per_defensive_possession, TRUE),
            ('shots_allowed_per_possession',        shots_allowed_per_possession,        FALSE),
            ('shot_clock_expiration_rate',          shot_clock_expiration_rate,          FALSE)
    ) AS m(metric_name, metric_value, higher_is_better)
)

SELECT
    metric_name,
    higher_is_better,
    team_id,
    team_name,
    games_played,
    metric_value,
    RANK() OVER (
        PARTITION BY metric_name
        ORDER BY CASE WHEN higher_is_better THEN -metric_value ELSE metric_value END
    ) AS rank_value,
    COUNT(*)  OVER (PARTITION BY metric_name) AS n_teams,
    AVG(metric_value) OVER (PARTITION BY metric_name) AS league_mean,
    metric_value - AVG(metric_value) OVER (PARTITION BY metric_name) AS diff_from_league_mean,
    -- Population stddev over the 8 teams: this is the full league, not a
    -- sample drawn from one, so STDDEV_POP is the correct denominator.
    CASE WHEN STDDEV_POP(metric_value) OVER (PARTITION BY metric_name) = 0 THEN NULL
         ELSE (metric_value - AVG(metric_value) OVER (PARTITION BY metric_name))
              / STDDEV_POP(metric_value) OVER (PARTITION BY metric_name)
    END AS z_score
FROM metrics
ORDER BY metric_name, rank_value, team_id;
