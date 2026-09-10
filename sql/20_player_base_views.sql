-- Phase 6 base views for the player-value layer.
--
-- Loads the canonical tables and derives the shared player-level building
-- blocks. Reuses the Phase 1-5 eligibility rules unchanged: a game counts if
-- games.include_in_league_analytics AND is_completed AND NOT is_all_star; an
-- event counts if events.is_analysis_eligible_event.
--
-- {data_dir} is substituted by scripts/pll_build_player_value.py.

CREATE OR REPLACE VIEW games_raw        AS SELECT * FROM read_csv_auto('{data_dir}/games.csv');
CREATE OR REPLACE VIEW players_raw      AS SELECT * FROM read_csv_auto('{data_dir}/players.csv');
CREATE OR REPLACE VIEW events_raw       AS SELECT * FROM read_csv_auto('{data_dir}/events.csv');
CREATE OR REPLACE VIEW possessions_raw  AS SELECT * FROM read_csv_auto('{data_dir}/possessions.csv');
CREATE OR REPLACE VIEW player_game_raw  AS SELECT * FROM read_csv_auto('{data_dir}/player_game_stats.csv');
CREATE OR REPLACE VIEW team_game_raw    AS SELECT * FROM read_csv_auto('{data_dir}/team_game_stats.csv');


CREATE OR REPLACE VIEW eligible_games AS
SELECT game_id, game_slug, week, game_type, is_playoff, home_team_id, away_team_id
FROM games_raw
WHERE is_completed AND include_in_league_analytics AND NOT is_all_star;


-- ---------------------------------------------------------------------------
-- Position mapping.
--
-- PLL roster labels are already role-specific and map cleanly; no NCAA
-- convention is assumed. The two rows in the season with a null label are
-- mapped to 'unknown' rather than guessed.
--
--   A    Attack                -> attack             (offensive_field)
--   M    Midfield              -> midfield           (offensive_field)
--   SSDM Defensive Midfield    -> defensive_midfield (defensive_field)
--   LSM  Long Stick Midfield   -> long_stick_midfield(defensive_field)
--   D    Defense               -> defense            (defensive_field)
--   FO   Faceoff               -> faceoff            (faceoff)
--   G    Goalie                -> goalie             (goalie)
--
-- baseline_group is the coarser grouping used for per-opportunity baselines,
-- chosen to keep every group's sample large enough to estimate a rate (§
-- "Position handling" in PLAYER_VALUE_METHODOLOGY.md). Position itself is
-- preserved on every output row.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW position_map AS
SELECT * FROM (VALUES
    ('A',    'attack',              'offensive_field'),
    ('M',    'midfield',            'offensive_field'),
    ('SSDM', 'defensive_midfield',  'defensive_field'),
    ('LSM',  'long_stick_midfield', 'defensive_field'),
    ('D',    'defense',             'defensive_field'),
    ('FO',   'faceoff',             'faceoff'),
    ('G',    'goalie',              'goalie')
) AS t(position_code, position_name, baseline_group);


-- Resolve each player's position ONCE, at the player level.
--
-- This matters for more than tidiness. Four player-game rows in the season
-- carry a null position for a player who is labelled normally in his other
-- games. If the baseline groups were formed from the per-row label while a
-- player's own group came from an aggregate of his rows, those rows would land
-- in one group's baseline and the player in another -- and the residual
-- identity every component depends on (sum of observed minus expected = 0
-- within a group) would silently stop holding. Resolving here keeps the two
-- consistent by construction.
--
-- The rule is the modal non-null label, ties broken alphabetically so the
-- result is deterministic; a player with no label in any game stays 'UNK'.
CREATE OR REPLACE VIEW player_position AS
WITH labelled AS (
    SELECT LPAD(CAST(pg.officialId AS VARCHAR), 6, '0') AS player_id,
           pg.position AS position_code,
           COUNT(*)    AS n_games
    FROM player_game_raw pg
    JOIN eligible_games g USING (game_id)
    WHERE pg.position IS NOT NULL
    GROUP BY 1, 2
),
ranked AS (
    SELECT player_id, position_code,
           ROW_NUMBER() OVER (PARTITION BY player_id
                              ORDER BY n_games DESC, position_code) AS rn
    FROM labelled
),
all_players AS (
    SELECT DISTINCT LPAD(CAST(pg.officialId AS VARCHAR), 6, '0') AS player_id
    FROM player_game_raw pg JOIN eligible_games g USING (game_id)
)
SELECT
    a.player_id,
    COALESCE(r.position_code, 'UNK')       AS position_code,
    COALESCE(pm.position_name, 'unknown')  AS position_name,
    COALESCE(pm.baseline_group, 'unknown') AS baseline_group
FROM all_players a
LEFT JOIN ranked r ON r.player_id = a.player_id AND r.rn = 1
LEFT JOIN position_map pm ON pm.position_code = r.position_code;


-- One row per (player, eligible game), with PLL points made explicit.
--
-- NOTE on player_game_stats.points: PLL's player-level `points` column is
-- goals + assists in the traditional lacrosse sense WITH the two-point goal
-- counted twice (verified: onePointGoals + 2*twoPointGoals + assists equals it
-- on all 1,824 rows). It is therefore NOT PLL scoring points and is never used
-- as such here. pll_points below is the scoring quantity, and it sums to the
-- official team score exactly.
CREATE OR REPLACE VIEW player_game AS
SELECT
    pg.game_id,
    pg.game_slug,
    LPAD(CAST(pg.officialId AS VARCHAR), 6, '0') AS player_id,
    pg.teamId                                    AS team_id,
    pg.firstName || ' ' || pg.lastName           AS player_name,
    pp.position_code,
    pp.position_name,
    pp.baseline_group,
    pg.onePointGoals                             AS one_point_goals,
    pg.twoPointGoals                             AS two_point_goals,
    pg.goals,
    pg.onePointGoals + 2 * pg.twoPointGoals      AS pll_points,
    pg.assists                                   AS official_assists,
    pg.shots,
    pg.shotsOnGoal                               AS shots_on_goal,
    pg.twoPointShots                             AS two_point_attempts,
    pg.shots - pg.twoPointShots                  AS one_point_attempts,
    pg.turnovers,
    pg.causedTurnovers                           AS caused_turnovers,
    pg.groundBalls                               AS ground_balls,
    pg.faceoffs,
    pg.faceoffsWon                               AS faceoff_wins,
    pg.faceoffsLost                              AS faceoff_losses,
    pg.saves,
    pg.goalsAgainst                              AS goals_allowed,
    pg.twoPointGoalsAgainst                      AS two_point_goals_allowed,
    pg.scoresAgainst                             AS pll_points_allowed,
    pg.numPenalties                              AS penalties,
    pg.touches,
    pg.totalPasses                               AS total_passes,
    pg.assistOpportunities                       AS assist_opportunities
FROM player_game_raw pg
JOIN eligible_games g USING (game_id)
JOIN player_position pp
  ON pp.player_id = LPAD(CAST(pg.officialId AS VARCHAR), 6, '0');


-- Analysis-eligible shot events, with the goalie who faced them. Used for the
-- goalie opportunity split (one-point vs two-point shots on goal faced), which
-- the official player box score does not provide.
CREATE OR REPLACE VIEW eligible_shot_events AS
SELECT
    e.game_id,
    LPAD(CAST(e.player_id AS VARCHAR), 6, '0')  AS shooter_id,
    LPAD(CAST(e.goalie_id AS VARCHAR), 6, '0')  AS goalie_id,
    e.team_id,
    COALESCE(e.is_two_point_attempt, FALSE)                       AS is_two_point,
    e.is_valid_goal                                               AS is_goal,
    e.shot_outcome IN ('goal', 'saved', 'on_goal_no_save')         AS is_shot_on_goal,
    CASE WHEN e.is_valid_goal AND COALESCE(e.is_two_point_attempt, FALSE) THEN 2
         WHEN e.is_valid_goal THEN 1 ELSE 0 END                    AS pll_points
FROM events_raw e
JOIN eligible_games g USING (game_id)
WHERE e.is_analysis_eligible_event
  AND e.event_type IN ('shot', 'goal')
  AND e.shot_outcome IS NOT NULL;


-- Play shares: how many times a player appears anywhere in the eligible event
-- log, in any role. This is the opportunity proxy Lacrosse Reference documents
-- for usage-adjusted EGA ("the number of times each player appears in the
-- play-by-play logs"). It is explicitly NOT a claim that the player was on the
-- field for a possession -- the feed carries no lineup data, so team
-- possessions while a player was on field cannot be computed at all.
CREATE OR REPLACE VIEW player_play_shares AS
WITH appearances AS (
    SELECT game_id, LPAD(CAST(player_id AS VARCHAR), 6, '0') AS player_id
    FROM events_raw WHERE is_analysis_eligible_event AND player_id IS NOT NULL
    UNION ALL
    SELECT game_id, LPAD(CAST(gb_player_id AS VARCHAR), 6, '0')
    FROM events_raw WHERE is_analysis_eligible_event AND gb_player_id IS NOT NULL
    UNION ALL
    SELECT game_id, LPAD(CAST(goalie_id AS VARCHAR), 6, '0')
    FROM events_raw WHERE is_analysis_eligible_event AND goalie_id IS NOT NULL
    UNION ALL
    SELECT game_id, LPAD(CAST(secondary_player_id AS VARCHAR), 6, '0')
    FROM events_raw WHERE is_analysis_eligible_event AND secondary_player_id IS NOT NULL
)
SELECT a.player_id, COUNT(*) AS play_shares
FROM appearances a
JOIN eligible_games g USING (game_id)
GROUP BY a.player_id;
