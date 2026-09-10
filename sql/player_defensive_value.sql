-- Phase 6: PARTIAL defensive value.
--
-- This component measures exactly one thing: caused turnovers relative to what
-- an average player in the same position group produces per game. It is NOT a
-- defensive EGA and it is not comprehensive. Most of what a defender does --
-- positioning, matchup difficulty, forcing a bad shot rather than a turnover,
-- sliding, communication -- leaves no trace in this feed at all, so no
-- component here can represent it. The column is named and documented as
-- partial for that reason.
--
--   caused_turnover_value = (caused_turnovers - expected_caused_turnovers)
--                           * points_per_caused_turnover
--   expected_caused_turnovers = games_played * league caused turnovers per game
--                               for the player's baseline group
--
-- SOURCE. Caused turnovers come from the OFFICIAL player box score, which
-- reconciles exactly with the official team totals in all 100 team-games
-- (741 season-wide). They are NOT inferred from turnover events: Phase 4.25
-- established that the event-level caused-turnover field is null in every
-- event of the season, and nothing here works around that.
--
-- DENOMINATOR LIMITATION. Games played is a crude exposure measure. The feed
-- has no minutes, shifts or lineups, so a defender who plays every defensive
-- possession and one who rotates are treated as having the same opportunity.
-- This is the weakest denominator in the framework and is flagged as such on
-- every row and in player_value_metric_definitions.csv.
--
-- WHY GROUND BALLS ARE NOT ADDED HERE. See player_value_components.sql and
-- docs/PLAYER_VALUE_ACCOUNTING.md scenario E: a caused turnover is very often
-- immediately followed by a ground-ball recovery describing the same change of
-- possession, and 99.7% of post-faceoff ground balls belong to the faceoff
-- winner's team. Adding a per-ground-ball credit on top would value one
-- possession change two or three times.

CREATE OR REPLACE TABLE player_defensive_value AS
WITH group_rates AS (
    SELECT
        REPLACE(baseline_name, 'caused_turnovers_per_game__', '') AS baseline_group,
        baseline_value                                            AS caused_turnovers_per_game
    FROM player_value_baselines
    WHERE baseline_name LIKE 'caused_turnovers_per_game__%'
)
SELECT
    o.player_id,
    o.player_name,
    o.primary_team_id,
    o.position_code,
    o.baseline_group,
    o.games_played,
    o.caused_turnovers,
    o.ground_balls,
    gr.caused_turnovers_per_game        AS baseline_caused_turnovers_per_game,
    o.games_played * gr.caused_turnovers_per_game        AS expected_caused_turnovers,
    o.caused_turnovers - o.games_played * gr.caused_turnovers_per_game
        AS caused_turnovers_above_expected,
    (o.caused_turnovers - o.games_played * gr.caused_turnovers_per_game)
        * c.points_per_caused_turnover                   AS caused_turnover_value,
    ((o.caused_turnovers - o.games_played * gr.caused_turnovers_per_game)
        * c.points_per_caused_turnover)
      / NULLIF(CAST(o.games_played AS DOUBLE), 0)        AS caused_turnover_value_per_game,
    'partial: caused turnovers only, relative to positional per-game average'
        AS defensive_value_scope
FROM player_opportunities o
JOIN group_rates gr USING (baseline_group)
CROSS JOIN value_coefficients c
ORDER BY o.player_id;
