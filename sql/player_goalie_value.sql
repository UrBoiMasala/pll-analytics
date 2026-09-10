-- Phase 6: goalkeeper value -- PLL points prevented.
--
--   goalie_value = expected PLL points allowed on the shots on goal faced
--                - actual PLL points allowed
--
--   expected = one_point_shots_on_goal_faced  * E[points | one-point SOG]
--            + two_point_shots_on_goal_faced  * E[points | two-point SOG]
--
-- Positive means the goalie conceded fewer points than a league-average
-- goalie would have on the same shots. The sign is deliberately flipped
-- relative to the shooting component so that "more is better" holds for every
-- component in the framework.
--
-- Goalkeepers are valued on their OWN opportunity set -- shots on goal faced,
-- not shot attempts. A goalie is not responsible for a shot that missed the
-- cage, so charging him an expectation for it would be valuing something he
-- did not face.
--
-- TWO-POINT HANDLING, and why it matters more here than it looks. Separate
-- baselines are estimated for one-point and two-point shots on goal because
-- the conversion rates differ sharply: 46.1% of one-point shots on goal go in
-- versus 24.1% of two-point shots on goal. But each two-point goal is worth 2
-- points, so the EXPECTED POINTS per shot on goal are nearly identical --
-- 0.461 for a one-point shot on goal, 0.482 for a two-point one. A goalie who
-- happens to face more long-range shots is therefore neither rewarded nor
-- punished for the shot mix. The 1pt/2pt split of shots faced does not exist
-- in the official player box score and is recovered from the event log, where
-- every shot carries its goalie (reconciled against official saves in 116/117
-- goalie-games, goals allowed in 117/117).
--
-- WHAT THIS IS NOT. This is points prevented relative to the league-average
-- outcome on shots on goal. It does NOT adjust for shot quality: the feed
-- carries no shot location, distance or defender information, so a goalie
-- behind a defence that concedes point-blank looks worse and one behind a
-- defence that forces long shots looks better. That confound is real,
-- unmeasurable here, and stated rather than hidden.
--
-- NULL, not zero, for a player who faced no shots on goal.

CREATE OR REPLACE TABLE player_goalie_value AS
SELECT
    o.player_id,
    o.player_name,
    o.primary_team_id,
    o.position_code,
    o.games_played,
    o.shots_on_goal_faced,
    o.one_point_shots_on_goal_faced,
    o.two_point_shots_on_goal_faced,
    o.saves,
    o.goals_allowed,
    o.two_point_goals_allowed,
    o.pll_points_allowed                            AS actual_points_allowed,
    o.save_pct,
    CASE WHEN o.shots_on_goal_faced > 0
         THEN o.one_point_shots_on_goal_faced * c.xp_allowed_per_one_point_sog
            + o.two_point_shots_on_goal_faced * c.xp_allowed_per_two_point_sog END
        AS expected_points_allowed,
    CASE WHEN o.shots_on_goal_faced > 0
         THEN (o.one_point_shots_on_goal_faced * c.xp_allowed_per_one_point_sog
             + o.two_point_shots_on_goal_faced * c.xp_allowed_per_two_point_sog)
            - o.pll_points_allowed END
        AS goalie_value,
    CASE WHEN o.shots_on_goal_faced > 0
         THEN ((o.one_point_shots_on_goal_faced * c.xp_allowed_per_one_point_sog
              + o.two_point_shots_on_goal_faced * c.xp_allowed_per_two_point_sog)
             - o.pll_points_allowed) / o.shots_on_goal_faced END
        AS goalie_value_per_shot_on_goal_faced
FROM player_opportunities o
CROSS JOIN value_coefficients c
ORDER BY o.player_id;
