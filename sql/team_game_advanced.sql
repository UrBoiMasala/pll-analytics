-- Phase 5: team-game advanced metrics.
--
-- One row per (eligible game, participating team) -- 100 rows over the 50
-- league-analytics-eligible 2026 games. Every rate uses NULLIF on its
-- denominator so a zero denominator yields NULL, never an infinity or a
-- silent zero (validation check 9).
--
-- Source discipline (see TEAM_ADVANCED_METRICS.md "Source selection"): every
-- column name carries its provenance where two sources exist and disagree.
--   *_pbp      -- derived from events.csv / possessions.csv
--   *_official -- taken from team_game_stats.csv (PLL's own box score)
-- Columns with no suffix are ones where the two sources were verified to
-- agree exactly across all 100 team-games (shots, shots on goal, goals,
-- points, two-point shots, two-point goals) or where only one source exists.

CREATE OR REPLACE TABLE team_game_advanced AS

WITH
-- Possessions this team ran on offense.
offense AS (
    SELECT
        game_id,
        offense_team_id                                        AS team_id,
        COUNT(*)                                               AS offensive_possessions,
        SUM(points_scored)                                     AS points_scored_poss,
        SUM(goals)                                             AS goals_poss,
        SUM(shot_attempts)                                     AS shots_poss,
        SUM(shots_on_goal)                                     AS shots_on_goal_poss,
        SUM(ended_in_turnover)                                 AS possession_ending_turnovers,
        SUM(started_on_faceoff)                                AS faceoff_start_possessions,
        COUNT(*) FILTER (WHERE has_two_point_attempt)          AS possessions_with_two_point_attempt,
        COUNT(*) FILTER (WHERE is_ambiguous)                   AS ambiguous_offensive_possessions,
        COUNT(*) FILTER (WHERE is_truncated)                   AS truncated_possessions,
        COUNT(*) FILTER (WHERE NOT is_truncated)               AS complete_possessions,
        COUNT(*) FILTER (WHERE is_measurable_span)             AS measurable_span_possessions,
        SUM(duration_seconds)                                  AS observed_possession_seconds,
        SUM(duration_seconds) FILTER (WHERE NOT is_truncated)  AS complete_possession_seconds,
        AVG(duration_seconds)    FILTER (WHERE NOT is_truncated)   AS mean_complete_possession_duration,
        MEDIAN(duration_seconds) FILTER (WHERE NOT is_truncated)   AS median_complete_possession_duration,
        AVG(duration_seconds)    FILTER (WHERE is_measurable_span) AS mean_measurable_span_seconds,
        MEDIAN(duration_seconds) FILTER (WHERE is_measurable_span) AS median_measurable_span_seconds
    FROM possessions
    GROUP BY game_id, offense_team_id
),

-- The same possessions viewed from the defending side.
defense AS (
    SELECT
        game_id,
        defense_team_id                        AS team_id,
        COUNT(*)                               AS defensive_possessions,
        SUM(points_scored)                     AS points_allowed_poss,
        SUM(goals)                             AS goals_allowed_poss,
        SUM(shot_attempts)                     AS shots_faced_poss,
        SUM(shots_on_goal)                     AS shots_on_goal_faced_poss,
        COUNT(*) FILTER (WHERE is_ambiguous)   AS ambiguous_defensive_possessions
    FROM possessions
    GROUP BY game_id, defense_team_id
),

-- Shooting, straight off the cleaned event log.
shooting AS (
    SELECT
        game_id,
        team_id,
        COUNT(*)                                                          AS shots,
        COUNT(*) FILTER (WHERE is_shot_on_goal)                           AS shots_on_goal,
        COUNT(*) FILTER (WHERE is_valid_goal)                             AS goals,
        SUM(points_scored)                                                AS points,
        COUNT(*) FILTER (WHERE is_two_point_attempt)                      AS two_point_attempts,
        COUNT(*) FILTER (WHERE is_two_point_attempt AND is_shot_on_goal)  AS two_point_shots_on_goal,
        COUNT(*) FILTER (WHERE is_two_point_attempt AND is_valid_goal)    AS two_point_goals,
        COUNT(*) FILTER (WHERE NOT is_two_point_attempt)                  AS one_point_attempts,
        COUNT(*) FILTER (WHERE NOT is_two_point_attempt AND is_valid_goal) AS one_point_goals,
        -- PLL's MU / MU_2_PT shot_type tag appears on GOAL events only: all 90
        -- tagged events season-wide are valid goals, and official powerPlayShots
        -- exceeds the tagged count in 70 of 100 team-games. So the tag supports a
        -- man-up GOAL count (and its point value, since MU_2_PT is worth 2), but
        -- not a man-up shot count and not a man-up possession count. Man-up shot
        -- volume therefore comes from the official box score below; see
        -- TEAM_ADVANCED_METRICS.md "Man-up".
        COUNT(*) FILTER (WHERE is_man_up_shot AND is_valid_goal)          AS man_up_goals_pbp,
        SUM(CASE WHEN is_man_up_shot THEN points_scored ELSE 0 END)       AS man_up_points_pbp
    FROM eligible_shots
    GROUP BY game_id, team_id
),

official AS (
    SELECT
        game_id,
        officialId              AS team_id,
        turnovers               AS turnovers_official,
        causedTurnovers         AS caused_turnovers_official,
        groundBalls             AS ground_balls_official,
        shotClockExpirations    AS shot_clock_expirations_official,
        faceoffs                AS faceoffs_official,
        faceoffsWon             AS faceoff_wins_official,
        faceoffsLost            AS faceoff_losses_official,
        saves                   AS saves_official,
        savePct                 AS save_pct_official,
        goalsAgainst            AS goals_allowed_official,
        scoresAgainst           AS points_allowed_official,
        scores                  AS points_official,
        twoPointGoalsAgainst    AS two_point_goals_allowed_official,
        numPenalties            AS penalties_official,
        pim                     AS penalty_minutes_official,
        timesManUp              AS man_up_opportunities_official,
        powerPlayShots          AS man_up_shots_official,
        powerPlayGoals          AS man_up_goals_official,
        timesShortHanded        AS man_down_opportunities_official,
        powerPlayGoalsAgainst   AS man_down_goals_allowed_official,
        clears                  AS clears_official,
        clearAttempts           AS clear_attempts_official,
        rideAttempts            AS ride_attempts_official,
        timeInPossesion         AS time_of_possession_official_seconds,
        timeInPossesionPct      AS time_of_possession_official_pct
    FROM team_game_stats
),

-- Opponent-side official figures, needed for save% denominators and for
-- shots-on-goal-allowed. Pulled through game_participants rather than a
-- self-join so the opponent mapping stays single-sourced.
opponent_shooting AS (
    SELECT
        p.game_id,
        p.team_id,
        s.shots         AS shots_allowed,
        s.shots_on_goal AS shots_on_goal_allowed,
        s.two_point_attempts AS two_point_attempts_allowed
    FROM game_participants p
    JOIN shooting s ON s.game_id = p.game_id AND s.team_id = p.opponent_team_id
),

opponent_official AS (
    SELECT p.game_id, p.team_id, o.turnovers_official AS opponent_turnovers_official
    FROM game_participants p
    JOIN official o ON o.game_id = p.game_id AND o.team_id = p.opponent_team_id
),

base AS (
    SELECT
        gp.game_id,
        gp.game_slug,
        gp.start_date_utc,
        gp.week,
        gp.game_type,
        gp.is_playoff,
        gp.team_id,
        t.full_name AS team_name,
        gp.opponent_team_id,
        gp.is_home,
        CAST(gp.team_score_official     AS INTEGER) AS team_score_official,
        CAST(gp.opponent_score_official AS INTEGER) AS opponent_score_official,
        CASE WHEN gp.team_score_official > gp.opponent_score_official THEN 'W'
             WHEN gp.team_score_official < gp.opponent_score_official THEN 'L'
             ELSE 'T' END AS result,
        o.*  EXCLUDE (game_id, team_id),
        d.*  EXCLUDE (game_id, team_id),
        s.*  EXCLUDE (game_id, team_id),
        ofc.* EXCLUDE (game_id, team_id),
        os.* EXCLUDE (game_id, team_id),
        oo.* EXCLUDE (game_id, team_id),
        tp.turnovers_pbp,
        tp.ground_balls_pbp,
        tp.shot_clock_expirations_pbp,
        tp.faceoff_wins_pbp,
        tp.penalties_pbp,
        sv.saves_pbp,
        vf.* EXCLUDE (game_id)
    FROM game_participants gp
    JOIN teams_raw            t   ON t.team_id = gp.team_id
    JOIN offense              o   ON o.game_id  = gp.game_id AND o.team_id  = gp.team_id
    JOIN defense              d   ON d.game_id  = gp.game_id AND d.team_id  = gp.team_id
    JOIN shooting             s   ON s.game_id  = gp.game_id AND s.team_id  = gp.team_id
    JOIN official             ofc ON ofc.game_id = gp.game_id AND ofc.team_id = gp.team_id
    JOIN opponent_shooting    os  ON os.game_id = gp.game_id AND os.team_id = gp.team_id
    JOIN opponent_official    oo  ON oo.game_id = gp.game_id AND oo.team_id = gp.team_id
    LEFT JOIN team_pbp_counts tp  ON tp.game_id = gp.game_id AND tp.team_id = gp.team_id
    LEFT JOIN team_saves_pbp  sv  ON sv.game_id = gp.game_id AND sv.team_id = gp.team_id
    LEFT JOIN game_validation_flags vf ON vf.game_id = gp.game_id
)

SELECT
    -- ---- keys / context -------------------------------------------------
    game_id, game_slug, start_date_utc, week, game_type, is_playoff,
    team_id, team_name, opponent_team_id, is_home,
    team_score_official, opponent_score_official, result,

    -- ---- core possession metrics ---------------------------------------
    offensive_possessions,
    defensive_possessions,
    offensive_possessions + defensive_possessions              AS total_game_possessions,
    points_scored_poss                                         AS points_scored,
    points_allowed_poss                                        AS points_allowed,
    points_scored_poss  / NULLIF(offensive_possessions, 0)     AS points_per_possession,
    points_allowed_poss / NULLIF(defensive_possessions, 0)     AS points_allowed_per_possession,
    -- offensive_efficiency / defensive_efficiency are, by the Phase 5
    -- definition, identical to the two columns above. Both names are exposed
    -- because both are named in the brief; metric_definitions.csv records the
    -- alias explicitly rather than leaving two same-valued columns unexplained.
    points_scored_poss  / NULLIF(offensive_possessions, 0)     AS offensive_efficiency,
    points_allowed_poss / NULLIF(defensive_possessions, 0)     AS defensive_efficiency,
      points_scored_poss  / NULLIF(offensive_possessions, 0)
    - points_allowed_poss / NULLIF(defensive_possessions, 0)   AS net_efficiency,
    100 * points_scored_poss  / NULLIF(offensive_possessions, 0) AS offensive_efficiency_per_100,
    100 * points_allowed_poss / NULLIF(defensive_possessions, 0) AS defensive_efficiency_per_100,
    100 * (  points_scored_poss  / NULLIF(offensive_possessions, 0)
           - points_allowed_poss / NULLIF(defensive_possessions, 0)) AS net_efficiency_per_100,

    -- ---- shooting / scoring efficiency ---------------------------------
    shots, shots_on_goal, goals, points,
    goals  / NULLIF(CAST(shots AS DOUBLE), 0)                  AS shooting_pct,
    shots_on_goal / NULLIF(CAST(shots AS DOUBLE), 0)           AS shots_on_goal_pct,
    goals / NULLIF(CAST(shots_on_goal AS DOUBLE), 0)           AS goals_per_shot_on_goal,
    points / NULLIF(CAST(shots AS DOUBLE), 0)                  AS points_per_shot,
    goals  / NULLIF(CAST(offensive_possessions AS DOUBLE), 0)  AS goals_per_possession,
    shots  / NULLIF(CAST(offensive_possessions AS DOUBLE), 0)  AS shots_per_possession,
    shots_on_goal / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS shots_on_goal_per_possession,

    -- ---- PLL two-point metrics -----------------------------------------
    two_point_attempts,
    two_point_shots_on_goal,
    two_point_goals,
    2 * two_point_goals                                        AS two_point_points,
    one_point_attempts,
    one_point_goals,
    one_point_goals                                            AS one_point_points,
    two_point_attempts / NULLIF(CAST(shots AS DOUBLE), 0)      AS two_point_attempt_rate,
    two_point_goals / NULLIF(CAST(two_point_attempts AS DOUBLE), 0)  AS two_point_conversion_pct,
    one_point_goals / NULLIF(CAST(one_point_attempts AS DOUBLE), 0)  AS one_point_conversion_pct,
    (2.0 * two_point_goals) / NULLIF(CAST(points AS DOUBLE), 0)      AS two_point_points_share,
    (2.0 * two_point_goals) / NULLIF(CAST(two_point_attempts AS DOUBLE), 0) AS points_per_two_point_attempt,
    possessions_with_two_point_attempt,
    possessions_with_two_point_attempt / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS two_point_possession_rate,

    -- ---- turnovers / possession security -------------------------------
    turnovers_official                                         AS turnovers,
    turnovers_pbp,
    turnovers_pbp - turnovers_official                         AS turnovers_pbp_minus_official,
    possession_ending_turnovers,
    caused_turnovers_official,
    opponent_turnovers_official                                AS turnovers_forced,
    turnovers_official / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS turnovers_per_possession,
    turnovers_official / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS turnover_rate,
    possession_ending_turnovers / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS possession_ending_turnover_rate,
    opponent_turnovers_official / NULLIF(CAST(defensive_possessions AS DOUBLE), 0) AS turnovers_forced_per_defensive_possession,

    -- ---- faceoffs / possession share -----------------------------------
    faceoffs_official                                          AS faceoffs,
    faceoff_wins_official                                      AS faceoff_wins,
    faceoff_losses_official                                    AS faceoff_losses,
    faceoff_wins_official / NULLIF(CAST(faceoffs_official AS DOUBLE), 0) AS faceoff_win_pct,
    faceoff_wins_pbp,
    faceoff_wins_pbp - faceoff_wins_official                   AS faceoff_wins_pbp_minus_official,
    faceoff_start_possessions,
    faceoff_start_possessions / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS faceoff_start_possession_share,

    -- ---- man-up (see TEAM_ADVANCED_METRICS.md "Man-up") ----------------
    -- The extra-man OPPORTUNITY is the denominator here, not a possession: the
    -- feed cannot say which reconstructed possessions were played man-up, and
    -- inventing one from penalty timing would be exactly the unevidenced
    -- penalty-state inference this phase refuses to make.
    man_up_opportunities_official                              AS man_up_opportunities,
    man_up_shots_official                                      AS man_up_shots,
    man_up_goals_official                                      AS man_up_goals,
    man_up_goals_official / NULLIF(CAST(man_up_shots_official AS DOUBLE), 0)         AS man_up_shooting_pct,
    man_up_goals_official / NULLIF(CAST(man_up_opportunities_official AS DOUBLE), 0) AS man_up_goals_per_opportunity,
    man_up_goals_pbp,
    man_up_points_pbp                                          AS man_up_points,
    man_up_points_pbp / NULLIF(CAST(man_up_opportunities_official AS DOUBLE), 0) AS man_up_points_per_opportunity,
    man_up_goals_pbp - man_up_goals_official                   AS man_up_goals_pbp_minus_official,
    man_down_opportunities_official                            AS man_down_opportunities,
    man_down_goals_allowed_official                            AS man_down_goals_allowed,
    man_down_goals_allowed_official / NULLIF(CAST(man_down_opportunities_official AS DOUBLE), 0) AS man_down_goals_allowed_per_opportunity,

    -- ---- ground balls ---------------------------------------------------
    ground_balls_official                                      AS ground_balls,
    ground_balls_pbp,
    ground_balls_pbp - ground_balls_official                   AS ground_balls_pbp_minus_official,
    ground_balls_official / NULLIF(CAST(offensive_possessions + defensive_possessions AS DOUBLE), 0) AS ground_balls_per_possession,

    -- ---- team goalkeeping ----------------------------------------------
    shots_allowed,
    shots_on_goal_allowed,
    goals_allowed_official                                     AS goals_allowed,
    points_allowed_official                                    AS points_allowed_boxscore,
    two_point_goals_allowed_official                           AS two_point_goals_allowed,
    two_point_attempts_allowed,
    saves_official                                             AS saves,
    saves_pbp,
    saves_pbp - saves_official                                 AS saves_pbp_minus_official,
    -- PLL's own savePct uses saves / (saves + goals allowed); it excludes the
    -- on_goal_no_save shot class. Both denominators are exposed, named.
    save_pct_official,
    saves_official / NULLIF(CAST(shots_on_goal_allowed AS DOUBLE), 0) AS save_pct_vs_shots_on_goal,
    goals_allowed_official / NULLIF(CAST(shots_on_goal_allowed AS DOUBLE), 0) AS opponent_shooting_pct_on_goal,

    -- ---- penalties / shot-clock ----------------------------------------
    penalties_official                                         AS penalties,
    penalties_pbp,
    penalty_minutes_official                                   AS penalty_minutes,
    shot_clock_expirations_official                            AS shot_clock_expirations,
    shot_clock_expirations_pbp,
    shot_clock_expirations_pbp - shot_clock_expirations_official AS shot_clock_expirations_pbp_minus_official,
    shot_clock_expirations_official / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS shot_clock_expiration_rate,

    -- ---- clearing / riding (official counts only; NOT efficiency models) --
    clears_official        AS clears,
    clear_attempts_official AS clear_attempts,
    ride_attempts_official  AS ride_attempts,

    -- ---- possession span / time of possession --------------------------
    -- "possession seconds" here means the span from a possession's first
    -- logged event to its last logged event. It is NOT time of possession:
    -- season-wide it recovers only ~76% of the official figure and correlates
    -- with it at r=0.58. See TEAM_ADVANCED_METRICS.md "Time of possession".
    observed_possession_seconds,
    complete_possession_seconds,
    truncated_possessions,
    complete_possessions,
    measurable_span_possessions,
    -- "complete" = not truncated by a period/game boundary. "measurable span"
    -- additionally requires the possession to be unambiguous and to span two
    -- DISTINCT logged events, so its duration is a real measurement rather
    -- than the 0 that a single-event possession carries by construction.
    mean_complete_possession_duration,
    median_complete_possession_duration,
    mean_measurable_span_seconds,
    median_measurable_span_seconds,
    time_of_possession_official_seconds,
    time_of_possession_official_pct,
    observed_possession_seconds / NULLIF(CAST(time_of_possession_official_seconds AS DOUBLE), 0) AS possession_span_coverage_ratio,

    -- ---- possession-model uncertainty ----------------------------------
    ambiguous_offensive_possessions,
    ambiguous_defensive_possessions,
    ambiguous_offensive_possessions / NULLIF(CAST(offensive_possessions AS DOUBLE), 0) AS ambiguous_offensive_possession_share,

    -- ---- validation flags (game-level evidence from validation_report) --
    turnover_validation_status,
    ground_ball_validation_status,
    shot_clock_validation_status,
    save_validation_status,
    penalty_validation_status,
    COALESCE(turnover_validation_status,   'PASS') <> 'PASS' AS has_turnover_validation_issue,
    COALESCE(ground_ball_validation_status,'PASS') <> 'PASS' AS has_ground_ball_validation_issue,
    COALESCE(shot_clock_validation_status, 'PASS') <> 'PASS' AS has_shot_clock_validation_issue,
    COALESCE(save_validation_status,       'PASS') <> 'PASS' AS has_save_validation_issue,
    COALESCE(penalty_validation_status,    'PASS') <> 'PASS' AS has_penalty_validation_issue,
    (   COALESCE(turnover_validation_status,   'PASS') = 'UNRESOLVED'
     OR COALESCE(ground_ball_validation_status,'PASS') = 'UNRESOLVED'
     OR COALESCE(shot_clock_validation_status, 'PASS') = 'UNRESOLVED'
     OR COALESCE(save_validation_status,       'PASS') = 'UNRESOLVED'
     OR COALESCE(penalty_validation_status,    'PASS') = 'UNRESOLVED') AS has_unresolved_validation_issue
FROM base
ORDER BY game_id, team_id;
