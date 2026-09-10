-- Phase 7 base views for the usage / positional-normalization layer.
--
-- Runs AFTER sql/20_player_base_views.sql, which already provides
-- `eligible_games`, `player_position`, `player_game`, `eligible_shot_events`
-- and `player_play_shares`. Nothing here modifies a Phase 6 view or table.
--
-- Phase 6's published outputs are loaded from disk RATHER than recomputed, so
-- that every raw EPA_points value in Phase 7 is byte-identical to the number
-- Phase 6 published. Validation check 8 asserts this.
--
-- {data_dir} is substituted by scripts/pll_build_adjusted_player_value.py.

CREATE OR REPLACE VIEW phase6_components AS
SELECT * FROM read_csv_auto('{data_dir}/player_value_components.csv',
                            types={'player_id': 'VARCHAR', 'team_id': 'VARCHAR'});

CREATE OR REPLACE VIEW phase6_opportunities AS
SELECT * FROM read_csv_auto('{data_dir}/player_opportunities.csv',
                            types={'player_id': 'VARCHAR', 'primary_team_id': 'VARCHAR'});

CREATE OR REPLACE VIEW phase6_shrinkage AS
SELECT * FROM read_csv_auto('{data_dir}/player_value_shrinkage.csv',
                            types={'player_id': 'VARCHAR', 'primary_team_id': 'VARCHAR'});


-- ---------------------------------------------------------------------------
-- RECORDED OFFENSIVE OPPORTUNITIES -- the Phase 7 usage numerator.
--
-- Defined as  shots + turnovers  from the official player box score.
--
-- WHY THESE TWO AND NOTHING ELSE. The quantity being proxied is "how much of
-- the team's offensive workload did this player personally take on". The feed
-- attributes exactly two kinds of individually-credited action that CONSUME an
-- offensive opportunity:
--
--   a shot attempt  -- the player used a possession to try to score
--   a turnover      -- the player ended a possession without a shot
--
-- They are disjoint events (a shot is not a turnover), so nothing is counted
-- twice, and together they cover the ways a named player finishes an offensive
-- sequence.
--
-- ASSISTS ARE DELIBERATELY EXCLUDED. An assist is attached to a goal that is
-- ALREADY counted as the shooter's shot attempt. Adding the assist would count
-- one offensive sequence twice at team level and would inflate the usage of
-- feeders relative to shooters purely as an artefact of the accounting. The
-- Lacrosse Reference play-share definition does not require it either (it
-- counts appearances in the log, which is reproduced separately below as
-- `event_log_play_shares`). An assist-inclusive alternative is run in
-- player_adjusted_value_sensitivity.csv.
--
-- GROUND BALLS ARE EXCLUDED for the same double-counting reason Phase 6 gave:
-- 1,095 of 3,091 immediately follow a faceoff and 99.7% go to the winning
-- team, so they measure faceoff outcome, not offensive workload.
--
-- KNOWN LIMITATION, carried on every row. Player-attributed turnovers total
-- 1,369 against an official team total of 1,699 -- about 19% of the league's
-- turnovers name only a team. Numerator and denominator here are BOTH built
-- from player-attributed sums, so the share is internally consistent, but the
-- absolute opportunity count is understated for every player. `shots` alone
-- reconciles exactly (4,106 = 4,106 in all 100 team-games), and a shots-only
-- usage definition is run as a sensitivity alternative.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW player_game_usage AS
SELECT
    pg.game_id,
    pg.player_id,
    pg.team_id,
    pg.position_code,
    pg.baseline_group,
    pg.shots,
    pg.turnovers,
    pg.shots + pg.turnovers                       AS recorded_offensive_opportunities,
    pg.official_assists,
    pg.shots + pg.turnovers + pg.official_assists AS offensive_opportunities_with_assists,
    pg.touches,
    pg.faceoffs,
    pg.caused_turnovers,
    pg.saves + pg.goals_allowed                   AS shots_on_goal_faced_boxscore
FROM player_game pg;


-- Team totals, from the SAME player-attributed rows the numerator uses, so the
-- share is a true share by construction rather than a ratio of two different
-- accountings.
CREATE OR REPLACE VIEW team_game_usage AS
SELECT
    game_id,
    team_id,
    SUM(recorded_offensive_opportunities)     AS team_recorded_offensive_opportunities,
    SUM(offensive_opportunities_with_assists) AS team_offensive_opportunities_with_assists,
    SUM(shots)                                AS team_shots,
    SUM(turnovers)                            AS team_turnovers,
    SUM(touches)                              AS team_touches,
    SUM(faceoffs)                             AS team_faceoffs,
    SUM(caused_turnovers)                     AS team_caused_turnovers,
    SUM(shots_on_goal_faced_boxscore)         AS team_shots_on_goal_faced
FROM player_game_usage
GROUP BY game_id, team_id;


-- Event-log play shares per team, needed for the Lacrosse Reference "1% of a
-- team's play shares" eligibility rule. Attributed per game so a mid-season
-- mover is credited to the team he actually played for.
CREATE OR REPLACE VIEW player_game_event_log_play_shares AS
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
SELECT a.game_id, a.player_id, COUNT(*) AS event_log_play_shares
FROM appearances a
JOIN eligible_games g USING (game_id)
GROUP BY a.game_id, a.player_id;
