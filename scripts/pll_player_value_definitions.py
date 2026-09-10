"""
Phase 6: machine-readable provenance for every player-value metric.

Single source of truth for
data/processed/2026/player_value_metric_definitions.csv. A reader who has never
seen this repository should be able to reconstruct exactly what any published
number means from this table alone.
"""

DEFINITION_COLUMNS = [
    "metric_name", "definition", "unit", "numerator", "denominator", "baseline",
    "source_table", "source_columns", "model_type", "eligibility",
    "uncertainty_method", "known_limitations", "status",
]

ELIG = ("league-analytics-eligible completed games only (50 games); all-star game and "
        "all-star squads excluded; events filtered on is_analysis_eligible_event")
UNIT = "EPA_points (PLL points above league-average expected opportunity outcome)"
NA = "not_applicable"

OPP_SRC = "player_game_stats.csv"
EVT_SRC = "events.csv"


def _d(name, definition, unit, num, den, baseline, src, cols, model, unc, lim, status):
    return dict(zip(DEFINITION_COLUMNS, [
        name, definition, unit, num, den, baseline, src, cols, model, ELIG, unc, lim, status,
    ]))


DEFINITIONS = [
    # ------------------------------------------------------------------ unit
    _d("EPA_points",
       "Expected PLL Points Added. For each component: what the player produced on his own "
       "recorded opportunities, minus what a league-average player would have produced on the "
       "same opportunities. +3.2 means roughly 3.2 PLL points more than league-average outcomes "
       "on those opportunities.",
       UNIT, "observed outcome", "the player's own recorded opportunities",
       "league-average expected opportunity outcome", "derived", NA, "residual",
       "component-specific; see each row",
       "Not above replacement -- replacement level is not estimated anywhere in Phase 6. Not "
       "opponent-adjusted. Not a measure of playing time.",
       "production"),

    # -------------------------------------------------------------- shooting
    _d("shooting_value",
       "PLL points from shots minus the league-average expected points for the same shot "
       "attempts, split by shot class.",
       UNIT,
       "one_point_goals + 2*two_point_goals",
       "one_point_attempts and two_point_attempts (valued at their league rates)",
       "0.29300 points per one-point attempt; 0.26866 per two-point attempt",
       f"{OPP_SRC} + {EVT_SRC}",
       "onePointGoals, twoPointGoals, shots, twoPointShots",
       "empirical two-class conversion rate (logistic alternative fitted and rejected on "
       "cross-validated Brier score)",
       "binomial standard error on each baseline; bootstrap intervals on player totals",
       "Values finishing only, never shot creation or possession. No shot location, distance or "
       "defender data exists in the feed, so no shot-quality adjustment is possible. Sums to "
       "exactly zero across the league by construction.",
       "production"),
    _d("shooting_value_one_point",
       "The part of shooting_value earned on shots from inside the two-point arc.",
       UNIT, "one_point_goals", "one_point_attempts",
       "0.29300 points per one-point attempt", OPP_SRC, "onePointGoals, shots, twoPointShots",
       "empirical rate", "binomial", "See shooting_value.", "production"),
    _d("shooting_value_two_point",
       "The part of shooting_value earned from behind the two-point arc. Expected value uses "
       "P(goal) x 2, not P(goal): a two-point goal is one goal worth two points.",
       UNIT, "2 * two_point_goals", "two_point_attempts",
       "0.26866 points per two-point attempt (0.13433 conversion x 2)", OPP_SRC,
       "twoPointGoals, twoPointShots", "empirical rate", "binomial",
       "536 league two-point attempts total, so individual two-point rates are extremely noisy; "
       "see player_value_shrinkage.csv.", "production"),
    _d("shooting_value_per_shot",
       "shooting_value divided by shot attempts -- finishing efficiency, separated from volume.",
       "EPA_points per shot", "shooting_value", "shots",
       "0 (a league-average finisher)", "derived", "shooting_value, shots", "residual rate",
       "bootstrap", "Unstable below roughly 30 attempts; sample size is published alongside.",
       "production"),

    # -------------------------------------------------------------- turnover
    _d("turnover_value",
       "Negative value of turnovers committed above the number an average player of the same "
       "position group would commit on the same number of touches.",
       UNIT, "-(turnovers - expected_turnovers) x 0.20047",
       "touches (as the exposure measure)",
       "position-group turnovers per touch (offensive_field 0.0531, defensive_field 0.0490, "
       "faceoff 0.1085, goalie 0.0269)",
       OPP_SRC, "turnovers, touches, position",
       "residual against a position-group rate; coefficient from the forward-window event model",
       "bootstrap on the coefficient; binomial on the rate",
       "Player-attributed turnovers total 1,369 against an official team total of 1,699 -- about "
       "19% of league turnovers are credited to no player, because the feed's turnover "
       "descriptions name only a team. Every player's turnover load is therefore understated. "
       "Touches reconcile to team totals within 1.2%.",
       "production"),
    _d("points_per_turnover",
       "Empirical cost of one turnover: the net PLL points swing associated with a turnover over "
       "the following 60 seconds of play, net of the neutral reference.",
       "PLL points", "points for minus points against in the next 60s",
       "1,721 turnover events", "neutral reference +0.01512 (same statistic over all "
       "team-attributed events)", EVT_SRC, "event_type, seconds_passed, period, team_id",
       "forward-window empirical event value (the method Lacrosse Reference documents)",
       "bootstrap, 2000 resamples", "Not a causal estimate. A 60-second window is a convention "
       "inherited from the reference methodology, not an optimised choice; the sensitivity "
       "analysis re-runs the framework on alternative turnover costs.",
       "production"),

    # --------------------------------------------------------------- faceoff
    _d("faceoff_value",
       "Value of faceoff wins above the number expected from the league win probability.",
       UNIT, "(faceoff_wins - faceoffs x 0.49656) x 0.34643", "faceoffs taken",
       "empirical league faceoff win probability = 1300/2618 = 0.49656 (not exactly 0.5: 18 draws have no recorded winner)",
       OPP_SRC, "faceoffsWon, faceoffs",
       "residual against a structural baseline; coefficient from the forward-window event model",
       "bootstrap on the coefficient", "The counterfactual is a league-average faceoff man, not "
       "an absent one: a 50% specialist scores exactly zero. No opponent adjustment, so a player "
       "who happened to face weaker opposing specialists is not discounted. NULL for players who "
       "took no faceoffs.", "production"),
    _d("points_per_marginal_faceoff_win",
       "Value of converting one faceoff loss into one win: twice the empirical event value of a "
       "faceoff, because the same draw either gives the value to you or to the opponent.",
       "PLL points", "2 x 0.17322", "one marginal faceoff win",
       "neutral reference-adjusted faceoff event value", EVT_SRC,
       "event_type, seconds_passed, period, team_id", "forward-window empirical event value",
       "bootstrap, 2000 resamples",
       "A possession-based alternative (2 x the 0.24520 points a faceoff-started possession is "
       "worth = 0.49040) is roughly 42% larger; both are run in player_value_sensitivity.csv.",
       "production"),

    # ------------------------------------------------------------- defensive
    _d("caused_turnover_value",
       "PARTIAL defensive value: caused turnovers above the position group's per-game average.",
       UNIT, "(caused_turnovers - games_played x group rate) x 0.20047", "games played",
       "position-group caused turnovers per game", OPP_SRC, "causedTurnovers, position",
       "residual against a position-group per-game rate",
       "bootstrap on the coefficient",
       "PARTIAL AND NOT COMPREHENSIVE. Measures one countable defensive act. Positioning, "
       "matchup difficulty, forcing a bad shot instead of a turnover, sliding and communication "
       "leave no trace in this feed and are absent from this number. Games played is a crude "
       "exposure measure -- the feed has no minutes, shifts or lineups -- so a defender who plays "
       "every possession and one who rotates are treated identically.",
       "production_partial"),

    # ---------------------------------------------------------------- goalie
    _d("goalie_value",
       "PLL points prevented: expected points allowed on the shots on goal faced, minus points "
       "actually allowed. Positive is better.",
       UNIT, "expected_points_allowed - actual pll points allowed",
       "shots on goal faced, split one-point and two-point",
       "0.46120 points per one-point shot on goal; 0.48161 per two-point shot on goal",
       f"{OPP_SRC} + {EVT_SRC}",
       "saves, goalsAgainst, twoPointGoalsAgainst, scoresAgainst, goalie_id, shot_outcome",
       "empirical two-class conversion rate on shots on goal",
       "binomial on each baseline; bootstrap on player totals",
       "No shot-quality adjustment is possible: the feed has no shot location, distance or "
       "defender data, so a goalie behind a defence that concedes close-range shots is penalised "
       "for it. Goalies are valued only on shots ON GOAL, not attempts. The one-point/two-point "
       "split of shots faced is event-derived (official player stats do not carry it) and "
       "reconciles with official saves in 116/117 goalie-games. NULL for players who faced no "
       "shots on goal.",
       "production"),

    # ------------------------------------------------------- deferred / null
    _d("ground_ball_value", "DEFERRED. Not computed; NULL for every player.",
       UNIT, NA, NA, NA, OPP_SRC, "groundBalls", "not_built", NA,
       "Three independent reasons. (1) No opportunity denominator exists -- the feed records no "
       "'ground-ball chance' -- so the quantity cannot be expressed as a residual and is not "
       "commensurable with the other components. (2) The three contexts the feed can distinguish "
       "are not statistically separable at 2026 sample sizes: faceoff-scrum 0.163 [0.124, 0.201], "
       "possession-gaining 0.130 [0.098, 0.162], retained 0.082 [-0.040, 0.204] net points. "
       "(3) 1,095 of 3,091 ground balls immediately follow a faceoff; 99.7% go to the "
       "faceoff-winning team and 61.5% to the faceoff winner himself, so a per-ground-ball credit "
       "would pay the same player twice for one change of possession. The descriptive per-event "
       "value is preserved in ground_ball_event_value_descriptive.",
       "deferred"),
    _d("ground_ball_event_value_descriptive",
       "Descriptive only, OUTSIDE every total: ground balls x the empirical per-ground-ball event "
       "value. Preserved for a later phase; not part of total_player_value.",
       "PLL points (forward-window event value)", "ground_balls x 0.12402", "ground balls",
       "neutral reference-adjusted ground-ball event value", f"{OPP_SRC} + {EVT_SRC}",
       "groundBalls, event_type", "forward-window empirical event value", "bootstrap",
       "Not a residual and not comparable with the EPA_points components. Double-counts faceoff "
       "value for faceoff specialists -- that is precisely why it is excluded from the total.",
       "descriptive"),
    _d("assist_value", "DEFERRED. Not computed; NULL for every player.",
       UNIT, NA, NA, NA, OPP_SRC, "assists", "not_built", NA,
       "Official assists are reliable (560 season-wide, reconciling exactly with team totals in "
       "100/100 team-games) and are carried as a descriptive count, but they are not valued: the "
       "points from an assisted goal are already fully credited to the shooter through "
       "shooting_value, so an independent assist credit would create two players' worth of value "
       "from one goal. Splitting credit between shooter and assister is a defensible alternative "
       "that changes what shooting_value means, so the choice is left to the phase that needs it. "
       "The feed's shotAssistId is NOT used anywhere -- it is a pre-shot pass indicator, not a "
       "confirmed assist, and an unpopulated value is not a negative assertion.",
       "deferred"),
    _d("possession_participation_value", "NOT SUPPORTED. Never computed.",
       UNIT, NA, NA, NA, NA, NA, "not_built", NA,
       "Team possessions while a player was on the field cannot be computed: the PLL feed carries "
       "no lineup, substitution or on-field data of any kind. No metric in Phase 6 divides by "
       "possessions played, and no player receives value from a possession he cannot be tied to.",
       "unsupported"),

    # ----------------------------------------------------------- opportunity
    _d("touches", "Recorded offensive touches, official box score. The exposure measure for "
       "turnover_value.",
       "count", "touches", NA, NA, OPP_SRC, "touches", "raw", NA,
       "Player sums reconcile to team totals within 1.2% (26,228 vs 26,554 season-wide); only "
       "4/100 team-games match exactly. An individual recorded opportunity, NOT possessions "
       "played.", "production"),
    _d("play_shares",
       "Number of times a player appears anywhere in the eligible event log, in any role. The "
       "usage proxy Lacrosse Reference documents for usage-adjusted EGA.",
       "count", "appearances as shooter, ground-ball recoverer, goalie or secondary player",
       NA, NA, EVT_SRC, "player_id, gb_player_id, goalie_id, secondary_player_id", "raw", NA,
       "A usage proxy only. NOT possessions played and NOT playing time. Roles appear in the log "
       "at very different rates, so play shares are not comparable across positions.",
       "production"),
    _d("total_player_value",
       "Sum of the components that apply to the player: shooting + turnover + caused-turnover + "
       "faceoff + goalie value.",
       UNIT, "sum of supported components", NA,
       "league-average expected opportunity outcome", "derived",
       "shooting_value, turnover_value, caused_turnover_value, faceoff_value, goalie_value",
       "additive residual", "bootstrap on components",
       "A NULL component contributes nothing because the player had no opportunities of that "
       "class -- it is not treated as a zero score. Ground-ball and assist value are excluded "
       "entirely. This is a VALUE measure, not an MVP ranking: it is not adjusted for role, "
       "usage, opponent or team context, and no composite award model is built in Phase 6.",
       "production"),

    # ------------------------------------------------------------- shrinkage
    _d("shooting_pct_shrunk",
       "Empirical-Bayes (beta-binomial) shrunk shooting percentage, prior estimated from the "
       "league by method of moments.",
       "probability", "goals + prior alpha", "shots + prior alpha + prior beta",
       "league pooled shooting rate", "derived", "goals, shots", "empirical Bayes",
       "prior strength reported alongside as prior_strength_trials",
       "Published for comparison ONLY. Not substituted into any value component: shrinking a "
       "rate and then multiplying it by the player's own opportunity count would drag every "
       "player's total toward zero in proportion to his sample, which is a much stronger claim "
       "than shrinking the rate itself.",
       "diagnostic"),
]
