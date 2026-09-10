-- Phase 7: offensive play shares and every other usage measure.
--
-- ===========================================================================
-- WHAT "USAGE" MEANS HERE, AND WHAT IT DOES NOT MEAN
-- ===========================================================================
--
-- Usage is the share of a team's RECORDED OFFENSIVE OPPORTUNITIES that a
-- player personally accounted for.
--
-- It is NOT "the percentage of team possessions the player was on the field
-- for". That quantity is not computable from this feed at all -- the PLL API
-- carries no lineup, substitution, shift or minutes data of any kind, verified
-- across all 51 raw games in Phases 1-6. Every share below has an explicitly
-- countable numerator and denominator and neither is a possession. Validation
-- checks 21 and 22 enforce that no measure here is denominated in possessions
-- or in time.
--
-- ===========================================================================
-- THE FOUR MEASURES, AND WHY THERE ARE FOUR
-- ===========================================================================
--
--   offensive_play_share
--       recorded_offensive_opportunities (shots + turnovers)
--     / the same quantity summed over the player's TEAM in the games he played
--
--       The primary usage measure. Denominated in games played rather than
--       the whole season so that a player who missed five games is not
--       recorded as low-usage when he was in fact high-usage while available.
--       Because the denominator differs per player, these do NOT sum to 1
--       within a team -- which is exactly why the season-wide variant below
--       exists as well.
--
--   offensive_play_share_season
--       the same numerator over the team's FULL-SEASON total. Summed over a
--       team's players this is exactly 1.000 by construction, which is what
--       validation check 7 asserts. A mid-season mover contributes a separate
--       component to each of his teams; the player-level column is the sum of
--       his components, so it is a share of "a team season" rather than of one
--       team.
--
--   event_log_play_share
--       the player's appearances anywhere in the eligible event log, over his
--       team's appearances in the games he played. This is a faithful
--       reproduction of the ONE usage definition Lacrosse Reference publishes
--       ("the number of times each player appears in the play-by-play logs"),
--       kept so their uaEGA operation can be reproduced exactly. It is
--       reproduced, NOT adopted as this project's usage measure, because an
--       audit of it (see below) shows it is not comparable across roles.
--
--   touch_share
--       official box-score touches over team touches in games played. A
--       broader "involvement" measure that includes defensive and clearing
--       touches. Published as a cross-check and used in the sensitivity
--       analysis; not the primary measure, because it counts a defenseman's
--       clear and an attackman's dodge as the same unit.
--
-- ===========================================================================
-- AUDIT OF THE PHASE 6 `play_shares` MEASURE (Phase 7 brief section 2)
-- ===========================================================================
--
-- Phase 6 published `play_shares` = appearances anywhere in the eligible event
-- log. Its definition was audited before anything was changed, and it is NOT
-- modified: `event_log_play_shares` below reproduces it exactly and validation
-- check 5 asserts equality with the Phase 6 column player by player.
--
-- What the audit found the 17,063 appearances actually consist of:
--
--   8,779  primary actor        shooter / faceoff winner / ground-ball
--                               recoverer / penalty committer
--   4,106  goalie of record     ONE PER SHOT OR GOAL EVENT, so a goalie
--                               accumulates a play share for every shot he
--                               faces including misses
--   3,092  secondary actor      faceoff LOSER (1,301) and the shot's
--                               `shotAssistId` pre-shot passer (1,791)
--   1,086  faceoff `gbPlayerId` the scrum recovery folded into the faceoff
--                               event itself
--
-- Three consequences, all of which disqualify it as this project's usage
-- measure:
--
--   1. IT IS NOT COMPARABLE ACROSS POSITIONS. Per game: faceoff 38.0,
--      goalie 27.4, attack 8.8, midfield 6.0, SSDM 3.5, LSM 3.2, defense 2.5.
--      A goalie's play-share count is essentially "shots faced" and an
--      attackman's is essentially "shots taken"; dividing either player's EPA
--      by it produces two numbers that are not on one scale.
--
--   2. ONE FACEOFF GENERATES UP TO THREE APPEARANCES -- winner, loser, and
--      the scrum recovery, 61.5% of which is the winner himself. A faceoff
--      specialist is therefore credited roughly twice per draw in the
--      denominator.
--
--   3. IT CONTAINS `shotAssistId`. The 1,791 secondary appearances on shots
--      and goals are the feed's pre-shot pass indicator, which Phase 6
--      documented as unreliable (populated on only ~42-48% of shots, and an
--      empty value is not a negative assertion) and excluded from every value
--      component. It is inside this usage count. That is faithful to Lacrosse
--      Reference's definition and is the reason the measure is reproduced
--      rather than adopted.
--
-- Turnovers, notably, contribute ZERO play shares: the event log's turnover
-- events name only a team (the `commitedTurnoverId` field is null in every
-- event of the season), so the single most common negative offensive act is
-- invisible to the Lacrosse Reference definition while being fully present in
-- the box-score-based definition used here.

CREATE OR REPLACE TABLE player_usage AS

WITH per_game AS (
    SELECT
        u.player_id,
        u.game_id,
        u.team_id,
        u.recorded_offensive_opportunities,
        u.offensive_opportunities_with_assists,
        u.shots,
        u.turnovers,
        u.official_assists,
        u.touches,
        u.faceoffs,
        u.caused_turnovers,
        t.team_recorded_offensive_opportunities,
        t.team_offensive_opportunities_with_assists,
        t.team_shots,
        t.team_touches,
        t.team_faceoffs,
        t.team_caused_turnovers,
        t.team_shots_on_goal_faced,
        COALESCE(ps.event_log_play_shares, 0) AS event_log_play_shares
    FROM player_game_usage u
    JOIN team_game_usage t USING (game_id, team_id)
    LEFT JOIN player_game_event_log_play_shares ps
           ON ps.game_id = u.game_id AND ps.player_id = u.player_id
),

-- team event-log play shares per game, for the LR-style denominator
team_event_log AS (
    SELECT g.game_id, u.team_id, SUM(pg.event_log_play_shares) AS team_event_log_play_shares
    FROM player_game_event_log_play_shares pg
    JOIN eligible_games g USING (game_id)
    JOIN player_game_usage u ON u.game_id = pg.game_id AND u.player_id = pg.player_id
    GROUP BY g.game_id, u.team_id
),

with_team_log AS (
    SELECT p.*, COALESCE(tl.team_event_log_play_shares, 0) AS team_event_log_play_shares
    FROM per_game p
    LEFT JOIN team_event_log tl ON tl.game_id = p.game_id AND tl.team_id = p.team_id
),

-- season totals for each TEAM, used for the sums-to-one seasonal share
team_season AS (
    SELECT team_id,
           SUM(team_recorded_offensive_opportunities) AS season_team_opps_all_games
    FROM (SELECT DISTINCT game_id, team_id, team_recorded_offensive_opportunities
          FROM with_team_log)
    GROUP BY team_id
),

-- one row per (player, team): needed because five players changed team
-- mid-season and a season share must be attributed to the team it was earned
-- against
player_team AS (
    SELECT
        w.player_id,
        w.team_id,
        COUNT(*)                                          AS games_with_team,
        SUM(w.recorded_offensive_opportunities)           AS recorded_offensive_opportunities,
        SUM(w.team_recorded_offensive_opportunities)      AS team_recorded_offensive_opportunities,
        SUM(w.offensive_opportunities_with_assists)       AS offensive_opportunities_with_assists,
        SUM(w.team_offensive_opportunities_with_assists)  AS team_offensive_opportunities_with_assists,
        SUM(w.shots)                                      AS shots,
        SUM(w.team_shots)                                 AS team_shots,
        SUM(w.touches)                                    AS touches,
        SUM(w.team_touches)                               AS team_touches,
        SUM(w.faceoffs)                                   AS faceoffs,
        SUM(w.team_faceoffs)                              AS team_faceoffs,
        SUM(w.caused_turnovers)                           AS caused_turnovers,
        SUM(w.team_caused_turnovers)                      AS team_caused_turnovers,
        SUM(w.event_log_play_shares)                      AS event_log_play_shares,
        SUM(w.team_event_log_play_shares)                 AS team_event_log_play_shares,
        MAX(ts.season_team_opps_all_games)                AS season_team_opps_all_games
    FROM with_team_log w
    JOIN team_season ts USING (team_id)
    GROUP BY w.player_id, w.team_id
)

SELECT
    pt.player_id,
    SUM(pt.games_with_team)                              AS games_played,
    COUNT(*)                                             AS n_teams,

    SUM(pt.recorded_offensive_opportunities)             AS recorded_offensive_opportunities,
    SUM(pt.team_recorded_offensive_opportunities)        AS team_recorded_offensive_opportunities,
    SUM(pt.offensive_opportunities_with_assists)         AS offensive_opportunities_with_assists,
    SUM(pt.team_offensive_opportunities_with_assists)    AS team_offensive_opportunities_with_assists,
    SUM(pt.shots)                                        AS shots,
    SUM(pt.team_shots)                                   AS team_shots,
    SUM(pt.touches)                                      AS touches,
    SUM(pt.team_touches)                                 AS team_touches,
    SUM(pt.faceoffs)                                     AS faceoffs,
    SUM(pt.team_faceoffs)                                AS team_faceoffs_in_games_played,
    SUM(pt.caused_turnovers)                             AS caused_turnovers,
    SUM(pt.team_caused_turnovers)                        AS team_caused_turnovers,
    SUM(pt.event_log_play_shares)                        AS event_log_play_shares,
    SUM(pt.team_event_log_play_shares)                   AS team_event_log_play_shares,

    -- PRIMARY: share of team offensive opportunities in the games he played
    SUM(pt.recorded_offensive_opportunities)
      / NULLIF(CAST(SUM(pt.team_recorded_offensive_opportunities) AS DOUBLE), 0)
                                                         AS offensive_play_share,

    -- Sums to exactly 1.000 within a team-season (validation check 7)
    SUM(pt.recorded_offensive_opportunities
        / NULLIF(CAST(pt.season_team_opps_all_games AS DOUBLE), 0))
                                                         AS offensive_play_share_season,

    -- Alternatives, published for the sensitivity analysis
    SUM(pt.offensive_opportunities_with_assists)
      / NULLIF(CAST(SUM(pt.team_offensive_opportunities_with_assists) AS DOUBLE), 0)
                                                         AS offensive_play_share_with_assists,
    SUM(pt.shots) / NULLIF(CAST(SUM(pt.team_shots) AS DOUBLE), 0)
                                                         AS shot_share,
    SUM(pt.touches) / NULLIF(CAST(SUM(pt.team_touches) AS DOUBLE), 0)
                                                         AS touch_share,
    SUM(pt.faceoffs) / NULLIF(CAST(SUM(pt.team_faceoffs) AS DOUBLE), 0)
                                                         AS faceoff_team_share,
    SUM(pt.caused_turnovers)
      / NULLIF(CAST(SUM(pt.team_caused_turnovers) AS DOUBLE), 0)
                                                         AS caused_turnover_team_share,

    -- Lacrosse Reference reproduction
    SUM(pt.event_log_play_shares)
      / NULLIF(CAST(SUM(pt.team_event_log_play_shares) AS DOUBLE), 0)
                                                         AS event_log_play_share,

    -- per-game volume, kept separate from every share
    SUM(pt.recorded_offensive_opportunities)
      / NULLIF(CAST(SUM(pt.games_with_team) AS DOUBLE), 0)
                                                         AS offensive_opportunities_per_game
FROM player_team pt
GROUP BY pt.player_id
ORDER BY pt.player_id;


-- The per-(player, team) decomposition, kept so the seasonal share can be
-- checked to sum to 1 within each team without re-deriving mid-season moves.
CREATE OR REPLACE TABLE player_team_usage AS
WITH per_game AS (
    SELECT u.player_id, u.game_id, u.team_id,
           u.recorded_offensive_opportunities,
           t.team_recorded_offensive_opportunities
    FROM player_game_usage u
    JOIN team_game_usage t USING (game_id, team_id)
),
team_season AS (
    SELECT team_id, SUM(team_recorded_offensive_opportunities) AS season_team_opps_all_games
    FROM (SELECT DISTINCT game_id, team_id, team_recorded_offensive_opportunities FROM per_game)
    GROUP BY team_id
)
SELECT
    p.player_id,
    p.team_id,
    COUNT(*)                                    AS games_with_team,
    SUM(p.recorded_offensive_opportunities)     AS recorded_offensive_opportunities,
    MAX(ts.season_team_opps_all_games)          AS season_team_opportunities,
    SUM(p.recorded_offensive_opportunities)
      / NULLIF(CAST(MAX(ts.season_team_opps_all_games) AS DOUBLE), 0)
                                                AS offensive_play_share_season_component
FROM per_game p
JOIN team_season ts USING (team_id)
GROUP BY p.player_id, p.team_id
ORDER BY p.team_id, p.player_id;
