-- Phase 7: canonical position map and analytical value roles.
--
-- Two DIFFERENT things are produced here and they must not be conflated:
--
--   canonical_position  -- what the player is ROSTERED as, cleaned and named.
--                          Comes from the official box-score `position` label,
--                          resolved once per player exactly as Phase 6 does it
--                          (modal non-null label, ties broken alphabetically).
--
--   value_role          -- what the player MEASURABLY DID in 2026, derived
--                          from his own recorded opportunities by explicit
--                          reproducible thresholds. No player is assigned by
--                          hand.
--
-- ---------------------------------------------------------------------------
-- WHAT THE ROSTER LABELS ARE
--
-- PLL publishes seven role-specific labels and they map one-to-one; no NCAA
-- convention is assumed and no label is invented:
--
--   A    -> attack                     M    -> midfield
--   SSDM -> short_stick_defensive_midfield
--   LSM  -> long_stick_midfield        D    -> defense
--   FO   -> faceoff                    G    -> goalie
--
-- Two of the season's 228 players carry no label in any game they played.
-- They are mapped `unknown` rather than guessed; both played 1-2 games with
-- fewer than 8 recorded touches.
--
-- `position_group` is the coarser partition Phase 7 standardizes within. It
-- splits attack from midfield -- which Phase 6's `baseline_group` does not,
-- because Phase 6 needed groups large enough to estimate a turnover RATE while
-- Phase 7 needs groups whose EPA DISTRIBUTION is meaningful, and attackmen and
-- midfielders have visibly different opportunity volumes. Phase 6's
-- `baseline_group` is carried through unchanged alongside it; nothing in the
-- Phase 6 value layer is recomputed against the new partition.
--
-- ---------------------------------------------------------------------------
-- HOW value_role IS DECIDED
--
-- Lacrosse Reference publicly documents a classifier of exactly this shape
-- (2019, "In which we use box scores to classify players"): FOGO if >= 50% of
-- a player's value comes from faceoffs, defensive if >= 30% comes from
-- defensive plays, offensive otherwise. That rule cannot be applied literally
-- here, because Lacrosse Reference's value is a cumulative event sum while
-- EPA_points is a SIGNED residual -- "50% of a signed residual that may be
-- negative" is not a well-defined share. The thresholds are therefore applied
-- to OPPORTUNITY shares, which are non-negative and well defined. The
-- divergence is recorded in docs/USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md.
--
-- Rule, in order, first match wins:
--
--   1. goalie   -- the player faced at least one shot on goal as the goalie of
--                  record in the event log. Perfectly separating in 2026: all
--                  16 players with a shot on goal faced are rostered G, and
--                  every rostered G with zero shots faced (1 player, 1 game) is
--                  still mapped goalie by roster and flagged.
--
--   2. faceoff  -- the player took >= 50% of his team's faceoffs in the games
--                  he played. This is a team-share threshold, not a raw count,
--                  so it cannot be met by a wing player who took three draws in
--                  one game. It lands in a WIDE EMPIRICAL GAP: the 13 players
--                  above it sit between 0.812 and 0.977, the next-highest
--                  player in the league is at 0.158, and nobody in 2026 falls
--                  between 0.16 and 0.81. The threshold is not fitted to that
--                  gap -- it is Lacrosse Reference's published 50% -- but the
--                  gap is why no player's classification is sensitive to it.
--
--   3. offensive_field / defensive_field -- BY ROSTER POSITION, not by
--                  measured opportunity.
--
-- Step 3 is a deliberate, evidence-based refusal. A measured offence/defence
-- split was built and rejected: the feed attributes exactly ONE defensive act
-- (caused turnovers, 741 league-wide) against 4,106 shots and 1,369 turnovers,
-- so an opportunity-share rule classifies a close defender who took four shots
-- as an offensive player. Applying the documented 30% defensive threshold to
-- opportunity shares put 24 of 96 rostered defenders (including 21 of 42
-- SSDMs) in the offensive class. That is a measurement artefact of a
-- one-act-wide defensive record, not a finding about those players, so the
-- roster label is used instead and the reason is recorded on every row.
--
-- Faceoff participation OUTSIDE the specialist role is not thrown away: every
-- player carries `faceoff_team_share` and `takes_faceoffs`, so a midfielder
-- who takes 29 draws is visible without being relabelled.

CREATE OR REPLACE TABLE player_position_map AS

WITH raw_labels AS (
    -- every distinct label the player carried, with how many games it appeared
    -- in, so `raw_position` can show a genuinely mixed label rather than
    -- silently presenting the modal one as if it were the only one
    SELECT player_id,
           STRING_AGG(DISTINCT position_code, '|' ORDER BY position_code) AS raw_position_labels,
           COUNT(DISTINCT position_code)                                  AS n_distinct_labels
    FROM player_game
    WHERE position_code IS NOT NULL
    GROUP BY player_id
),

role_inputs AS (
    SELECT
        u.player_id,
        SUM(u.faceoffs)                                     AS faceoffs,
        SUM(t.team_faceoffs)                                AS team_faceoffs_in_games_played,
        SUM(u.recorded_offensive_opportunities)             AS recorded_offensive_opportunities,
        SUM(u.caused_turnovers)                             AS caused_turnovers
    FROM player_game_usage u
    JOIN team_game_usage t USING (game_id, team_id)
    GROUP BY u.player_id
),

goalie_opportunity AS (
    SELECT goalie_id AS player_id,
           COUNT(*) FILTER (WHERE is_shot_on_goal) AS shots_on_goal_faced
    FROM eligible_shot_events
    GROUP BY goalie_id
),

assembled AS (
    SELECT
        pp.player_id,
        COALESCE(rl.raw_position_labels, 'UNLABELLED')  AS raw_position,
        COALESCE(rl.n_distinct_labels, 0)               AS n_distinct_raw_labels,
        pp.position_code,
        CASE pp.position_code
            WHEN 'A'    THEN 'attack'
            WHEN 'M'    THEN 'midfield'
            WHEN 'SSDM' THEN 'short_stick_defensive_midfield'
            WHEN 'LSM'  THEN 'long_stick_midfield'
            WHEN 'D'    THEN 'defense'
            WHEN 'FO'   THEN 'faceoff'
            WHEN 'G'    THEN 'goalie'
            ELSE 'unknown'
        END                                             AS canonical_position,
        CASE pp.position_code
            WHEN 'A'    THEN 'attack'
            WHEN 'M'    THEN 'midfield'
            WHEN 'SSDM' THEN 'defensive_field'
            WHEN 'LSM'  THEN 'defensive_field'
            WHEN 'D'    THEN 'defensive_field'
            WHEN 'FO'   THEN 'faceoff'
            WHEN 'G'    THEN 'goalie'
            ELSE 'unknown'
        END                                             AS position_group,
        pp.baseline_group                               AS phase6_baseline_group,
        COALESCE(ri.faceoffs, 0)                        AS faceoffs,
        COALESCE(ri.team_faceoffs_in_games_played, 0)   AS team_faceoffs_in_games_played,
        COALESCE(ri.recorded_offensive_opportunities, 0) AS recorded_offensive_opportunities,
        COALESCE(ri.caused_turnovers, 0)                AS caused_turnovers,
        COALESCE(go.shots_on_goal_faced, 0)             AS shots_on_goal_faced,
        COALESCE(ri.faceoffs, 0)
            / NULLIF(CAST(ri.team_faceoffs_in_games_played AS DOUBLE), 0) AS faceoff_team_share
    FROM player_position pp
    LEFT JOIN raw_labels rl       ON rl.player_id = pp.player_id
    LEFT JOIN role_inputs ri      ON ri.player_id = pp.player_id
    LEFT JOIN goalie_opportunity go ON go.player_id = pp.player_id
)

SELECT
    a.*,
    (a.faceoffs > 0)                                        AS takes_faceoffs,

    CASE
        WHEN a.shots_on_goal_faced > 0                THEN 'goalie'
        WHEN a.position_code = 'G'                    THEN 'goalie'
        WHEN COALESCE(a.faceoff_team_share, 0) >= 0.50 THEN 'faceoff'
        WHEN a.position_group IN ('attack', 'midfield') THEN 'offensive_field'
        WHEN a.position_group = 'defensive_field'      THEN 'defensive_field'
        ELSE 'unclassified_field'
    END                                                     AS value_role,

    CASE
        WHEN a.shots_on_goal_faced > 0
            THEN 'measured_opportunity: faced ' || a.shots_on_goal_faced
                 || ' shots on goal as goalie of record'
        WHEN a.position_code = 'G'
            THEN 'roster_position: rostered goalie who faced no shot on goal '
                 || '(no goalie opportunity to measure)'
        WHEN COALESCE(a.faceoff_team_share, 0) >= 0.50
            THEN 'measured_opportunity: took ' || ROUND(100 * a.faceoff_team_share, 1)
                 || '% of team faceoffs in games played (threshold 50%)'
        WHEN a.position_group IN ('attack', 'midfield', 'defensive_field')
            THEN 'roster_position: measurable opportunities cannot separate offensive from '
                 || 'defensive field roles (the feed attributes one defensive act, caused '
                 || 'turnovers, 741 league-wide)'
        ELSE 'unlabelled: no position in any game played and no role-defining opportunity'
    END                                                     AS mapping_reason,

    CASE
        WHEN a.shots_on_goal_faced > 0                                    THEN 'high'
        WHEN COALESCE(a.faceoff_team_share, 0) >= 0.80                    THEN 'high'
        WHEN COALESCE(a.faceoff_team_share, 0) >= 0.50                    THEN 'medium'
        WHEN a.position_code = 'G'                                        THEN 'medium'
        WHEN a.n_distinct_raw_labels = 1 AND a.position_code <> 'UNK'     THEN 'medium'
        WHEN a.n_distinct_raw_labels > 1                                  THEN 'low'
        ELSE 'low'
    END                                                     AS mapping_confidence
FROM assembled a
ORDER BY a.player_id;
