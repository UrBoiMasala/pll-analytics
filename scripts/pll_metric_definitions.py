"""
Phase 5: machine-readable metric provenance.

Single source of truth for data/processed/2026/metric_definitions.csv. Every
metric that appears in team_game_advanced.csv / team_season_advanced.csv /
possession_length_splits.csv should have a row here, plus rows for the
Lacrosse Reference concepts that were examined and deliberately NOT built.

Columns
-------
metric_name        column name as it appears in the output tables
level              team_game | team_season | possession_bucket | n/a
definition         plain-English definition
numerator          exact numerator expression
denominator        exact denominator expression ('n/a' for count metrics)
source_table       which canonical table the inputs come from
source_columns     the specific columns used
uncertainty_notes  what a consumer must know before trusting this number
pll_specific       TRUE if the metric only exists / only makes sense in the PLL
status             production | diagnostic | deferred | unsupported
lacrosse_reference_concept       the closest LR metric, or 'none'
lacrosse_reference_relationship  identical | adapted | pll_only | not_built
"""

DEFINITION_COLUMNS = [
    "metric_name", "level", "definition", "numerator", "denominator",
    "source_table", "source_columns", "uncertainty_notes", "pll_specific",
    "status", "lacrosse_reference_concept", "lacrosse_reference_relationship",
]

POSS = "possessions.csv"
EVENTS = "events.csv"
OFFICIAL = "team_game_stats.csv"
GAMES = "games.csv"

# Uncertainty notes reused across many rows.
U_POSS_STRUCT = (
    "Possession team attribution and points are structurally validated (0 possessions with "
    "uncertain offensive team; possession points reconcile exactly to official final scores in "
    "all 50 eligible games). 36.2% of possessions carry an is_ambiguous flag, but that ambiguity "
    "is about the boundary mechanism/instant, not about which team had the ball. See "
    "team_metric_sensitivity.csv for the measured effect on this metric."
)
U_EVENT_EXACT = (
    "Play-by-play derived value was verified to equal the official team box-score value in all "
    "100 team-games, so the two sources do not disagree for this metric."
)
U_OFFICIAL_TO = (
    "Official box-score value is used as the numerator. Phase 4.25 left 19 games with unresolved "
    "turnover residuals; the per-team play-by-play-minus-official residual is carried on the same "
    "row (turnovers_pbp_minus_official) and has_turnover_validation_issue flags the game."
)
U_OFFICIAL_GB = (
    "Official box-score value is used. Phase 4.25 left 16 games with unresolved ground-ball "
    "residuals; ground_balls_pbp_minus_official carries the per-team disagreement and "
    "has_ground_ball_validation_issue flags the game."
)
U_SPAN = (
    "'Possession seconds' is the span from a possession's first logged event to its last logged "
    "event. It is NOT time of possession: it recovers ~76% of the official figure season-wide and "
    "correlates with it at only r=0.58, because the span excludes the interval between the "
    "previous possession's last logged event and this one's first. Use "
    "time_of_possession_official_seconds for time of possession."
)
U_MANUP = (
    "Official box score. The play-by-play man-up tag (shot_type MU / MU_2_PT) lands on GOAL events "
    "only -- all 90 tagged events in the season are valid goals -- so the event feed supports a "
    "man-up goal count but not a man-up shot count and not a man-up possession count. No "
    "penalty-clock state is reconstructed anywhere; the extra-man opportunity is the denominator."
)


def _d(name, level, definition, num, den, src, cols, unc, pll, status,
       lr="none", lrrel="pll_only"):
    # "n/a" is written out as "not_applicable": pandas reads the bare string
    # "n/a" back as NaN under its default na_values, which would make a
    # deliberately-empty denominator indistinguishable from a missing one.
    fix = lambda v: "not_applicable" if v == "n/a" else v  # noqa: E731
    return dict(zip(DEFINITION_COLUMNS, [
        name, fix(level), definition, fix(num), fix(den), fix(src), fix(cols), unc,
        "TRUE" if pll else "FALSE", status, lr, lrrel,
    ]))


DEFINITIONS = [
    # ---------------- core possession ----------------
    _d("offensive_possessions", "team_game/team_season",
       "Reconstructed possessions on which this team had offensive control.",
       "count(possessions where offense_team_id = team)", "n/a",
       POSS, "offense_team_id", U_POSS_STRUCT, False, "production",
       "possessions", "adapted"),
    _d("defensive_possessions", "team_game/team_season",
       "Reconstructed possessions this team defended.",
       "count(possessions where defense_team_id = team)", "n/a",
       POSS, "defense_team_id", U_POSS_STRUCT, False, "production",
       "possessions faced", "adapted"),
    _d("points_scored", "team_game/team_season",
       "PLL points scored on this team's offensive possessions (2 for a two-point goal).",
       "sum(possessions.points_scored) over offensive possessions", "n/a",
       POSS, "points_scored, offense_team_id",
       "Reconciles exactly with the official final score in all 50 eligible games.",
       True, "production", "goals", "adapted"),
    _d("points_allowed", "team_game/team_season",
       "PLL points allowed on possessions this team defended.",
       "sum(possessions.points_scored) over defensive possessions", "n/a",
       POSS, "points_scored, defense_team_id",
       "Reconciles exactly with the official final score in all 50 eligible games.",
       True, "production", "goals allowed", "adapted"),
    _d("points_per_possession", "team_game/team_season",
       "PLL points scored per offensive possession.",
       "sum(points_scored)", "count(offensive possessions)",
       POSS, "points_scored, offense_team_id", U_POSS_STRUCT, True, "production",
       "offensive efficiency (goals/possession)", "adapted"),
    _d("offensive_efficiency", "team_game/team_season",
       "Alias of points_per_possession. Both names are exposed because both are in common use; "
       "they are the same number, not two measurements.",
       "sum(points_scored)", "count(offensive possessions)",
       POSS, "points_scored, offense_team_id", U_POSS_STRUCT, True, "production",
       "offensive efficiency", "adapted"),
    _d("points_allowed_per_possession", "team_game/team_season",
       "PLL points allowed per defensive possession.",
       "sum(points_scored on defensive possessions)", "count(defensive possessions)",
       POSS, "points_scored, defense_team_id", U_POSS_STRUCT, True, "production",
       "defensive efficiency", "adapted"),
    _d("defensive_efficiency", "team_game/team_season",
       "Alias of points_allowed_per_possession. Lower is better.",
       "sum(points_scored on defensive possessions)", "count(defensive possessions)",
       POSS, "points_scored, defense_team_id", U_POSS_STRUCT, True, "production",
       "defensive efficiency", "adapted"),
    _d("net_efficiency", "team_game/team_season",
       "offensive_efficiency minus defensive_efficiency, in points per possession.",
       "offensive_efficiency - defensive_efficiency", "n/a",
       POSS, "points_scored, offense_team_id, defense_team_id",
       U_POSS_STRUCT + " Not opponent-adjusted -- schedule strength is not accounted for and is "
       "deferred to a later phase.", True, "production",
       "cumulative efficiency (differently constructed)", "adapted"),
    _d("offensive_efficiency_per_100", "team_game/team_season",
       "offensive_efficiency x 100, i.e. points per 100 offensive possessions. Exposed under an "
       "explicit name so the per-possession and per-100 scales are never confused.",
       "100 * sum(points_scored)", "count(offensive possessions)",
       POSS, "points_scored, offense_team_id", U_POSS_STRUCT, True, "production",
       "offensive efficiency", "adapted"),
    _d("defensive_efficiency_per_100", "team_game/team_season",
       "defensive_efficiency x 100.", "100 * sum(points allowed)",
       "count(defensive possessions)", POSS, "points_scored, defense_team_id",
       U_POSS_STRUCT, True, "production", "defensive efficiency", "adapted"),
    _d("net_efficiency_per_100", "team_game/team_season",
       "net_efficiency x 100.", "100 * (off_eff - def_eff)", "n/a",
       POSS, "points_scored, offense_team_id, defense_team_id", U_POSS_STRUCT,
       True, "production", "none", "adapted"),

    # ---------------- pace ----------------
    _d("team_possessions_per_game", "team_season",
       "Offensive possessions per game. Pace is expressed in possession COUNTS, not seconds -- "
       "see time_of_possession_official_seconds for why duration is not used.",
       "sum(offensive_possessions)", "games_played",
       POSS, "offense_team_id", U_POSS_STRUCT, False, "production",
       "pace", "adapted"),
    _d("combined_possessions_per_game", "team_season",
       "Total possessions by both teams per game (offensive + defensive).",
       "sum(offensive_possessions + defensive_possessions)", "games_played",
       POSS, "offense_team_id, defense_team_id", U_POSS_STRUCT, False, "production",
       "pace", "adapted"),

    # ---------------- shooting ----------------
    _d("shots", "team_game/team_season",
       "Shot attempts (shot and goal events carrying a resolved shot_outcome).",
       "count(shot/goal events)", "n/a", EVENTS,
       "event_type, shot_outcome, team_id, is_analysis_eligible_event",
       U_EVENT_EXACT, False, "production", "shots", "identical"),
    _d("shots_on_goal", "team_game/team_season",
       "Shots whose outcome was goal, saved, or on_goal_no_save.",
       "count(shots with is_shot_on_goal)", "n/a", EVENTS, "shot_outcome",
       U_EVENT_EXACT, False, "production", "shots on goal", "identical"),
    _d("goals", "team_game/team_season",
       "Valid goals. A two-point goal counts as ONE goal here; its second point appears in points.",
       "count(events where is_valid_goal)", "n/a", EVENTS,
       "is_valid_goal, shot_type", U_EVENT_EXACT, True, "production",
       "goals", "adapted"),
    _d("points", "team_game/team_season",
       "PLL points: 1 per one-point goal, 2 per two-point goal. Equals the official final score.",
       "sum(1 or 2 per valid goal by shot_type)", "n/a", EVENTS,
       "is_valid_goal, is_two_point_attempt",
       "Verified equal to games.csv home_score/away_score in all 100 team-games.",
       True, "production", "goals (NCAA has no two-point goal)", "pll_only"),
    _d("shooting_pct", "team_game/team_season",
       "Goals per shot attempt. Deliberately NOT points per shot -- a two-point goal is one goal.",
       "goals", "shots", EVENTS, "is_valid_goal, shot_outcome",
       U_EVENT_EXACT, False, "production", "shooting percentage", "identical"),
    _d("shots_on_goal_pct", "team_game/team_season",
       "Share of shot attempts that were on goal.", "shots_on_goal", "shots",
       EVENTS, "shot_outcome", U_EVENT_EXACT, False, "production",
       "shots on goal percentage", "identical"),
    _d("goals_per_shot_on_goal", "team_game/team_season",
       "Finishing rate against the goalie.", "goals", "shots_on_goal",
       EVENTS, "is_valid_goal, shot_outcome", U_EVENT_EXACT, False, "production",
       "none", "adapted"),
    _d("points_per_shot", "team_game/team_season",
       "PLL points produced per shot attempt. This is the metric that rewards two-point volume; "
       "shooting_pct deliberately does not.",
       "points", "shots", EVENTS, "is_valid_goal, is_two_point_attempt",
       U_EVENT_EXACT, True, "production",
       "shooting percentage (equivalent only where all goals are worth 1)", "pll_only"),
    _d("goals_per_possession", "team_game/team_season",
       "Share of offensive possessions ending in a goal. A possession can contain at most one goal "
       "(a goal closes it), verified season-wide, so this is directly comparable to Lacrosse "
       "Reference's 'Efficiency' column.",
       "goals", "offensive_possessions", f"{EVENTS} + {POSS}",
       "is_valid_goal, offense_team_id", U_POSS_STRUCT, False, "production",
       "efficiency (% of possessions ending in a goal)", "identical"),
    _d("shots_per_possession", "team_game/team_season",
       "Shot attempts per offensive possession.", "shots", "offensive_possessions",
       f"{EVENTS} + {POSS}", "shot_outcome, offense_team_id", U_POSS_STRUCT,
       False, "production", "shots per possession", "identical"),
    _d("shots_on_goal_per_possession", "team_game/team_season",
       "Shots on goal per offensive possession.", "shots_on_goal", "offensive_possessions",
       f"{EVENTS} + {POSS}", "shot_outcome, offense_team_id", U_POSS_STRUCT,
       False, "production", "none", "adapted"),

    # ---------------- two-point ----------------
    _d("two_point_attempts", "team_game/team_season",
       "Shot attempts from behind the two-point arc (shot_type 2_PT or MU_2_PT).",
       "count(shots where is_two_point_attempt)", "n/a", EVENTS,
       "is_two_point_attempt, shot_type",
       "Equals official twoPointShots in all 100 team-games.", True, "production",
       "none -- NCAA has no two-point shot", "pll_only"),
    _d("two_point_goals", "team_game/team_season",
       "Made two-point shots. Counts as 1 goal and 2 points.",
       "count(valid goals where is_two_point_attempt)", "n/a", EVENTS,
       "is_two_point_attempt, is_valid_goal",
       "Equals official twoPointGoals in all 100 team-games.", True, "production",
       "none", "pll_only"),
    _d("two_point_points", "team_game/team_season", "Points produced by two-point goals.",
       "2 * two_point_goals", "n/a", EVENTS, "is_two_point_attempt, is_valid_goal",
       "Exact.", True, "production", "none", "pll_only"),
    _d("one_point_goals", "team_game/team_season", "Goals from inside the arc.",
       "count(valid goals where NOT is_two_point_attempt)", "n/a", EVENTS,
       "is_two_point_attempt, is_valid_goal",
       "Equals official onePointGoals in all 100 team-games.", True, "production",
       "goals", "adapted"),
    _d("one_point_points", "team_game/team_season",
       "Points from one-point goals (numerically equal to one_point_goals; exposed so the two-point "
       "and one-point point contributions can be added without a mental conversion).",
       "one_point_goals", "n/a", EVENTS, "is_two_point_attempt, is_valid_goal",
       "Exact.", True, "production", "none", "pll_only"),
    _d("two_point_attempt_rate", "team_game/team_season",
       "Share of all shot attempts taken from two-point range.",
       "two_point_attempts", "shots", EVENTS, "is_two_point_attempt",
       "Exact vs official.", True, "production", "none", "pll_only"),
    _d("two_point_conversion_pct", "team_game/team_season",
       "Make rate on two-point attempts.", "two_point_goals", "two_point_attempts",
       EVENTS, "is_two_point_attempt, is_valid_goal", "Exact vs official.",
       True, "production", "none", "pll_only"),
    _d("one_point_conversion_pct", "team_game/team_season",
       "Make rate on one-point attempts, exposed as the comparison baseline for "
       "two_point_conversion_pct.", "one_point_goals", "one_point_attempts",
       EVENTS, "is_two_point_attempt, is_valid_goal", "Exact vs official.",
       True, "production", "shooting percentage", "adapted"),
    _d("two_point_points_share", "team_game/team_season",
       "Share of a team's total points that came from two-point goals.",
       "two_point_points", "points", EVENTS, "is_two_point_attempt, is_valid_goal",
       "Exact vs official.", True, "production", "none", "pll_only"),
    _d("points_per_two_point_attempt", "team_game/team_season",
       "Expected points yielded by a two-point attempt. Compare directly against "
       "one_point_conversion_pct to judge whether the longer shot is worth taking.",
       "two_point_points", "two_point_attempts", EVENTS,
       "is_two_point_attempt, is_valid_goal", "Exact vs official.", True,
       "production", "none", "pll_only"),
    _d("two_point_possession_rate", "team_game/team_season",
       "Share of offensive possessions containing at least one two-point attempt.",
       "count(possessions where has_two_point_attempt)", "offensive_possessions",
       POSS, "has_two_point_attempt, offense_team_id", U_POSS_STRUCT, True,
       "production", "none", "pll_only"),

    # ---------------- turnovers ----------------
    _d("turnovers", "team_game/team_season",
       "Turnovers committed, from the official box score.",
       "team_game_stats.turnovers", "n/a", OFFICIAL, "turnovers", U_OFFICIAL_TO,
       False, "production", "turnovers", "identical"),
    _d("turnovers_pbp", "team_game/team_season",
       "Turnover events in the cleaned play-by-play. Exposed alongside the official count, never "
       "blended with it: the two disagree in 33 of 100 team-games (play-by-play higher by 22 "
       "events season-wide).",
       "count(events where event_type='turnover')", "n/a", EVENTS,
       "event_type, team_id", U_OFFICIAL_TO, False, "diagnostic",
       "turnovers", "adapted"),
    _d("possession_ending_turnovers", "team_game/team_season",
       "Possessions closed by a turnover. Lower than the turnover count because the possession "
       "engine suppresses same-instant companion turnover events (e.g. the turnover PLL logs "
       "alongside the opponent's goal).",
       "count(possessions where end_reason='turnover')", "n/a", POSS,
       "end_reason, offense_team_id",
       "Internally consistent with the possession model; NOT the official turnover count. Used as "
       "the turnover metric in the sensitivity analysis because it can be subset by possession.",
       False, "production", "turnovers", "adapted"),
    _d("turnovers_per_possession", "team_game/team_season",
       "Official turnovers per offensive possession.", "turnovers",
       "offensive_possessions", f"{OFFICIAL} + {POSS}", "turnovers, offense_team_id",
       U_OFFICIAL_TO, False, "production", "turnover rate", "identical"),
    _d("turnover_rate", "team_game/team_season",
       "Alias of turnovers_per_possession -- the Phase 5 brief names both and defines them "
       "identically, so both are emitted and the identity is recorded here rather than left for a "
       "reader to discover.",
       "turnovers", "offensive_possessions", f"{OFFICIAL} + {POSS}",
       "turnovers, offense_team_id", U_OFFICIAL_TO, False, "production",
       "turnover rate", "identical"),
    _d("possession_ending_turnover_rate", "team_game/team_season",
       "Share of offensive possessions that ended in a turnover.",
       "possession_ending_turnovers", "offensive_possessions", POSS,
       "end_reason, offense_team_id", U_POSS_STRUCT, False, "production",
       "turnover rate", "adapted"),
    _d("turnovers_forced", "team_game/team_season",
       "Turnovers committed by the opponent (official).",
       "opponent team_game_stats.turnovers", "n/a", OFFICIAL, "turnovers",
       U_OFFICIAL_TO, False, "production", "none", "adapted"),
    _d("turnovers_forced_per_defensive_possession", "team_game/team_season",
       "Opponent turnovers per possession this team defended.", "turnovers_forced",
       "defensive_possessions", f"{OFFICIAL} + {POSS}", "turnovers, defense_team_id",
       U_OFFICIAL_TO, False, "production", "defensive turnover rate", "adapted"),
    _d("caused_turnovers_official", "team_game/team_season",
       "Caused turnovers, official box score ONLY. The event-level caused-turnover field is "
       "structurally null in every event of the season, so this can never be derived from the "
       "play-by-play or attributed to a possession.",
       "team_game_stats.causedTurnovers", "n/a", OFFICIAL, "causedTurnovers",
       "Not available at event or possession level -- do not attempt to build a possession-level "
       "caused-turnover metric from events.csv.", False, "production",
       "caused turnovers", "identical"),

    # ---------------- faceoffs ----------------
    _d("faceoffs", "team_game/team_season",
       "Faceoffs taken (official). Both teams in a game carry the same value.",
       "team_game_stats.faceoffs", "n/a", OFFICIAL, "faceoffs",
       "In 8 games faceoffsWon + faceoffsLost is 1-2 short of faceoffs -- PLL counts draws that "
       "produced no recorded winner (violations/redraws) in the denominator.",
       False, "production", "faceoffs", "identical"),
    _d("faceoff_wins", "team_game/team_season", "Faceoffs won (official).",
       "team_game_stats.faceoffsWon", "n/a", OFFICIAL, "faceoffsWon",
       "Play-by-play faceoff events match this in 99 of 100 team-games (faceoff_wins_pbp_minus_"
       "official carries the one disagreement).", False, "production",
       "faceoff wins", "identical"),
    _d("faceoff_win_pct", "team_game/team_season",
       "Faceoff win rate, using PLL's own denominator (all draws, including no-decision draws).",
       "faceoff_wins", "faceoffs", OFFICIAL, "faceoffsWon, faceoffs",
       "Official source chosen over play-by-play: it is cleaner (matches in 99/100) and its "
       "denominator includes no-decision draws that the event log does not represent.",
       False, "production", "faceoff win percentage", "identical"),
    _d("faceoff_start_possessions", "team_game/team_season",
       "Offensive possessions that began with a faceoff win.",
       "count(possessions where start_reason='faceoff_win')", "n/a", POSS,
       "start_reason, offense_team_id",
       "Faceoff-started possessions are never flagged ambiguous -- a faceoff event's team "
       "attribution was verified 1,326/1,326 resolved in Phase 3.5.", False,
       "production", "possessions started off a faceoff", "identical"),
    _d("faceoff_start_possession_share", "team_game/team_season",
       "Share of a team's offensive possessions that began with a faceoff win.",
       "faceoff_start_possessions", "offensive_possessions", POSS,
       "start_reason, offense_team_id", U_POSS_STRUCT, False, "production",
       "possession source split", "adapted"),

    # ---------------- man-up ----------------
    _d("man_up_opportunities", "team_game/team_season",
       "Extra-man opportunities (official timesManUp). The only trustworthy count of how often a "
       "team was actually man-up.", "team_game_stats.timesManUp", "n/a", OFFICIAL,
       "timesManUp", U_MANUP, False, "production", "EMO opportunities", "identical"),
    _d("man_up_shots", "team_game/team_season",
       "Shots taken while man-up (official powerPlayShots). Official-only by necessity: the event "
       "feed carries no man-up tag on a missed or saved shot.",
       "team_game_stats.powerPlayShots", "n/a", OFFICIAL, "powerPlayShots",
       U_MANUP, False, "production", "EMO shots", "identical"),
    _d("man_up_goals", "team_game/team_season",
       "Goals scored while man-up (official powerPlayGoals).",
       "team_game_stats.powerPlayGoals", "n/a", OFFICIAL, "powerPlayGoals",
       "Official. The play-by-play tagged goal count agrees in 97 of 100 team-games; the "
       "disagreement is carried as man_up_goals_pbp_minus_official.", False,
       "production", "EMO goals", "identical"),
    _d("man_up_goals_pbp", "team_game/team_season",
       "Goals carrying PLL's MU / MU_2_PT shot_type tag. Exposed only because it is the source of "
       "man_up_points -- the official box score gives no one-point/two-point split of man-up goals.",
       "count(valid goals where is_man_up_shot)", "n/a", EVENTS,
       "is_man_up_shot, is_valid_goal", U_MANUP, False, "diagnostic",
       "EMO goals", "adapted"),
    _d("man_up_points", "team_game/team_season",
       "PLL points scored while man-up (a MU_2_PT goal is worth 2). Derived from the play-by-play "
       "tag because only it distinguishes one- from two-point man-up goals.",
       "sum(points over tagged man-up goals)", "n/a", EVENTS,
       "is_man_up_shot, is_valid_goal, is_two_point_attempt", U_MANUP, True,
       "production", "EMO goals", "adapted"),
    _d("man_up_shooting_pct", "team_game/team_season",
       "Make rate on man-up shots. Both sides official, so the numerator and denominator come from "
       "the same counting rule.", "man_up_goals", "man_up_shots", OFFICIAL,
       "powerPlayGoals, powerPlayShots", U_MANUP, False, "production",
       "EMO shooting percentage", "identical"),
    _d("man_up_goals_per_opportunity", "team_game/team_season",
       "Extra-man conversion rate.", "man_up_goals", "man_up_opportunities",
       OFFICIAL, "powerPlayGoals, timesManUp",
       "Fully official; no possession or event inference involved.", False,
       "production", "EMO conversion", "identical"),
    _d("man_up_points_per_opportunity", "team_game/team_season",
       "PLL points scored per extra-man opportunity. This is the Phase 5 brief's "
       "man_up_points_per_possession, re-denominated on opportunities -- see the "
       "man_up_possessions row for why a possession denominator is not supportable.",
       "man_up_points", "man_up_opportunities", f"{EVENTS} + {OFFICIAL}",
       "is_man_up_shot, timesManUp",
       U_MANUP + " Numerator is play-by-play (the only source with a two-point split), denominator "
       "is official -- a deliberate mix, stated here rather than hidden.", True,
       "production", "EMO efficiency", "adapted"),
    _d("man_up_possessions", "n/a",
       "Count of offensive possessions played while man-up. UNSUPPORTED -- not built.",
       "n/a", "n/a", POSS, "has_man_up_shot",
       "The possession flag has_man_up_shot is TRUE for exactly 90 possessions season-wide, and "
       "every one of them contains a man-up goal: the underlying tag only ever appears on goal "
       "events. A 'man-up possessions' column built from it would be an exact copy of the man-up "
       "goal count wearing a different name, and any rate built on it (shooting percentage, points "
       "per possession) would be structurally degenerate -- man_up_shooting_pct from that flag is "
       "1.000 for all 8 teams. Penalty events carry no possession linkage either, so man-up "
       "possessions cannot be recovered from penalty timing without inventing the state. Use "
       "man_up_opportunities as the denominator instead.",
       False, "unsupported", "EMO possessions", "not_built"),

    # ---------------- ground balls ----------------
    _d("ground_balls", "team_game/team_season", "Ground balls recovered (official).",
       "team_game_stats.groundBalls", "n/a", OFFICIAL, "groundBalls", U_OFFICIAL_GB,
       False, "production", "ground balls", "identical"),
    _d("ground_balls_pbp", "team_game/team_season",
       "Ground-ball events in the cleaned play-by-play; disagrees with official in 21 of 100 "
       "team-games.", "count(events where event_type='groundball')", "n/a", EVENTS,
       "event_type, team_id", U_OFFICIAL_GB, False, "diagnostic", "ground balls", "adapted"),
    _d("ground_balls_per_possession", "team_game/team_season",
       "Ground balls per possession played. Denominator is offensive + defensive possessions "
       "because ground balls are recovered on both sides of the ball -- using offensive "
       "possessions alone would misattribute the rate.",
       "ground_balls", "offensive_possessions + defensive_possessions",
       f"{OFFICIAL} + {POSS}", "groundBalls, offense_team_id, defense_team_id",
       U_OFFICIAL_GB, False, "production", "ground balls per possession", "adapted"),

    # ---------------- goalkeeping ----------------
    _d("shots_on_goal_allowed", "team_game/team_season",
       "Opponent shots on goal.", "opponent shots_on_goal", "n/a", EVENTS,
       "shot_outcome, team_id", U_EVENT_EXACT, False, "production",
       "shots on goal allowed", "identical"),
    _d("goals_allowed", "team_game/team_season", "Opponent goals (official goalsAgainst).",
       "team_game_stats.goalsAgainst", "n/a", OFFICIAL, "goalsAgainst",
       "Matches opponent goals in all 100 team-games.", False, "production",
       "goals allowed", "identical"),
    _d("saves", "team_game/team_season", "Team saves (official).",
       "team_game_stats.saves", "n/a", OFFICIAL, "saves",
       "Play-by-play opponent saved-shot count matches official in 99 of 100 team-games; the one "
       "disagreement is the known unresolved 2026-ev-8 residual, carried as "
       "saves_pbp_minus_official.", False, "production", "saves", "identical"),
    _d("save_pct_official", "team_game/team_season",
       "PLL's own save percentage: saves / (saves + goals allowed). Excludes the on_goal_no_save "
       "shot class, so it is NOT saves per shot on goal.",
       "saves", "saves + goals_allowed", OFFICIAL, "savePct, saves, goalsAgainst",
       "Reproduced from its components rather than averaging the per-game percentage.",
       False, "production", "save percentage", "identical"),
    _d("save_pct_vs_shots_on_goal", "team_game/team_season",
       "Saves per opponent shot on goal. Differs from save_pct_official because 154 shots "
       "season-wide are on goal but classified neither saved nor goal.",
       "saves", "shots_on_goal_allowed", f"{OFFICIAL} + {EVENTS}",
       "saves, shot_outcome", "Both save-percentage denominators are exposed under distinct "
       "names; neither silently replaces the other.", False, "production",
       "save percentage", "adapted"),

    # ---------------- possession span / ToP ----------------
    _d("observed_possession_seconds", "team_game/team_season",
       "Sum of possession spans (last logged event minus first logged event). A LOWER BOUND on "
       "time of possession, not time of possession.",
       "sum(possessions.duration_seconds)", "n/a", POSS,
       "duration_seconds, offense_team_id", U_SPAN, False, "diagnostic",
       "time of possession", "not_built"),
    _d("complete_possession_seconds", "team_game/team_season",
       "Same as observed_possession_seconds but excluding possessions truncated by a period or "
       "game boundary.", "sum(duration_seconds where NOT is_truncated)", "n/a",
       POSS, "duration_seconds, is_truncated", U_SPAN, False, "diagnostic",
       "time of possession", "not_built"),
    _d("truncated_possessions", "team_game/team_season",
       "Possessions still open at a period/game boundary; their duration_seconds is a lower bound.",
       "count(possessions where is_truncated)", "n/a", POSS, "is_truncated",
       "159 season-wide (3.6%). Excluded from every duration statistic in these tables.",
       False, "production", "none", "pll_only"),
    _d("complete_possessions", "team_game/team_season",
       "Possessions not truncated by a period/game boundary.",
       "count(possessions where NOT is_truncated)", "n/a", POSS, "is_truncated",
       "", False, "production", "none", "pll_only"),
    _d("measurable_span_possessions", "team_game/team_season",
       "Possessions whose span is a real measurement: unambiguous, not truncated, and spanning two "
       "distinct logged events.",
       "count(possessions where is_measurable_span)", "n/a", POSS,
       "is_ambiguous, is_truncated, event_count",
       "2,096 of 4,388 season-wide (47.8%). The sole eligibility set for possession-length splits.",
       False, "production", "none", "pll_only"),
    _d("mean_complete_possession_duration", "team_game/team_season",
       "Mean span of non-truncated possessions.", "sum(duration_seconds)",
       "count(non-truncated possessions)", POSS, "duration_seconds, is_truncated",
       U_SPAN + " Includes single-event possessions whose span is 0 by construction; "
       "mean_measurable_span_seconds excludes those.", False, "production",
       "average possession length", "adapted"),
    _d("median_complete_possession_duration", "team_game/team_season",
       "Median span of non-truncated possessions.", "median(duration_seconds)",
       "n/a", POSS, "duration_seconds, is_truncated", U_SPAN, False, "production",
       "average possession length", "adapted"),
    _d("mean_measurable_span_seconds", "team_game/team_season",
       "Mean span over measurable-span possessions only.", "sum(duration_seconds)",
       "count(measurable-span possessions)", POSS,
       "duration_seconds, is_ambiguous, is_truncated, event_count", U_SPAN, False,
       "production", "average possession length", "adapted"),
    _d("median_measurable_span_seconds", "team_game/team_season",
       "Median span over measurable-span possessions only.", "median(duration_seconds)",
       "n/a", POSS, "duration_seconds, is_measurable_span", U_SPAN, False,
       "production", "average possession length", "adapted"),
    _d("time_of_possession_official_seconds", "team_game/team_season",
       "Time of possession from PLL's own box score. This is the authoritative time-of-possession "
       "figure for this dataset; no reconstructed alternative is published.",
       "team_game_stats.timeInPossesion", "n/a", OFFICIAL, "timeInPossesion",
       "Official only. Not independently verifiable from the event feed -- see "
       "possession_span_coverage_ratio.", False, "production",
       "time of possession", "identical"),
    _d("possession_span_coverage_ratio", "team_game/team_season",
       "observed_possession_seconds divided by the official time of possession. A pure diagnostic: "
       "how much of the official figure the reconstructed spans recover.",
       "observed_possession_seconds", "time_of_possession_official_seconds",
       f"{POSS} + {OFFICIAL}", "duration_seconds, timeInPossesion",
       "Median 0.75 across team-games, range 0.54-1.00, correlation with official 0.58. This is "
       "the evidence for NOT publishing a reconstructed time-of-possession metric.",
       False, "diagnostic", "time of possession", "not_built"),

    # ---------------- possession-length splits ----------------
    _d("length_bucket", "possession_bucket",
       "Possession span bucket: 0s / 01-09s / 10-19s / 20-29s / 30-44s / 45-59s / 60s+. Length "
       "only -- no style label is attached to any bucket.",
       "n/a", "n/a", POSS, "duration_seconds",
       "Computed over measurable-span possessions only (unambiguous, not truncated, spanning two "
       "or more distinct logged events). Same-second possessions form their own '0s' bucket "
       "because they score at 0.81 points per possession against 0.43 for genuine 1-9s "
       "possessions -- merging them would fabricate a fast-offence efficiency spike.",
       False, "production", "efficiency by possession length", "adapted"),
    _d("points_per_possession (bucket)", "possession_bucket",
       "Points per possession within a span bucket.", "sum(points_scored) in bucket",
       "count(possessions) in bucket", POSS, "duration_seconds, points_scored",
       "Bucket cell counts are exposed on every row; team-level 60s+ cells are thin.",
       True, "production", "efficiency by possession length", "adapted"),

    # ---------------- uncertainty metadata ----------------
    _d("ambiguous_offensive_possession_share", "team_game/team_season",
       "Share of a team's offensive possessions flagged is_ambiguous by the Phase 4 engine.",
       "count(ambiguous offensive possessions)", "offensive_possessions", POSS,
       "is_ambiguous, offense_team_id",
       "Ambiguity is about boundary mechanism/instant, never about which team had the ball.",
       False, "production", "none", "pll_only"),
    _d("has_turnover_validation_issue", "team_game",
       "TRUE if this game's official-vs-play-by-play turnover count did not PASS validation.",
       "validation_report.final_status <> 'PASS'", "n/a", "validation_report.csv",
       "metric, final_status",
       "Game-level, because validation_report.csv is game-level. The per-team residual is on the "
       "same row as turnovers_pbp_minus_official.", False, "production", "none", "pll_only"),
    _d("turnovers_pbp_minus_official", "team_game/team_season",
       "Per-team disagreement between the play-by-play turnover count and the official box score. "
       "Recovers which of the two teams in a flagged game carries the discrepancy, which "
       "validation_report.csv cannot express.",
       "turnovers_pbp - turnovers", "n/a", f"{EVENTS} + {OFFICIAL}",
       "event_type, turnovers", "Reported, never corrected.", False, "production",
       "none", "pll_only"),

    # ---------------- supporting counts and secondary rates ----------------
    _d("total_game_possessions", "team_game/team_season",
       "All possessions in the game(s) this team played: its own plus its opponent's.",
       "offensive_possessions + defensive_possessions", "n/a", POSS,
       "offense_team_id, defense_team_id", U_POSS_STRUCT, False, "production",
       "possessions", "adapted"),
    _d("possessions_with_two_point_attempt", "team_game/team_season",
       "Offensive possessions containing at least one two-point attempt.",
       "count(possessions where has_two_point_attempt)", "n/a", POSS,
       "has_two_point_attempt", U_POSS_STRUCT, True, "production", "none", "pll_only"),
    _d("two_point_shots_on_goal", "team_game/team_season",
       "Two-point attempts that reached the goal.",
       "count(two-point shots where is_shot_on_goal)", "n/a", EVENTS,
       "is_two_point_attempt, shot_outcome",
       "Equals official twoPointShotsOnGoal.", True, "production", "none", "pll_only"),
    _d("one_point_attempts", "team_game/team_season",
       "Shot attempts from inside the two-point arc.",
       "count(shots where NOT is_two_point_attempt)", "n/a", EVENTS,
       "is_two_point_attempt", U_EVENT_EXACT, True, "production", "shots", "adapted"),
    _d("shots_allowed", "team_game/team_season", "Opponent shot attempts.",
       "opponent shots", "n/a", EVENTS, "event_type, shot_outcome, team_id",
       U_EVENT_EXACT, False, "production", "shots allowed", "identical"),
    _d("shots_allowed_per_possession", "team_season",
       "Opponent shot attempts per possession this team defended.", "shots_allowed",
       "defensive_possessions", f"{EVENTS} + {POSS}", "shot_outcome, defense_team_id",
       U_POSS_STRUCT, False, "production", "shots allowed per possession", "identical"),
    _d("two_point_attempts_allowed", "team_game/team_season",
       "Opponent two-point attempts -- how often this defence conceded the long shot.",
       "opponent two_point_attempts", "n/a", EVENTS, "is_two_point_attempt",
       U_EVENT_EXACT, True, "production", "none", "pll_only"),
    _d("two_point_goals_allowed", "team_game/team_season",
       "Opponent two-point goals conceded (official twoPointGoalsAgainst).",
       "team_game_stats.twoPointGoalsAgainst", "n/a", OFFICIAL, "twoPointGoalsAgainst",
       "Official.", True, "production", "none", "pll_only"),
    _d("points_allowed_boxscore", "team_game",
       "Opponent points from the official box score (scoresAgainst). Kept as an independent "
       "cross-check on the possession-derived points_allowed, not as a second answer.",
       "team_game_stats.scoresAgainst", "n/a", OFFICIAL, "scoresAgainst",
       "Verified equal to possession-derived points_allowed and to the opponent's final score in "
       "all 100 team-games.", True, "diagnostic", "goals allowed", "adapted"),
    _d("opponent_shooting_pct", "team_season",
       "Opponent goals per opponent shot attempt -- the defensive mirror of shooting_pct.",
       "goals_allowed", "shots_allowed", f"{OFFICIAL} + {EVENTS}",
       "goalsAgainst, shot_outcome", U_EVENT_EXACT, False, "production",
       "opponent shooting percentage", "identical"),
    _d("opponent_shooting_pct_on_goal", "team_game/team_season",
       "Opponent goals per opponent shot ON goal. The complement of save_pct_vs_shots_on_goal only "
       "up to the on_goal_no_save class, which belongs to neither.",
       "goals_allowed", "shots_on_goal_allowed", f"{OFFICIAL} + {EVENTS}",
       "goalsAgainst, shot_outcome", U_EVENT_EXACT, False, "production",
       "none", "adapted"),
    _d("faceoff_losses", "team_game/team_season", "Faceoffs lost (official).",
       "team_game_stats.faceoffsLost", "n/a", OFFICIAL, "faceoffsLost",
       "faceoff_wins + faceoff_losses is 1-2 short of faceoffs in 8 games -- PLL counts "
       "no-decision draws in the total but in neither outcome column.", False,
       "production", "faceoff losses", "identical"),
    _d("faceoff_wins_pbp", "team_game/team_season",
       "Faceoff events in the play-by-play, i.e. draws won. Diagnostic companion to the official "
       "count.", "count(events where event_type='faceoff')", "n/a", EVENTS,
       "event_type, team_id", "Agrees with official in 99 of 100 team-games.",
       False, "diagnostic", "faceoff wins", "adapted"),
    _d("penalties", "team_game/team_season", "Penalties committed (official numPenalties).",
       "team_game_stats.numPenalties", "n/a", OFFICIAL, "numPenalties",
       "One game (2026-ev-45) has an unresolved +1 penalty residual; "
       "has_penalty_validation_issue flags it.", False, "production",
       "penalties", "identical"),
    _d("penalties_pbp", "team_game/team_season",
       "Valid penalty events in the play-by-play.",
       "count(events where event_type='penalty' AND is_valid_penalty)", "n/a", EVENTS,
       "event_type, is_valid_penalty",
       "Diagnostic companion to the official count; not used in any rate.", False,
       "diagnostic", "penalties", "adapted"),
    _d("penalty_minutes", "team_game/team_season", "Penalty minutes (official pim).",
       "team_game_stats.pim", "n/a", OFFICIAL, "pim", "Official.", False,
       "production", "penalty minutes", "identical"),
    _d("shot_clock_expirations", "team_game/team_season",
       "Shot-clock violations committed (official).",
       "team_game_stats.shotClockExpirations", "n/a", OFFICIAL, "shotClockExpirations",
       "5 games carry an unresolved +1 residual vs the play-by-play; "
       "has_shot_clock_validation_issue flags them.", False, "production",
       "shot clock violations", "identical"),
    _d("shot_clock_expirations_pbp", "team_game/team_season",
       "Shot-clock-expiration events in the play-by-play.",
       "count(events where event_type='shotclockexpired')", "n/a", EVENTS,
       "event_type, team_id", "Diagnostic companion to the official count.",
       False, "diagnostic", "shot clock violations", "adapted"),
    _d("shot_clock_expiration_rate", "team_game/team_season",
       "Share of offensive possessions ending in a shot-clock violation.",
       "shot_clock_expirations", "offensive_possessions", f"{OFFICIAL} + {POSS}",
       "shotClockExpirations, offense_team_id", U_POSS_STRUCT, False,
       "production", "none", "adapted"),
    _d("saves_pbp", "team_game/team_season",
       "Opponent shots classified 'saved' in the play-by-play -- the play-by-play view of this "
       "team's saves.", "count(opponent shots where shot_outcome='saved')", "n/a",
       EVENTS, "shot_outcome, team_id",
       "Agrees with official saves in 99 of 100 team-games.", False, "diagnostic",
       "saves", "adapted"),
    _d("man_up_shots_per_opportunity", "team_season",
       "Shots generated per extra-man opportunity -- man-up shot volume, separated from man-up "
       "finishing.", "man_up_shots", "man_up_opportunities", OFFICIAL,
       "powerPlayShots, timesManUp", U_MANUP, False, "production",
       "EMO shots per opportunity", "adapted"),
    _d("man_down_opportunities", "team_game/team_season",
       "Times short-handed (official timesShortHanded).",
       "team_game_stats.timesShortHanded", "n/a", OFFICIAL, "timesShortHanded",
       U_MANUP, False, "production", "man-down opportunities", "identical"),
    _d("man_down_goals_allowed", "team_game/team_season",
       "Goals conceded while short-handed (official powerPlayGoalsAgainst).",
       "team_game_stats.powerPlayGoalsAgainst", "n/a", OFFICIAL,
       "powerPlayGoalsAgainst", U_MANUP, False, "production",
       "man-down goals allowed", "identical"),
    _d("man_down_goals_allowed_per_opportunity", "team_game/team_season",
       "Man-down kill rate, inverted: goals conceded per short-handed opportunity. Lower is "
       "better.", "man_down_goals_allowed", "man_down_opportunities", OFFICIAL,
       "powerPlayGoalsAgainst, timesShortHanded", U_MANUP, False, "production",
       "man-down efficiency", "identical"),
    _d("clears", "team_game/team_season",
       "Successful clears (official). Passed through as a raw count only -- see "
       "clearing_efficiency for why no possession-linked clearing metric is built.",
       "team_game_stats.clears", "n/a", OFFICIAL, "clears", "Official; not validated "
       "against the event feed because the feed logs no clear event.", False,
       "production", "clears", "identical"),
    _d("clear_attempts", "team_game/team_season", "Clear attempts (official).",
       "team_game_stats.clearAttempts", "n/a", OFFICIAL, "clearAttempts",
       "Official; no event-level counterpart exists.", False, "production",
       "clear attempts", "identical"),
    _d("ride_attempts", "team_game/team_season", "Ride attempts (official).",
       "team_game_stats.rideAttempts", "n/a", OFFICIAL, "rideAttempts",
       "Official; no event-level counterpart exists.", False, "production",
       "ride attempts", "identical"),
    _d("time_of_possession_official_pct", "team_game",
       "PLL's own share-of-game-time-in-possession figure.",
       "team_game_stats.timeInPossesionPct", "n/a", OFFICIAL, "timeInPossesionPct",
       "Official; not independently verifiable from the event feed.", False,
       "production", "time of possession share", "identical"),
    _d("time_of_possession_official_seconds_per_game", "team_season",
       "Official time of possession per game played.",
       "time_of_possession_official_seconds", "games_played", OFFICIAL,
       "timeInPossesion", "Official.", False, "production",
       "time of possession", "identical"),
    _d("ambiguous_offensive_possessions", "team_game/team_season",
       "Offensive possessions the Phase 4 engine flagged is_ambiguous.",
       "count(offensive possessions where is_ambiguous)", "n/a", POSS,
       "is_ambiguous, offense_team_id",
       "Ambiguity concerns the boundary mechanism/instant, never which team had the ball.",
       False, "production", "none", "pll_only"),
    _d("ambiguous_defensive_possessions", "team_game/team_season",
       "Defensive possessions flagged is_ambiguous.",
       "count(defensive possessions where is_ambiguous)", "n/a", POSS,
       "is_ambiguous, defense_team_id", "As above.", False, "production",
       "none", "pll_only"),

    # ---------------- examined and NOT built ----------------
    _d("time_of_possession_reconstructed", "n/a",
       "A team time-of-possession metric derived from reconstructed possession spans. NOT BUILT.",
       "n/a", "n/a", POSS, "duration_seconds",
       "Rejected on evidence: span sums recover a median 75% of the official figure with a 0.54-"
       "1.00 range and correlate with it at only r=0.58, and team possession SHARE derived from "
       "spans differs from the official share by 4.9 percentage points on average. The gap is "
       "structural -- a possession's span starts at its first LOGGED event, not at the instant "
       "control was gained. Use time_of_possession_official_seconds.",
       False, "deferred", "time of possession", "not_built"),
    _d("clearing_efficiency", "n/a",
       "Clears / clear attempts as a possession-linked metric. NOT BUILT as an efficiency model.",
       "n/a", "n/a", OFFICIAL, "clears, clearAttempts",
       "Official clear/ride counts are passed through as raw columns, but no possession-linked "
       "clearing or riding efficiency is built: the feed logs no clear event, so a clear cannot be "
       "tied to a possession boundary, and 36.2% of possessions have an unconfirmed start "
       "mechanism -- exactly the field this metric would need.",
       False, "deferred", "clearing / riding efficiency", "not_built"),
    _d("possession_source_efficiency_split", "n/a",
       "Lacrosse Reference splits efficiency by how the possession began (defensive stop / ground "
       "ball / faceoff). PARTIALLY DEFERRED.",
       "n/a", "n/a", POSS, "start_reason",
       "faceoff_start_possession_share is published because faceoff starts are never ambiguous. "
       "The full three-way split is deferred: 922 possessions carry start_reason="
       "'other_confirmed_control' (team known, mechanism unknown), so a stop-vs-ground-ball split "
       "would assign ~21% of possessions to a bucket the feed never established.",
       False, "deferred", "efficiency by possession start type", "not_built"),
    _d("assist_metrics", "n/a", "Any assist-denominated team metric. UNSUPPORTED.",
       "n/a", "n/a", EVENTS, "pre_shot_pass_player_id",
       "The feed's shotAssistId is a pre-shot pass indicator, not a confirmed assist, and an "
       "unpopulated value is not a negative assertion. No assist metric is computed anywhere.",
       False, "unsupported", "assist metrics", "not_built"),
    _d("opponent_adjusted_efficiency", "n/a",
       "Schedule-strength-adjusted offensive/defensive efficiency. DEFERRED BY SCOPE.",
       "n/a", "n/a", "n/a", "n/a",
       "Explicitly out of scope for Phase 5 (team strength ratings are a later phase). Every "
       "efficiency metric in these tables is raw, not opponent-adjusted.",
       False, "deferred", "adjusted efficiency", "not_built"),
]
