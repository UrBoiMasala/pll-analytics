-- Phase 6: player opportunity / usage table.
--
-- One row per player over the 2026 league-analytics-eligible season. Holds the
-- raw opportunity counts every value component divides by, so each component
-- can be audited by hand from this table plus player_value_baselines.csv.
--
-- IMPORTANT -- what "opportunity" means here. Every column below is an
-- INDIVIDUAL RECORDED opportunity: something the player himself was credited
-- with in the box score or the event log. None of them is "team possessions
-- while this player was on the field". The PLL feed carries no lineup or
-- substitution data, so on-field possession participation is not computable
-- and is not claimed anywhere in this phase.
--
-- Five players changed teams mid-season, so the season key is player_id alone;
-- primary_team_id is the team they played the most games for and n_teams flags
-- the movers.

CREATE OR REPLACE TABLE player_opportunities AS

WITH team_games AS (
    SELECT player_id, team_id, COUNT(*) AS games,
           ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY COUNT(*) DESC, team_id) AS rn
    FROM player_game
    GROUP BY player_id, team_id
),

-- Goalie opportunity split. The official player box score gives saves and
-- goals allowed but no one-point/two-point breakdown of the shots faced, so
-- the split comes from the event log, where every shot carries its goalie.
goalie_faced AS (
    SELECT
        goalie_id AS player_id,
        COUNT(*) FILTER (WHERE is_shot_on_goal)                        AS shots_on_goal_faced,
        COUNT(*) FILTER (WHERE is_shot_on_goal AND NOT is_two_point)   AS one_point_shots_on_goal_faced,
        COUNT(*) FILTER (WHERE is_shot_on_goal AND is_two_point)       AS two_point_shots_on_goal_faced,
        COUNT(*)                                                       AS shots_faced_including_misses,
        SUM(pll_points) FILTER (WHERE is_shot_on_goal)                 AS pll_points_allowed_events
    FROM eligible_shot_events
    GROUP BY goalie_id
),

season AS (
    SELECT
        player_id,
        ANY_VALUE(player_name)    AS player_name,
        ANY_VALUE(position_code)  AS position_code,
        ANY_VALUE(position_name)  AS position_name,
        ANY_VALUE(baseline_group) AS baseline_group,
        COUNT(*)                  AS games_played,
        COUNT(DISTINCT team_id)   AS n_teams,

        SUM(shots)                AS shots,
        SUM(one_point_attempts)   AS one_point_attempts,
        SUM(two_point_attempts)   AS two_point_attempts,
        SUM(shots_on_goal)        AS shots_on_goal,
        SUM(goals)                AS goals,
        SUM(one_point_goals)      AS one_point_goals,
        SUM(two_point_goals)      AS two_point_goals,
        SUM(pll_points)           AS pll_points,
        SUM(official_assists)     AS official_assists,
        SUM(assist_opportunities) AS assist_opportunities,

        SUM(turnovers)            AS turnovers,
        SUM(caused_turnovers)     AS caused_turnovers,
        SUM(ground_balls)         AS ground_balls,
        SUM(touches)              AS touches,
        SUM(total_passes)         AS total_passes,
        SUM(penalties)            AS penalties,

        SUM(faceoffs)             AS faceoffs,
        SUM(faceoff_wins)         AS faceoff_wins,
        SUM(faceoff_losses)       AS faceoff_losses,

        SUM(saves)                AS saves,
        SUM(goals_allowed)        AS goals_allowed,
        SUM(two_point_goals_allowed) AS two_point_goals_allowed,
        SUM(pll_points_allowed)   AS pll_points_allowed
    FROM player_game
    GROUP BY player_id
)

SELECT
    s.player_id,
    s.player_name,
    tg.team_id                AS primary_team_id,
    s.n_teams,
    s.position_code,
    s.position_name,
    s.baseline_group,
    s.games_played,

    -- offensive recorded opportunities
    s.shots, s.one_point_attempts, s.two_point_attempts, s.shots_on_goal,
    s.goals, s.one_point_goals, s.two_point_goals, s.pll_points,
    s.official_assists, s.assist_opportunities,
    s.touches, s.total_passes,
    s.turnovers, s.ground_balls, s.penalties,

    -- defensive recorded opportunities
    s.caused_turnovers,

    -- faceoff opportunities
    s.faceoffs, s.faceoff_wins, s.faceoff_losses,

    -- goalie opportunities (official counts; the 1pt/2pt split is event-derived)
    s.saves, s.goals_allowed, s.two_point_goals_allowed, s.pll_points_allowed,
    COALESCE(gf.shots_on_goal_faced, 0)            AS shots_on_goal_faced,
    COALESCE(gf.one_point_shots_on_goal_faced, 0)  AS one_point_shots_on_goal_faced,
    COALESCE(gf.two_point_shots_on_goal_faced, 0)  AS two_point_shots_on_goal_faced,

    -- usage proxy (see the play_shares view for what this is and is not)
    COALESCE(ps.play_shares, 0)                    AS play_shares,

    -- convenience rates, all NULLIF-guarded
    s.goals  / NULLIF(CAST(s.shots AS DOUBLE), 0)              AS shooting_pct,
    s.pll_points / NULLIF(CAST(s.shots AS DOUBLE), 0)          AS points_per_shot,
    s.two_point_goals / NULLIF(CAST(s.two_point_attempts AS DOUBLE), 0) AS two_point_pct,
    s.one_point_goals / NULLIF(CAST(s.one_point_attempts AS DOUBLE), 0) AS one_point_pct,
    s.faceoff_wins / NULLIF(CAST(s.faceoffs AS DOUBLE), 0)     AS faceoff_win_pct,
    s.turnovers / NULLIF(CAST(s.touches AS DOUBLE), 0)         AS turnovers_per_touch,
    s.saves / NULLIF(CAST(s.saves + s.goals_allowed AS DOUBLE), 0) AS save_pct
FROM season s
JOIN team_games tg ON tg.player_id = s.player_id AND tg.rn = 1
LEFT JOIN goalie_faced gf ON gf.player_id = s.player_id
LEFT JOIN player_play_shares ps ON ps.player_id = s.player_id
ORDER BY s.player_id;
