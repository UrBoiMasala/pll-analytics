"""Phase 8 metric catalog: team-level rows. See pll_phase8_catalog_core.py."""
from pll_phase8_catalog_core import (  # noqa: F401
    M, L_NOT_OPP_ADJ, L_SMALL_LEAGUE, L_POSS_SUBSET, L_OFFICIAL_TO, L_OFFICIAL_GB,
    L_MANUP, L_TWO_POINT_THIN, L_SPAN_NOT_TOP,
)

TS = "team_season"
POSS = "possessions.csv (Phase 4 reconstruction)"
OFF = "team_game_stats.csv (official PLL box score)"
PBP = "events.csv (cleaned play-by-play)"
GAMES = "games.csv (official schedule and final scores)"

TEAM_METRICS = [
    # ================= RECORD / SCORING CONTEXT =================
    M("games_played", "Games", TS, "record", "count",
      "eligible completed games the team appeared in", "not_applicable",
      "count(eligible games with this team as a participant)", GAMES,
      "Season length. 12 or 13, because two teams played an extra quarterfinal.",
      "neither", "CORE", "phase_5",
      "Regular season plus the 2 completed quarterfinals. The all-star game is "
      "excluded league-wide, once, in the eligible_games view.",
      official="official"),
    M("wins", "Wins", TS, "record", "count", "games with a higher final score",
      "not_applicable", "count(games where team_score > opponent_score)", GAMES,
      "Wins.", "TRUE", "CORE", "phase_5",
      "Playoff games are included, so a 13-game team's record is not directly "
      "comparable to a 12-game team's.", official="official"),
    M("losses", "Losses", TS, "record", "count", "games with a lower final score",
      "not_applicable", "count(games where team_score < opponent_score)", GAMES,
      "Losses.", "FALSE", "CORE", "phase_5", "See wins.", official="official"),
    M("ties", "Ties", TS, "record", "count", "games ending level", "not_applicable",
      "count(games where scores equal)", GAMES,
      "Zero in 2026 -- PLL plays overtime. Kept so the identity "
      "wins+losses+ties=games_played is checkable rather than assumed.",
      "neither", "DIAGNOSTIC", "phase_5", "Always 0 in 2026.", official="official"),
    M("playoff_games", "Playoff games", TS, "record", "count",
      "eligible games flagged is_playoff", "not_applicable",
      "count(eligible games where is_playoff)", GAMES,
      "How much of the record is postseason. 0 or 1 in 2026.",
      "neither", "CONTEXTUAL", "phase_5",
      "Only the 2 completed quarterfinals; semifinals and the championship were "
      "unplayed at extraction.", official="official"),
    M("win_pct", "Win %", TS, "record", "percentage", "wins", "games played",
      "wins / games_played", GAMES,
      "Share of games won.", "TRUE", "CORE", "phase_8",
      L_SMALL_LEAGUE + " Ties would break this definition; there are none in 2026.",
      official="official"),
    M("points_scored", "Points scored", TS, "scoring", "count",
      "PLL points on the team's offensive possessions (2 for a two-point goal)",
      "not_applicable", "sum(possessions.points_scored) over offensive possessions", POSS,
      "Season points. Reconciles exactly with the official final score in all 50 "
      "eligible games.", "TRUE", "CORE", "phase_5",
      "PLL points, not goals: a two-point goal is ONE goal worth TWO points. "
      "Never mix this with a goal count.", official="reconstructed_reconciled"),
    M("points_allowed", "Points allowed", TS, "scoring", "count",
      "PLL points on possessions the team defended", "not_applicable",
      "sum(possessions.points_scored) over defensive possessions", POSS,
      "Season points conceded.", "FALSE", "CORE", "phase_5",
      "See points_scored.", official="reconstructed_reconciled"),
    M("point_differential", "Point differential", TS, "scoring", "count",
      "points scored minus points allowed", "not_applicable",
      "points_scored - points_allowed", POSS,
      "Season scoring margin. In 2026 it diverges sharply from record for two "
      "teams (Whipsnakes +14 at 5-8, Waterdogs +14 at 9-3), which is a real "
      "close-game result, not an error.", "TRUE", "CORE", "phase_8",
      L_NOT_OPP_ADJ + " Sums to exactly 0 across the league.",
      official="reconstructed_reconciled"),
    M("points_per_game", "Points/game", TS, "scoring", "rate",
      "points scored", "games played", "points_scored / games_played", POSS,
      "Scoring rate uncorrected for pace. Compare with offensive_efficiency, "
      "which is pace-corrected -- the two orderings differ.",
      "TRUE", "CONTEXTUAL", "phase_8",
      "NOT pace-adjusted. A fast team scores more per game at the same "
      "efficiency. " + L_NOT_OPP_ADJ, redundancy="RELATED_BUT_DISTINCT"),
    M("points_allowed_per_game", "Points allowed/game", TS, "scoring", "rate",
      "points allowed", "games played", "points_allowed / games_played", POSS,
      "Concession rate uncorrected for pace.", "FALSE", "CONTEXTUAL", "phase_8",
      "NOT pace-adjusted; see points_per_game.", redundancy="RELATED_BUT_DISTINCT"),
    M("point_differential_per_game", "Point differential/game", TS, "scoring", "rate",
      "point differential", "games played", "point_differential / games_played", POSS,
      "Margin per game. Puts the 12- and 13-game teams on one scale.",
      "TRUE", "CORE", "phase_8", L_NOT_OPP_ADJ),

    # ================= POSSESSION =================
    M("offensive_possessions", "Offensive possessions", TS, "possession", "count",
      "reconstructed possessions with this team on offence", "not_applicable",
      "count(possessions where offense_team_id = team)", POSS,
      "The denominator of every offensive efficiency metric.",
      "neither", "CORE", "phase_5",
      "Which team had the ball is structurally certain (0 possessions with an "
      "uncertain offensive team). 36.2% carry is_ambiguous, but that flags the "
      "BOUNDARY MECHANISM, not the team. " + L_POSS_SUBSET),
    M("defensive_possessions", "Defensive possessions", TS, "possession", "count",
      "reconstructed possessions this team defended", "not_applicable",
      "count(possessions where defense_team_id = team)", POSS,
      "The denominator of every defensive efficiency metric. Sums league-wide to "
      "exactly the same total as offensive possessions.",
      "neither", "CORE", "phase_5", "See offensive_possessions."),
    M("possession_differential", "Possession differential", TS, "possession", "count",
      "offensive minus defensive possessions", "not_applicable",
      "offensive_possessions - defensive_possessions", POSS,
      "How many more times a team had the ball than its opponents did. Driven "
      "almost entirely by the faceoff, which is why it tracks faceoff_win_pct "
      "closely.", "TRUE", "CONTEXTUAL", "phase_8",
      "Small by construction and heavily faceoff-driven; it is not an "
      "independent skill from faceoff win percentage. Sums to 0 league-wide.",
      redundancy="HIGHLY_OVERLAPPING"),
    M("total_game_possessions", "Total possessions", TS, "possession", "count",
      "offensive plus defensive possessions", "not_applicable",
      "offensive_possessions + defensive_possessions", POSS,
      "Total possessions the team was involved in. The correct denominator for "
      "two-sided rates such as ground balls.", "neither", "CORE", "phase_5",
      "Not a pace measure on its own -- divide by games."),
    M("team_possessions_per_game", "Possessions/game", TS, "possession", "rate",
      "offensive possessions", "games played",
      "offensive_possessions / games_played", POSS,
      "PACE, expressed in possession COUNTS. Deliberately not in seconds: "
      "possession counts are structurally validated, possession durations are "
      "not a valid time measure.", "neither", "CORE", "phase_5",
      "Higher is neither good nor bad -- it is a style. " + L_SPAN_NOT_TOP),
    M("combined_possessions_per_game", "Combined possessions/game", TS, "possession",
      "rate", "offensive plus defensive possessions", "games played",
      "total_game_possessions / games_played", POSS,
      "Game pace including the opponent's share.", "neither", "CORE", "phase_5",
      "Nearly double team_possessions_per_game by construction.",
      redundancy="HIGHLY_OVERLAPPING"),
    M("faceoff_start_possessions", "Faceoff-started possessions", TS, "possession",
      "count", "offensive possessions whose start_reason is faceoff_win",
      "not_applicable", "count(possessions where start_reason='faceoff_win')", POSS,
      "How many possessions arrived off the draw.", "neither", "CORE", "phase_5",
      "Faceoff-started possessions are never flagged ambiguous (1,326/1,326 "
      "faceoff team attributions resolved), so this split is trustworthy where "
      "the fuller possession-source split is not."),
    M("faceoff_start_possession_share", "Faceoff-start share", TS, "possession",
      "percentage", "faceoff-started offensive possessions", "offensive possessions",
      "faceoff_start_possessions / offensive_possessions", POSS,
      "Share of a team's offence that began on a won draw. The one possession-"
      "source split the feed supports.", "TRUE", "CORE", "phase_5",
      "The complementary splits are NOT published: 922 possessions carry "
      "start_reason='other_confirmed_control' (team known, mechanism unknown), so "
      "a defensive-stop vs. ground-ball split would assign ~21% of possessions to "
      "a bucket the feed never established."),

    # ================= EFFICIENCY =================
    M("offensive_efficiency", "Offensive efficiency", TS, "efficiency",
      "points per possession", "points scored", "offensive possessions",
      "points_scored / offensive_possessions", POSS,
      "PLL points per offensive possession -- the pace-free measure of offence. "
      "League 2026: 0.271.", "TRUE", "CORE", "phase_5",
      L_NOT_OPP_ADJ + " " + L_POSS_SUBSET + " " + L_SMALL_LEAGUE,
      redundancy="IDENTICAL(points_per_possession)"),
    M("points_per_possession", "Points per possession", TS, "efficiency",
      "points per possession", "points scored", "offensive possessions",
      "points_scored / offensive_possessions", POSS,
      "The same number as offensive_efficiency. Both names are emitted because "
      "both are in common use; the alias is recorded rather than left as two "
      "unexplained identical columns.", "TRUE", "CONTEXTUAL", "phase_5",
      "ALIAS. Never report both as if they were two measurements.",
      redundancy="IDENTICAL(offensive_efficiency)"),
    M("defensive_efficiency", "Defensive efficiency", TS, "efficiency",
      "points per possession", "points allowed", "defensive possessions",
      "points_allowed / defensive_possessions", POSS,
      "PLL points conceded per defensive possession. LOWER IS BETTER.",
      "FALSE", "CORE", "phase_5",
      L_NOT_OPP_ADJ + " " + L_POSS_SUBSET,
      redundancy="IDENTICAL(points_allowed_per_possession)"),
    M("points_allowed_per_possession", "Points allowed per possession", TS,
      "efficiency", "points per possession", "points allowed", "defensive possessions",
      "points_allowed / defensive_possessions", POSS,
      "Alias of defensive_efficiency.", "FALSE", "CONTEXTUAL", "phase_5",
      "ALIAS.", redundancy="IDENTICAL(defensive_efficiency)"),
    M("net_efficiency", "Net efficiency", TS, "efficiency", "points per possession",
      "offensive minus defensive efficiency", "not_applicable",
      "offensive_efficiency - defensive_efficiency", POSS,
      "The single best pace-free summary of team quality available here. Uniquely "
      "among the possession metrics it is INVARIANT to possession ambiguity in "
      "LEVEL as well as in rank (Phase 5 null model: shift +0.0006, p=0.94), "
      "because the offensive and defensive selection effects cancel.",
      "TRUE", "CORE", "phase_5",
      L_NOT_OPP_ADJ + " " + L_SMALL_LEAGUE + " In 2026 the top two teams are "
      "separated by 0.00012 points per possession -- a tie in everything but "
      "sort order."),
    M("offensive_efficiency_per_100", "Offensive efficiency /100", TS, "efficiency",
      "points per 100 possessions", "100 x points scored", "offensive possessions",
      "100 * offensive_efficiency", POSS,
      "The same metric on a per-100 scale, exposed under an explicit name so the "
      "two scales are never confused.", "TRUE", "CONTEXTUAL", "phase_5",
      "ALIAS at 100x scale.", redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("defensive_efficiency_per_100", "Defensive efficiency /100", TS, "efficiency",
      "points per 100 possessions", "100 x points allowed", "defensive possessions",
      "100 * defensive_efficiency", POSS, "Per-100 scale.", "FALSE", "CONTEXTUAL",
      "phase_5", "ALIAS at 100x scale.", redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("net_efficiency_per_100", "Net efficiency /100", TS, "efficiency",
      "points per 100 possessions", "100 x net efficiency", "not_applicable",
      "100 * net_efficiency", POSS, "Per-100 scale.", "TRUE", "CONTEXTUAL",
      "phase_5", "ALIAS at 100x scale.", redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("goals_per_possession", "Goals per possession", TS, "efficiency",
      "goals per possession", "goals", "offensive possessions",
      "goals / offensive_possessions", POSS,
      "Share of offensive possessions ending in a goal -- a goal always closes "
      "its possession, verified season-wide. This is the column that is directly "
      "comparable to Lacrosse Reference's NCAA 'Efficiency'.",
      "TRUE", "CORE", "phase_5",
      "Discards the second point of every two-point goal, which is 12.1% of PLL "
      "scoring. Use offensive_efficiency for PLL offence and this only for NCAA "
      "comparison.", redundancy="RELATED_BUT_DISTINCT"),
    M("shots_per_possession", "Shots per possession", TS, "efficiency",
      "shots per possession", "shot attempts", "offensive possessions",
      "shots / offensive_possessions", POSS,
      "How often a possession produces a shot. League 2026: 0.93.",
      "TRUE", "CORE", "phase_5", L_POSS_SUBSET),
    M("shots_on_goal_per_possession", "Shots on goal per possession", TS,
      "efficiency", "shots on goal per possession", "shots on goal",
      "offensive possessions", "shots_on_goal / offensive_possessions", POSS,
      "Shot generation net of misses.", "TRUE", "CONTEXTUAL", "phase_5",
      L_POSS_SUBSET, redundancy="HIGHLY_OVERLAPPING"),
    M("turnovers_per_possession", "Turnovers per possession", TS, "efficiency",
      "turnovers per possession", "official turnovers", "offensive possessions",
      "turnovers / offensive_possessions", OFF,
      "Possession security.", "FALSE", "CORE", "phase_5", L_OFFICIAL_TO,
      official="official", redundancy="IDENTICAL(turnover_rate)"),
    M("turnover_rate", "Turnover rate", TS, "efficiency", "turnovers per possession",
      "official turnovers", "offensive possessions",
      "turnovers / offensive_possessions", OFF,
      "Alias of turnovers_per_possession; both names are in the brief.",
      "FALSE", "CORE", "phase_5", L_OFFICIAL_TO, official="official",
      redundancy="IDENTICAL(turnovers_per_possession)"),
    M("possession_ending_turnover_rate", "Possession-ending turnover rate", TS,
      "efficiency", "percentage", "possessions whose end_reason is turnover",
      "offensive possessions",
      "possession_ending_turnovers / offensive_possessions", POSS,
      "NOT a duplicate of turnover_rate. The possession engine suppresses the "
      "companion turnover PLL logs alongside an opponent's goal, so possession-"
      "ending turnovers (1,352) are fewer than turnover events (1,721) and fewer "
      "than official turnovers (1,699). This is the version that can be subset by "
      "possession, and is therefore the one the sensitivity analysis uses.",
      "FALSE", "CONTEXTUAL", "phase_5",
      "Systematically lower than turnover_rate. Do not quote the two "
      "interchangeably.", redundancy="RELATED_BUT_DISTINCT"),

    # ================= SHOOTING =================
    M("shots", "Shots", TS, "shooting", "count", "shot attempts", "not_applicable",
      "count(shot and goal events with a shot_outcome)", PBP,
      "Attempt volume.", "neither", "CORE", "phase_5",
      "Play-by-play derived and verified EQUAL to the official box score in all "
      "100 team-games, so source choice is not a live question here.",
      official="reconstructed_reconciled"),
    M("shots_on_goal", "Shots on goal", TS, "shooting", "count",
      "shots with outcome goal, saved or on_goal_no_save", "not_applicable",
      "count(shots where shot_outcome in ('goal','saved','on_goal_no_save'))", PBP,
      "Attempts that reached the cage.", "neither", "CORE", "phase_5",
      "154 shots season-wide are on goal but neither saved nor a goal, which is "
      "why two save percentages exist.", official="reconstructed_reconciled"),
    M("goals", "Goals", TS, "shooting", "count", "valid goals", "not_applicable",
      "count(shots where is_valid_goal)", PBP,
      "GOALS, not points. A two-point goal counts once here.",
      "TRUE", "CORE", "phase_5",
      "Never use goals as a scoring total in the PLL -- that discards 12.1% of "
      "league scoring.", official="reconstructed_reconciled"),
    M("points", "Points (shooting table)", TS, "shooting", "count",
      "one-point goals + 2 x two-point goals", "not_applicable",
      "one_point_goals + 2*two_point_goals", PBP,
      "PLL points from the shooting table. Identical to points_scored, derived "
      "from a different table, and asserted equal on every row.",
      "TRUE", "DIAGNOSTIC", "phase_5",
      "Kept as an independent cross-check on the possession-derived total, not "
      "as a second answer.", redundancy="IDENTICAL(points_scored)"),
    M("shooting_pct", "Shooting %", TS, "shooting", "percentage", "goals",
      "shot attempts", "goals / shots", PBP,
      "Finishing accuracy. DELIBERATELY NOT points per shot: a team that scores "
      "two two-point goals on two shots shot 100%, not 200%.",
      "TRUE", "CORE", "phase_5",
      "Ignores the extra point on a two-point goal by design. Read alongside "
      "points_per_shot, which does not.", official="reconstructed_reconciled",
      redundancy="RELATED_BUT_DISTINCT"),
    M("shots_on_goal_pct", "SOG %", TS, "shooting", "percentage", "shots on goal",
      "shot attempts", "shots_on_goal / shots", PBP,
      "Share of attempts that reached the cage.", "TRUE", "CORE", "phase_5",
      "Not a quality measure on its own: a team that only shoots from close range "
      "will have a high SOG% for reasons of shot selection this feed cannot see."),
    M("goals_per_shot_on_goal", "Goals per SOG", TS, "shooting", "percentage",
      "goals", "shots on goal", "goals / shots_on_goal", PBP,
      "Finishing rate against the keeper, net of misses. The offensive mirror of "
      "save_pct_vs_shots_on_goal.", "TRUE", "CORE", "phase_5",
      "Confounded with opposing goalkeeping. It is a joint outcome, not a pure "
      "shooting measure."),
    M("points_per_shot", "Points per shot", TS, "shooting", "points per attempt",
      "PLL points", "shot attempts", "points / shots", PBP,
      "The PLL-native shooting metric: it is the only one that credits two-point "
      "volume. League 2026: 0.290.", "TRUE", "CORE", "phase_5",
      "Diverges from shooting_pct exactly to the extent a team scores two-point "
      "goals. That divergence is the point of the metric, not a defect.",
      redundancy="RELATED_BUT_DISTINCT"),

    # ================= TWO-POINT =================
    M("one_point_attempts", "1PT attempts", TS, "two_point", "count",
      "shots with shot_type 1_PT or MU", "not_applicable",
      "count(shots where not is_two_point_attempt)", PBP,
      "Inside-the-arc volume.", "neither", "CORE", "phase_5",
      "Derived from the unambiguous shot_type tag; equals official "
      "shots - twoPointShots in all 100 team-games.",
      official="reconstructed_reconciled"),
    M("one_point_goals", "1PT goals", TS, "two_point", "count",
      "valid goals with shot_type 1_PT or MU", "not_applicable",
      "count(goals where not is_two_point_attempt)", PBP,
      "Inside-the-arc goals.", "TRUE", "CORE", "phase_5", "See one_point_attempts.",
      official="reconstructed_reconciled"),
    M("one_point_points", "1PT points", TS, "two_point", "count",
      "one-point goals", "not_applicable", "one_point_goals", PBP,
      "Points from inside the arc. Numerically equal to one_point_goals.",
      "TRUE", "CONTEXTUAL", "phase_5",
      "Equal to one_point_goals by construction; emitted so the "
      "one-point/two-point points decomposition is complete.",
      redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("one_point_conversion_pct", "1PT conversion %", TS, "two_point", "percentage",
      "one-point goals", "one-point attempts",
      "one_point_goals / one_point_attempts", PBP,
      "The comparison baseline for every two-point claim. League 2026: 29.3%.",
      "TRUE", "CORE", "phase_5",
      "Numerically identical to points_per_one_point_attempt, because a one-point "
      "goal is worth one point.", redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("two_point_attempts", "2PT attempts", TS, "two_point", "count",
      "shots with shot_type 2_PT or MU_2_PT", "not_applicable",
      "count(shots where is_two_point_attempt)", PBP,
      "Long-range volume. 536 league-wide in 2026.", "neither", "CORE", "phase_5",
      "Equals official twoPointShots in all 100 team-games.",
      official="reconstructed_reconciled"),
    M("two_point_shots_on_goal", "2PT shots on goal", TS, "two_point", "count",
      "two-point attempts reaching the cage", "not_applicable",
      "count(two-point shots where is_shot_on_goal)", PBP,
      "Long-range shots the keeper had to handle. The denominator of the goalie "
      "two-point baseline.", "neither", "CONTEXTUAL", "phase_5",
      "299 league-wide -- thin for any team-level split."),
    M("two_point_goals", "2PT goals", TS, "two_point", "count",
      "valid two-point goals", "not_applicable",
      "count(goals where is_two_point_attempt)", PBP,
      "Long-range goals. 72 league-wide in 2026 -- 3 to 14 per team.",
      "TRUE", "CORE", "phase_5", L_TWO_POINT_THIN,
      official="reconstructed_reconciled"),
    M("two_point_points", "2PT points", TS, "two_point", "count",
      "2 x two-point goals", "not_applicable", "2 * two_point_goals", PBP,
      "Points from behind the arc.", "TRUE", "CORE", "phase_5",
      "Exactly twice two_point_goals.", redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("two_point_conversion_pct", "2PT conversion %", TS, "two_point", "percentage",
      "two-point goals", "two-point attempts",
      "two_point_goals / two_point_attempts", PBP,
      "Long-range accuracy. League 2026: 13.4%.", "TRUE", "CONTEXTUAL", "phase_5",
      L_TWO_POINT_THIN + " Team values range 4.3% to 18.4% on 38-83 attempts; the "
      "binomial standard error on a 69-attempt team rate is about 4 percentage "
      "points, so most of that range is noise.",
      reliability="thin: 38-83 attempts per team", freeze="FREEZE_WITH_CAVEAT"),
    M("two_point_attempt_rate", "2PT attempt rate", TS, "two_point", "percentage",
      "two-point attempts", "shot attempts", "two_point_attempts / shots", PBP,
      "How committed a team is to the long shot. A STYLE measure, not a quality "
      "measure. League 2026: 13.1%.", "neither", "CORE", "phase_5",
      "Direction is deliberately 'neither': the 2026 evidence does not establish "
      "that taking more or fewer two-pointers is better."),
    M("two_point_points_share", "2PT points share", TS, "two_point", "percentage",
      "two-point points", "total points", "two_point_points / points", PBP,
      "How dependent a team's scoring is on the arc. League 2026: 12.1%.",
      "neither", "CORE", "phase_5",
      "A high share can mean a team shoots well from range OR that its inside "
      "offence is poor. It does not distinguish them."),
    M("points_per_two_point_attempt", "Points per 2PT attempt", TS, "two_point",
      "points per attempt", "2 x two-point goals", "two-point attempts",
      "2 * two_point_goals / two_point_attempts", PBP,
      "The expected return on a long shot, in the same units as "
      "points_per_one_point_attempt. League 2026: 0.269 against 0.293.",
      "TRUE", "CORE", "phase_5",
      L_TWO_POINT_THIN + " The league-level gap of -0.024 is INSIDE one standard "
      "error of the two-point return (0.030), so 2026 does not establish that the "
      "long shot returns less -- only that it does not clearly return more.",
      freeze="FREEZE_WITH_CAVEAT"),
    M("points_per_one_point_attempt", "Points per 1PT attempt", TS, "two_point",
      "points per attempt", "one-point goals", "one-point attempts",
      "one_point_points / one_point_attempts", PBP,
      "The inside-the-arc return, stated in matching units so the two-point "
      "comparison does not require the reader to know that conversion and return "
      "coincide inside the arc.", "TRUE", "CORE", "phase_8",
      "Numerically identical to one_point_conversion_pct.",
      redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("two_point_minus_one_point_return", "2PT return advantage", TS, "two_point",
      "points per attempt", "difference of the two returns", "not_applicable",
      "points_per_two_point_attempt - points_per_one_point_attempt", PBP,
      "The PLL question with no NCAA analogue: at THIS season's conversion rates, "
      "did the long shot pay? League 2026: -0.024.",
      "TRUE", "CONTEXTUAL", "phase_8",
      "NOT A SHOT-SELECTION FINDING. Shot events carry no location, distance or "
      "defender, so the counterfactual -- what this attempt would have returned "
      "from inside the arc -- is unobservable. Team values range -0.230 to +0.107 "
      "on standard errors of 0.05-0.10, i.e. the team-level spread is noise. "
      + L_TWO_POINT_THIN, freeze="FREEZE_WITH_CAVEAT"),
    M("possessions_with_two_point_attempt", "Possessions with a 2PT attempt", TS,
      "two_point", "count", "offensive possessions containing >=1 two-point attempt",
      "not_applicable", "count(distinct possessions with a two-point shot)", POSS,
      "Possession-level long-shot usage.", "neither", "CONTEXTUAL", "phase_5",
      L_POSS_SUBSET),
    M("two_point_possession_rate", "2PT possession rate", TS, "two_point",
      "percentage", "possessions with a two-point attempt", "offensive possessions",
      "possessions_with_two_point_attempt / offensive_possessions", POSS,
      "Share of possessions in which the team looked from range.",
      "neither", "CONTEXTUAL", "phase_5",
      L_POSS_SUBSET, redundancy="HIGHLY_OVERLAPPING"),

    # ================= FACEOFF =================
    M("faceoffs", "Faceoffs", TS, "faceoff", "count", "official faceoffs taken",
      "not_applicable", "sum(team_game_stats.faceoffs)", OFF,
      "Draw volume. The official denominator includes NO-DECISION draws "
      "(violations and redraws), which is why faceoffsWon + faceoffsLost falls "
      "1-2 short of faceoffs in 8 games.", "neither", "CORE", "phase_5",
      "Using wins+losses as the denominator instead would silently drop the "
      "no-decision draws and inflate every win percentage.", official="official"),
    M("faceoff_wins", "Faceoff wins", TS, "faceoff", "count",
      "official faceoffs won", "not_applicable", "sum(faceoffsWon)", OFF,
      "Draws won.", "TRUE", "CORE", "phase_5",
      "Official chosen over play-by-play: the two agree in 99 of 100 team-games "
      "and the official denominator is the cleaner one.", official="official"),
    M("faceoff_losses", "Faceoff losses", TS, "faceoff", "count",
      "official faceoffs lost", "not_applicable", "sum(faceoffsLost)", OFF,
      "Draws lost.", "FALSE", "CORE", "phase_5", "See faceoffs.", official="official"),
    M("faceoff_win_pct", "Faceoff win %", TS, "faceoff", "percentage",
      "faceoff wins", "faceoffs (including no-decision draws)",
      "faceoff_wins / faceoffs", OFF,
      "The most reliably measured team rate in this system: 2,618 league draws, "
      "and the analogous player rate is the only one with strong individual "
      "identification.", "TRUE", "CORE", "phase_5",
      "League mean is 0.4966 rather than 0.5000 because 18 draws had no recorded "
      "winner. " + L_NOT_OPP_ADJ, official="official",
      reliability="strong: 300-400 draws per team"),

    # ================= TURNOVERS / GROUND BALLS =================
    M("turnovers", "Turnovers", TS, "turnovers", "count", "official turnovers",
      "not_applicable", "sum(team_game_stats.turnovers)", OFF,
      "Possessions given away.", "FALSE", "CORE", "phase_5", L_OFFICIAL_TO,
      official="official"),
    M("possession_ending_turnovers", "Possession-ending turnovers", TS, "turnovers",
      "count", "possessions whose end_reason is turnover", "not_applicable",
      "count(possessions where end_reason='turnover')", POSS,
      "The subsettable turnover count. 1,352 league-wide against 1,699 official.",
      "FALSE", "DIAGNOSTIC", "phase_5",
      "Deliberately NOT the published turnover count; it exists so a turnover rate "
      "can be recomputed on a possession subset with numerator and denominator "
      "from the same subset.", redundancy="RELATED_BUT_DISTINCT"),
    M("turnovers_forced", "Turnovers forced", TS, "turnovers", "count",
      "opponent turnovers", "not_applicable", "sum(opponent turnovers)", OFF,
      "Turnovers the opposition committed. A JOINT outcome of defence and "
      "opponent ball security.", "TRUE", "CONTEXTUAL", "phase_5",
      "Not a pure defensive measure: it credits a defence for an opponent's own "
      "unforced errors.", official="official"),
    M("turnovers_forced_per_defensive_possession", "Turnovers forced/possession",
      TS, "turnovers", "rate", "opponent turnovers", "defensive possessions",
      "turnovers_forced / defensive_possessions", OFF,
      "Defensive takeaway rate.", "TRUE", "CONTEXTUAL", "phase_5",
      "See turnovers_forced. " + L_POSS_SUBSET, official="official"),
    M("caused_turnovers_official", "Caused turnovers", TS, "turnovers", "count",
      "official caused turnovers", "not_applicable", "sum(causedTurnovers)", OFF,
      "The one countable defensive act in this feed. 741 league-wide.",
      "TRUE", "CORE", "phase_5",
      "OFFICIAL-ONLY AND ALWAYS WILL BE: the event-level causedTurnoverId field is "
      "structurally null in every event of the season, so a caused turnover can "
      "never be tied to a possession or a moment.", official="official"),
    M("ground_balls", "Ground balls", TS, "ground_balls", "count",
      "official ground balls", "not_applicable", "sum(groundBalls)", OFF,
      "Loose-ball recoveries.", "TRUE", "CORE", "phase_5", L_OFFICIAL_GB,
      official="official"),
    M("ground_balls_per_possession", "Ground balls per possession", TS,
      "ground_balls", "rate", "official ground balls",
      "offensive PLUS defensive possessions",
      "ground_balls / total_game_possessions", OFF,
      "Recovery rate. The denominator is BOTH sides of the ball, because ground "
      "balls are recovered on both -- dividing by offensive possessions alone "
      "would misattribute the rate.", "TRUE", "CORE", "phase_5",
      L_OFFICIAL_GB + " No offensive-ground-ball or contested-ground-ball "
      "percentage is computed: the feed supplies no such denominator.",
      official="official"),

    # ================= GOALKEEPING / TEAM DEFENCE =================
    M("shots_allowed", "Shots allowed", TS, "team_defense", "count",
      "opponent shot attempts", "not_applicable", "count(opponent shots)", PBP,
      "Attempt volume conceded.", "FALSE", "CORE", "phase_5",
      "Volume, not quality -- a team that concedes many long shots looks worse "
      "here and may not be.", official="reconstructed_reconciled"),
    M("shots_on_goal_allowed", "Shots on goal allowed", TS, "team_defense", "count",
      "opponent shots on goal", "not_applicable", "count(opponent shots on goal)",
      PBP, "What the keeper actually faced.", "FALSE", "CORE", "phase_5",
      "Matches official exactly.", official="reconstructed_reconciled"),
    M("goals_allowed", "Goals allowed", TS, "team_defense", "count",
      "official goals against", "not_applicable", "sum(goalsAgainst)", OFF,
      "Goals conceded (not points).", "FALSE", "CORE", "phase_5",
      "GOALS, not points: a two-point goal against counts once here and twice in "
      "points_allowed.", official="official"),
    M("two_point_goals_allowed", "2PT goals allowed", TS, "team_defense", "count",
      "official two-point goals against", "not_applicable",
      "sum(twoPointGoalsAgainst)", OFF,
      "Long-range goals conceded. 3-12 per team.", "FALSE", "CONTEXTUAL", "phase_5",
      L_TWO_POINT_THIN, official="official"),
    M("two_point_attempts_allowed", "2PT attempts allowed", TS, "team_defense",
      "count", "opponent two-point attempts", "not_applicable",
      "count(opponent two-point shots)", PBP,
      "How often a defence conceded the long look.", "FALSE", "CONTEXTUAL",
      "phase_5", "Whether conceding long shots is good or bad is exactly the "
      "question the 2026 two-point evidence cannot settle.",
      official="reconstructed_reconciled"),
    M("saves", "Saves", TS, "team_defense", "count", "official saves",
      "not_applicable", "sum(saves)", OFF, "Saves made.", "TRUE", "CORE", "phase_5",
      "Official chosen: play-by-play agrees in 99 of 100 team-games (the known "
      "2026-ev-8 residual).", official="official"),
    M("save_pct_official", "Save % (official)", TS, "team_defense", "percentage",
      "saves", "saves + goals allowed", "saves / (saves + goals_allowed)", OFF,
      "PLL's own save-percentage definition.", "TRUE", "CORE", "phase_5",
      "Its denominator EXCLUDES the 154 season shots that were on goal but "
      "neither saved nor a goal, which is why it differs from "
      "save_pct_vs_shots_on_goal. Neither replaces the other.",
      official="official", redundancy="RELATED_BUT_DISTINCT"),
    M("save_pct_vs_shots_on_goal", "Save % vs SOG", TS, "team_defense", "percentage",
      "saves", "opponent shots on goal", "saves / shots_on_goal_allowed",
      OFF + " + " + PBP,
      "Saves per shot the keeper actually faced.", "TRUE", "CORE", "phase_5",
      "Systematically lower than save_pct_official by construction.",
      redundancy="RELATED_BUT_DISTINCT"),
    M("opponent_shooting_pct", "Opponent shooting %", TS, "team_defense",
      "percentage", "opponent goals", "opponent shot attempts",
      "goals_allowed / shots_allowed", PBP,
      "The defensive mirror of shooting_pct.", "FALSE", "CORE", "phase_5",
      "A joint outcome of defence, goalkeeping and opponent finishing. It does "
      "not separate them, and this feed cannot."),
    M("opponent_shooting_pct_on_goal", "Opponent goals per SOG", TS, "team_defense",
      "percentage", "opponent goals", "opponent shots on goal",
      "goals_allowed / shots_on_goal_allowed", PBP,
      "Conversion rate conceded once the shot reached the cage.",
      "FALSE", "CORE", "phase_5",
      "Complement of save_pct_vs_shots_on_goal up to the on_goal_no_save shots.",
      redundancy="HIGHLY_OVERLAPPING"),
    M("shots_allowed_per_possession", "Shots allowed per possession", TS,
      "team_defense", "rate", "opponent shot attempts", "defensive possessions",
      "shots_allowed / defensive_possessions", PBP,
      "Shot suppression, pace-corrected.", "FALSE", "CORE", "phase_5",
      L_POSS_SUBSET),

    # ================= DISCIPLINE / SHOT CLOCK =================
    M("penalties", "Penalties", TS, "discipline", "count", "official penalties",
      "not_applicable", "sum(numPenalties)", OFF, "Penalties committed.",
      "FALSE", "CORE", "phase_5",
      "6 team-game rows carry an unresolved penalty validation residual.",
      official="official"),
    M("penalty_minutes", "Penalty minutes", TS, "discipline", "count",
      "official penalty minutes", "not_applicable", "sum(pim)", OFF,
      "Time conceded to penalties.", "FALSE", "CONTEXTUAL", "phase_5",
      "Not converted into a man-down possession count anywhere -- see "
      "man_up_possessions (UNSUPPORTED).", official="official"),
    M("shot_clock_expirations", "Shot-clock expirations", TS, "discipline", "count",
      "official shot-clock expirations", "not_applicable",
      "sum(shot clock violations)", OFF,
      "Possessions ended by the clock.", "FALSE", "CORE", "phase_5",
      "10 team-game rows carry an unresolved residual.", official="official"),
    M("shot_clock_expiration_rate", "Shot-clock expiration rate", TS, "discipline",
      "rate", "shot-clock expirations", "offensive possessions",
      "shot_clock_expirations / offensive_possessions", OFF,
      "How often a team failed to get a shot away.", "FALSE", "CORE", "phase_5",
      L_POSS_SUBSET, official="official"),

    # ================= EXTRA MAN =================
    M("man_up_opportunities", "Extra-man opportunities", TS, "extra_man", "count",
      "official timesManUp", "not_applicable", "sum(timesManUp)", OFF,
      "The only defensible extra-man denominator in this feed.",
      "neither", "CORE", "phase_5", L_MANUP, official="official"),
    M("man_up_shots", "Extra-man shots", TS, "extra_man", "count",
      "official powerPlayShots", "not_applicable", "sum(powerPlayShots)", OFF,
      "Man-up shot volume, from the OFFICIAL box score.", "neither", "CORE",
      "phase_5", L_MANUP + " Official powerPlayShots exceeds the play-by-play "
      "tagged count in 70 of 100 team-games, which is how the tag was identified "
      "as goals-only.", official="official"),
    M("man_up_goals", "Extra-man goals", TS, "extra_man", "count",
      "official powerPlayGoals", "not_applicable", "sum(powerPlayGoals)", OFF,
      "Man-up goals.", "TRUE", "CORE", "phase_5", L_MANUP, official="official"),
    M("man_up_points", "Extra-man points", TS, "extra_man", "count",
      "PLL points from tagged man-up goals", "not_applicable",
      "sum(points on MU / MU_2_PT goal events)", PBP,
      "Man-up POINTS come from the play-by-play tag, because only it "
      "distinguishes a one-point from a two-point man-up goal.",
      "TRUE", "CONTEXTUAL", "phase_5",
      L_MANUP + " The tagged goal count matches official powerPlayGoals in 97 of "
      "100 team-games; the residual is exposed as "
      "man_up_goals_pbp_minus_official.", freeze="FREEZE_WITH_CAVEAT"),
    M("man_up_shooting_pct", "Extra-man shooting %", TS, "extra_man", "percentage",
      "official powerPlayGoals", "official powerPlayShots",
      "man_up_goals / man_up_shots", OFF,
      "Official over official.", "TRUE", "CONTEXTUAL", "phase_5",
      L_MANUP + " Denominators are 15-47 shots per team -- far too thin to "
      "separate teams. Publish with the denominator visible or not at all.",
      official="official", reliability="thin: 15-47 attempts per team",
      freeze="FREEZE_WITH_CAVEAT"),
    M("man_up_goals_per_opportunity", "Extra-man goals per opportunity", TS,
      "extra_man", "rate", "man-up goals", "extra-man opportunities",
      "man_up_goals / man_up_opportunities", OFF,
      "Conversion of the extra-man situation.", "TRUE", "CORE", "phase_5",
      L_MANUP + " 22-41 opportunities per team.", official="official",
      reliability="thin: 22-41 opportunities per team",
      freeze="FREEZE_WITH_CAVEAT"),
    M("man_up_points_per_opportunity", "Extra-man points per opportunity", TS,
      "extra_man", "rate", "man-up points", "extra-man opportunities",
      "man_up_points / man_up_opportunities", OFF + " + " + PBP,
      "The PLL-correct extra-man conversion metric: it counts the second point on "
      "a two-point man-up goal, which the goals version cannot.",
      "TRUE", "CORE", "phase_5", L_MANUP,
      reliability="thin: 22-41 opportunities per team",
      freeze="FREEZE_WITH_CAVEAT"),
    M("man_up_shots_per_opportunity", "Extra-man shots per opportunity", TS,
      "extra_man", "rate", "official powerPlayShots", "extra-man opportunities",
      "man_up_shots / man_up_opportunities", OFF,
      "How much shot volume a team generates with the extra man.",
      "TRUE", "CONTEXTUAL", "phase_5", L_MANUP, official="official",
      freeze="FREEZE_WITH_CAVEAT"),
    M("man_down_opportunities", "Man-down opportunities", TS, "extra_man", "count",
      "official timesShortHanded", "not_applicable", "sum(timesShortHanded)", OFF,
      "Times short-handed.", "FALSE", "CORE", "phase_5", L_MANUP, official="official"),
    M("man_down_goals_allowed", "Man-down goals allowed", TS, "extra_man", "count",
      "official man-down goals against", "not_applicable",
      "sum(man-down goals against)", OFF, "Goals conceded short-handed.",
      "FALSE", "CORE", "phase_5", L_MANUP, official="official"),
    M("man_down_goals_allowed_per_opportunity", "Man-down goals allowed per "
      "opportunity", TS, "extra_man", "rate", "man-down goals allowed",
      "man-down opportunities",
      "man_down_goals_allowed / man_down_opportunities", OFF,
      "Penalty-kill concession rate.", "FALSE", "CONTEXTUAL", "phase_5",
      L_MANUP + " 18-46 opportunities per team.", official="official",
      reliability="thin: 18-46 opportunities per team",
      freeze="FREEZE_WITH_CAVEAT"),

    # ================= CLEARING / RIDING: raw counts only =================
    M("clears", "Clears", TS, "clearing", "count", "official successful clears",
      "not_applicable", "sum(clears)", OFF,
      "Raw count only. NO clearing efficiency is published -- see "
      "clearing_efficiency (DEFERRED).", "TRUE", "CONTEXTUAL", "phase_5",
      "Passed through untouched. The feed logs no clear EVENT, so a clear cannot "
      "be tied to a possession boundary.", official="official"),
    M("clear_attempts", "Clear attempts", TS, "clearing", "count",
      "official clear attempts", "not_applicable", "sum(clearAttempts)", OFF,
      "Raw count only.", "neither", "CONTEXTUAL", "phase_5", "See clears.",
      official="official"),
    M("ride_attempts", "Ride attempts", TS, "clearing", "count",
      "official ride attempts", "not_applicable", "sum(rideAttempts)", OFF,
      "Raw count only. NO riding efficiency is published.", "neither",
      "CONTEXTUAL", "phase_5",
      "The feed gives no ride SUCCESS count, so a ride percentage cannot be "
      "formed at all -- not merely 'is unreliable'.", official="official"),

    # ================= TIME OF POSSESSION =================
    M("time_of_possession_official_seconds", "Time of possession (official)", TS,
      "time", "seconds", "PLL's own timeInPossesion", "not_applicable",
      "sum(team_game_stats.timeInPossesion)", OFF,
      "THE authoritative time-of-possession column. No reconstructed alternative "
      "is published anywhere in this project.", "neither", "CORE", "phase_5",
      "Official and unverifiable against the event log -- the log has no "
      "comparable quantity. " + L_SPAN_NOT_TOP, official="official"),
    M("time_of_possession_official_seconds_per_game", "ToP per game (official)", TS,
      "time", "seconds per game", "official time of possession", "games played",
      "time_of_possession_official_seconds / games_played", OFF,
      "Per-game official ToP.", "neither", "CONTEXTUAL", "phase_5",
      "See time_of_possession_official_seconds.", official="official"),
    M("possession_span_coverage_ratio", "Possession span coverage", TS, "time",
      "ratio", "sum of reconstructed possession spans", "official ToP",
      "observed_possession_seconds / time_of_possession_official_seconds",
      POSS + " + " + OFF,
      "A PURE DIAGNOSTIC: how much of the official figure the reconstructed spans "
      "recover. Published so the gap is visible per row rather than described "
      "once in a document.", "neither", "DIAGNOSTIC", "phase_5", L_SPAN_NOT_TOP),

    # ================= UNCERTAINTY COLUMNS =================
    M("ambiguous_offensive_possessions", "Ambiguous offensive possessions", TS,
      "uncertainty", "count", "offensive possessions flagged is_ambiguous",
      "not_applicable", "count(possessions where is_ambiguous)", POSS,
      "Possessions whose BOUNDARY MECHANISM the engine could not confirm. The "
      "team that had the ball is still known with certainty.",
      "FALSE", "DIAGNOSTIC", "phase_5",
      "52.7% of ambiguous possessions end in ambiguous_control_change, which "
      "structurally cannot have ended in a goal -- so excluding them "
      "preferentially discards non-scoring possessions and RAISES measured "
      "efficiency. That is a selection effect, not a correction."),
    M("ambiguous_offensive_possession_share", "Ambiguous possession share", TS,
      "uncertainty", "percentage", "ambiguous offensive possessions",
      "offensive possessions",
      "ambiguous_offensive_possessions / offensive_possessions", POSS,
      "Per-team exposure to possession-boundary ambiguity.",
      "FALSE", "DIAGNOSTIC", "phase_5", "See ambiguous_offensive_possessions."),
    M("truncated_possessions", "Truncated possessions", TS, "uncertainty", "count",
      "possessions cut by a period or game boundary", "not_applicable",
      "count(possessions where is_truncated)", POSS,
      "Possessions whose span is bounded by the clock rather than by play.",
      "FALSE", "DIAGNOSTIC", "phase_5", "Excluded from the possession-length splits."),
    M("complete_possessions", "Complete possessions", TS, "uncertainty", "count",
      "possessions not truncated", "not_applicable",
      "count(possessions where not is_truncated)", POSS,
      "Complement of truncated_possessions.", "neither", "DIAGNOSTIC", "phase_5",
      "Complement by construction.", redundancy="ALGEBRAICALLY_REDUNDANT"),
    M("measurable_span_possessions", "Measurable-span possessions", TS,
      "uncertainty", "count",
      "possessions that are unambiguous, untruncated and have >1 event",
      "not_applicable",
      "count(possessions where is_measurable_span)", POSS,
      "The eligibility base for the possession-length splits: 2,096 of 4,388 "
      "(47.8%).", "neither", "DIAGNOSTIC", "phase_5",
      "871 possessions season-wide are opened and closed by the SAME single "
      "event, so their span is 0 by construction -- an absence of measurement, "
      "not a fast possession."),
    M("games_with_unresolved_validation_issue", "Games with an unresolved "
      "validation issue", TS, "uncertainty", "count",
      "eligible games carrying any unresolved Phase 4.25 residual",
      "not_applicable", "count(games with has_unresolved_validation_issue)",
      "validation_report.csv", "Per-team exposure to the 42 unresolved "
      "season-wide validation residuals.", "FALSE", "DIAGNOSTIC", "phase_5",
      "68 of 100 team-game rows carry at least one. Almost all are +/-1 in "
      "turnovers or ground balls; season aggregates move by well under 1%."),
]
