-- Phase 6: assembled player-value components.
--
-- Unit: EPA_points -- Expected PLL Points Added. Every component is
--
--     (what the player actually produced on his own recorded opportunities)
--   - (what a league-average player would have produced on the SAME
--      opportunities)
--
-- so a value of +3.2 reads as "roughly 3.2 PLL points more than league-average
-- outcomes on this player's own opportunities". The baseline is LEAGUE-AVERAGE
-- EXPECTED OPPORTUNITY OUTCOME. It is not replacement level -- replacement
-- level has not been estimated anywhere in this phase -- and no WAR-style
-- language is used.
--
-- NULL DISCIPLINE (Phase 6 brief §14). A component is NULL when the player had
-- no opportunities of that class and the component therefore does not apply to
-- him: faceoff value for a player who never took a draw, goalie value for a
-- field player. A component is 0 when it was measured and came out at zero:
-- a player who took shots and converted them at exactly the league rate. The
-- two are never conflated, and ground_ball_value is NULL for every player
-- because the component is deferred, not because everyone scored zero on it.
--
-- WHY THERE IS NO GROUND-BALL COMPONENT IN THE TOTAL. Three findings, all in
-- docs/PLAYER_VALUE_ACCOUNTING.md:
--   1. A ground ball has no opportunity denominator. There is no such thing as
--      a "ground-ball chance" in this feed, so it cannot be expressed as a
--      residual and is not commensurable with the components above.
--   2. Its measurable contexts are not statistically separable at 2026 sample
--      sizes: faceoff-scrum 0.163 [0.124, 0.201], possession-gaining 0.130
--      [0.098, 0.162], retained 0.082 [-0.040, 0.204] net points.
--   3. 1,095 of 3,091 ground balls immediately follow a faceoff, and 99.7% of
--      those go to the faceoff-winning team with 61.5% to the winner himself.
--      Crediting them on top of faceoff value would pay the same player twice
--      for one change of possession.
-- The empirical per-ground-ball event value is still carried below as a
-- descriptive column, outside the total, so a later phase can use it.
--
-- WHY THERE IS NO ASSIST COMPONENT IN THE TOTAL. Official assists reconcile
-- exactly (560 season-wide, 100/100 team-games) and are carried as a
-- descriptive column, but they are not valued: the points from an assisted
-- goal are already fully accounted for in the shooter's shooting_value, and
-- adding an independent assist credit would create two players' worth of value
-- from one goal. Splitting the credit between shooter and assister is a
-- defensible alternative but it changes what shooting_value means, so it is
-- deferred to the phase that needs it rather than chosen here.

CREATE OR REPLACE TABLE player_value_components AS
WITH assembled AS (
    SELECT
        o.player_id,
        o.player_name,
        o.primary_team_id                AS team_id,
        o.n_teams,
        o.position_code,
        o.position_name,
        o.baseline_group,
        o.games_played,

        -- ---- raw opportunities, so every component is auditable in place ----
        o.shots, o.one_point_attempts, o.two_point_attempts, o.shots_on_goal,
        o.goals, o.one_point_goals, o.two_point_goals, o.pll_points,
        o.touches, o.turnovers, o.ground_balls, o.caused_turnovers,
        o.faceoffs, o.faceoff_wins,
        o.saves, o.shots_on_goal_faced, o.one_point_shots_on_goal_faced,
        o.two_point_shots_on_goal_faced, o.pll_points_allowed,
        o.official_assists, o.play_shares, o.penalties,

        -- ---- components (EPA_points) ----
        sv.expected_points_from_shots,
        sv.shooting_value,
        sv.shooting_value_one_point,
        sv.shooting_value_two_point,
        sv.shooting_value_per_shot,

        tv.expected_turnovers,
        tv.turnovers_above_expected,
        tv.turnover_value,
        tv.turnover_value_per_touch,

        fv.expected_faceoff_wins,
        fv.faceoff_wins_above_expected,
        fv.faceoff_value,
        fv.faceoff_value_per_faceoff,

        dv.expected_caused_turnovers,
        dv.caused_turnovers_above_expected,
        dv.caused_turnover_value,
        dv.caused_turnover_value_per_game,
        dv.defensive_value_scope,

        gv.expected_points_allowed,
        gv.goalie_value,
        gv.goalie_value_per_shot_on_goal_faced,

        -- ---- deferred / descriptive, NOT part of any total ----
        CAST(NULL AS DOUBLE)                        AS ground_ball_value,
        'deferred: no opportunity denominator; contexts not separable; overlaps faceoff value'
                                                    AS ground_ball_value_status,
        o.ground_balls * c.points_per_ground_ball_event
                                                    AS ground_ball_event_value_descriptive,
        CAST(NULL AS DOUBLE)                        AS assist_value,
        'deferred: goal value already credited to the shooter'
                                                    AS assist_value_status
    FROM player_opportunities o
    LEFT JOIN player_shooting_value  sv USING (player_id)
    LEFT JOIN player_turnover_value  tv USING (player_id)
    LEFT JOIN player_faceoff_value   fv USING (player_id)
    LEFT JOIN player_defensive_value dv USING (player_id)
    LEFT JOIN player_goalie_value    gv USING (player_id)
    CROSS JOIN value_coefficients c
)
SELECT
    a.*,
    -- Role totals. COALESCE inside a total means "this player had no
    -- opportunities of that class, so it adds nothing" -- the component column
    -- itself stays NULL so the distinction survives in the output.
    COALESCE(shooting_value, 0) + COALESCE(turnover_value, 0) AS total_offensive_value,
    COALESCE(caused_turnover_value, 0)                        AS total_defensive_value,
    COALESCE(faceoff_value, 0)                                AS total_faceoff_value,
    COALESCE(goalie_value, 0)                                 AS total_goalie_value,
    COALESCE(shooting_value, 0) + COALESCE(turnover_value, 0)
      + COALESCE(caused_turnover_value, 0) + COALESCE(faceoff_value, 0)
      + COALESCE(goalie_value, 0)                             AS total_player_value,

    -- Per-opportunity views. Kept separate from the totals throughout: a
    -- high-volume player can post a large total on average efficiency, and a
    -- low-volume player a high per-opportunity figure on almost no
    -- contribution. Both remain visible, neither is blended into the other.
    (COALESCE(shooting_value, 0) + COALESCE(turnover_value, 0)
      + COALESCE(caused_turnover_value, 0) + COALESCE(faceoff_value, 0)
      + COALESCE(goalie_value, 0)) / NULLIF(CAST(games_played AS DOUBLE), 0)
        AS total_player_value_per_game,
    -- Play shares are appearances in the event log -- a usage proxy, NOT
    -- possessions played. See the player_play_shares view.
    (COALESCE(shooting_value, 0) + COALESCE(turnover_value, 0)
      + COALESCE(caused_turnover_value, 0) + COALESCE(faceoff_value, 0)
      + COALESCE(goalie_value, 0)) / NULLIF(CAST(play_shares AS DOUBLE), 0)
        AS total_player_value_per_play_share,

    -- Which components actually applied to this player, so a reader never has
    -- to infer coverage from a NULL.
    CONCAT_WS('+',
        CASE WHEN shooting_value      IS NOT NULL THEN 'shooting' END,
        CASE WHEN turnover_value      IS NOT NULL THEN 'turnover' END,
        CASE WHEN caused_turnover_value IS NOT NULL THEN 'defense' END,
        CASE WHEN faceoff_value       IS NOT NULL THEN 'faceoff' END,
        CASE WHEN goalie_value        IS NOT NULL THEN 'goalie' END
    ) AS components_supported
FROM assembled a
ORDER BY total_player_value DESC, player_id;
