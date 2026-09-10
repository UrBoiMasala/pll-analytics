-- Phase 6: shooting value.
--
--   shooting_value = observed PLL points from shots
--                  - expected PLL points for the same shot attempts
--
-- where expected points come from the league conversion rate for each shot
-- CLASS the player actually attempted:
--
--   expected = one_point_attempts * E[points | one-point attempt]
--            + two_point_attempts * E[points | two-point attempt]
--
-- Two-point handling is explicit and is the reason the unit is points rather
-- than goals: a two-point goal is ONE goal worth TWO points, so its expected
-- value is P(goal) * 2, not P(goal). A player who takes two-point shots is
-- charged a two-point-sized expectation for them.
--
-- The model behind the baseline is the simple two-class empirical rate. A
-- logistic model adding game state (score margin, period, game progress) was
-- fitted and REJECTED: it was worse out of sample (5-fold CV Brier 0.195675 vs
-- 0.195476). The 2026 feed carries no shot location, distance or defender
-- information, and PLL's man-up shot tag appears on goals only, so there is no
-- further attempt-level context to model. See scripts/pll_player_value_models.py
-- and shot_model_validation.csv.
--
-- This component values FINISHING ONLY. It deliberately carries no credit for
-- generating the shot or for having the possession -- those are not the
-- player's measurable contribution in this framework, and crediting them here
-- is what would double-count possession value. See docs/PLAYER_VALUE_ACCOUNTING.md.
--
-- By construction the league sum is exactly zero: every attempt contributes
-- its own class's league mean to the expectation, so observed and expected
-- points sum to the same total. Validation check 14 asserts this.

CREATE OR REPLACE TABLE player_shooting_value AS
SELECT
    o.player_id,
    o.player_name,
    o.primary_team_id,
    o.position_code,
    o.baseline_group,
    o.games_played,
    o.shots,
    o.one_point_attempts,
    o.two_point_attempts,
    o.shots_on_goal,
    o.goals,
    o.one_point_goals,
    o.two_point_goals,
    o.pll_points                                   AS observed_points_from_shots,
    o.one_point_attempts * c.xp_per_one_point_attempt
      + o.two_point_attempts * c.xp_per_two_point_attempt AS expected_points_from_shots,
    o.pll_points
      - (o.one_point_attempts * c.xp_per_one_point_attempt
         + o.two_point_attempts * c.xp_per_two_point_attempt) AS shooting_value,
    -- split so a reader can see whether a player's edge came from inside or
    -- from behind the arc
    o.one_point_goals - o.one_point_attempts * c.xp_per_one_point_attempt
        AS shooting_value_one_point,
    2 * o.two_point_goals - o.two_point_attempts * c.xp_per_two_point_attempt
        AS shooting_value_two_point,
    (o.pll_points
      - (o.one_point_attempts * c.xp_per_one_point_attempt
         + o.two_point_attempts * c.xp_per_two_point_attempt))
      / NULLIF(CAST(o.shots AS DOUBLE), 0)          AS shooting_value_per_shot
FROM player_opportunities o
CROSS JOIN value_coefficients c
ORDER BY o.player_id;
