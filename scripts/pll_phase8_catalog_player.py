"""Phase 8 metric catalog: player-level rows, plus the rejected/deferred
concepts. See pll_phase8_catalog_core.py."""
from pll_phase8_catalog_core import (  # noqa: F401
    M, L_TURNOVER_ATTRIB, L_XPOS_C, L_DEF_PARTIAL, L_GOALIE_NO_SQ,
    L_SHOOTING_NOISE, L_USAGE_NOT_POSS, L_ASSIST_UNVALUED, L_GB_UNVALUED,
    L_TWO_POINT_NOT_ID, L_TWO_POINT_THIN, L_MANUP, L_SPAN_NOT_TOP, L_NOT_OPP_ADJ,
)

PS = "player_season"
OFFP = "player_game_stats.csv (official PLL box score)"
PBP = "events.csv (cleaned play-by-play)"
P6 = "player_value_components.csv (Phase 6)"
P7 = "player_adjusted_value.csv (Phase 7)"

EPA_UNIT = "EPA_points (PLL points above league-average expected opportunity outcome)"

PLAYER_METRICS = [
    # ================= IDENTITY / ROLE =================
    M("canonical_position", "Position", PS, "identity", "label",
      "modal non-null box-score position label", "not_applicable",
      "mode(position label over the player's games), ties broken alphabetically",
      OFFP, "What the player is ROSTERED as. One of attack / midfield / "
      "short_stick_defensive_midfield / long_stick_midfield / defense / faceoff / "
      "goalie / unknown.", "neither", "CORE", "phase_7",
      "2 of 228 players carry no label in any game and are mapped 'unknown' "
      "rather than guessed. Resolved once per PLAYER, not per game: four "
      "player-game rows carry a null label for players labelled normally "
      "elsewhere, and resolving per row would break the value residual identity.",
      official="official"),
    M("position_group", "Position group", PS, "identity", "label",
      "canonical position collapsed to 5 analysis groups", "not_applicable",
      "attack | midfield | defensive_field | faceoff | goalie | unknown", OFFP,
      "The partition used for POSITIONAL DISTRIBUTIONS. Splits attack from "
      "midfield, which Phase 6's baseline_group does not, because the two phases "
      "need different things: Phase 6 needed groups large enough to estimate a "
      "turnover RATE, Phase 7 needs groups whose EPA DISTRIBUTION is meaningful.",
      "neither", "CORE", "phase_7",
      "Attack n=37, midfield n=63, defensive_field n=96, faceoff n=13, goalie "
      "n=17, unknown n=2. The unknown group's spread is suppressed.",
      official="official"),
    M("value_role", "Value role", PS, "identity", "label",
      "measured role: goalie, faceoff, or roster-derived field role",
      "not_applicable",
      "goalie if faced >=1 SOG; else faceoff if faceoff_team_share >= 0.50; "
      "else the roster position's field side", OFFP + " + " + PBP,
      "What the player MEASURABLY did, as opposed to what he is rostered as. In "
      "2026 the two never disagree, and both are published so a future divergence "
      "is visible rather than absorbed.", "neither", "CORE", "phase_7",
      "STEP 3 IS A DELIBERATE REFUSAL. A measured offence/defence split was built "
      "and rejected: applying Lacrosse Reference's documented 30% defensive "
      "threshold to opportunity shares put 24 of 96 rostered defenders in the "
      "offensive class, including 21 of 42 SSDMs, because the feed attributes ONE "
      "defensive act. The roster label is used instead. The faceoff threshold "
      "lands in a wide empirical gap (13 specialists at 0.812-0.977, next player "
      "at 0.158, nobody between), so no player's classification depends on it."),
    M("games_played", "Games played", PS, "identity", "count",
      "eligible games with a box-score row", "not_applicable",
      "count(distinct eligible game_id)", OFFP,
      "The ONLY metric in this project that is unambiguously comparable across "
      "every position (Phase 7 cross-position class A).", "neither", "CORE",
      "phase_6", "A game is a game -- but it is not playing time. The feed has no "
      "minutes, shifts or lineups.", xpos="A: directly comparable",
      official="official"),

    # ================= DESCRIPTIVE SCORING =================
    M("goals", "Goals", PS, "scoring", "count", "official goals", "not_applicable",
      "sum(goals)", OFFP, "Goals scored (a two-point goal counts once).",
      "TRUE", "CORE", "phase_6",
      "Reconciles EXACTLY with official team totals in all 100 team-games. Never "
      "use as a scoring total in the PLL.", official="official",
      xpos="C: role-determined"),
    M("one_point_goals", "1PT goals", PS, "scoring", "count",
      "official onePointGoals", "not_applicable", "sum(onePointGoals)", OFFP,
      "Inside-the-arc goals.", "TRUE", "CORE", "phase_6",
      "Exact in 100/100 team-games.", official="official", xpos="C: role-determined"),
    M("two_point_goals", "2PT goals", PS, "scoring", "count",
      "official twoPointGoals", "not_applicable", "sum(twoPointGoals)", OFFP,
      "Long-range goals. DESCRIPTIVE production, not evidence of two-point "
      "ability.", "TRUE", "CORE", "phase_6",
      L_TWO_POINT_NOT_ID, official="official", xpos="C: role-determined",
      freeze="FREEZE_WITH_CAVEAT"),
    M("scoring_points", "Points", PS, "scoring", "count",
      "one-point goals + 2 x two-point goals", "not_applicable",
      "one_point_goals + 2*two_point_goals", OFFP,
      "PLL SCORING POINTS. Sums to the official final score exactly.",
      "TRUE", "CORE", "phase_6",
      "CRITICAL: player_game_stats.points is NOT this. PLL's own 'points' column "
      "is onePointGoals + 2*twoPointGoals + ASSISTS (verified on all 1,824 rows) "
      "and must never be used as a scoring quantity.", official="official",
      xpos="C: role-determined"),
    M("scoring_points_per_game", "Points per game", PS, "scoring", "rate",
      "one-point goals + 2 x two-point goals", "games played",
      "scoring_points / games_played", OFFP,
      "Scoring rate, for comparing a player who missed games with one who did "
      "not. Published because 2026 appearance counts run from 1 to 13 and the "
      "raw total silently rewards availability.",
      "TRUE", "CONTEXTUAL", "phase_8",
      "The denominator is APPEARANCES, not minutes: the feed carries no lineup, "
      "shift or minutes data, so a player who took 4 shifts and one who played "
      "the whole game are both 1 game. It is therefore NOT a per-opportunity "
      "rate and a low-usage specialist is not flattered by it the way a "
      "per-minute figure would flatter him.", official="official",
      xpos="C: role-determined", redundancy="RELATED_BUT_DISTINCT",
      freeze="FREEZE"),
    M("official_assists", "Assists", PS, "scoring", "count", "official assists",
      "not_applicable", "sum(assists)", OFFP,
      "Assists. DESCRIPTIVE ONLY -- reliable, and deliberately assigned no value.",
      "TRUE", "CONTEXTUAL", "phase_6", L_ASSIST_UNVALUED, official="official",
      xpos="C: role-determined"),

    # ================= DESCRIPTIVE SHOOTING =================
    M("shots", "Shots", PS, "shooting", "count", "official shot attempts",
      "not_applicable", "sum(shots)", OFFP, "Attempt volume. 4,106 league-wide.",
      "neither", "CORE", "phase_6",
      "Reconciles exactly to team totals in 100/100 team-games.",
      official="official", xpos="C: role-determined"),
    M("shots_on_goal", "Shots on goal", PS, "shooting", "count",
      "official shots on goal", "not_applicable", "sum(shotsOnGoal)", OFFP,
      "Attempts that reached the cage.", "neither", "CORE", "phase_6",
      "Exact in 100/100 team-games.", official="official", xpos="C: role-determined"),
    M("one_point_attempts", "1PT attempts", PS, "shooting", "count",
      "shots minus two-point shots", "not_applicable",
      "shots - two_point_attempts", OFFP, "Inside-the-arc attempt volume.",
      "neither", "CORE", "phase_6", "Exact.", official="official",
      xpos="C: role-determined"),
    M("two_point_attempts", "2PT attempts", PS, "shooting", "count",
      "official twoPointShots", "not_applicable", "sum(twoPointShots)", OFFP,
      "Long-range attempt volume. Median player: 2. Maximum: 29.",
      "neither", "CORE", "phase_6", L_TWO_POINT_NOT_ID, official="official",
      xpos="C: role-determined"),
    M("shooting_pct", "Shooting %", PS, "shooting", "percentage", "goals",
      "shot attempts", "goals / shots", OFFP,
      "Finishing accuracy. Goals over attempts -- a two-point goal counts once.",
      "TRUE", "CONTEXTUAL", "phase_6",
      L_SHOOTING_NOISE + " The median shooter took 9 attempts; a raw shooting "
      "percentage at that sample is mostly noise, which is why the QUALIFIED "
      "leaderboard requires reliability 0.5 (71 attempts) and admits 13 players.",
      eligibility="QUALIFIED: shooting_reliability >= 0.5 (>= 70.8 attempts)",
      min_reason="Empirical-Bayes reliability 0.5 -- the point at which the "
                 "posterior weights the player's own record more than the league "
                 "prior. The trial count is set by the estimated prior strength, "
                 "not chosen.",
      reliability="weak individual identification: 13 of 192 shooters reach 0.5",
      official="official", xpos="B: comparable after a volume/reliability gate",
      freeze="FREEZE"),
    M("shots_on_goal_pct", "SOG %", PS, "shooting", "percentage", "shots on goal",
      "shot attempts", "shots_on_goal / shots", OFFP,
      "Share of a player's attempts that reached the cage.",
      "TRUE", "CONTEXTUAL", "phase_8",
      "No reliability estimate exists for this rate specifically; the shooting "
      "gate is reused as the nearest defensible proxy because the denominator is "
      "identical. Not a quality measure on its own -- shot selection is invisible "
      "in this feed.",
      eligibility="QUALIFIED: shooting_reliability >= 0.5",
      min_reason="Shares a denominator with shooting %, so the shooting gate "
                 "applies unchanged.",
      reliability="not separately estimated", official="official",
      xpos="B: comparable after a volume gate", freeze="FREEZE_WITH_CAVEAT"),
    M("one_point_conversion_pct", "1PT conversion %", PS, "shooting", "percentage",
      "one-point goals", "one-point attempts",
      "one_point_goals / one_point_attempts", OFFP,
      "Inside-the-arc accuracy.", "TRUE", "CONTEXTUAL", "phase_6",
      "Weakly identified: 8 of 168 players reach reliability 0.5 (76 attempts).",
      eligibility="QUALIFIED: one_point_reliability >= 0.5 (>= 75.3 attempts)",
      min_reason="Empirical-Bayes reliability 0.5; the prior strength is estimated "
                 "separately for this rate.",
      reliability="weak individual identification: 8 of 168 reach 0.5",
      official="official", xpos="B", freeze="FREEZE"),
    M("two_point_conversion_pct", "2PT conversion %", PS, "shooting", "percentage",
      "two-point goals", "two-point attempts",
      "two_point_goals / two_point_attempts", OFFP,
      "Long-range accuracy. PUBLISHED DESCRIPTIVELY WITH ITS DENOMINATOR AND "
      "NEVER RANKED AS AN ABILITY.", "TRUE", "CONTEXTUAL", "phase_6",
      L_TWO_POINT_NOT_ID + " No QUALIFIED leaderboard exists for this metric at "
      "any sample size, and that absence is the finding.",
      eligibility="NO player qualifies -- deliberately empty QUALIFIED scope",
      min_reason="Unattainable by construction: the estimated prior strength is "
                 "capped at 1,000,000 trials, so reliability 0.5 would require "
                 "1,000,000 attempts.",
      reliability="NOT IDENTIFIED: every reliability < 0.001",
      official="official", xpos="D: unsupported for everyone",
      freeze="FREEZE_WITH_CAVEAT"),
    M("points_per_shot", "Points per shot", PS, "shooting", "points per attempt",
      "PLL scoring points", "shot attempts", "scoring_points / shots", OFFP,
      "The PLL-native player shooting rate: the only one that credits two-point "
      "volume.", "TRUE", "CONTEXTUAL", "phase_6",
      L_SHOOTING_NOISE + " Its two-point component is not identifiable "
      "individually, so a high value driven by two-point goals should be read as "
      "production, not skill.",
      eligibility="QUALIFIED: shooting_reliability >= 0.5",
      reliability="weak", official="official", xpos="B",
      redundancy="RELATED_BUT_DISTINCT", freeze="FREEZE"),

    # ================= DESCRIPTIVE POSSESSION SECURITY =================
    M("turnovers", "Turnovers", PS, "turnovers", "count", "official turnovers",
      "not_applicable", "sum(turnovers)", OFFP,
      "Turnovers charged to this player.", "FALSE", "CONTEXTUAL", "phase_6",
      L_TURNOVER_ATTRIB, official="official", xpos="C: role-determined",
      freeze="FREEZE_WITH_CAVEAT"),
    M("touches", "Touches", PS, "turnovers", "count", "official touches",
      "not_applicable", "sum(touches)", OFFP,
      "The denominator of the turnover rate. Ranges 3 to 524.",
      "neither", "CORE", "phase_6",
      "Official and unreconciled against the event log -- the log has no touch "
      "event. Volume differs by role by two orders of magnitude.",
      official="official", xpos="C: role-determined"),
    M("turnovers_per_touch", "Turnover rate", PS, "turnovers", "percentage",
      "official turnovers", "official touches", "turnovers / touches", OFFP,
      "Ball security per touch. Genuinely role-dependent: faceoff specialists turn "
      "the ball over roughly twice as often per touch (0.109 vs 0.053) because "
      "their touches are overwhelmingly contested scrum recoveries.",
      "FALSE", "CONTEXTUAL", "phase_6",
      L_TURNOVER_ATTRIB + " NO THRESHOLD FIXES THAT: the numerator is missing "
      "~19% of its events for reasons uncorrelated with the denominator.",
      eligibility="QUALIFIED: touches >= 108.8 (empirical-Bayes reliability 0.5)",
      min_reason="Prior strength estimated in Phase 8 with Phase 6's own "
                 "beta_prior_by_moments estimator (imported, not reimplemented): "
                 "kappa = 108.8 touches. 81 of 228 players clear it.",
      reliability="moderate: 81 of 228 players reach reliability 0.5",
      official="official", xpos="B: after conditioning on role and volume",
      freeze="FREEZE_WITH_CAVEAT"),
    M("caused_turnovers", "Caused turnovers", PS, "partial_defense", "count",
      "official caused turnovers", "not_applicable", "sum(causedTurnovers)", OFFP,
      "THE ONE COUNTABLE DEFENSIVE ACT in this feed. 741 league-wide.",
      "TRUE", "CORE", "phase_6",
      "Reconciles exactly with official team totals in 100/100 team-games. It is "
      "not inferred from turnover events: the event-level causedTurnoverId is null "
      "in every event of the season.", official="official",
      xpos="C: role-determined"),
    M("ground_balls", "Ground balls", PS, "possession", "count",
      "official ground balls", "not_applicable", "sum(groundBalls)", OFFP,
      "Loose-ball recoveries. DESCRIPTIVE ONLY.", "TRUE", "CONTEXTUAL", "phase_6",
      L_GB_UNVALUED, official="official", xpos="C: role-determined"),
    M("penalties", "Penalties", PS, "discipline", "count", "official penalties",
      "not_applicable", "sum(numPenalties)", OFFP,
      "Penalties committed. DESCRIPTIVE ONLY -- there is no penalty component in "
      "the value framework, though the event coefficient (-0.417) is estimated "
      "and published.", "FALSE", "CONTEXTUAL", "phase_6",
      "Unvalued by choice, not by inability: a penalty component was estimated "
      "but not folded into any total in Phase 6, and Phase 8 does not add one.",
      official="official", xpos="C: role-determined"),

    # ================= DESCRIPTIVE FACEOFF =================
    M("faceoffs", "Faceoffs", PS, "faceoff", "count", "official faceoffs taken",
      "not_applicable", "sum(faceoffs)", OFFP,
      "Draw volume. 47 players took at least one; 13 are specialists.",
      "neither", "CORE", "phase_6", "Exact in 100/100 team-games.",
      official="official", xpos="D: meaningful only within the faceoff role"),
    M("faceoff_wins", "Faceoff wins", PS, "faceoff", "count",
      "official faceoffs won", "not_applicable", "sum(faceoffsWon)", OFFP,
      "Draws won.", "TRUE", "CORE", "phase_6", "Exact.", official="official",
      xpos="D"),
    M("faceoff_losses", "Faceoff losses", PS, "faceoff", "count",
      "official faceoffs lost", "not_applicable", "sum(faceoffsLost)", OFFP,
      "Draws lost.", "FALSE", "CORE", "phase_6",
      "wins + losses falls 1-2 short of faceoffs in 8 games, because PLL counts "
      "no-decision draws in the total.", official="official", xpos="D"),
    M("faceoff_win_pct", "Faceoff win %", PS, "faceoff", "percentage",
      "faceoff wins", "faceoffs taken", "faceoff_wins / faceoffs", OFFP,
      "THE MOST STRONGLY IDENTIFIED PLAYER RATE IN THIS SYSTEM. Prior strength is "
      "only 15.9 draws, implied true between-player sd 0.122, and 18 of 47 takers "
      "reach reliability 0.5.", "TRUE", "CORE", "phase_6",
      "League mean 0.4966, not 0.5000, because 18 draws had no recorded winner. "
      + L_NOT_OPP_ADJ,
      eligibility="QUALIFIED: faceoff_reliability >= 0.5 (>= 15.9 draws)",
      min_reason="Empirical-Bayes reliability 0.5; the implied 16-draw threshold "
                 "is small precisely because faceoff skill is strongly identified.",
      reliability="STRONG: 18 of 47 takers reach 0.5; implied skill share of "
                  "variance 0.70",
      official="official", xpos="D: faceoff takers only", freeze="FREEZE"),

    # ================= DESCRIPTIVE GOALKEEPING =================
    M("saves", "Saves", PS, "goalie", "count", "official saves", "not_applicable",
      "sum(saves)", OFFP, "Saves made.", "TRUE", "CORE", "phase_6",
      "Exact in 100/100 team-games; reconciled against the event-derived count in "
      "116 of 117 goalie-games.", official="official", xpos="D: goalies only"),
    M("goals_allowed", "Goals allowed", PS, "goalie", "count",
      "official goals against", "not_applicable", "sum(goalsAgainst)", OFFP,
      "Goals conceded (not points).", "FALSE", "CORE", "phase_6",
      "Exact in 117/117 goalie-games.", official="official", xpos="D"),
    M("two_point_goals_allowed", "2PT goals allowed", PS, "goalie", "count",
      "official twoPointGoalsAgainst", "not_applicable",
      "sum(twoPointGoalsAgainst)", OFFP, "Long-range goals conceded.",
      "FALSE", "CONTEXTUAL", "phase_6", "Exact.", official="official", xpos="D"),
    M("pll_points_allowed", "Points allowed", PS, "goalie", "count",
      "goals allowed + two-point goals allowed", "not_applicable",
      "goals_allowed + two_point_goals_allowed", OFFP,
      "PLL POINTS conceded -- the quantity goalie value is actually built on.",
      "FALSE", "CORE", "phase_6",
      "Distinct from goals_allowed by exactly the two-point count.",
      official="official", xpos="D"),
    M("shots_on_goal_faced", "Shots on goal faced", PS, "goalie", "count",
      "shot/goal events on goal with this player as goalie of record",
      "not_applicable",
      "count(events where goalie_id = player and shot was on goal)", PBP,
      "The goalie opportunity base: 2,567 across 16 keepers. Goalies are valued "
      "on shots ON GOAL, not attempts -- a keeper is not responsible for a shot "
      "that missed the cage.", "neither", "CORE", "phase_6",
      "EVENT-DERIVED, because the official player box score has no one-point / "
      "two-point split of shots faced. Reconciled against official saves in "
      "116/117 goalie-games and goals allowed in 117/117.",
      official="reconstructed_reconciled", xpos="D: 16 players"),
    M("one_point_shots_on_goal_faced", "1PT SOG faced", PS, "goalie", "count",
      "one-point shots on goal faced", "not_applicable",
      "count(one-point shots on goal with this goalie)", PBP,
      "Split needed because the two classes convert at very different rates "
      "(46.1% vs 24.1% on shots on goal).", "neither", "CORE", "phase_6",
      "See shots_on_goal_faced.", official="reconstructed_reconciled", xpos="D"),
    M("two_point_shots_on_goal_faced", "2PT SOG faced", PS, "goalie", "count",
      "two-point shots on goal faced", "not_applicable",
      "count(two-point shots on goal with this goalie)", PBP,
      "The other half of the split.", "neither", "CORE", "phase_6",
      "299 league-wide -- thin per goalie.", official="reconstructed_reconciled",
      xpos="D"),
    M("save_pct", "Save %", PS, "goalie", "percentage", "saves",
      "saves + goals allowed", "saves / (saves + goals_allowed)", OFFP,
      "PLL's own save-percentage definition, at player level.",
      "TRUE", "CONTEXTUAL", "phase_6",
      "REAL between-goalie spread exists (estimated true sd about 2.9 percentage "
      "points) but almost no individual goalie can be separated from the prior: "
      "the busiest keeper in the league faced 332 shots on goal against a prior "
      "strength of 300, so exactly ONE of sixteen reaches reliability 0.5. Both "
      "statements are true and they answer different questions. " + L_GOALIE_NO_SQ,
      eligibility="QUALIFIED: save_reliability >= 0.5 (>= 300.3 SOG). Exactly 1 "
                  "goalie qualifies in 2026 -- a one-row leaderboard is the "
                  "correct output of the rule, not a defect.",
      min_reason="Empirical-Bayes reliability 0.5. The prior is strong because "
                 "goalies differ less than they appear to at 2026 volumes.",
      reliability="spread real, individual identification very weak: 1 of 16",
      official="official", xpos="D: goalies only", freeze="FREEZE_WITH_CAVEAT"),
    M("points_allowed_per_sog_faced", "Points allowed per SOG faced", PS, "goalie",
      "points per shot", "PLL points allowed", "shots on goal faced",
      "pll_points_allowed / shots_on_goal_faced", OFFP + " + " + PBP,
      "The goalie analogue of points_per_shot, and the denominator goalie value is "
      "actually built on. Distinguishes a keeper who concedes two-pointers from "
      "one who concedes the same number of one-point goals.",
      "FALSE", "CONTEXTUAL", "phase_8",
      L_GOALIE_NO_SQ + " Same identification problem as save_pct.",
      eligibility="QUALIFIED: save_reliability >= 0.5",
      reliability="very weak individually", xpos="D",
      redundancy="RELATED_BUT_DISTINCT", freeze="FREEZE_WITH_CAVEAT"),

    # ================= USAGE =================
    M("recorded_offensive_opportunities", "Recorded offensive opportunities", PS,
      "usage", "count", "shots + turnovers", "not_applicable",
      "shots + turnovers", OFFP,
      "How much of the team's offensive workload the player personally consumed. "
      "A VOLUME measure: it says nothing about whether the opportunities were "
      "used well.", "neither", "CORE", "phase_7",
      "Shots and turnovers are the only two individually-credited actions that "
      "CONSUME an offensive opportunity, and they are disjoint. Assists are "
      "excluded (an assist attaches to a goal already counted as the shooter's "
      "attempt); ground balls are excluded (they measure faceoff outcome); "
      "faceoffs are excluded (already paid in faceoff_value). "
      + L_TURNOVER_ATTRIB, official="official", xpos="C: measures the role"),
    M("offensive_opportunities_per_game", "Offensive opportunities/game", PS,
      "usage", "rate", "recorded offensive opportunities", "games played",
      "recorded_offensive_opportunities / games_played", OFFP,
      "Workload rate, absence-corrected.", "neither", "CONTEXTUAL", "phase_7",
      "See recorded_offensive_opportunities.", official="official", xpos="C"),
    M("offensive_play_share", "Offensive play share", PS, "usage", "percentage",
      "player recorded offensive opportunities",
      "the same quantity summed over the player's TEAM in the games he played",
      "player_opps / team_opps_in_games_played", OFFP,
      "USAGE. The denominator is the games the player actually appeared in, so a "
      "player who missed five games is not counted as low-usage -- he was absent.",
      "neither", "CORE", "phase_7",
      L_USAGE_NOT_POSS + " " + L_TURNOVER_ATTRIB + " Because the denominator "
      "differs per player these do NOT sum to 1 within a team; "
      "offensive_play_share_season does.",
      official="official", xpos="C: attack averages 0.114, defensive field 0.013 "
                                "-- the ordering is the role, not the player"),
    M("offensive_play_share_season", "Offensive play share (season denominator)",
      PS, "usage", "percentage", "player recorded offensive opportunities",
      "team recorded offensive opportunities over the FULL season",
      "player_opps / team_season_opps", OFFP,
      "The version that sums to exactly 1.000 per team, which is what makes the "
      "accounting checkable. Penalises absence by construction.",
      "neither", "CONTEXTUAL", "phase_7",
      "A mid-season mover contributes a separate component to each of his teams.",
      official="official", xpos="C"),
    M("shot_share", "Shot share", PS, "usage", "percentage", "player shots",
      "team shots in the games he played", "player_shots / team_shots", OFFP,
      "Usage on the exactly-attributed half of the opportunity definition. Its "
      "rank correlation with offensive_play_share is 0.959.",
      "neither", "CONTEXTUAL", "phase_7",
      "Free of the turnover-attribution gap, which is why it is worth publishing "
      "next to offensive_play_share rather than instead of it.",
      official="official", xpos="C", redundancy="HIGHLY_OVERLAPPING"),
    M("touch_share", "Touch share", PS, "usage", "percentage", "player touches",
      "team touches in the games he played", "player_touches / team_touches", OFFP,
      "Broadest usage proxy.", "neither", "CONTEXTUAL", "phase_7",
      "Counts a defenseman's clear and an attackman's dodge as one unit, so it is "
      "not comparable across roles.", official="official", xpos="C"),
    M("faceoff_team_share", "Faceoff team share", PS, "usage", "percentage",
      "player faceoffs", "team faceoffs in the games he played",
      "player_faceoffs / team_faceoffs", OFFP,
      "The specialist classifier's input. Lands in a wide empirical gap in 2026: "
      "13 players at 0.812-0.977, next-highest 0.158, nobody between.",
      "neither", "CORE", "phase_7", "Undefined for 181 of 228 players.",
      official="official", xpos="D"),
    M("caused_turnover_team_share", "Caused-turnover team share", PS,
      "partial_defense", "percentage", "player caused turnovers",
      "team caused turnovers in the games he played",
      "player_ct / team_ct", OFFP,
      "A defender's share of the one defensive act the feed counts.",
      "TRUE", "CONTEXTUAL", "phase_7", L_DEF_PARTIAL, official="official",
      xpos="C"),
    M("event_log_play_shares", "Play shares (Lacrosse Reference definition)", PS,
      "usage", "count", "appearances anywhere in the eligible event log",
      "not_applicable",
      "count(events where the player is primary actor, secondary actor, goalie of "
      "record, or faceoff ground-ball recoverer)", PBP,
      "A FAITHFUL REPRODUCTION of Lacrosse Reference's own usage proxy, published "
      "for reference comparison and NOT used as this project's usage measure.",
      "neither", "DIAGNOSTIC", "phase_7",
      "Three reasons it is not adopted: (1) per game it runs 38.0 for a faceoff "
      "specialist against 2.5 for a close defender, so it measures how often the "
      "feed records a role; (2) ONE faceoff generates up to three appearances "
      "(winner, loser, scrum recovery -- 61.5% of which is the winner himself); "
      "(3) it contains shotAssistId, the unreliable pre-shot-pass indicator every "
      "Phase 6 value component deliberately excludes. Turnovers contribute ZERO "
      "appearances. Swapping to it moves 226 of 228 usage ranks at a rank "
      "correlation of 0.556.", xpos="C: worse than the alternatives"),
    M("event_log_play_share", "Play share (LR, normalized)", PS, "usage",
      "percentage", "player event-log appearances", "team event-log appearances",
      "player_appearances / team_appearances", PBP,
      "Normalized reproduction of the LR proxy. The input to the 1% eligibility "
      "rule LR publishes.", "neither", "DIAGNOSTIC", "phase_7",
      "See event_log_play_shares.", xpos="C"),

    # ================= VALUE COMPONENTS (Phase 6 raw) =================
    M("shooting_value_raw", "Shooting value", PS, "value", EPA_UNIT,
      "observed PLL points from the player's own attempts",
      "expected points for a league-average shooter on the SAME attempt mix",
      "(1pt_goals + 2*2pt_goals) - (1pt_attempts*0.29300 + 2pt_attempts*0.26866)",
      P6, "Finishing above or below league-average expectation, in PLL points. "
      "It values FINISHING ONLY -- it carries no credit for generating the shot "
      "or for having the possession, because those are not separable in this feed "
      "and crediting them here is what would double-count possession value.",
      "TRUE", "CORE", "phase_6",
      L_SHOOTING_NOISE + " Highly sensitive to shrinkage: replacing raw rates "
      "with empirical-Bayes rates moves 219 of 228 ranks (rank correlation "
      "0.758). Sums to exactly 0 across the league.",
      reliability="implied skill share of variance 0.12 -- the weakest component",
      xpos="B: same opportunity and baseline for every role, but attempt volumes "
           "differ 4.5x in chance spread"),
    M("shooting_value_one_point_raw", "Shooting value (1PT)", PS, "value", EPA_UNIT,
      "one-point goals", "one-point attempts x 0.29300",
      "one_point_goals - one_point_attempts*0.29300", P6,
      "The inside-the-arc half of shooting value.", "TRUE", "CONTEXTUAL", "phase_6",
      "Adds to shooting_value_two_point_raw to give shooting_value_raw exactly.",
      redundancy="ALGEBRAICALLY_REDUNDANT (component of shooting_value_raw)",
      xpos="B"),
    M("shooting_value_two_point_raw", "Shooting value (2PT)", PS, "value", EPA_UNIT,
      "2 x two-point goals", "two-point attempts x 0.26866",
      "2*two_point_goals - two_point_attempts*0.26866", P6,
      "The long-range half of shooting value.", "TRUE", "CONTEXTUAL", "phase_6",
      L_TWO_POINT_NOT_ID + " Differences between players in this column are, on "
      "2026 evidence, indistinguishable from chance. Do not rank it.",
      reliability="NOT IDENTIFIED",
      redundancy="ALGEBRAICALLY_REDUNDANT (component of shooting_value_raw)",
      xpos="D", freeze="FREEZE_WITH_CAVEAT"),
    M("turnover_value_raw", "Turnover value", PS, "value", EPA_UNIT,
      "turnovers above the position group's per-touch expectation, negated",
      "touches x the group turnover-per-touch rate",
      "-(turnovers - touches*group_rate) * 0.20046", P6,
      "Possession security above role expectation. A RESIDUAL, not a raw charge: "
      "a flat -turnovers*cost would punish volume, making a 400-touch attackman "
      "always look worse than an 80-touch close defender, which measures role "
      "rather than performance.", "TRUE", "CORE", "phase_6",
      L_TURNOVER_ATTRIB + " Rankings are COMPLETELY insensitive to the "
      "coefficient choice (0 players change rank under three alternatives) "
      "because the alternatives are linear rescalings of the same residual.",
      reliability="implied skill share of variance 0.38",
      xpos="B: already residualized against a role rate; residual "
           "incomparability is volume"),
    M("faceoff_value_raw", "Faceoff value", PS, "value", EPA_UNIT,
      "faceoff wins above league-average expectation",
      "faceoffs x 0.49656", "(faceoff_wins - faceoffs*0.49656) * 0.34643", P6,
      "Draws won above what a league-average faceoff man would have won on the "
      "same draws. THE COUNTERFACTUAL IS EXPLICIT: the alternative to this player "
      "winning is an average specialist winning at 49.656%, NOT the team "
      "forfeiting the ball. A specialist who wins exactly at the league rate "
      "scores exactly zero.", "TRUE", "CORE", "phase_6",
      "The coefficient is twice the faceoff event value (2 x 0.17321), because "
      "converting a loss into a win moves the value from one team to the other. "
      "The largest open magnitude question in the framework: a possession-native "
      "alternative is 42% larger and would raise the top specialist from +10.6 to "
      "+15.1 -- but 0 players change rank under it. NULL, not zero, for players "
      "who never took a draw.",
      reliability="STRONGEST component: implied skill share of variance 0.70",
      xpos="D: NULL for 181 players"),
    M("goalie_value_raw", "Goalie value", PS, "value", EPA_UNIT,
      "expected points allowed on the shots faced",
      "actual PLL points allowed",
      "(1pt_SOG_faced*0.46120 + 2pt_SOG_faced*0.48161) - pll_points_allowed", P6,
      "Points PREVENTED against a league-average keeper facing the same shots. "
      "Sign is flipped relative to shooting so that 'more is better' holds "
      "everywhere.", "TRUE", "CORE", "phase_6",
      L_GOALIE_NO_SQ + " Separate one-point / two-point baselines are used, but "
      "the expected POINTS per shot on goal are nearly equal (0.461 vs 0.482), so "
      "a goalie facing more long-range shots is neither rewarded nor punished for "
      "the mix. Goalies DOMINATE raw EPA totals on opportunity volume alone: 150-"
      "332 shots on goal faced against an attackman's ~80 attempts.",
      reliability="implied skill share of variance 0.43",
      xpos="D: NULL for 212 players"),
    M("defensive_value_partial_raw", "Defensive value (PARTIAL)", PS, "value",
      EPA_UNIT, "caused turnovers above the position group's per-game expectation",
      "games played x the group per-game caused-turnover rate",
      "(caused_turnovers - games_played*group_rate) * 0.20046", P6,
      "Caused turnovers above positional expectation. THE WORD 'PARTIAL' IS IN "
      "THE NAME ON PURPOSE.", "TRUE", "CONTEXTUAL", "phase_6", L_DEF_PARTIAL,
      xpos="C AND PARTIAL: comparable in form across roles, not in meaning",
      freeze="FREEZE_WITH_CAVEAT"),
    M("offensive_EPA_points_raw", "Offensive EPA", PS, "value", EPA_UNIT,
      "shooting value + turnover value", "not_applicable",
      "shooting_value_raw + turnover_value_raw", P6,
      "The offensive half of a player's measured value.", "TRUE", "CORE", "phase_7",
      "Excludes faceoff, goalie and partial-defensive value by construction.",
      redundancy="ALGEBRAICALLY_REDUNDANT (sum of two published components)",
      xpos="B"),
    M("EPA_points_raw", "Total EPA", PS, "value", EPA_UNIT,
      "sum of every supported component", "not_applicable",
      "shooting + turnover + faceoff + goalie + defensive_partial", P6,
      "The retrospective record of what a player's measured actions produced "
      "against league-average expectation in 2026. Sums to exactly 0 across the "
      "league, verified to 10 decimal places.", "TRUE", "CONTEXTUAL", "phase_6",
      L_XPOS_C + " Ground balls, assists and penalties are DELIBERATELY OUTSIDE "
      "this total. It is NOT replacement level, NOT WAR, and NOT an award score. "
      "In 2026 the top 15 contains 5 goalies, which is opportunity volume, not a "
      "ranking claim.", xpos="C: NOT cross-position comparable",
      freeze="FREEZE_WITH_CAVEAT"),
    M("components_supported", "Components supported", PS, "value", "label",
      "which value components are non-NULL for this player", "not_applicable",
      "list of supported components", P6,
      "Which parts of the framework actually measured this player.",
      "neither", "DIAGNOSTIC", "phase_6",
      "A defender with only shooting, turnover and partial-defensive components "
      "has had far less of his job measured than a goalie has."),

    # ================= EFFICIENCY =================
    M("EPA_per_recorded_opportunity", "EPA per opportunity", PS, "efficiency",
      EPA_UNIT + " per opportunity", "offensive EPA points",
      "recorded offensive opportunities",
      "offensive_EPA_points_raw / recorded_offensive_opportunities", P7,
      "Offensive production per opportunity consumed.", "TRUE", "CONTEXTUAL",
      "phase_7",
      "Volume-free, so a 3-opportunity player can top it on nothing. "
      + L_TURNOVER_ATTRIB,
      eligibility="QUALIFIED: offensive_rate_ranking_eligible (shooting "
                  "reliability >= 0.5) -- 13 of 228 players",
      min_reason="Phase 7 gates offensive efficiency on the SHOOTING rate "
                 "specifically, so that a faceoff specialist superbly identified "
                 "on draws is not licensed onto a per-shot leaderboard.",
      reliability="weak", xpos="B: comparable after the reliability gate"),
    M("shooting_EPA_per_shot", "Shooting EPA per shot", PS, "efficiency",
      EPA_UNIT + " per attempt", "shooting value", "shot attempts",
      "shooting_value_raw / shots", P7,
      "Finishing above expectation, per attempt. Algebraically this is (points per "
      "shot) minus (the expected points of the player's own attempt mix), so it "
      "prices the two-point mix correctly where a raw shooting percentage does "
      "not.", "TRUE", "CONTEXTUAL", "phase_7", L_SHOOTING_NOISE,
      eligibility="QUALIFIED: offensive_rate_ranking_eligible",
      reliability="weak", xpos="B: volume-free and same-unit across roles",
      redundancy="RELATED_BUT_DISTINCT"),
    M("faceoff_EPA_per_faceoff", "Faceoff EPA per draw", PS, "efficiency",
      EPA_UNIT + " per draw", "faceoff value", "faceoffs",
      "faceoff_value_raw / faceoffs", P7,
      "Faceoff value per draw taken. A linear function of faceoff win percentage.",
      "TRUE", "CONTEXTUAL", "phase_7", "Faceoff takers only.",
      eligibility="QUALIFIED: faceoff_reliability >= 0.5",
      reliability="strong", xpos="D",
      redundancy="ALGEBRAICALLY_REDUNDANT (linear in faceoff_win_pct)"),
    M("goalie_EPA_per_SOG", "Goalie EPA per SOG", PS, "efficiency",
      EPA_UNIT + " per shot on goal", "goalie value", "shots on goal faced",
      "goalie_value_raw / shots_on_goal_faced", P7,
      "Points prevented per shot faced -- the volume-free goalie measure.",
      "TRUE", "CONTEXTUAL", "phase_7", L_GOALIE_NO_SQ,
      eligibility="QUALIFIED: save_reliability >= 0.5 (1 goalie)",
      reliability="very weak individually", xpos="D",
      redundancy="RELATED_BUT_DISTINCT"),
    M("defensive_EPA_partial_per_game", "Partial defensive EPA per game", PS,
      "efficiency", EPA_UNIT + " per game", "partial defensive value",
      "games played", "defensive_value_partial_raw / games_played", P7,
      "Caused turnovers above positional expectation, per game.",
      "TRUE", "CONTEXTUAL", "phase_7", L_DEF_PARTIAL,
      xpos="C: the denominator is games, so this is a role property before it is "
           "a player property", freeze="FREEZE_WITH_CAVEAT"),
    M("EPA_points_per_game", "EPA per game", PS, "efficiency",
      EPA_UNIT + " per game", "total EPA", "games played",
      "EPA_points_raw / games_played", P7,
      "Total value per appearance. Corrects for absence, NOT for playing time.",
      "TRUE", "CONTEXTUAL", "phase_7",
      L_XPOS_C + " Games played is the weakest denominator in the framework: the "
      "feed has no minutes, shifts or lineups, so a player who plays every "
      "possession and one who rotates are treated as having equal exposure.",
      xpos="C"),
    M("uaEPA_per_event_log_play_share", "uaEPA (LR reproduction)", PS, "efficiency",
      EPA_UNIT + " per play share", "total EPA", "event-log play shares",
      "EPA_points_raw / event_log_play_shares", P7,
      "A faithful reproduction of Lacrosse Reference's published usage "
      "adjustment -- 'you just divide total EGA by play shares'. Published for "
      "reference comparison only.", "TRUE", "DIAGNOSTIC", "phase_7",
      "Inherits the incomparability of its denominator entirely. MUST NOT be used "
      "in any cross-position comparison. The numerator is also a different "
      "estimand from LR's EGA, which is why it is not named uaEGA.",
      xpos="C: unusable across roles"),

    # ================= USAGE-RELATIVE =================
    M("expected_EPA_given_usage", "Expected EPA given usage", PS, "usage_relative",
      EPA_UNIT, "fitted value of offensive EPA at the player's usage level",
      "not_applicable", "constant model selected by 5-fold cross-validated MSE",
      P7, "What a typical field player produced at this usage level. In 2026 the "
      "selected model is a CONSTANT: both a linear and a quadratic fit are worse "
      "out of sample than a flat line, and Pearson r between usage and offensive "
      "EPA is +0.072.", "neither", "EXPERIMENTAL", "phase_7",
      "NULL for goalies and faceoff specialists -- they are outside the fitted "
      "population and no offensive-usage expectation is defined for them. NULL, "
      "never 0, because 0 would be a claim. PHASE 9 RESOLVED THE OPEN QUESTION: "
      "refitted on 844 player-seasons across 2022-2026, with cross-validation "
      "folds cut by PLAYER rather than by row, the CONSTANT still wins (CV MSE "
      "7.4407 against 7.5067 linear and 7.5235 quadratic). The per-season "
      "correlation between usage and offensive EPA is NEGATIVE in four of the "
      "five seasons (-0.057, -0.021, -0.036, -0.027) and +0.072 only in 2026, so "
      "2026's weak positive was noise rather than a small real effect. The "
      "definition therefore does not need revising -- what needs to travel with "
      "it is that the fitted expectation is a single number.",
      xpos="B: field players only",
      freeze="FREEZE_WITH_CAVEAT"),
    M("EPA_vs_usage_expectation", "EPA vs usage expectation", PS, "usage_relative",
      EPA_UNIT, "offensive EPA", "expected EPA at that usage",
      "offensive_EPA_points_raw - expected_EPA_given_usage", P7,
      "How much more than a typical player at the same usage level.",
      "TRUE", "EXPERIMENTAL", "phase_7",
      "Because the fitted model is a constant, this is offensive EPA minus a "
      "single league number -- it does very little work in 2026. THE FINDING "
      "BEHIND IT IS THE USEFUL PART: usage moves the VARIANCE of measured value, "
      "not its mean (sd of offensive EPA rises from 0.50 in the lowest usage "
      "quintile to 4.73 in the highest, tracking the chance spread closely).",
      xpos="B: field players only",
      redundancy="ALGEBRAICALLY_REDUNDANT (a constant offset of "
                 "offensive_EPA_points_raw: Pearson r and Spearman rho are both "
                 "exactly 1.000 in metric_redundancy_2026.csv, because the fitted "
                 "model is flat). Phase 9 refitted on five seasons and the "
                 "constant still won, so this is now a settled property rather "
                 "than a one-season accident.",
      freeze="FREEZE_WITH_CAVEAT"),
    M("EPA_vs_usage_expectation_z", "EPA vs usage expectation (z)", PS,
      "usage_relative", "standard deviations",
      "EPA above the usage expectation", "the CHANCE sd at the player's own "
      "opportunity counts",
      "EPA_vs_usage_expectation / offensive_EPA_null_sd", P7,
      "How unusual the player's offensive production is GIVEN HIS WORKLOAD. This "
      "is the column that does the real work, because it adjusts the thing usage "
      "actually changes -- the spread.", "TRUE", "EXPERIMENTAL", "phase_7",
      "See EPA_vs_usage_expectation.", xpos="B: field players only",
      freeze="FREEZE_WITH_CAVEAT"),

    # ================= CHANCE-RELATIVE =================
    M("EPA_points_null_sd", "EPA chance sd", PS, "chance", EPA_UNIT,
      "closed-form sd of the value components under chance alone at the player's "
      "own opportunity counts", "not_applicable",
      "sqrt of the sum of component null variances; two-point terms carry a "
      "factor of 4 because a two-point attempt pays 2 points", P7,
      "How far from zero luck alone could put this player, given how many "
      "opportunities he had.", "neither", "CORE", "phase_7",
      "Assumes opportunity outcomes are INDEPENDENT, which shots within a game "
      "are not exactly. NULL, not 0, where the player had no opportunities of a "
      "class -- reporting 0 would say the value is known exactly. No resampling "
      "is used because none is needed: a bootstrap over the same 80 shot outcomes "
      "estimates the same binomial variance with Monte Carlo noise added."),
    M("EPA_points_null_z", "EPA vs chance (z)", PS, "chance", "standard deviations",
      "total EPA", "the chance sd at the player's own opportunity volume",
      "EPA_points_raw / EPA_points_null_sd", P7,
      "How far a season is from what luck alone could produce. THE ONLY "
      "VALUE-ADJACENT MEASURE IN THIS PROJECT THAT IS CROSS-POSITION COMPARABLE, "
      "because it does not depend on a peer group's size or composition.",
      "TRUE", "CORE", "phase_7",
      "IT IS STILL NOT A VALUE MEASURE. A goalie's +2 and an attackman's +2 mean "
      "equally UNUSUAL seasons, not equal contributions. Using it as an award "
      "input would rank unusualness.",
      xpos="A: same meaning in every role", freeze="FREEZE"),
    M("shooting_value_null_z", "Shooting value vs chance (z)", PS, "chance",
      "standard deviations", "shooting value",
      "the chance sd of shooting value at the player's own attempt mix",
      "shooting_value_raw / shooting_value_null_sd", P7,
      "Whether a shooting season is distinguishable from chance.",
      "TRUE", "CORE", "phase_7",
      "The league sd of this column is 1.067 against 1.0 under the pure-chance "
      "null, implying only about 12% of the observed between-player variance in "
      "shooting value is skill.", xpos="A"),
    M("faceoff_value_null_z", "Faceoff value vs chance (z)", PS, "chance",
      "standard deviations", "faceoff value",
      "the chance sd of faceoff value at the player's own draw count",
      "faceoff_value_raw / faceoff_value_null_sd", P7,
      "Whether a faceoff season is distinguishable from chance.",
      "TRUE", "CORE", "phase_7",
      "League sd 1.830, implying a skill share of variance of 0.70 -- the "
      "strongest in the framework. The MEAN across all 47 draw-takers is -1.01: "
      "non-specialists who take occasional draws lose them at a clearly "
      "below-average rate, and the specialists' surplus is largely funded by wing "
      "players taking draws when the specialist is off the field.", xpos="A"),
    M("goalie_value_null_z", "Goalie value vs chance (z)", PS, "chance",
      "standard deviations", "goalie value",
      "the chance sd of goalie value at the player's own shots faced",
      "goalie_value_raw / goalie_value_null_sd", P7,
      "Whether a goalie season is distinguishable from chance. THE RIGHT COLUMN "
      "FOR COMPARING GOALIES TO NON-GOALIES, where raw goalie value is not.",
      "TRUE", "CORE", "phase_7", "League sd 1.320, skill share 0.43.", xpos="A"),

    # ================= RATES: RAW vs SHRUNK =================
    M("shooting_rate_raw", "Shooting % (raw)", PS, "rate_raw", "percentage",
      "goals", "shot attempts", "goals / shots", P7,
      "WHAT HAPPENED in 2026. Never overwritten by shrinkage.",
      "TRUE", "CONTEXTUAL", "phase_7", L_SHOOTING_NOISE,
      reliability="weak", xpos="B",
      redundancy="IDENTICAL(shooting_pct)"),
    M("shooting_rate_shrunk", "Shooting % (shrunk)", PS, "rate_shrunk",
      "percentage", "goals + prior alpha", "shots + prior strength",
      "(goals + alpha) / (shots + kappa), kappa = 70.8", P7,
      "AN ABILITY ESTIMATE, not a season record. Use it for questions about how "
      "good a player is or what he will do next; use the raw rate for what he did.",
      "TRUE", "CONTEXTUAL", "phase_7",
      "Shrinks hard: raw sd 0.192 collapses to 0.024. Replacing raw shooting with "
      "this moves 219 of 228 total-value ranks, maximum single move 161 places, "
      "rank correlation 0.758. PRESENTING ONE ORDERING WITHOUT THE OTHER IS "
      "PRESENTING A METHODOLOGICAL CHOICE AS A FINDING.",
      reliability="the shrinkage IS the small-sample handling", xpos="B"),
    M("one_point_rate_raw", "1PT % (raw)", PS, "rate_raw", "percentage",
      "one-point goals", "one-point attempts",
      "one_point_goals / one_point_attempts", P7, "What happened.",
      "TRUE", "CONTEXTUAL", "phase_7", "Weakly identified.", xpos="B",
      redundancy="IDENTICAL(one_point_conversion_pct)"),
    M("one_point_rate_shrunk", "1PT % (shrunk)", PS, "rate_shrunk", "percentage",
      "one-point goals + prior alpha", "one-point attempts + 75.3",
      "(goals + alpha) / (attempts + 75.3)", P7, "Ability estimate.",
      "TRUE", "CONTEXTUAL", "phase_7", "Raw sd 0.205 collapses to 0.023.",
      xpos="B"),
    M("two_point_rate_raw", "2PT % (raw)", PS, "rate_raw", "percentage",
      "two-point goals", "two-point attempts",
      "two_point_goals / two_point_attempts", P7,
      "What happened. Descriptive only.", "TRUE", "CONTEXTUAL", "phase_7",
      L_TWO_POINT_NOT_ID, reliability="NOT IDENTIFIED", xpos="D",
      redundancy="IDENTICAL(two_point_conversion_pct)",
      freeze="FREEZE_WITH_CAVEAT"),
    M("two_point_rate_shrunk", "2PT % (shrunk)", PS, "rate_shrunk", "percentage",
      "two-point goals + prior alpha", "two-point attempts + 1,000,000",
      "(goals + alpha) / (attempts + 1e6)", P7,
      "EVERY PLAYER'S VALUE IS THE LEAGUE MEAN, to seven decimal places. Published "
      "so that the absence of a signal is visible in the data rather than only in "
      "a document.", "neither", "DIAGNOSTIC", "phase_7",
      L_TWO_POINT_NOT_ID + " Shrunk sd is 7.7e-7. This column CANNOT distinguish "
      "players and must never be ranked.", reliability="NOT IDENTIFIED",
      xpos="D: unsupported for everyone", freeze="FREEZE_WITH_CAVEAT"),
    M("faceoff_rate_raw", "Faceoff % (raw)", PS, "rate_raw", "percentage",
      "faceoff wins", "faceoffs", "faceoff_wins / faceoffs", P7,
      "What happened.", "TRUE", "CORE", "phase_7", "Strongly identified.",
      xpos="D", redundancy="IDENTICAL(faceoff_win_pct)"),
    M("faceoff_rate_shrunk", "Faceoff % (shrunk)", PS, "rate_shrunk", "percentage",
      "faceoff wins + prior alpha", "faceoffs + 15.9",
      "(wins + alpha) / (faceoffs + 15.9)", P7,
      "Ability estimate. The prior is weak (15.9 draws) because faceoff skill is "
      "genuinely well identified, so this stays close to the raw rate for any "
      "real specialist.", "TRUE", "CORE", "phase_7",
      "Raw sd 0.272 to shrunk 0.092 -- a much smaller collapse than any other "
      "rate, which is itself the evidence that the differences are real.",
      xpos="D"),
    M("save_rate_raw", "Save % (raw)", PS, "rate_raw", "percentage", "saves",
      "saves + goals allowed", "saves / (saves + goals_allowed)", P7,
      "What happened.", "TRUE", "CONTEXTUAL", "phase_7",
      "Only 1 of 16 goalies reaches reliability 0.5.", xpos="D",
      redundancy="IDENTICAL(save_pct)"),
    M("save_rate_shrunk", "Save % (shrunk)", PS, "rate_shrunk", "percentage",
      "saves + prior alpha", "shots on goal + 300.3",
      "(saves + alpha) / (SOG + 300.3)", P7,
      "Ability estimate. THE MOST USEFUL GOALIE RATE IN 2026, precisely because "
      "the raw rate at these volumes is not separable from the prior.",
      "TRUE", "CONTEXTUAL", "phase_7",
      "Raw sd 0.153 collapses to 0.017. Real between-goalie spread exists "
      "(estimated true sd about 2.9 percentage points) but individual goalies "
      "cannot be told apart at 2026 volumes.", xpos="D"),

    # ================= RELIABILITY =================
    M("shooting_reliability", "Shooting reliability", PS, "reliability", "weight",
      "shot attempts", "shot attempts + 70.8", "n / (n + kappa)", P7,
      "The weight the empirical-Bayes posterior places on the player's OWN record "
      "rather than on the league prior. A statement about EVIDENCE, not quality.",
      "neither", "CORE", "phase_7",
      "MUST NEVER BE RANKED AS A QUALITY MEASURE. kappa is Phase 6's own estimate, "
      "imported not re-derived, so Phase 6 shrinkage and Phase 7 reliability "
      "cannot silently diverge.",
      xpos="A as a statement about evidence"),
    M("one_point_reliability", "1PT reliability", PS, "reliability", "weight",
      "one-point attempts", "one-point attempts + 75.3", "n / (n + kappa)", P7,
      "Evidence weight for the one-point rate.", "neither", "CORE", "phase_7",
      "See shooting_reliability.", xpos="A"),
    M("two_point_reliability", "2PT reliability", PS, "reliability", "weight",
      "two-point attempts", "two-point attempts + 1,000,000", "n / (n + kappa)",
      P7, "Below 0.001 for EVERY player in the league. The number that makes the "
      "two-point ban concrete rather than editorial.", "neither", "CORE", "phase_7",
      L_TWO_POINT_NOT_ID, xpos="A"),
    M("faceoff_reliability", "Faceoff reliability", PS, "reliability", "weight",
      "faceoffs", "faceoffs + 15.9", "n / (n + kappa)", P7,
      "Evidence weight for the faceoff rate. 18 of 47 takers reach 0.5.",
      "neither", "CORE", "phase_7", "See shooting_reliability.", xpos="A"),
    M("save_reliability", "Save reliability", PS, "reliability", "weight",
      "shots on goal faced", "shots on goal faced + 300.3", "n / (n + kappa)", P7,
      "Evidence weight for save percentage. Exactly 1 of 16 goalies reaches 0.5.",
      "neither", "CORE", "phase_7", "See shooting_reliability.", xpos="A"),
    M("shooting_posterior_ci_width", "Shooting posterior CI width", PS,
      "reliability", "percentage points", "95% beta-posterior upper minus lower",
      "not_applicable", "exact beta posterior quantiles", P7,
      "How wide the uncertainty on a player's shooting ability actually is.",
      "FALSE", "CONTEXTUAL", "phase_7",
      "Exact quantiles from a regularized incomplete beta function written out in "
      "the repo (this project runs without scipy by choice) and tested against "
      "closed forms.", xpos="A"),
    M("faceoff_posterior_ci_width", "Faceoff posterior CI width", PS, "reliability",
      "percentage points", "95% beta-posterior width", "not_applicable",
      "exact beta posterior quantiles", P7, "Uncertainty on faceoff ability.",
      "FALSE", "CONTEXTUAL", "phase_7", "See shooting_posterior_ci_width.",
      xpos="A"),
    M("save_posterior_ci_width", "Save posterior CI width", PS, "reliability",
      "percentage points", "95% beta-posterior width", "not_applicable",
      "exact beta posterior quantiles", P7, "Uncertainty on save ability.",
      "FALSE", "CONTEXTUAL", "phase_7", "See shooting_posterior_ci_width.",
      xpos="A"),
    M("role_rate_reliability", "Role-rate reliability", PS, "reliability", "weight",
      "trials of the rate that defines the player's role",
      "trials + that rate's prior strength", "n / (n + kappa) on the role rate",
      P7, "Evidence on the rate that defines what the player does: faceoff % for a "
      "specialist, save % for a goalie, shooting % otherwise.",
      "neither", "CORE", "phase_7",
      "ROLE-SPECIFIC BY DESIGN, which is why a separate offensive gate exists: a "
      "specialist with 353 draws is superbly identified on the rate that defines "
      "his role while having taken six offensive opportunities, and his faceoff "
      "reliability must not license him onto an efficiency-per-shot leaderboard.",
      xpos="A"),

    # ================= POSITIONAL STANDARDIZATION =================
    M("position_n_players", "Position group size", PS, "positional", "count",
      "players in the position group", "not_applicable",
      "count(players in position_group)", P7,
      "The size of the peer group a percentile or z-score is computed against.",
      "neither", "CORE", "phase_7",
      "Percentiles in the 13-player faceoff group and the 17-player goalie group "
      "are COARSE -- 7.7 and 5.9 percentile points between adjacent players -- and "
      "that coarseness is information."),
    M("position_EPA_mean", "Position EPA mean", PS, "positional", EPA_UNIT,
      "mean EPA in the position group", "not_applicable",
      "mean(EPA_points_raw) within position_group", P7,
      "The group centre a z-score is measured from.", "neither", "DIAGNOSTIC",
      "phase_7", "attack +1.076, midfield -0.309, defensive_field -0.369, "
      "faceoff +1.550, goalie -0.300."),
    M("position_EPA_sd", "Position EPA sd", PS, "positional", EPA_UNIT,
      "population sd of EPA in the position group", "not_applicable",
      "sd(EPA_points_raw) within position_group", P7,
      "The group spread a z-score is scaled by. THE 6.6x RANGE ACROSS GROUPS "
      "(goalie 9.591, defensive_field 1.461) IS THE CENTRAL CROSS-POSITION "
      "FINDING.", "neither", "CORE", "phase_7",
      "SUPPRESSED for groups with fewer than 9 players: the relative standard "
      "error of an estimated sd is 1/sqrt(2(n-1)), which is 25% at n=9, and below "
      "that the denominator of a z-score is more uncertain than the numerator it "
      "is meant to scale. Only the 2-player 'unknown' group is suppressed for "
      "this metric."),
    M("EPA_position_percentile", "EPA percentile (within position)", PS,
      "positional", "percentile 0-100", "mid-rank of the player within his group",
      "group size", "mid-rank empirical CDF within position_group", P7,
      "RECOMMENDED FIRST of the three standardizations: it assumes nothing about "
      "the distribution, which matters because offensive-field EPA has skew +0.75 "
      "and excess kurtosis +1.7.", "TRUE", "CORE", "phase_7",
      "A PERCENTILE IS NOT A VALUE. The 95th-percentile goalie and the "
      "95th-percentile attackman are equally unusual within role and are NOT "
      "thereby equally valuable -- one percentile point means 6.6x more points in "
      "the goalie group than in the defensive-field group. Treating equal "
      "percentiles as equal value is the exact error a naive award model makes.",
      xpos="B with a caveat: removes the group effect, does not create "
           "comparability of value"),
    M("EPA_position_robust_z", "EPA robust z (within position)", PS, "positional",
      "robust standard deviations", "EPA minus the group median",
      "1.4826 x the group MAD", "(x - median) / (1.4826 * MAD)", P7,
      "Second choice. Same scale as an ordinary z under normality, but a single "
      "+8 outlier cannot set the denominator.", "TRUE", "CORE", "phase_7",
      "Ordinary z against robust z moves 209 of 226 ranks at a rank correlation "
      "of 0.987.", xpos="B with the same caveat as the percentile"),
    M("EPA_position_z", "EPA z (within position)", PS, "positional",
      "standard deviations", "EPA minus the group mean", "the group sd",
      "(x - mean) / sd", P7,
      "Last of the three. Familiar, and correct when the group is large and "
      "symmetric.", "TRUE", "CONTEXTUAL", "phase_7",
      "NULL where the group has fewer than 9 players. Positional against "
      "league-wide standardization moves 224 of 226 ranks at a rank correlation "
      "of 0.945.", xpos="B with the same caveat"),
    M("usage_position_percentile", "Usage percentile (within position)", PS,
      "positional", "percentile 0-100", "mid-rank of usage within the group",
      "group size", "mid-rank empirical CDF of offensive_play_share", P7,
      "How much of his team's offence a player took, relative to his positional "
      "peers.", "neither", "CONTEXTUAL", "phase_7",
      "Usage is not value; a high usage percentile is a workload statement.",
      xpos="B"),
    M("efficiency_position_percentile", "Efficiency percentile (within position)",
      PS, "positional", "percentile 0-100",
      "mid-rank of EPA per opportunity within the group", "group size",
      "mid-rank empirical CDF of EPA_per_recorded_opportunity", P7,
      "Per-opportunity production relative to positional peers.",
      "TRUE", "CONTEXTUAL", "phase_7",
      "Inherits the reliability problem of its input: most players' per-opportunity "
      "figures are not separable from chance.", xpos="B"),

    # ================= VALUE DECOMPOSITION =================
    M("faceoff_share_of_absolute_value", "Faceoff share of |value|", PS,
      "decomposition", "percentage", "|faceoff value|",
      "sum of the absolute values of all components",
      "|faceoff_value| / sum|components|", P7,
      "Where a player's measured value comes from. Denominated in ABSOLUTE "
      "magnitudes because the components are signed residuals: a share of a "
      "signed sum can be negative or unbounded and is not interpretable.",
      "neither", "CORE", "phase_7",
      "ACROSS THE 13 SPECIALISTS THE FACEOFF SHARE AVERAGES 0.53 AND SPANS "
      "0.12-0.88 -- so 'a FOGO's value is his faceoffs' is true on average and "
      "emphatically not true player by player. Petey LaSalla's measured value is "
      "87% offensive. Read faceoff_value_raw directly rather than inferring it "
      "from a total."),
    M("offensive_share_of_absolute_value", "Offensive share of |value|", PS,
      "decomposition", "percentage", "|shooting value| + |turnover value|",
      "sum of the absolute values of all components",
      "(|shooting| + |turnover|) / sum|components|", P7,
      "The offensive share of measured value.", "neither", "CORE", "phase_7",
      "See faceoff_share_of_absolute_value."),
    M("defensive_partial_share_of_absolute_value", "Partial-defensive share of "
      "|value|", PS, "decomposition", "percentage",
      "|partial defensive value|", "sum of the absolute values of all components",
      "|defensive_partial| / sum|components|", P7,
      "How much of a player's MEASURED value is the one defensive act the feed "
      "counts. Mean share among faceoff specialists: 0.05.",
      "neither", "CONTEXTUAL", "phase_7",
      "A LOW SHARE FOR A DEFENDER IS A MEASUREMENT STATEMENT, NOT A PERFORMANCE "
      "ONE. " + L_DEF_PARTIAL, freeze="FREEZE_WITH_CAVEAT"),

    # ================= ELIGIBILITY FLAGS =================
    M("descriptive_eligible", "Descriptive eligible", PS, "eligibility", "boolean",
      "played at least one eligible game", "not_applicable",
      "games_played >= 1", P7,
      "TRUE for all 228 players. NOBODY IS EVER DROPPED FOR A SMALL SAMPLE; they "
      "are flagged out of leaderboards their sample cannot support and keep their "
      "observed production.", "neither", "CORE", "phase_7",
      "The absence of a filter is deliberate.", xpos="A"),
    M("rate_ranking_eligible", "Rate-ranking eligible", PS, "eligibility",
      "boolean", "reliability >= 0.5 on the rate that defines the player's role",
      "not_applicable", "role_rate_reliability >= 0.5", P7,
      "Who has enough evidence to appear on a ROLE-rate leaderboard. 27 of 228.",
      "neither", "CORE", "phase_7",
      "Role-specific by design; see role_rate_reliability.", xpos="A"),
    M("offensive_rate_ranking_eligible", "Offensive-rate eligible", PS,
      "eligibility", "boolean", "shooting reliability >= 0.5", "not_applicable",
      "shooting_reliability >= 0.5", P7,
      "Who may appear on a per-shot or per-opportunity efficiency leaderboard. "
      "13 of 228.", "neither", "CORE", "phase_7",
      "Separate from rate_ranking_eligible precisely so faceoff identification "
      "cannot license a shooting leaderboard appearance.", xpos="A"),
    M("reliability_adjusted_eligible", "Reliability-adjusted eligible", PS,
      "eligibility", "boolean", "at least one trial of the relevant rate",
      "not_applicable", "trials >= 1", P7,
      "Who has a shrunk estimate at all. 200 of 228.", "neither", "CORE",
      "phase_7", "A shrunk estimate exists wherever a trial does.", xpos="A"),
    M("future_award_input_eligible", "1% play-share eligible (LR rule)", PS,
      "eligibility", "boolean", "at least 1% of team event-log play shares",
      "not_applicable", "event_log_play_share >= 0.01", P7,
      "Lacrosse Reference's published minimum-usage rule, reproduced verbatim. "
      "204 of 228 clear it.", "neither", "CONTEXTUAL", "phase_7",
      "THE ONE ADOPTED THRESHOLD THAT IS NOT DERIVED FROM THIS DATA. It is "
      "adopted because Lacrosse Reference publishes it and is labelled as a "
      "reference reproduction. Its denominator, event_log_play_shares, is the "
      "usage measure this project does NOT use. Phase 8 uses it nowhere as a "
      "leaderboard gate.", xpos="A", freeze="FREEZE_WITH_CAVEAT"),
    M("small_sample", "Small sample", PS, "eligibility", "boolean",
      "reliability < 0.5 on the role rate", "not_applicable",
      "role_rate_reliability < 0.5", P7,
      "About EVIDENCE. 201 of 228 players.", "FALSE", "CORE", "phase_7",
      "Complement of rate_ranking_eligible.", xpos="A",
      redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("chance_variation_exceeds_peer_spread", "Chance exceeds peer spread", PS,
      "eligibility", "boolean",
      "the player's own chance sd is at least his position group's sd",
      "not_applicable", "EPA_points_null_sd >= position_EPA_sd", P7,
      "A DIFFERENT kind of smallness from small_sample, and it catches "
      "HIGH-volume players too: a 96-attempt midfielder has a chance sd of about "
      "4.5 EPA_points against a midfield group sd of 3.3, so luck alone could put "
      "him anywhere in his group. 50 of 228.", "FALSE", "CORE", "phase_7",
      "Not a sample-size flag. Do not collapse it with small_sample.", xpos="A"),
    M("defense_partial", "Defence is partial", PS, "eligibility", "boolean",
      "always TRUE", "not_applicable", "TRUE on all 228 rows", P7,
      "A constant, carried on every row so the caveat cannot be lost by "
      "subsetting.", "neither", "CORE", "phase_7", L_DEF_PARTIAL, xpos="A"),
    M("usage_proxy_only", "Usage is a proxy", PS, "eligibility", "boolean",
      "always TRUE", "not_applicable", "TRUE on all 228 rows", P7,
      "A constant, carried on every row.", "neither", "CORE", "phase_7",
      L_USAGE_NOT_POSS, xpos="A"),
]


# ---------------------------------------------------------------------------
# Metrics that are DELIBERATELY NOT PUBLISHED. Catalogued so that "we did not
# build this" is a data row with a reason and a named missing input, rather
# than an absence a later phase rediscovers and quietly fills in.
# ---------------------------------------------------------------------------
REJECTED_METRICS = [
    M("time_of_possession_reconstructed", "Reconstructed time of possession",
      "team_season", "time", "seconds",
      "sum of reconstructed possession spans", "not_applicable",
      "sum(possessions.duration_seconds)", "possessions.csv",
      "TEMPTING BECAUSE the possession layer has a duration on every row and "
      "summing it looks like time of possession.", "neither", "DEFERRED",
      "phase_5",
      "IT IS NOT TIME OF POSSESSION. The span from a possession's first logged "
      "event to its last excludes the interval between the previous possession's "
      "last logged event and this one's first -- transition, the clear, the dead "
      "ball. Median coverage of PLL's official figure is 0.751 with a 0.536-0.998 "
      "range and r = 0.58, and mean absolute error in team possession SHARE is "
      "4.9 percentage points. A 25% shortfall that varied consistently would be "
      "rescalable; a 0.54-1.00 range at r=0.58 is not. MISSING INPUT: an event "
      "stream that logs possession start as well as possession action. NOTE the "
      "clock itself is sound -- three independent checks confirm it -- so this is "
      "a coverage problem, not a timing problem, which is why possession-LENGTH "
      "splits remain defensible.", freeze="DO_NOT_USE"),
    M("clearing_efficiency", "Clearing efficiency", "team_season", "clearing",
      "percentage", "successful clears", "clear attempts",
      "clears / clear_attempts", "team_game_stats.csv",
      "TEMPTING BECAUSE both official counts exist and the division is trivial.",
      "TRUE", "DEFERRED", "phase_5",
      "Two independent blockers. (1) The feed logs NO CLEAR EVENT, so a clear "
      "cannot be tied to a possession boundary and the metric cannot be "
      "integrated with anything else in the system -- it would be an orphan ratio. "
      "(2) 36.2% of possessions have an unconfirmed start mechanism, which is "
      "exactly the field this metric would need to matter. The raw counts ARE "
      "published; the ratio is not, because a published ratio would be read as a "
      "possession-linked statistic it is not. MISSING INPUT: a clear/ride event "
      "type in the play-by-play.", freeze="DO_NOT_USE"),
    M("riding_efficiency", "Riding efficiency", "team_season", "clearing",
      "percentage", "successful rides", "ride attempts", "not_computable",
      "team_game_stats.csv",
      "TEMPTING BECAUSE rideAttempts is published and looks like half of a rate.",
      "TRUE", "UNSUPPORTED", "phase_5",
      "THE NUMERATOR DOES NOT EXIST. The feed gives ride ATTEMPTS and no ride "
      "success count anywhere, so this is not an unreliable rate -- it is an "
      "unformable one. MISSING INPUT: a ride outcome field.", freeze="DO_NOT_USE"),
    M("man_up_possessions", "Man-up possessions", "team_season", "extra_man",
      "count", "offensive possessions played man-up", "not_applicable",
      "not_computable", "possessions.csv",
      "TEMPTING BECAUSE possessions.has_man_up_shot exists and looks like a "
      "man-up flag.", "neither", "UNSUPPORTED", "phase_5",
      "IT IS A GOAL FLAG. It is TRUE for exactly 90 possessions and every one "
      "contains a man-up goal, so the column would be a renamed goal count and "
      "every rate on it is degenerate -- man-up shooting percentage computed that "
      "way is 1.000 for all 8 teams. Penalty events carry no possession linkage "
      "either, so man-up possessions cannot be recovered from penalty timing "
      "without inventing the state. A regression test asserts the goals-only "
      "property, so if PLL starts tagging missed man-up shots this decision gets "
      "revisited rather than silently inherited. MISSING INPUT: man-up tagging on "
      "shot events, or penalty-to-possession linkage.", freeze="DO_NOT_USE"),
    M("possession_source_efficiency_split", "Efficiency by possession start type",
      "team_season", "possession", "points per possession",
      "points on possessions of a given start type",
      "possessions of that start type", "not_computable", "possessions.csv",
      "TEMPTING BECAUSE Lacrosse Reference publishes efficiency by possession "
      "source and the possession layer has a start_reason column.",
      "TRUE", "DEFERRED", "phase_5",
      "922 possessions carry start_reason = 'other_confirmed_control' -- the team "
      "is known, the control-gain mechanism is not -- so a defensive-stop vs. "
      "ground-ball split would assign about 21% of possessions to a bucket the "
      "feed never established. ONLY THE FACEOFF SPLIT IS PUBLISHED, because "
      "faceoff-started possessions are never ambiguous. MISSING INPUT: a "
      "possession-start mechanism in the feed.", freeze="DO_NOT_USE"),
    M("true_possession_participation", "True possession participation",
      "player_season", "usage", "percentage",
      "team possessions the player was on the field for", "team possessions",
      "not_computable", "not_available",
      "TEMPTING BECAUSE it is the correct denominator for almost every player "
      "rate, and every other sport's public data has it.", "neither",
      "UNSUPPORTED", "phase_6",
      "THE PLL FEED CARRIES NO LINEUP, SUBSTITUTION, SHIFT OR MINUTES DATA OF ANY "
      "KIND, verified across all 51 raw games. Two validation checks and two tests "
      "scan every Phase 7 output and query for a possession- or "
      "duration-denominated player column and fail if one appears. Every usage "
      "measure in this project is an INDIVIDUAL ACTION COUNT and says so. MISSING "
      "INPUT: lineup or shift data.", freeze="DO_NOT_USE"),
    M("individual_two_point_shooting_ability", "Two-point shooting ability ranking",
      "player_season", "shooting", "percentage", "two-point goals",
      "two-point attempts", "not_supportable", OFFP,
      "TEMPTING BECAUSE the raw rate computes for 127 players and a two-point "
      "specialist is an intuitive archetype.", "TRUE", "UNSUPPORTED", "phase_7",
      L_TWO_POINT_NOT_ID + " The median two-point shooter took 2 attempts and the "
      "maximum was 29. Raw two-point PRODUCTION (goals, attempts, conversion with "
      "its denominator) IS published descriptively; ABILITY is not ranked at any "
      "sample size. MISSING INPUT: more seasons -- 2022-2025 are structurally "
      "identical and would add 190 games, which is what would make this testable "
      "rather than foreclosed.", freeze="DO_NOT_USE"),
    M("complete_defensive_value", "Complete defensive value", "player_season",
      "value", EPA_UNIT, "everything a defender does", "defensive opportunities",
      "not_computable", "not_available",
      "TEMPTING BECAUSE defensive_value_partial_raw looks like a defensive rating "
      "and the word 'partial' is easy to drop.", "TRUE", "UNSUPPORTED", "phase_6",
      "THE FEED ATTRIBUTES EXACTLY ONE DEFENSIVE ACT: caused turnovers, 741 "
      "league-wide, against 4,106 shots and 1,369 attributed turnovers. " +
      L_DEF_PARTIAL + " Validation check 19 and three tests fail if the word "
      "'partial' is dropped from any defensive column name. MISSING INPUT: "
      "matchup, shot-location and lineup data.", freeze="DO_NOT_USE"),
    M("caused_turnover_total_defensive_impact", "Caused-turnover-based defensive "
      "impact", "player_season", "value", EPA_UNIT,
      "caused turnovers x an event value", "not_applicable",
      "not_supportable", OFFP,
      "TEMPTING BECAUSE caused turnovers reconcile perfectly and multiplying by "
      "the turnover coefficient gives a clean-looking number.", "TRUE",
      "UNSUPPORTED", "phase_6",
      "Scaling one act does not make it a total. It would also invite the reader "
      "to treat a defender's zero as an average defensive season, which is exactly "
      "the error the PARTIAL naming exists to prevent. The residual form IS "
      "published as defensive_value_partial_raw; what is refused is the "
      "presentation of it as a defensive TOTAL.", freeze="DO_NOT_USE"),
    M("opponent_adjusted_value", "Opponent-adjusted value", "team_and_player",
      "adjustment", EPA_UNIT, "value adjusted for schedule strength",
      "not_applicable", "not_implemented", "not_available",
      "TEMPTING BECAUSE nothing in this project is opponent-adjusted and everyone "
      "knows it should be.", "TRUE", "DEFERRED", "phase_5",
      "PHASE 9 MEASURED THE FEASIBILITY AND THE ANSWER IS 'YES, BUT IT BUYS "
      "ALMOST NOTHING'. Identifiability is not the problem: PLL plays an 8-team "
      "near-round-robin, so all 28 possible pairings occur in every season and "
      "schedule connectivity is 1.00 -- the best possible case. The problem is "
      "that a balanced schedule leaves nothing to adjust FOR. The spread in "
      "strength of opposition actually faced is only 15-29% of the spread "
      "between teams, a ridge fit moves offensive-efficiency ranks by at most 2 "
      "places (0-1 in four of five seasons, Spearman 0.93-1.00 against "
      "unadjusted), and in 2026 the adjustment is SMALLER than its own bootstrap "
      "standard error (signal-to-noise 0.73; 1.04-2.02 in the other seasons). "
      "Publishing an 'adjusted' number less reliable than the unadjusted one "
      "would be a regression. Pooling seasons does not help: a 2022 roster and a "
      "2026 roster are not the same unit, so extra seasons replicate the "
      "question rather than adding connectivity. STILL DEFERRED, now for a "
      "measured reason rather than an assumed one. Evidence: "
      "multi_season_opponent_adjustment.csv.", freeze="DO_NOT_USE"),
    M("assisted_unassisted_value_split", "Assisted / unassisted value split",
      "player_season", "value", EPA_UNIT,
      "value split between shooter and feeder", "not_applicable",
      "not_supportable", PBP,
      "TEMPTING BECAUSE official assists are reliable and splitting credit is "
      "standard practice in other sports.", "TRUE", "DEFERRED", "phase_6",
      "Not an attribution problem -- an ACCOUNTING one. The points from an "
      "assisted goal are already fully priced in the shooter's shooting_value, so "
      "an independent assist credit creates two players' worth of value from one "
      "goal. Splitting credit between shooter and assister is a DEFENSIBLE "
      "alternative, but it changes what shooting_value means, so the choice "
      "belongs to the phase that needs it rather than being slipped in as a "
      "default. Separately, the feed's shotAssistId is a PRE-SHOT PASS indicator, "
      "not a confirmed assist, and an unpopulated value is not a negative "
      "assertion -- validation greps the value SQL to enforce that it is used "
      "nowhere.", freeze="DO_NOT_USE"),
    M("shot_quality_model", "Expected goals / shot-quality model", "player_season",
      "shooting", "probability", "modelled goal probability", "shot attempt",
      "not_computable", PBP,
      "TEMPTING BECAUSE expected-goals models are the standard advanced shooting "
      "metric in every comparable sport.", "TRUE", "UNSUPPORTED", "phase_6",
      "SHOT EVENTS CARRY NO LOCATION, NO DISTANCE AND NO DEFENDER in any of the "
      "51 raw games -- the only populated details keys are shotOnGoal, shotSaved "
      "and saveType. A richer model WAS fitted on what remains (shot class plus "
      "game state) and LOST on 5-fold cross-validated Brier score to the simple "
      "two-class empirical rate. An earlier version appeared to win by 2.1% and "
      "that was TARGET LEAKAGE: PLL's score columns already include the goal on "
      "the row itself. MISSING INPUT: shot coordinates.", freeze="DO_NOT_USE"),
    M("ground_ball_value", "Ground ball value", "player_season", "value", EPA_UNIT,
      "ground balls x a context-specific event value", "no opportunity denominator",
      "not_supportable", OFFP,
      "TEMPTING BECAUSE ground balls are the classic lacrosse hustle statistic and "
      "the event value (+0.124) is estimated and published.", "TRUE", "DEFERRED",
      "phase_6",
      "Three independent reasons. (1) NO OPPORTUNITY DENOMINATOR: the feed records "
      "no ground-ball CHANCE, so the quantity cannot be expressed as a residual "
      "and is not commensurable with the other components. (2) The distinguishable "
      "contexts are NOT statistically separable at 2026 samples -- faceoff scrum "
      "0.163 [0.124,0.201], possession-gaining 0.130 [0.098,0.162], retained 0.082 "
      "[-0.040,0.204]. (3) IT WOULD DOUBLE-COUNT FACEOFF VALUE: 1,095 of 3,091 "
      "ground balls immediately follow a faceoff, 99.7% go to the winning team and "
      "61.5% to the winner himself, so a per-ground-ball credit would pay the same "
      "player twice for one change of possession 673 times. The empirical event "
      "value is preserved as ground_ball_event_value_descriptive, OUTSIDE every "
      "total.", freeze="DO_NOT_USE"),
    M("statistical_tewaaraton_or_mvp_composite", "MVP / Statistical Tewaaraton / "
      "composite player score", "player_season", "composite", "index",
      "weighted combination of value components across positions", "not_applicable",
      "NOT BUILT -- PROHIBITED IN PHASE 8", "not_applicable",
      "TEMPTING BECAUSE every component is in the same unit and a weighted sum is "
      "one line of SQL.", "TRUE", "UNSUPPORTED", "phase_8",
      "NO COMPOSITE, AWARD SCORE, WAR, REPLACEMENT LEVEL OR CROSS-POSITION "
      "RANKING EXISTS ANYWHERE IN THIS REPOSITORY, and Phase 8 adds an automated "
      "test that fails if one appears. THE UNIT IS SHARED; THE SCALE IS NOT. "
      "Opportunity bases differ by 6.6x in observed spread, the only class-A "
      "value-adjacent metric measures unusualness rather than contribution, and "
      "positional percentiles remove the group effect without creating "
      "comparability of value. A cross-position weighting is a JUDGEMENT that has "
      "to be argued for in the open; no metric in this system supplies one. "
      "Category leaders and within-role rankings ARE published.",
      freeze="DO_NOT_USE"),
]
