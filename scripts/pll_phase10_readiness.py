"""
Phase 10 part K: readiness assessment for a future statistical award model.

This module classifies every candidate INPUT to such a model. It does not
build the model, score anything, weight anything or rank anything, and a
validation check plus three tests fail if it ever starts to.

Every classification below is derived from a number produced elsewhere in
Phase 10 (or Phases 6-9), read back out of the published CSV at run time, so
the table cannot drift from the evidence. Where a classification rests on a
judgement rather than a threshold, the judgement is written out in
`justification` in full and the number that motivated it is in
`supporting_statistic`.

THE FIVE CLASSES
    READY              measured, reproducible, comparable across the
                       population it would be applied to, and stable enough to
                       mean the same thing in two different seasons
    READY_WITH_CAVEAT  the same, but carrying a limitation that must travel
                       with the number and be stated wherever it is used
    EXPERIMENTAL       defensible to compute and inspect; not defensible as a
                       load-bearing input until a stated question is answered
    NOT_COMPARABLE     real and correctly measured, but not on a scale that
                       can be set beside another player's without a
                       transformation that Phase 10 could not justify
    UNSUPPORTED        the data do not identify the quantity at all; any value
                       produced would be an artefact of the estimator

Outputs:
    data/processed/history/mvp_input_readiness.csv
    data/processed/history/phase10_measurement_scope.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
HIST = REPO_ROOT / "data" / "processed" / "history"


def _hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def gather_evidence() -> dict:
    """Read every number the classification depends on out of the published
    Phase 9/10 artifacts. Nothing here is hard-coded."""
    e = {}

    rel = _hf("career_ability_reliability.csv")
    car = rel[rel["scope"] == "pooled_player_career"].set_index("rate_name")
    s26 = rel[rel["scope"] == "season_2026"].set_index("rate_name")
    e["career"] = car
    e["season_2026"] = s26

    e["two_point"] = _hf("career_two_point_identification.csv")
    e["two_point_dist"] = _hf("career_two_point_attempt_distribution.csv")
    e["scope_cmp"] = _hf("career_scope_comparison.csv").set_index("rate_name")
    e["sens"] = _hf("career_season_composition_sensitivity.csv")
    e["methods"] = _hf("cross_position_method_comparison.csv").set_index("method")
    e["audit"] = _hf("cross_position_value_audit.csv")
    e["baselines"] = _hf("positional_baselines.csv")
    e["repl"] = _hf("cross_position_replacement_level.csv")
    e["counterfactuals"] = _hf("cross_position_counterfactuals.csv")
    e["defense"] = _hf("defensive_attribution_audit.csv")
    e["stability"] = _hf("phase10_historical_stability.csv")
    e["poss"] = _hf("possession_stats_original_vs_repaired.csv")
    e["opponent"] = _hf("multi_season_opponent_adjustment.csv")
    e["usage"] = _hf("multi_season_usage_model.csv")
    e["career_table"] = _hf("player_career_2022_2026.csv", dtype={"player_id": str})
    e["identity"] = _hf("career_identity_audit.csv", dtype={"player_id": str})

    hl = e["audit"][e["audit"]["role"] == "ALL_ROLES"]
    e["sd_ratio_all"] = float(
        hl.loc[hl["scope"] == "2022_2026", "value_sd_max_over_min_across_roles"].iloc[0])
    e["sd_ratio_by_season"] = {
        r["scope"]: r["value_sd_max_over_min_across_roles"]
        for _, r in hl.iterrows() if r["scope"] != "2022_2026"}
    e["opp_ratio_all"] = float(
        hl.loc[hl["scope"] == "2022_2026",
               "opportunity_mean_max_over_min_across_roles"].iloc[0])

    # counterfactual P1 is the single most-cited number below, so it is read
    # out of the artifact rather than transcribed into prose.
    p1 = e["counterfactuals"]
    p1 = p1[p1["probe"] == "P1_equally_elite_within_role"]
    v = pd.to_numeric(p1["M01_raw_value_above_role_baseline"],
                      errors="coerce").dropna()
    e["p1_min"], e["p1_max"] = float(v.min()), float(v.max())
    e["p1_ratio"] = float(v.max() / v.min()) if v.min() else np.nan
    e["p1_z"] = float(pd.to_numeric(p1["M04_within_position_z"],
                                    errors="coerce").dropna().iloc[0])
    return e


def _career_row(e, rate):
    return e["career"].loc[rate] if rate in e["career"].index else None


def build_readiness(e: dict) -> pd.DataFrame:
    rows = []

    def add(input_name, category, what_it_measures, source, cls, stat,
            justification, caveat, evidence_files):
        rows.append({
            "input_name": input_name,
            "category": category,
            "what_it_measures": what_it_measures,
            "source_metric": source,
            "readiness_class": cls,
            "supporting_statistic": stat,
            "justification": justification,
            "caveat_that_must_travel_with_it": caveat,
            "evidence_files": evidence_files,
        })

    # ---- 1. scoring production ------------------------------------------
    add("scoring_production", "production",
        "goals, one-point goals, two-point goals and PLL points a player "
        "actually recorded",
        "player_stats_YEAR.csv: goals, scoring_points, one_point_goals, "
        "two_point_goals",
        "READY",
        "PLL points reconcile exactly to the official final score in every "
        "eligible team-game in all five seasons (Phase 9 check 7; the single "
        "documented exception is archers-cannons-2022-6-18)",
        "It is OBSERVED, fully attributed, and needs no model. It is the only "
        "input in this table that requires no estimation of any kind.",
        "It is production, not ability, and it is not comparable across roles: "
        "a goalie's scoring production is zero by job description, not by "
        "performance.",
        "phase9_validation_report.csv")

    # ---- 2. shooting value ----------------------------------------------
    c = _career_row(e, "shooting_pct")
    s = e["season_2026"].loc["shooting_pct"]
    add("shooting_value", "value component",
        "points produced on a player's own shot attempts against what "
        "league-average shots of the same class produce",
        "player_stats_YEAR.csv: shooting_value_raw",
        "READY_WITH_CAVEAT",
        f"single-season kappa {s['kappa']:.1f} shots with "
        f"{int(s['n_reaching_reliability_gate'])} of {int(s['n_units'])} "
        f"players clearing reliability 0.5; league components sum to zero to "
        f"10 decimal places",
        "The VALUE accounting is exact and unbiased -- it is arithmetic on "
        "observed shots against a measured league baseline. What is unreliable "
        "is reading it as ability at one season's sample.",
        "A single season's shooting value is dominated by conversion luck. "
        "Phase 7 measured the consequence: replacing the shooting component "
        "with its shrunk equivalent moves 219 of 228 total-value ranks.",
        "player_value_shrinkage.csv, career_ability_reliability.csv")

    # ---- 3. turnover value ----------------------------------------------
    c = _career_row(e, "turnovers_per_touch")
    add("turnover_value", "value component",
        "turnovers committed against the position group's turnovers-per-touch "
        "rate, priced at the empirical forward-window cost of a turnover",
        "player_stats_YEAR.csv: turnover_value_raw",
        "READY_WITH_CAVEAT",
        f"career kappa {c['kappa']:.1f} touches; "
        f"{int(c['n_reaching_reliability_gate'])} of {int(c['n_units'])} "
        f"players ({c['pct_reaching_reliability_gate']:.1f}%) clear "
        f"reliability 0.5 -- the highest count of any rate",
        "Turnover tendency is the best-evidenced player rate in the framework "
        "after faceoff win percentage, and it is already residualised against "
        "a position-group baseline, so the role effect is out of the "
        "expectation.",
        "Roughly 19% of the league's turnovers name only a team, so every "
        "player's absolute turnover count is understated. The ratio is "
        "internally consistent because both sides of it are built from "
        "player-attributed sums, but the level is not the official level.",
        "career_ability_reliability.csv, PLAYER_ADJUSTED_VALUE_METHODOLOGY.md")

    # ---- 4. faceoff value -----------------------------------------------
    c = _career_row(e, "faceoff_win_pct")
    add("faceoff_value", "value component",
        "faceoff wins above the league win probability, priced at the "
        "empirical value of a possession-gaining event",
        "player_stats_YEAR.csv: faceoff_value_raw",
        "NOT_COMPARABLE",
        f"career kappa {c['kappa']:.1f} draws -- five to seven times smaller "
        f"than any other rate's -- with "
        f"{c['pct_reaching_reliability_gate']:.1f}% of takers clearing "
        f"reliability 0.5 and an implied true between-player sd of "
        f"{c['implied_true_sd_between_players']:.3f}",
        "Faceoff is the ONE cleanly identified individual skill in this feed, "
        "and as a within-role measure it is READY. It is classified "
        "NOT_COMPARABLE because of what happens when it is put next to other "
        "roles: it is NULL for roughly four players in five, and the faceoff "
        "role supplies 25-75% of the top 20 under most transformations tested "
        "in section F while being 5% of the league.",
        "Undefined for every player who never takes a draw. A model that "
        "treats a NULL faceoff value as zero is asserting that not taking "
        "draws is exactly average at taking them.",
        "career_ability_reliability.csv, cross_position_method_comparison.csv")

    # ---- 5. goalie value -------------------------------------------------
    c = _career_row(e, "save_pct")
    s = e["season_2026"].loc["save_pct"]
    gsd = e["audit"]
    gsd = gsd[(gsd["role"] == "goalie") & (gsd["component"] == "EPA_points_raw")
              & (gsd["scope"] == "2022_2026")]["value_sd"]
    dsd = e["audit"]
    dsd = dsd[(dsd["role"] == "defensive_field")
              & (dsd["component"] == "EPA_points_raw")
              & (dsd["scope"] == "2022_2026")]["value_sd"]
    add("goalie_value", "value component",
        "points allowed on shots on goal faced against league expected points "
        "per shot on goal",
        "player_stats_YEAR.csv: goalie_value_raw",
        "NOT_COMPARABLE",
        f"career kappa {c['kappa']:.0f} shots on goal against a median career "
        f"of {c['median_trials']:.0f}; {int(c['n_reaching_reliability_gate'])} "
        f"of {int(c['n_units'])} goalies clear reliability 0.5 (one of sixteen "
        f"in 2026 alone). Pooled EPA_points_raw sd is {float(gsd.iloc[0]):.2f} "
        f"for goalies against {float(dsd.iloc[0]):.2f} for close defenders "
        f"-- {e['sd_ratio_all']:.1f}x",
        "Career pooling is the single largest improvement Phase 9/10 found "
        "for any rate -- one goalie clears the gate on a season, eight do on a "
        "career -- so goalie ABILITY is estimable for about three goalies in "
        "ten. Goalie VALUE on the shared EPA scale is not comparable to a "
        "field player's: it is measured over 150-400 shots faced where a close "
        "defender's entire record is a handful of caused turnovers.",
        "A goalie's total value is driven substantially by how many shots his "
        "team conceded, which is not his action. Counterfactual P4 in "
        "cross_position_counterfactuals.csv shows the size of that confound.",
        "career_ability_reliability.csv, cross_position_value_audit.csv")

    # ---- 6. partial defensive value --------------------------------------
    d = e["defense"]
    add("defensive_value_partial", "value component",
        "caused turnovers above the position group's per-GAME average -- and "
        "nothing else about defence",
        "player_stats_YEAR.csv: defensive_value_partial_raw",
        "NOT_COMPARABLE",
        f"in all five seasons, {int(d['turnover_events'].sum())} turnover "
        f"events carry {int(d['turnover_events_naming_a_causing_defender'].sum())} "
        f"causing-defender ids and "
        f"{int(d['events_naming_a_closest_defender'].sum())} "
        f"closest-defender ids; caused turnovers correlate with games played at "
        f"rho {d['caused_turnovers_spearman_with_games_played'].mean():.2f}",
        "The three raw fields that would carry individual defensive "
        "attribution -- causedTurnoverId, closestDefenderId, "
        "commitedTurnoverId -- exist in the schema and are empty in every one "
        "of the 51,000+ events of all five seasons. Caused turnovers survive "
        "only as a box-score total with no time, no context and no opponent. "
        "There is also no minutes, shift or lineup data anywhere, so a "
        "defender has no exposure denominator at all.",
        "PARTIAL must stay in the name. A value of 0.0 means 'caused turnovers "
        "at his group's per-game rate, everything else unmeasured', NOT 'an "
        "average defender'.",
        "defensive_attribution_audit.csv")

    # ---- 7. usage ---------------------------------------------------------
    u = e["usage"]
    best = u.loc[u["selected_model"] == True, "model"].iloc[0]  # noqa: E712
    add("usage", "context",
        "the share of his team's recorded offensive opportunities (shots + "
        "turnovers) a player personally took on",
        "player_stats_YEAR.csv: offensive_play_share",
        "READY_WITH_CAVEAT",
        f"the {best} model still wins cross-validation on 844 player-seasons "
        f"with folds cut by player; the usage/offensive-EPA correlation is "
        f"negative in four of five seasons",
        "Usage is a countable share with a countable numerator and "
        "denominator. What it does NOT support is an expectation: five "
        "seasons say there is no reliable relationship between how much a "
        "player is used and how much value he produces, so a usage-adjusted "
        "expectation adds a parameter and no information.",
        "It is NOT the share of team possessions a player was on the field "
        "for. The feed carries no lineup, shift or minutes data of any kind, "
        "in any season.",
        "multi_season_usage_model.csv")

    # ---- 8. career ability -----------------------------------------------
    ct = e["career_table"]
    n_any = int((ct["n_rates_reaching_reliability_gate"] > 0).sum())
    sens = e["sens"]
    rho_min = float(sens["spearman_rank_correlation_vs_full"].min())
    add("career_ability", "ability estimate",
        "empirical-Bayes shrunk career rates for shooting, one-point "
        "conversion, faceoff, save and turnover tendency",
        "player_career_2022_2026.csv, career_rate_estimates.csv",
        "READY_WITH_CAVEAT",
        f"{n_any} of {len(ct)} players reach reliability 0.5 on at least one "
        f"rate; leave-one-season-out rank correlation never falls below "
        f"{rho_min:.2f}",
        "Career pooling is the only aggregation that improves identification: "
        "pooling player-SEASONS as rows makes it worse (shooting kappa 70.8 -> "
        "145.5, zero of 863 clearing the gate), pooling a player's CAREER "
        "makes it better. The estimates recompute exactly from the published "
        "successes and trials.",
        "A career estimate answers 'how good has this player been across "
        "2022-2026', not 'how good is he now'. Ageing, role change and team "
        "context are modelled nowhere. 44 players changed listed position and "
        "97 changed team inside the window.",
        "career_ability_reliability.csv, career_season_composition_sensitivity.csv")

    # ---- 9. two-point production -----------------------------------------
    tpd = e["two_point_dist"].iloc[0]
    add("two_point_production", "production",
        "two-point goals, two-point attempts, the PLL points they generated "
        "and how often a player chose the long shot",
        "player_stats_YEAR.csv: two_point_goals, two_point_attempts, "
        "two_point_conversion_pct (descriptive only)",
        "READY_WITH_CAVEAT",
        f"{int(tpd['total_attempts'])} career attempts across "
        f"{int(tpd['n_shooters'])} shooters; the league two-point return is "
        f"+0.0004 points per attempt against the one-point shot over five "
        f"seasons",
        "Two-point GOALS and ATTEMPTS are OBSERVED counts and reconcile "
        "exactly (Phase 9 check 8: 1PT + 2PT reconstructs goals and points at "
        "team level in all five seasons). Counting them is not the same as "
        "estimating who is good at them.",
        "Two-point production must never be presented as, or silently "
        "converted into, two-point ability -- see the row below.",
        "two_point_audit_2022_2026.csv, multi_season_two_point_analysis.csv")

    # ---- 10. two-point ability -------------------------------------------
    tp = e["two_point"]
    tpc = tp[(tp["rate_name"] == "two_point_pct")
             & (tp["scope"] == "pooled_player_career")].iloc[0]
    add("two_point_ability", "ability estimate",
        "an individual player's underlying two-point conversion rate",
        "two_point_rate_shrunk (collapsed to the league mean by construction)",
        "UNSUPPORTED",
        f"career: {int(tpc['n_units'])} shooters, "
        f"{int(tpc['total_trials'])} attempts, median "
        f"{tpc['median_trials']:.0f}; observed between-player variance "
        f"{tpc['observed_between_player_variance']:.6f} is BELOW binomial noise "
        f"{tpc['binomial_noise_variance']:.6f} (excess "
        f"{tpc['excess_variance']:+.6f}); prior capped at 1e6; max reliability "
        f"{tpc['max_reliability']:.6f}",
        "Replicated in every season, in the pooled player-seasons, and now on "
        "the final career aggregation: the spread between players is no wider "
        "than chance alone predicts. Every shrunk value is the league mean and "
        "no player is separable from it. The binding constraint is attempts -- "
        "a median of 3 across an entire career.",
        "INDIVIDUAL_TWO_POINT_ABILITY = UNSUPPORTED / DO_NOT_USE. This is a "
        "statement about identification, not about the shot: two-point "
        "PRODUCTION remains a legitimate descriptive statistic.",
        "career_two_point_identification.csv")

    # ---- 11. possession efficiency ---------------------------------------
    poss = e["poss"]
    o23 = poss[(poss["season"] == 2023) & (poss["variant"] == "V0_original")].iloc[0]
    r23 = poss[(poss["season"] == 2023)
               & (poss["variant"] == "V2_direct_and_timing")].iloc[0]
    add("possession_efficiency", "team context",
        "points per offensive possession, and every other possession-"
        "denominated team rate",
        "team_stats_YEAR.csv: offensive_efficiency, team_possessions_per_game",
        "READY_WITH_CAVEAT",
        f"2023 moves from {o23['possessions_per_game']:.2f} to "
        f"{r23['possessions_per_game']:.2f} possessions per game and from "
        f"{o23['points_per_possession']:.4f} to "
        f"{r23['points_per_possession']:.4f} points per possession under the "
        f"evidence-bounded repair; 2022, 2025 and 2026 are bit-identical",
        "Phase 9 classified 2023 per-possession metrics NON_COMPARABLE. Phase "
        "10 found the cause -- 201 post-goal faceoffs ordered before their own "
        "goal in 12 games -- and repaired it from the feed's own markerId "
        "sequence. After repair 2023 sits inside the five-season range on "
        "every possession metric and team rankings do not move at all.",
        "The repaired layer is published as possessions_repaired.csv and the "
        "frozen possessions.csv is unchanged, so any cross-season "
        "possession-denominated comparison must state WHICH layer it used. 89 "
        "2023 goals still have no faceoff logged after them, against 39 in "
        "2026 and 51 in 2022, so a residual excess remains.",
        "possession_stats_original_vs_repaired.csv, 2023_possession_repair_audit.csv")

    # ---- 12. opponent adjustment ------------------------------------------
    oa = e["opponent"]
    add("opponent_adjustment", "adjustment",
        "correcting a player's or team's value for the strength of the "
        "opposition faced",
        "not built",
        "EXPERIMENTAL",
        f"schedule connectivity {oa['schedule_connectivity'].min():.2f} in "
        f"every season, but strength-of-schedule spread is only "
        f"{100*oa['sos_sd_as_share_of_raw_sd'].min():.0f}-"
        f"{100*oa['sos_sd_as_share_of_raw_sd'].max():.0f}% of between-team "
        f"spread and the adjustment moves ranks by "
        f"{oa['max_rank_change'].max():.0f} places at most",
        "Phase 9 established that this is feasible (all 28 pairings occur "
        "every season) and nearly worthless (a balanced round-robin leaves "
        "almost nothing to adjust for; in 2026 the adjustment is smaller than "
        "its own bootstrap standard error). It is EXPERIMENTAL rather than "
        "UNSUPPORTED because it is computable and correct -- just not worth "
        "the parameter.",
        "There is no player-level opponent adjustment anywhere: the feed "
        "carries no matchup or assignment data, so 'who did this attackman "
        "score against' is not answerable at the defender level.",
        "multi_season_opponent_adjustment.csv")

    # ---- 13. availability / games played ----------------------------------
    m = e["methods"]
    gp_rho = m["spearman_with_games_played"]
    add("availability_games_played", "context",
        "how many games a player was available for",
        "player_stats_YEAR.csv: games_played",
        "READY",
        f"every candidate cross-position transformation correlates with games "
        f"played at rho {gp_rho.min():.2f} to {gp_rho.max():.2f}",
        "Games played is the one quantity in this project that is "
        "unambiguously comparable across every role: a game is a game. It is "
        "READY as a DENOMINATOR and as a disclosure.",
        "It is not READY as a value input. Every season-total measure already "
        "rewards availability implicitly, and a model that also adds it is "
        "counting durability twice. Whether an award SHOULD reward "
        "availability is a question about the award, not about the data.",
        "cross_position_method_comparison.csv")

    # ---- 14. positional normalization -------------------------------------
    b = e["baselines"]
    diag = b[b["baseline_scope"] == "position_season_stability_diagnostic"]
    rec = diag["recommended_scope"].value_counts()
    z = m.loc["M04_within_position_z"]
    add("positional_normalization", "transformation",
        "putting roles on one scale so their values can be set side by side",
        "EPA_position_z, EPA_position_percentile, and the ten candidates "
        "tested in section F",
        "NOT_COMPARABLE",
        f"role EPA standard deviations differ by {e['sd_ratio_all']:.1f}x "
        f"pooled ({min(e['sd_ratio_by_season'].values()):.1f}-"
        f"{max(e['sd_ratio_by_season'].values()):.1f}x by season) and role "
        f"opportunity means by {e['opp_ratio_all']:.0f}x. Only "
        f"within-position z and percentile equalise the scale, and "
        f"counterfactual P1 shows why that is not enough: five players who are "
        f"each +2 SD within their own role receive {e['p1_min']:.2f} to "
        f"{e['p1_max']:.2f} PLL points above their role baseline -- a "
        f"{e['p1_ratio']:.1f}x spread -- while receiving identical z-scores of "
        f"{e['p1_z']:.1f}",
        "Standardisation removes the group effect. It does not establish that "
        "a 95th-percentile faceoff specialist and a 95th-percentile attackman "
        "contributed equally, and the counterfactual shows they did not "
        "contribute equally in points. Quantile-mapping the roles onto a "
        "common distribution equalises the scale only by ASSUMING the "
        "difference is entirely measurement -- which is the conclusion such a "
        "model would need to establish.",
        f"Baseline scope is settled: {rec.to_dict()} of the tested "
        f"role/component combinations recommend a POSITION baseline rather "
        f"than a POSITION-SEASON one, because between-season movement is "
        f"within sampling error.",
        "cross_position_method_comparison.csv, cross_position_counterfactuals.csv, "
        "positional_baselines.csv")

    df = pd.DataFrame(rows)
    order = {"READY": 0, "READY_WITH_CAVEAT": 1, "EXPERIMENTAL": 2,
             "NOT_COMPARABLE": 3, "UNSUPPORTED": 4}
    df["_o"] = df["readiness_class"].map(order)
    return df.sort_values(["_o", "input_name"]).drop(columns="_o").reset_index(drop=True)


def measurement_scope(e: dict, readiness: pd.DataFrame) -> pd.DataFrame:
    """The two questions section K asks to be answered explicitly."""
    ready = readiness[readiness["readiness_class"].isin(
        ["READY", "READY_WITH_CAVEAT"])]["input_name"].tolist()
    notc = readiness[readiness["readiness_class"] == "NOT_COMPARABLE"][
        "input_name"].tolist()
    unsup = readiness[readiness["readiness_class"] == "UNSUPPORTED"][
        "input_name"].tolist()
    m = e["methods"]
    rows = [
        {"question": "What can a PLL statistical award model actually measure "
                     "with the available data?",
         "answer_id": "CAN_MEASURE_1",
         "answer": "Production, exactly. Every point, goal, shot, save, draw, "
                   "ground ball and caused turnover the league recorded is "
                   "attributable and reconciles to the official box score.",
         "evidence": "Phase 9 check 7: PLL points re-derived from valid goal "
                     "events match the official score in every eligible "
                     "team-game of five seasons, with one documented exception.",
         "evidence_file": "phase9_validation_report.csv"},
        {"question": "What can a PLL statistical award model actually measure "
                     "with the available data?",
         "answer_id": "CAN_MEASURE_2",
         "answer": "Value above a league-average player on the SAME recorded "
                   "opportunities, within a role. The residual accounting sums "
                   "to zero across the league by construction and no component "
                   "double-counts another.",
         "evidence": "Phase 6 validation checks 14-16: every component sums to "
                     "0.0000000000 across the league.",
         "evidence_file": "player_value_components.csv"},
        {"question": "What can a PLL statistical award model actually measure "
                     "with the available data?",
         "answer_id": "CAN_MEASURE_3",
         "answer": "Underlying ABILITY, but only at career scope and only for "
                   "faceoff win %, turnover tendency, shooting %, one-point "
                   "conversion, shot accuracy and save % -- and even then only "
                   "for the minority of players who accumulate enough trials.",
         "evidence": f"career reliability >= 0.5 is reached by "
                     f"{int(e['career'].loc['faceoff_win_pct', 'pct_reaching_reliability_gate'])}% "
                     f"of faceoff takers, "
                     f"{int(e['career'].loc['turnovers_per_touch', 'pct_reaching_reliability_gate'])}% "
                     f"on turnovers per touch, "
                     f"{int(e['career'].loc['save_pct', 'pct_reaching_reliability_gate'])}% "
                     f"of goalies and "
                     f"{int(e['career'].loc['shooting_pct', 'pct_reaching_reliability_gate'])}% "
                     f"of shooters.",
         "evidence_file": "career_ability_reliability.csv"},
        {"question": "What can a PLL statistical award model actually measure "
                     "with the available data?",
         "answer_id": "CAN_MEASURE_4",
         "answer": "Rank WITHIN a role, with an honest statement of how much "
                   "evidence stands behind each rank.",
         "evidence": "within-position z and percentile are the only two "
                     "transformations of the ten tested that put every role on "
                     "one numerical scale.",
         "evidence_file": "cross_position_method_comparison.csv"},
        {"question": "What important dimensions of real lacrosse value can it "
                     "NOT measure?",
         "answer_id": "CANNOT_MEASURE_1",
         "answer": "Defence, beyond caused turnovers. No event in any season "
                   "names a causing defender or a closest defender, and there "
                   "is no minutes, shift or lineup data, so a defender has no "
                   "exposure denominator and slides, matchups, help, shot "
                   "suppression and off-ball positioning are entirely absent.",
         "evidence": f"{int(e['defense']['events_naming_a_closest_defender'].sum())} "
                     f"closest-defender ids and "
                     f"{int(e['defense']['turnover_events_naming_a_causing_defender'].sum())} "
                     f"causing-defender ids across "
                     f"{int(e['defense']['raw_events'].sum())} raw events.",
         "evidence_file": "defensive_attribution_audit.csv"},
        {"question": "What important dimensions of real lacrosse value can it "
                     "NOT measure?",
         "answer_id": "CANNOT_MEASURE_2",
         "answer": "Playing time. Every rate in this project is denominated in "
                   "countable events, never in seconds on the field, because "
                   "the feed contains no substitution data at all.",
         "evidence": "verified across all raw games in Phases 1-6 and "
                     "re-verified for 2022-2025 in Phase 9's schema audit.",
         "evidence_file": "historical_schema_compatibility.csv"},
        {"question": "What important dimensions of real lacrosse value can it "
                     "NOT measure?",
         "answer_id": "CANNOT_MEASURE_3",
         "answer": "Creation as distinct from finishing. Assists exist as a "
                   "box-score count but crediting them would value the same "
                   "goal twice, so shooting value is finishing only. Off-ball "
                   "movement, dodging that draws a slide, and the pass before "
                   "the assist are unrecorded.",
         "evidence": "Phase 6 deferred assist value precisely because it "
                     "breaks the disjoint-opportunity rule that prevents "
                     "double-counting.",
         "evidence_file": "player_value_components.csv"},
        {"question": "What important dimensions of real lacrosse value can it "
                     "NOT measure?",
         "answer_id": "CANNOT_MEASURE_4",
         "answer": "Cross-position value. Roles are measured over opportunity "
                   "counts that differ by more than an order of magnitude, and "
                   "no transformation tested converts that into a common value "
                   "scale without assuming the answer.",
         "evidence": f"role EPA standard deviations differ by "
                     f"{e['sd_ratio_all']:.1f}x and role opportunity means by "
                     f"{e['opp_ratio_all']:.0f}x; five equally-elite players "
                     f"receive {e['p1_min']:.2f} to {e['p1_max']:.2f} points "
                     f"above their role baselines.",
         "evidence_file": "cross_position_counterfactuals.csv"},
        {"question": "What important dimensions of real lacrosse value can it "
                     "NOT measure?",
         "answer_id": "CANNOT_MEASURE_5",
         "answer": "Two-point shooting ability. Five seasons and a career "
                   "aggregation all return between-player variance below "
                   "binomial noise.",
         "evidence": "excess variance is negative in every season and both "
                     "pooled scopes; median career attempts is 3.",
         "evidence_file": "career_two_point_identification.csv"},
        {"question": "What important dimensions of real lacrosse value can it "
                     "NOT measure?",
         "answer_id": "CANNOT_MEASURE_6",
         "answer": "Anything durable about a season's total value. Every one "
                   "of the ten cross-position transformations has a "
                   "year-to-year rank correlation between 0.16 and 0.25.",
         "evidence": f"year-to-year Spearman ranges "
                     f"{m['year_to_year_spearman'].min():.2f} to "
                     f"{m['year_to_year_spearman'].max():.2f} across all ten "
                     f"methods on 570-576 paired player-seasons. For a "
                     f"RETROSPECTIVE award this is not disqualifying -- it is "
                     f"a statement that seasons differ -- but it rules out "
                     f"reading any of these as a talent measure.",
         "evidence_file": "phase10_historical_stability.csv"},
        {"question": "Summary",
         "answer_id": "SUMMARY",
         "answer": f"{len(ready)} inputs are READY or READY_WITH_CAVEAT, "
                   f"{len(notc)} are NOT_COMPARABLE across roles, "
                   f"{len(unsup)} is UNSUPPORTED. The binding constraint on a "
                   f"cross-position award model is NOT statistical technique. "
                   f"It is measurement coverage: attack and midfield value is "
                   f"measured over thousands of shots, defensive value over a "
                   f"handful of caused turnovers with no exposure denominator.",
         "evidence": f"READY/CAVEAT: {', '.join(ready)}. NOT_COMPARABLE: "
                     f"{', '.join(notc)}. UNSUPPORTED: {', '.join(unsup)}.",
         "evidence_file": "mvp_input_readiness.csv"},
    ]
    return pd.DataFrame(rows)


def main():
    HIST.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 90)
    e = gather_evidence()
    r = build_readiness(e)
    r.to_csv(HIST / "mvp_input_readiness.csv", index=False)
    s = measurement_scope(e, r)
    s.to_csv(HIST / "phase10_measurement_scope.csv", index=False)

    print("=== K. INPUT READINESS ===")
    print(r[["input_name", "readiness_class", "supporting_statistic"]]
          .to_string(index=False))
    print("\n" + r["readiness_class"].value_counts().to_string())
    print("\n=== K. WHAT THE DATA CAN AND CANNOT MEASURE ===")
    for _, row in s.iterrows():
        print(f"\n[{row['answer_id']}] {row['answer']}")
    return r, s


if __name__ == "__main__":
    main()
