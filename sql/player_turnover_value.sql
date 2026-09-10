-- Phase 6: turnover value (possession security).
--
--   turnover_value = -(turnovers - expected_turnovers) * points_per_turnover
--   expected_turnovers = touches * league turnovers-per-touch for the player's
--                        baseline group
--
-- Why a residual and not simply -(turnovers * cost). A raw turnover charge
-- punishes volume: an attackman with 400 touches will always look worse than a
-- close defender with 80, which measures role, not performance. Charging only
-- the turnovers ABOVE what an average player of that role commits on the same
-- number of touches puts the component on the same "relative to league-average
-- opportunity" footing as every other component in this framework, so the
-- pieces can be added together.
--
-- points_per_turnover is the empirical net-points swing associated with a
-- turnover over the following 60 seconds of play, net of the neutral reference
-- (see scripts/pll_player_value_models.py), taken as a positive magnitude and
-- applied with a negative sign.
--
-- WHY THIS DOES NOT DOUBLE-COUNT SHOOTING VALUE. The two components are
-- disjoint by opportunity class. shooting_value is computed over shot
-- ATTEMPTS and values only conversion relative to the league rate for those
-- attempts; it never credits or charges the possession itself. turnover_value
-- is computed over TOUCHES and never touches a shot outcome. A possession that
-- ends in a turnover after two missed shots contributes to shooting_value
-- through those two attempts (each already carrying its own league
-- expectation) and to turnover_value through the one turnover -- two different
-- events, valued once each. See docs/PLAYER_VALUE_ACCOUNTING.md scenarios A
-- and D.
--
-- KNOWN LIMITATION, carried on the output. Player-attributed turnovers sum to
-- 1,369 against a team-level official total of 1,699: roughly 19% of the
-- league's turnovers are credited to no player at all, because the feed's
-- turnover descriptions carry only a team ("Turnover by <TEAM>"). No player is
-- charged for those. The baseline is computed from the same player-level data,
-- so numerator and denominator are consistent, but the absolute magnitude of
-- every player's turnover load is understated.

CREATE OR REPLACE TABLE player_turnover_value AS
WITH group_rates AS (
    SELECT
        REPLACE(baseline_name, 'turnovers_per_touch__', '') AS baseline_group,
        baseline_value                                      AS turnovers_per_touch
    FROM player_value_baselines
    WHERE baseline_name LIKE 'turnovers_per_touch__%'
)
SELECT
    o.player_id,
    o.player_name,
    o.primary_team_id,
    o.position_code,
    o.baseline_group,
    o.games_played,
    o.touches,
    o.turnovers,
    gr.turnovers_per_touch          AS baseline_turnovers_per_touch,
    o.touches * gr.turnovers_per_touch                       AS expected_turnovers,
    o.turnovers - o.touches * gr.turnovers_per_touch         AS turnovers_above_expected,
    -1 * (o.turnovers - o.touches * gr.turnovers_per_touch)
         * c.points_per_turnover                             AS turnover_value,
    (-1 * (o.turnovers - o.touches * gr.turnovers_per_touch)
          * c.points_per_turnover)
      / NULLIF(CAST(o.touches AS DOUBLE), 0)                 AS turnover_value_per_touch
FROM player_opportunities o
JOIN group_rates gr USING (baseline_group)
CROSS JOIN value_coefficients c
ORDER BY o.player_id;
