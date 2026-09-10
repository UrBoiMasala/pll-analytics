-- Phase 5: possession-ambiguity sensitivity analysis.
--
-- Phase 4.25 left 36.2% of possessions flagged is_ambiguous and 3.6% flagged
-- is_truncated. Structural validation passing does NOT prove that a metric
-- built on those possessions is insensitive to the ambiguity, so this recomputes
-- the core possession-denominated metrics on three nested possession sets and
-- reports what actually moves:
--
--   full                        -- all 4,388 eligible possessions
--   non_ambiguous               -- is_ambiguous = FALSE (2,799)
--   non_ambiguous_non_truncated -- also not truncated (2,672)
--
-- Both numerator and denominator are taken from the SAME subset, so every
-- comparison is internally consistent. That forces one substitution: the
-- turnover metric here is possession_ending_turnover_rate (possessions closed
-- by a turnover / possessions in the subset), not the official-box-score
-- turnover_rate -- an official season total cannot be subset by possession
-- ambiguity, and pairing an unsubsettable numerator with a shrinking
-- denominator would manufacture a difference that is pure arithmetic.

CREATE OR REPLACE TABLE team_metric_sensitivity AS

WITH possession_sets AS (
    SELECT p.*, s.set_label
    FROM possessions p
    CROSS JOIN (VALUES ('full'), ('non_ambiguous'), ('non_ambiguous_non_truncated'))
               AS s(set_label)
    WHERE s.set_label = 'full'
       OR (s.set_label = 'non_ambiguous'               AND p.is_unambiguous)
       OR (s.set_label = 'non_ambiguous_non_truncated' AND p.is_high_confidence)
),

offense AS (
    SELECT set_label, offense_team_id AS team_id,
           COUNT(*)                                       AS offensive_possessions,
           SUM(points_scored)                             AS points_scored,
           SUM(shot_attempts)                             AS shot_attempts,
           SUM(ended_in_turnover)                         AS possession_ending_turnovers,
           COUNT(*) FILTER (WHERE has_two_point_attempt)  AS two_point_possessions
    FROM possession_sets GROUP BY set_label, offense_team_id
),

defense AS (
    SELECT set_label, defense_team_id AS team_id,
           COUNT(*)           AS defensive_possessions,
           SUM(points_scored) AS points_allowed
    FROM possession_sets GROUP BY set_label, defense_team_id
),

team_set AS (
    SELECT o.set_label, o.team_id,
           o.offensive_possessions, d.defensive_possessions,
           o.points_scored, d.points_allowed,
           o.shot_attempts, o.possession_ending_turnovers, o.two_point_possessions
    FROM offense o JOIN defense d USING (set_label, team_id)
),

-- Long form: one row per (set, team, metric). higher_is_better only drives
-- rank direction; for the volume metrics it is a stated convention, not a
-- claim that more is better lacrosse.
long AS (
    SELECT set_label, team_id, m.metric_name, m.metric_value, m.higher_is_better,
           CASE WHEN m.metric_name = 'defensive_efficiency' THEN defensive_possessions
                WHEN m.metric_name = 'net_efficiency'
                     THEN offensive_possessions + defensive_possessions
                ELSE offensive_possessions END AS n_possessions
    FROM team_set
    CROSS JOIN LATERAL (
        VALUES
            ('offensive_efficiency',
             points_scored  / CAST(offensive_possessions AS DOUBLE), TRUE),
            ('defensive_efficiency',
             points_allowed / CAST(defensive_possessions AS DOUBLE), FALSE),
            ('net_efficiency',
               points_scored  / CAST(offensive_possessions AS DOUBLE)
             - points_allowed / CAST(defensive_possessions AS DOUBLE), TRUE),
            ('shots_per_possession',
             shot_attempts / CAST(offensive_possessions AS DOUBLE), TRUE),
            ('possession_ending_turnover_rate',
             possession_ending_turnovers / CAST(offensive_possessions AS DOUBLE), FALSE),
            ('two_point_possession_rate',
             two_point_possessions / CAST(offensive_possessions AS DOUBLE), TRUE)
    ) AS m(metric_name, metric_value, higher_is_better)
),

ranked AS (
    SELECT *,
           RANK() OVER (
               PARTITION BY set_label, metric_name
               ORDER BY CASE WHEN higher_is_better THEN -metric_value ELSE metric_value END
           ) AS rank_value
    FROM long
)

SELECT
    hc.set_label                                   AS comparison_set,
    hc.metric_name,
    hc.higher_is_better,
    hc.team_id,
    f.metric_value                                 AS full_value,
    hc.metric_value                                AS high_confidence_value,
    hc.metric_value - f.metric_value               AS absolute_difference,
    (hc.metric_value - f.metric_value) / NULLIF(ABS(f.metric_value), 0) AS relative_difference,
    f.rank_value                                   AS rank_full,
    hc.rank_value                                  AS rank_high_confidence,
    hc.rank_value - f.rank_value                   AS rank_change,
    f.n_possessions                                AS n_possessions_full,
    hc.n_possessions                               AS n_possessions_high_confidence,
    hc.n_possessions / CAST(f.n_possessions AS DOUBLE) AS possession_retention_rate
FROM ranked hc
JOIN ranked f
  ON f.set_label = 'full'
 AND f.team_id = hc.team_id
 AND f.metric_name = hc.metric_name
WHERE hc.set_label <> 'full'
ORDER BY hc.set_label, hc.metric_name, hc.team_id;
