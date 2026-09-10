"""
Phase 13 Section B: the frozen model specification.

Written and run BEFORE any leaderboard, component table, or ranking is
generated (see docs/PLAYER_VALUE_MODEL_CHANGE_LOG for the discipline this
enforces). Every row cites the exact Phase 6-10 formula/column it reuses and
the Phase 12 evidence that classified it VIABLE/VIABLE_WITH_CAVEAT/ROLE_ONLY.

Phase 13 introduces NO new value formula. Every `formula` field below names
an already-published, already-validated Phase 6 SQL/Python computation
(sql/player_shooting_value.sql, sql/player_turnover_value.sql,
sql/player_faceoff_value.sql, sql/player_goalie_value.sql, and their
already-canonicalized 2022-2026 column, e.g. shooting_value_raw). The only
things genuinely new in Phase 13 are: (1) the rate/volume (or
rate/workload) decomposition for faceoff and goalie, which is an EXACT
algebraic identity on the existing published value (see
docs/OFFENSIVE_PLAYER_VALUE.md / FACEOFF_PLAYER_VALUE.md / GOALIE_PLAYER_VALUE.md
for the derivation), and (2) the bootstrap uncertainty and qualification
layers, neither of which changes any point estimate.

Output: data/processed/history/player_value_model_spec_v1.csv
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST = REPO_ROOT / "data" / "processed" / "history"

SPEC_COLUMNS = [
    "model_name", "role", "component", "target_concept", "unit", "formula",
    "numerator", "denominator", "baseline", "baseline_scope",
    "opportunity_measure", "shrinkage_used", "career_information_used",
    "minimum_sample_rule", "uncertainty_method", "additive",
    "publication_status", "known_limitations", "phase12_evidence_reference",
]


def _row(**kw):
    missing = set(SPEC_COLUMNS) - set(kw)
    if missing:
        raise ValueError(f"row missing columns: {missing}")
    return {c: kw[c] for c in SPEC_COLUMNS}


def build_spec() -> pd.DataFrame:
    rows = []

    # ================= OFFENSE =================
    rows.append(_row(
        model_name="offensive_value_v1", role="attack, midfield",
        component="shooting_value",
        target_concept="observed season production above a league-average shooter on the same shots",
        unit="PLL points",
        formula="shooting_value_raw = observed points from shots (1*one_point_goals + 2*two_point_goals) "
                "- league-expected points on the same shot mix (Phase 6 sql/player_shooting_value.sql, "
                "reused verbatim, never re-estimated)",
        numerator="observed PLL points from made shots",
        denominator="shot attempts (one_point_attempts + two_point_attempts)",
        baseline="league-average conversion rate per shot class (1PT, 2PT), estimated once per season by Phase 6/8/9",
        baseline_scope="season (Phase 6/8's own per-season estimate, reused unchanged across the 2022-2026 canonical rebuild)",
        opportunity_measure="shots",
        shrinkage_used="NO for the value itself (SHRINKAGE_POLICY.md sec 1: shrinking a rate and "
                       "multiplying by the player's own opportunity count is a stronger, unjustified claim)",
        career_information_used="NO for the value; the career-shrunk rate is displayed separately as "
                                 "context only, never blended in (see Section D discipline)",
        minimum_sample_rule="none for descriptive inclusion; QUALIFIED requires role_rate_reliability>=0.5 "
                             "AND future_award_input_eligible (both already published, reused unchanged)",
        uncertainty_method="parametric binomial bootstrap (1,000 draws, seed 20261013): "
                            "one_point_goals~Binomial(one_point_attempts, observed rate), "
                            "two_point_goals~Binomial(two_point_attempts, observed rate), "
                            "shooting_value_sim recomputed holding the published expected-points baseline fixed",
        additive="TRUE -- sums with turnover_value into offensive_value; player sums reconcile to team sums (Section M)",
        publication_status="VIABLE",
        known_limitations="finishing only, not creation; assists not independently valued (would double-count "
                           "the same goal, PLAYER_VALUE_ACCOUNTING.md sec 4H); two-point CONVERSION ability is "
                           "UNSUPPORTED at every scope (two-point SELECTION is not, and is reported separately, Section E)",
        phase12_evidence_reference="docs/OFFENSIVE_VALUE_RESEARCH.md; player_value_model_candidates.csv row MF3_offense_above_baseline (VIABLE)",
    ))
    rows.append(_row(
        model_name="offensive_value_v1", role="attack, midfield",
        component="turnover_value",
        target_concept="observed season ball-security production above the position group's per-touch turnover rate",
        unit="PLL points",
        formula="turnover_value_raw = -(observed turnover cost above the position-group per-touch rate) "
                "(Phase 6 sql/player_turnover_value.sql, reused verbatim)",
        numerator="turnovers committed",
        denominator="offensive touches",
        baseline="position-group turnovers-per-touch rate",
        baseline_scope="position (pooled across seasons, positional_baselines.csv recommendation)",
        opportunity_measure="touches",
        shrinkage_used="NO (same reasoning as shooting_value)",
        career_information_used="NO for the value; displayed as context only",
        minimum_sample_rule="none for descriptive inclusion; QUALIFIED requires career "
                             "turnovers_per_touch reliability>=0.5 (career_ability_reliability.csv) "
                             "displayed as context -- season-level turnover reliability is not separately "
                             "published by Phase 6-10, so the season component is always shown with the "
                             "sample-size caveat rather than a season-specific reliability gate",
        uncertainty_method="NOT independently bootstrapped in v1 -- held fixed at its published observed value "
                            "in the offensive bootstrap (stated limitation, docs/PLAYER_VALUE_UNCERTAINTY.md); "
                            "~19% of league turnovers name only a team (PLAYER_VALUE_ACCOUNTING.md sec 7), which "
                            "would bias any per-player resampling of turnover COUNT beyond ordinary sampling noise",
        additive="TRUE -- sums with shooting_value into offensive_value",
        publication_status="VIABLE",
        known_limitations="~19% of league turnovers are attributed to a team only, not a player -- every "
                           "player's turnover load is understated in absolute terms; the RATIO stays internally "
                           "consistent, the LEVEL does not",
        phase12_evidence_reference="docs/OFFENSIVE_VALUE_RESEARCH.md; player_value_model_candidates.csv row MF3_offense_above_baseline (VIABLE)",
    ))
    for comp, desc in [
        ("two_point_production", "what actually happened: two_point_goals, two_point_attempts, the PLL points they generated"),
        ("two_point_selection", "two_point_attempt_share -- the identifiable individual TENDENCY to take two-point shots"),
    ]:
        rows.append(_row(
            model_name="offensive_value_v1", role="attack, midfield", component=comp,
            target_concept="descriptive production" if comp == "two_point_production" else "identifiable individual selection tendency (NOT conversion skill)",
            unit="counts (goals, attempts, points)" if comp == "two_point_production" else "share (0-1)",
            formula="two_point_goals, two_point_attempts (box score, reconciles exactly to official scoring)"
                    if comp == "two_point_production" else
                    "two_point_attempt_share = two_point_attempts / shots, career-pooled empirical-Bayes shrunk "
                    "(career_ability_reliability.csv row two_point_attempt_share, kappa=2.99 attempts)",
            numerator="two_point_goals" if comp == "two_point_production" else "two_point_attempts",
            denominator="n/a (a count)" if comp == "two_point_production" else "shots",
            baseline="none -- descriptive" if comp == "two_point_production" else "league mean two-point attempt share",
            baseline_scope="n/a" if comp == "two_point_production" else "career (pooled 2022-2026)",
            opportunity_measure="shots" if comp == "two_point_production" else "shots",
            shrinkage_used="NO" if comp == "two_point_production" else "YES -- empirical-Bayes, career scope only, "
                           "displayed as context, never entering the season value component",
            career_information_used="NO" if comp == "two_point_production" else "YES, for the shrunk selection "
                                     "estimate only -- never for a conversion/ability claim",
            minimum_sample_rule="none -- always shown", uncertainty_method="binomial CI on the raw share (n=shots)",
            additive="already included exactly once inside shooting_value's observed-points numerator; "
                     "shown separately for interpretability, NEVER added a second time",
            publication_status="VIABLE" if comp == "two_point_production" else "VIABLE_WITH_CAVEAT",
            known_limitations="none beyond the general shooting caveats" if comp == "two_point_production" else
                              "must never be conflated with two_point_conversion_pct, which is UNSUPPORTED "
                              "(observed between-player variance 0.0102 < binomial noise 0.0137, career scope)",
            phase12_evidence_reference="docs/OFFENSIVE_VALUE_RESEARCH.md sec 3",
        ))

    # ================= FACEOFF =================
    rows.append(_row(
        model_name="faceoff_value_v1", role="faceoff", component="faceoff_value_total",
        target_concept="observed season value above a league-average faceoff man on the same number of draws",
        unit="PLL points",
        formula="faceoff_value_raw = (faceoff_wins - faceoffs*league_win_rate) * points_per_marginal_win "
                "(Phase 6 sql/player_faceoff_value.sql, reused verbatim)",
        numerator="faceoff wins", denominator="faceoffs taken",
        baseline="league faceoff win probability (empirical, ~0.4966)", baseline_scope="season",
        opportunity_measure="faceoffs",
        shrinkage_used="NO", career_information_used="NO for the value; shrunk career faceoff_win_pct shown as context",
        minimum_sample_rule="QUALIFIED requires role_rate_reliability>=0.5 AND future_award_input_eligible",
        uncertainty_method="parametric binomial bootstrap (1,000 draws): faceoff_wins~Binomial(faceoffs, observed "
                            "win rate); the marginal-win coefficient is recovered algebraically from the published "
                            "value and held fixed (see docs/FACEOFF_PLAYER_VALUE.md sec 2)",
        additive="TRUE -- decomposes exactly into rate_value + volume_value (see next two rows)",
        publication_status="VIABLE_WITH_CAVEAT",
        known_limitations="decisive workload confound (Phase 10 probe P5, reproduced in Phase 12 test T4): two "
                           "specialists at an identical rate above baseline can differ 2x+ in total value from "
                           "draw volume alone",
        phase12_evidence_reference="docs/FACEOFF_VALUE_RESEARCH.md; player_value_model_candidates.csv row MF3_faceoff_above_baseline (VIABLE_WITH_CAVEAT)",
    ))
    for comp, desc in [("faceoff_rate_value", "the value this player would have produced at his OWN rate, at the league-average draw volume"),
                       ("faceoff_volume_value", "the residual value from taking more or fewer draws than league-average, at his own rate above baseline")]:
        rows.append(_row(
            model_name="faceoff_value_v1", role="faceoff", component=comp,
            target_concept=desc, unit="PLL points",
            formula="rate_value = faceoff_value_total * (league_mean_faceoffs / faceoffs); "
                    "volume_value = faceoff_value_total - rate_value "
                    "(exact algebraic identity on the published value -- see docs/FACEOFF_PLAYER_VALUE.md sec 2)"
                    if comp == "faceoff_rate_value" else
                    "volume_value = faceoff_value_total - faceoff_rate_value (exact residual)",
            numerator="faceoff_value_total", denominator="faceoffs / league_mean_faceoffs",
            baseline="league-mean faceoffs-taken (season)", baseline_scope="season",
            opportunity_measure="faceoffs", shrinkage_used="NO", career_information_used="NO",
            minimum_sample_rule="inherits faceoff_value_total's qualification",
            uncertainty_method="derived from the faceoff_value_total bootstrap by the same exact identity, per draw",
            additive="TRUE by construction -- rate_value + volume_value = faceoff_value_total exactly, every row",
            publication_status="VIABLE_WITH_CAVEAT -- new in Phase 13, an exact decomposition of an already-VIABLE_WITH_CAVEAT quantity, not a new estimate",
            known_limitations="the decomposition answers 'how much is rate vs volume', not 'is volume within this "
                              "player's control' -- draw volume is largely a function of how many goals were "
                              "scored in his team's games, by either side (Phase 10 probe P5)",
            phase12_evidence_reference="docs/FACEOFF_VALUE_RESEARCH.md sec 2",
        ))

    # ================= GOALIE =================
    rows.append(_row(
        model_name="goalie_value_v1", role="goalie", component="goalie_value_total",
        target_concept="observed season points prevented above a league-average goalie on the same shots faced",
        unit="PLL points",
        formula="goalie_value_raw = expected points allowed (one_point_SOG*E[pts|1PT] + two_point_SOG*E[pts|2PT]) "
                "- actual points allowed (Phase 6 sql/player_goalie_value.sql, reused verbatim)",
        numerator="expected minus actual points allowed", denominator="shots on goal faced",
        baseline="league-average points-allowed rate, separately for one- and two-point shots on goal", baseline_scope="season",
        opportunity_measure="shots_on_goal_faced",
        shrinkage_used="NO", career_information_used="NO for the value; shrunk career save_pct shown as context",
        minimum_sample_rule="QUALIFIED requires role_rate_reliability>=0.5 AND future_award_input_eligible",
        uncertainty_method="parametric binomial bootstrap (1,000 draws): one/two-point goals allowed each "
                            "~Binomial(shots on goal faced of that class, observed allow rate); expected points "
                            "allowed is reconstructed exactly from the published value (actual + goalie_value_raw) and held fixed",
        additive="TRUE -- decomposes exactly into rate_value + workload_value (see next two rows)",
        publication_status="VIABLE_WITH_CAVEAT",
        known_limitations="decisive workload confound (Phase 10 probe P4, reproduced in Phase 12 test T5): two "
                           "goalies of IDENTICAL per-shot skill can differ 30x in total value from team-conceded "
                           "shot volume alone; NOT shot-quality adjusted -- no location/distance/defender data exists",
        phase12_evidence_reference="docs/GOALIE_VALUE_RESEARCH.md; player_value_model_candidates.csv row MF3_goalie_above_baseline (VIABLE_WITH_CAVEAT)",
    ))
    for comp, desc in [("goalie_rate_value", "the value this goalie would have produced at his OWN per-shot skill, at the league-average shot-facing workload"),
                       ("goalie_workload_value", "the residual value from facing more or fewer shots than league-average, at his own skill above baseline")]:
        rows.append(_row(
            model_name="goalie_value_v1", role="goalie", component=comp,
            target_concept=desc, unit="PLL points",
            formula="rate_value = goalie_value_total * (league_mean_shots_faced / shots_on_goal_faced); "
                    "workload_value = goalie_value_total - rate_value (exact algebraic identity, see docs/GOALIE_PLAYER_VALUE.md sec 2)"
                    if comp == "goalie_rate_value" else
                    "workload_value = goalie_value_total - goalie_rate_value (exact residual)",
            numerator="goalie_value_total", denominator="shots_on_goal_faced / league_mean_shots_faced",
            baseline="league-mean shots on goal faced (season)", baseline_scope="season",
            opportunity_measure="shots_on_goal_faced", shrinkage_used="NO", career_information_used="NO",
            minimum_sample_rule="inherits goalie_value_total's qualification",
            uncertainty_method="derived from the goalie_value_total bootstrap by the same exact identity, per draw",
            additive="TRUE by construction -- rate_value + workload_value = goalie_value_total exactly, every row",
            publication_status="VIABLE_WITH_CAVEAT -- new in Phase 13, an exact decomposition of an already-VIABLE_WITH_CAVEAT quantity, not a new estimate",
            known_limitations="workload (shots faced) is substantially the team's defense, not the goalie's own "
                              "action (Phase 10 probe P4) -- a high workload_value is not evidence the goalie "
                              "sought out more shots",
            phase12_evidence_reference="docs/GOALIE_VALUE_RESEARCH.md sec 2",
        ))

    # ================= DEFENSE =================
    rows.append(_row(
        model_name="defensive_production_v1", role="defensive_field", component="caused_turnovers",
        target_concept="descriptive box-score production, NOT individual defensive value",
        unit="count", formula="caused_turnovers (official box-score total, player_stats_2022_2026.csv)",
        numerator="caused turnovers", denominator="n/a (a count)",
        baseline="NONE -- deliberately not baselined or ranked as a value", baseline_scope="n/a",
        opportunity_measure="games_played (crude; no defensive-possession exposure exists)",
        shrinkage_used="NO", career_information_used="NO",
        minimum_sample_rule="none -- shown for every defensive_field player, sorted by games_played (an "
                            "availability fact), never by production",
        uncertainty_method="NONE -- a box-score count is not a rate estimate, so no interval is attached; "
                            "the availability confound (rho=0.49-0.80 with games_played) is disclosed instead",
        additive="TRUE trivially (a sum of counts) but NEVER combined with ground_balls or games_played into one score",
        publication_status="ROLE_ONLY (descriptive production, explicitly not a value model)",
        known_limitations="zero of 52,633 raw events (2022-2026) name a causing or closest defender; no minutes/"
                           "shifts/lineups exist; up to 64% of the rank variance in raw caused turnovers is "
                           "availability, not impact",
        phase12_evidence_reference="docs/DEFENSIVE_VALUE_FEASIBILITY.md; player_value_model_candidates.csv row MF3_defense_above_baseline_partial (ROLE_ONLY)",
    ))
    rows.append(_row(
        model_name="defensive_production_v1", role="defensive_field", component="ground_balls",
        target_concept="descriptive box-score production, NOT individual defensive value",
        unit="count", formula="ground_balls (official box-score total)",
        numerator="ground balls", denominator="n/a (a count)", baseline="NONE", baseline_scope="n/a",
        opportunity_measure="games_played", shrinkage_used="NO", career_information_used="NO",
        minimum_sample_rule="none -- shown, never ranked as value",
        uncertainty_method="NONE", additive="TRUE trivially; never combined with caused_turnovers into one score",
        publication_status="ROLE_ONLY",
        known_limitations="not separable from faceoff-scrum recovery context for defenders who also see faceoff "
                           "possessions; no possession-exposure denominator",
        phase12_evidence_reference="docs/DEFENSIVE_VALUE_FEASIBILITY.md",
    ))

    df = pd.DataFrame(rows)
    assert list(df.columns) == SPEC_COLUMNS
    return df


def main():
    spec = build_spec()
    out = HIST / "player_value_model_spec_v1.csv"
    spec.to_csv(out, index=False)
    print(f"Wrote {out.relative_to(REPO_ROOT)}: {len(spec)} rows, "
          f"{spec['model_name'].nunique()} models")
    print(spec.groupby("model_name")["component"].apply(list).to_string())


if __name__ == "__main__":
    main()
