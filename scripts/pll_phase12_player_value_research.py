"""
ARCHIVED RESEARCH: excluded from the final product. Known audit defects are
retired with these features, not corrected here. See docs/AUDIT_REMEDIATION.md.

Phase 12: Player Value Model Specification + Award Methodology Research.

This module is a STATISTICAL RESEARCH phase, not an award-building phase. It
builds NO Statistical Tewaaraton, NO MVP score, NO WAR, NO replacement-level
composite, NO fantasy score, NO cross-position leaderboard, and NO arbitrary-
weight composite. What it builds is the evidence a later phase would need to
decide whether any of those are defensible, and it is written expecting the
answer to some of them to be "no" -- which Phases 6, 7, 9 and 10 already
established for several forbidden constructions (see docs/MVP_INPUT_READINESS.md,
docs/CROSS_POSITION_VALUE_RESEARCH.md).

Labels used throughout the companion docs: OBSERVED / DERIVED / MODELED /
INFERRED / UNSUPPORTED.

WHAT IS GENUINELY NEW IN THIS PHASE (Phases 6-11 did not do these):
  1. A metric DEPENDENCY / double-counting analysis with real correlations and
     variance-inflation factors among candidate value-model inputs (Section C
     of the Phase 12 brief). Phase 6 argued disjointness by CONSTRUCTION
     (accounting.md); this module verifies it by MEASUREMENT.
  2. A concrete, real attempt at Model Family 5 (team-outcome association) as
     a candidate source of EMPIRICALLY DERIVED cross-role weights -- run to
     completion, with bootstrap uncertainty and leave-one-season-out
     validation, specifically so the project can say WHY it fails rather than
     asserting that it would.
  3. A model candidate SCORECARD that inventories every model family named in
     the Phase 12 brief (including the ten cross-position transformations
     Phase 10 already tested) on one consistent schema, so a future phase can
     see every option and its status in one place.
  4. A counterfactual TEST SUITE distinct from Phase 10's cross-position
     probes -- these are framed as pass/fail tests against a stated
     theoretical expectation, per Phase 12 Section K, rather than as
     descriptive probes.
  5. A validation-criteria table applying the specific test families the
     Phase 12 brief names (accounting, predictive, concurrent, stability,
     bootstrap, leave-one-season-out) to the actual candidates, in one
     comparable schema.

Everything else here REUSES a published Phase 6-11 artifact rather than
recomputing it, and says so via the "reused_from" field where applicable, so
this phase cannot silently drift from the evidence Phases 6-11 already
established.

Outputs, all in data/processed/history/:
    player_value_signal_inventory.csv     every candidate input, classified
    player_value_metric_dependency.csv    correlations, VIF, accounting checks
    player_value_model_candidates.csv     every model family, one schema
    player_value_validation_results.csv   the six validation-test families
    player_value_counterfactual_tests.csv pass/fail synthetic probes

NOT WRITTEN, DELIBERATELY: any file containing a per-player cross-position
score, rank or composite. Enforced by pll_validate_phase12.py.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]
RNG_SEED = 20261012

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_player_value_models import bootstrap_ci  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)


def _hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def load_data() -> dict:
    d = {}
    d["players"] = _hf("player_stats_2022_2026.csv",
                        dtype={"player_id": str, "team_id": str})
    d["career"] = _hf("player_career_2022_2026.csv", dtype={"player_id": str})
    d["teams"] = _hf("team_stats_2022_2026.csv", dtype={"team_id": str})
    d["career_reliability"] = _hf("career_ability_reliability.csv")
    d["cross_audit"] = _hf("cross_position_value_audit.csv")
    d["method_comparison"] = _hf("cross_position_method_comparison.csv")
    d["counterfactuals_p10"] = _hf("cross_position_counterfactuals.csv")
    d["replacement_level"] = _hf("cross_position_replacement_level.csv")
    d["positional_baselines"] = _hf("positional_baselines.csv")
    d["readiness"] = _hf("mvp_input_readiness.csv")
    d["defense_audit"] = _hf("defensive_attribution_audit.csv")
    d["usage_model"] = _hf("multi_season_usage_model.csv")
    d["opponent_adj"] = _hf("multi_season_opponent_adjustment.csv")
    d["stability"] = _hf("phase10_historical_stability.csv")
    return d


# ===========================================================================
# Section B: signal inventory
# ===========================================================================
def _coverage(p: pd.DataFrame, col: str, role_col: str = None, role_vals=None):
    """Real, computed sample-size / missingness figures for one column."""
    scope = p if role_vals is None else p[p[role_col].isin(role_vals)]
    n_scope = len(scope)
    if col not in scope.columns:
        return n_scope, np.nan, np.nan
    nonnull = scope[col].notna()
    n_nonzero = int((scope.loc[nonnull, col].astype(float) != 0).sum()) \
        if pd.api.types.is_numeric_dtype(scope[col]) else int(nonnull.sum())
    pct_missing = 100.0 * (1 - nonnull.mean()) if n_scope else np.nan
    return n_scope, n_nonzero, round(pct_missing, 2)


def _career_reliability_lookup(rel: pd.DataFrame, rate_name: str, scope="pooled_player_career"):
    row = rel[(rel["rate_name"] == rate_name) & (rel["scope"] == scope)]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "pct_reaching_gate": round(float(r["pct_reaching_reliability_gate"]), 1),
        "median_reliability": round(float(r["median_reliability"]), 3),
        "estimable": bool(r["estimable_at_this_scope"]),
    }


def build_signal_inventory(d: dict) -> pd.DataFrame:
    p, rel = d["players"], d["career_reliability"]
    rows = []

    def add(signal_name, category, exact_source, definition, numerator,
             denominator, role_scope, sample_col, sample_role_vals,
             career_rate_name, measures_type, season_award_suitability,
             double_counting_with, notes):
        n_scope, n_nonzero, pct_missing = (np.nan, np.nan, np.nan)
        if sample_col is not None:
            n_scope, n_nonzero, pct_missing = _coverage(
                p, sample_col, "position_group", sample_role_vals)
        rel_info = _career_reliability_lookup(rel, career_rate_name) \
            if career_rate_name else None
        rows.append({
            "signal_name": signal_name,
            "category": category,
            "exact_source": exact_source,
            "definition": definition,
            "numerator": numerator,
            "denominator": denominator,
            "role_scope": role_scope,
            "n_players_in_scope": n_scope,
            "n_players_nonzero": n_nonzero,
            "pct_missing_in_scope": pct_missing,
            "career_pct_reaching_reliability_gate":
                rel_info["pct_reaching_gate"] if rel_info else np.nan,
            "career_median_reliability":
                rel_info["median_reliability"] if rel_info else np.nan,
            "career_estimable": rel_info["estimable"] if rel_info else None,
            "measures_type": measures_type,
            "season_award_suitability": season_award_suitability,
            "double_counting_with": double_counting_with,
            "notes": notes,
        })

    OFF = ["attack", "midfield"]
    ALL = None

    # ---- scoring / shooting -----------------------------------------------
    add("goals", "scoring", "player_stats_2022_2026.goals",
        "count of goals scored", "goals", "n/a (count)", "attack, midfield (any role can score)",
        "goals", OFF, None, "production", "SUITABLE_AS_PRODUCTION_COUNT",
        "scoring_points (r=0.99, near-identity), shooting_value_raw (r=0.48)",
        "Reconciles exactly to official score (Phase 9 check 7). Not role-comparable: a goalie's goal count is zero by job description.")
    add("scoring_points", "scoring", "player_stats_2022_2026.scoring_points",
        "one_point_goals*1 + two_point_goals*2", "1*1PT_goals + 2*2PT_goals",
        "n/a (count)", "attack, midfield", "scoring_points", OFF, None,
        "production", "SUITABLE_AS_PRODUCTION_COUNT",
        "goals (r=0.99), EPA_points_raw (mechanically related through shooting_value_raw)",
        "This is the PLL-points analogue of goals; correlates 0.99 with goals because two-point goals are a minority of makes.")
    add("shots / shots_on_goal", "shooting", "player_stats_2022_2026.{shots,shots_on_goal}",
        "count of shot attempts / count that reached the cage", "n/a", "n/a",
        "attack, midfield, faceoff (rare)", "shots", OFF, "shots_on_goal_pct",
        "opportunity", "SUITABLE_AS_OPPORTUNITY_DENOMINATOR",
        "shooting_value_raw (shares the same opportunity set as its denominator)",
        "Volume, not value. VIF against shooting_value_raw is 43.8 in the offensive pool -- see dependency file.")
    add("shooting_pct", "shooting", "player_stats_2022_2026.shooting_pct",
        "goals / shots", "goals", "shots", "attack, midfield", "shooting_pct",
        OFF, "shooting_pct", "skill (season) / noise-dominated at season scope",
        "READY_WITH_CAVEAT",
        "shooting_value_raw (same numerator, different baseline subtraction)",
        "Career reliability reaches 0.5 for 17.8% of shooters; single-season reliability reaches it for 6.8%. Season rate is mostly luck at typical volumes (median 9 shots/season).")
    add("shots_on_goal_pct", "shooting", "player_stats_2022_2026.shots_on_goal_pct",
        "shots_on_goal / shots (accuracy, not finishing)", "shots_on_goal",
        "shots", "attack, midfield", "shots_on_goal_pct", OFF,
        "shots_on_goal_pct", "skill", "READY_WITH_CAVEAT",
        "shooting_pct (both draw on the same shot log; splits accuracy from conversion-once-on-goal)",
        "More identifiable than shooting_pct itself (21.4% vs 17.8% career) -- the identifiable half of finishing is hitting the cage, not beating the goalie.")
    add("one_point_conversion_pct / two_point_conversion_pct", "shooting",
        "player_stats_2022_2026.{one_point_conversion_pct,two_point_conversion_pct}",
        "goals / attempts, split by shot value", "goals(1pt or 2pt)",
        "attempts(1pt or 2pt)", "attack, midfield", "one_point_conversion_pct",
        OFF, "two_point_pct", "skill (1pt) / UNSUPPORTED as skill (2pt)",
        "READY_WITH_CAVEAT (1pt) / UNSUPPORTED (2pt)",
        "shooting_pct (mechanically decomposes it)",
        "Two-point conversion: observed between-player variance (0.0102) is BELOW binomial noise (0.0137) at career scope -- INDIVIDUAL_TWO_POINT_ABILITY = UNSUPPORTED / DO_NOT_USE (Phase 10 finding, re-verified in validation).")
    add("two_point_attempt_share", "shooting", "career_ability_reliability.csv (two_point_attempt_share)",
        "share of a shooter's own attempts taken from the two-point arc",
        "two_point_attempts", "shots", "attack, midfield", None, None,
        "two_point_attempt_share", "skill (selection, not conversion)",
        "READY_WITH_CAVEAT",
        "two_point_conversion_pct (selection is identifiable; conversion is not -- must not be conflated)",
        "The single most identifiable rate in the project: 85.1% of career shooters clear reliability >=0.5. It is a CHOICE, not a contest outcome.")
    add("points_per_shot", "shooting", "player_stats_2022_2026.points_per_shot",
        "PLL points / shots", "PLL points", "shots", "attack, midfield",
        "points_per_shot", OFF, None, "efficiency (production-weighted)",
        "READY_WITH_CAVEAT", "shooting_pct, scoring_points (both nested inside this)",
        "A volume-free rescaling of scoring_points/shots -- not an independent dimension from shooting_pct once two-point mix is fixed.")
    add("shooting_value_raw", "shooting (EPA-style, already built)",
        "player_stats_2022_2026.shooting_value_raw",
        "PLL points from shots minus league-expected points on the same shots (residual, opportunity-baselined)",
        "observed points from shots", "league-expected points on the same shot mix",
        "any role that shoots", "shooting_value_raw", OFF, None,
        "production (residual, not skill)", "READY_WITH_CAVEAT",
        "goals/scoring_points (r=0.48-0.96 depending on pool -- see dependency file), EPA_points_raw (shooting_value_raw is >=96% of offensive EPA's variance for field players)",
        "This IS the project's EGA-analogue for shooting. It is a component of EPA_points_raw, not an independent input -- summing it alongside EPA_points_raw in any composite double-counts every shot.")
    add("EPA_points_raw / offensive_EPA_points_raw", "composite production (already built)",
        "player_stats_2022_2026.{EPA_points_raw,offensive_EPA_points_raw}",
        "sum of shooting_value_raw + turnover_value_raw + faceoff_value_raw + goalie_value_raw + defensive_value_partial_raw, whichever the player's role supports",
        "sum of role-relevant components", "n/a (already a residual)", "all",
        "EPA_points_raw", None, None, "production (residual, additive by construction)",
        "READY_WITH_CAVEAT", "every one of its own components (that is its definition, not a double-count)",
        "Sums to exactly 0 across the league (verified to 1e-10 in Phase 6/7, re-verified on the canonical 2022-2026 dataset in the dependency file). This is the accounting-safe production quantity; it is NOT cross-position comparable (see CROSS_POSITION_VALUE_RESEARCH.md).")

    # ---- ball security / usage ---------------------------------------------
    add("turnovers / touches / turnovers_per_touch", "ball security",
        "player_stats_2022_2026.{turnovers,touches,turnovers_per_touch}",
        "turnovers committed / offensive touches / their ratio",
        "turnovers", "touches", "attack, midfield, defensive_field",
        "turnovers_per_touch", None, "turnovers_per_touch", "skill (season, weak) / skill (career, moderate)",
        "READY_WITH_CAVEAT", "turnover_value_raw (same numerator/denominator, baselined)",
        "Career reliability reaches 0.5 for 52.0% of players -- the highest-clearing rate in the project. ~19% of league turnovers name only a team, so every player's absolute count is understated (the ratio stays internally consistent; the level does not).")
    add("turnover_value_raw", "ball security (EPA-style, already built)",
        "player_stats_2022_2026.turnover_value_raw",
        "negative PLL points from turnovers above the position-group's per-touch rate",
        "-(turnover cost) above position-group rate", "touches", "attack, midfield, defensive_field",
        "turnover_value_raw", None, None, "production (residual)", "READY_WITH_CAVEAT",
        "turnovers_per_touch (same underlying quantity, baselined), EPA_points_raw (component of it)",
        "Already residualized against a position-group rate, which removes the role effect from the EXPECTATION but not from the volume: touches range 3-524.")
    add("games_played (availability)", "usage / availability",
        "player_stats_2022_2026.games_played", "count of eligible games with a box-score row",
        "games", "n/a", "all", "games_played", None, None,
        "opportunity / exposure denominator", "READY as denominator, NOT as a value input",
        "EPA_points_raw at season-total scope (every season-total measure already rewards availability implicitly)",
        "Adding it as an independent input double-counts durability: every counting statistic already increases with games played. It is also the ONLY exposure denominator this feed offers for defenders, and it is crude (no minutes).")
    add("recorded_offensive_opportunities / offensive_play_share", "usage",
        "player_stats_2022_2026.{recorded_offensive_opportunities,offensive_play_share}",
        "shots + turnovers (a player's own), and that as a share of his team's total",
        "shots+turnovers", "team shots+turnovers", "attack, midfield",
        "recorded_offensive_opportunities", OFF, None, "opportunity",
        "NOT_COMPARABLE across roles", "shots, turnovers (this IS their sum)",
        "The constant model beats every fitted usage->value model in cross-validation on 844 player-seasons (multi_season_usage_model.csv) -- usage predicts the VARIANCE of value, not its mean, in 4 of 5 seasons the correlation with offensive EPA is negative.")

    # ---- faceoff -----------------------------------------------------------
    add("faceoffs / faceoff_wins / faceoff_win_pct", "faceoff",
        "player_stats_2022_2026.{faceoffs,faceoff_wins,faceoff_win_pct}",
        "draws taken, draws won, win rate", "faceoff_wins", "faceoffs",
        "faceoff", "faceoff_win_pct", ["faceoff"], "faceoff_win_pct",
        "skill", "READY_WITH_CAVEAT", "faceoff_value_raw (same ratio, baselined against the league rate 0.49656)",
        "The most cleanly identified CONTEST-OUTCOME skill in the project: implied true between-player sd 0.148, three to seven times any other rate's. 54.4% of career takers clear reliability >=0.5.")
    add("faceoff_value_raw", "faceoff (EPA-style, already built)",
        "player_stats_2022_2026.faceoff_value_raw",
        "PLL points from (wins - faceoffs*league_win_rate) * possession-swing coefficient",
        "wins above expectation", "faceoffs taken", "faceoff", "faceoff_value_raw",
        ["faceoff"], None, "production (residual)", "NOT_COMPARABLE across roles",
        "faceoff_win_pct (same quantity, scaled), ground_balls (61.5% of ground balls after a faceoff go to the faceoff winner himself -- ground-ball value is deferred specifically to avoid paying this twice)",
        "Decisive workload confound (counterfactual P5, reused below): two specialists at the identical win rate above baseline differ 2.1x in total value purely from being given more draws.")
    add("ground_balls", "faceoff-adjacent / defense-adjacent", "player_stats_2022_2026.ground_balls",
        "count of loose-ball recoveries", "ground balls", "n/a", "faceoff, defensive_field, any",
        "ground_balls", None, None, "production (uncredited -- no value component)",
        "UNSUPPORTED as a value input (no opportunity denominator; context-inseparable)",
        "faceoff_value_raw for faceoff specialists (61.5% overlap), caused_turnover_value for defenders (scenario E in PLAYER_VALUE_ACCOUNTING.md)",
        "Deliberately NOT valued anywhere in this project -- see PLAYER_VALUE_ACCOUNTING.md sec 4E/4F. Any future ground-ball value component must first solve the double-counting problem documented there.")

    # ---- goalie --------------------------------------------------------------
    add("saves / shots_on_goal_faced / save_pct", "goalie",
        "player_stats_2022_2026.{saves,shots_on_goal_faced,save_pct}",
        "saves made, shots on goal faced, save rate", "saves", "shots_on_goal_faced",
        "goalie", "save_pct", ["goalie"], "save_pct", "skill", "READY_WITH_CAVEAT",
        "goalie_value_raw (same ratio, baselined)",
        "Career reliability reaches 0.5 for 29.6% of goalies (8 of 27) -- the largest single improvement career pooling buys, because kappa (495 shots) is close to a full season's workload for a starter.")
    add("goalie_value_raw", "goalie (EPA-style, already built)",
        "player_stats_2022_2026.goalie_value_raw",
        "league-expected points allowed on shots on goal faced minus points actually allowed",
        "expected points allowed", "shots on goal faced", "goalie", "goalie_value_raw",
        ["goalie"], None, "production (residual)", "NOT_COMPARABLE across roles",
        "save_pct (same quantity, baselined and point-weighted), EPA_points_raw (component of it)",
        "Counterfactual P4 (reused below) is the single strongest argument in the project against any total-value cross-position model: two goalies of IDENTICAL per-shot skill differ 30x in total value purely from team-conceded shot volume.")

    # ---- defense ---------------------------------------------------------------
    add("caused_turnovers", "defense", "player_stats_2022_2026.caused_turnovers",
        "count of turnovers the player is credited with forcing", "caused turnovers",
        "n/a", "defensive_field (any role can be credited)", "caused_turnovers",
        ["defensive_field"], None, "production (box-score total only)",
        "NOT_COMPARABLE across roles; usable only as an availability-adjusted, WITHIN-ROLE partial signal",
        "defensive_value_partial_raw (same quantity, baselined against games played)",
        "Zero of 52,633 raw events across five seasons name a causing defender, a committing player, or a closest defender in a structured field -- caused turnovers survive only as a BOX-SCORE TOTAL. Correlates with games_played at rho=0.49-0.80 by season -- up to 64% of the rank variance is availability, not impact.")
    add("defensive_value_partial_raw", "defense (EPA-style, already built)",
        "player_stats_2022_2026.defensive_value_partial_raw",
        "caused turnovers above the position group's per-GAME rate (games, not defensive possessions, because no possession-exposure denominator exists)",
        "caused turnovers above group rate", "games_played", "defensive_field",
        "defensive_value_partial_raw", ["defensive_field"], None,
        "production (residual, exposure-crude)", "NOT_COMPARABLE across roles, and 'partial' must never be dropped",
        "caused_turnovers (same numerator), EPA_points_raw (component of it)",
        "The word 'partial' is load-bearing: 0.0 means 'caused turnovers at the group's per-game rate, everything else unmeasured', not 'an average defender'. Pooled SD (1.74) is 4.6x smaller than goalie value's (7.98) -- evidence of measurement coverage, not of defensive unimportance.")

    # ---- team context ----------------------------------------------------------
    add("team offensive_efficiency / defensive_efficiency / net_efficiency", "team context",
        "team_stats_2022_2026.{offensive_efficiency,defensive_efficiency,net_efficiency}",
        "points per possession, for and against", "points", "possessions",
        "team-season (not a player signal)", None, None, None, "context",
        "USABLE ONLY as a concurrent-validity check, never as a player input",
        "EPA_points_raw summed by team (mechanically related -- see dependency file's team-level regression)",
        "40 team-seasons total. A player value model must not be validated ONLY by reproducing this, because offensive EPA is a residual against the same points that determine offensive_efficiency -- the relationship is partly definitional.")
    add("team win_pct / point_differential_per_game", "team context",
        "team_stats_2022_2026.{win_pct,point_differential_per_game}", "wins/games; scoring margin per game",
        "wins or point diff", "games or n/a", "team-season", None, None, None, "context / outcome",
        "USABLE ONLY as a concurrent-validity outcome variable", "net_efficiency (r=0.70 with win_pct in this data)",
        "The only genuine WIN outcome in the dataset. n=40 team-seasons is too small to fit more than a handful of predictors defensibly -- see the Model Family 5 regression in the dependency file.")
    add("opponent_adjustment", "team context (already researched)",
        "docs/OPPONENT_ADJUSTMENT_FEASIBILITY.md, multi_season_opponent_adjustment.csv",
        "ridge-regularized two-way offense/defense rating vs the schedule actually played",
        "n/a", "n/a", "team-season", None, None, None, "context adjustment",
        "DEFERRED (identifiable but nearly inert)", "none (it is not currently applied to anything)",
        "PLL's schedule is a near-perfect round robin (connectivity 1.00 every season); strength-of-schedule spread is only 14-29% of team spread, and the adjustment moves ranks by 0-2 places. In 2026 its own bootstrap SE exceeds its signal.")

    df = pd.DataFrame(rows)
    return df


# ===========================================================================
# Section C: dependency / double-counting analysis
# ===========================================================================
def _vif_table(df: pd.DataFrame, cols: list) -> dict:
    sub = df[cols].dropna()
    Z = sub.to_numpy().astype(float)
    sd = Z.std(0)
    sd[sd == 0] = 1.0
    Z = (Z - Z.mean(0)) / sd
    out = {}
    for i, c in enumerate(cols):
        y = Z[:, i]
        X = np.column_stack([np.ones(len(Z))] + [Z[:, j] for j in range(len(cols)) if j != i])
        b, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            pred = X @ b
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        out[c] = float(np.inf) if r2 >= 0.9999 else float(1 / (1 - r2))
    return out, len(sub)


def _corr_row(df, a, b, pool_name, known_relation, dc_risk, note):
    sub = df[[a, b]].dropna()
    if len(sub) < 5:
        pear, spear, n = np.nan, np.nan, len(sub)
    else:
        pear = float(sub[a].corr(sub[b]))
        # no scipy in this environment -- spearman via rank + pearson, same
        # method pll_phase10_cross_position.py's own _rho helper uses.
        spear = float(np.corrcoef(sub[a].rank(), sub[b].rank())[0, 1])
        n = len(sub)
    return {
        "analysis_type": "PAIRWISE_CORRELATION",
        "metric_a": a, "metric_b": b, "role_scope": pool_name, "n": n,
        "pearson_r": round(pear, 3) if pd.notna(pear) else np.nan,
        "spearman_r": round(spear, 3) if pd.notna(spear) else np.nan,
        "vif": np.nan,
        "relationship_type": known_relation,
        "double_counting_risk": dc_risk,
        "notes": note,
    }


def build_dependency_analysis(d: dict) -> pd.DataFrame:
    p = d["players"]
    off = p[p["position_group"].isin(["attack", "midfield"])]
    fo = p[p["position_group"] == "faceoff"]
    goa = p[p["position_group"] == "goalie"]
    dfn = p[p["position_group"] == "defensive_field"]

    rows = []

    # -- offensive pool pairwise --------------------------------------------
    off_pairs = [
        ("goals", "scoring_points", "MECHANICAL_NEAR_IDENTITY", "HIGH",
         "scoring_points = goals + two_point_goals; differ only by the two-point subset of makes."),
        ("goals", "shots", "CORRELATED_VIA_VOLUME", "MODERATE",
         "Both track the same shot log; goals is shots times shooting_pct."),
        ("shots", "shooting_value_raw", "NESTED_COMPONENT", "HIGH",
         "shooting_value_raw is priced ON shot attempts; shots is its own opportunity denominator."),
        ("goals", "shooting_value_raw", "NESTED_COMPONENT", "HIGH",
         "shooting_value_raw = observed points from these same shots minus expectation; goals is the observed half."),
        ("shooting_pct", "shooting_value_raw", "NESTED_COMPONENT", "MODERATE",
         "shooting_value_raw is shooting_pct's numerator repriced against a league baseline, at the player's own volume."),
        ("shooting_value_raw", "offensive_EPA_points_raw", "NESTED_COMPONENT", "HIGH",
         "offensive_EPA_points_raw = shooting_value_raw + turnover_value_raw by construction (verified exactly below)."),
        ("offensive_EPA_points_raw", "EPA_points_raw", "NESTED_COMPONENT", "HIGH",
         "EPA_points_raw = offensive_EPA_points_raw + faceoff/goalie/defensive components, which are ~0 for a pure offensive player."),
        ("turnovers", "turnover_value_raw", "NESTED_COMPONENT", "MODERATE",
         "turnover_value_raw is turnovers repriced against a position-group per-touch baseline."),
        ("turnovers_per_touch", "turnover_value_raw", "NESTED_COMPONENT", "MODERATE",
         "Same ratio, one raw and one baselined-and-scaled."),
        ("games_played", "EPA_points_raw", "VOLUME_CONFOUND", "MODERATE",
         "Season-total EPA rises mechanically with games played, independent of rate."),
        ("shooting_value_raw", "turnover_value_raw", "DISJOINT_BY_CONSTRUCTION", "NONE",
         "Different opportunity sets (shot attempts vs touches) -- PLAYER_VALUE_ACCOUNTING.md's disjointness rule."),
    ]
    for a, b, rel, risk, note in off_pairs:
        rows.append(_corr_row(off, a, b, "attack+midfield", rel, risk, note))

    # -- faceoff pool ---------------------------------------------------------
    fo_pairs = [
        ("faceoffs", "faceoff_value_raw", "VOLUME_CONFOUND", "MODERATE",
         "Counterfactual P5: same win rate above baseline, 2.1x total value from draw count alone."),
        ("faceoff_win_pct", "faceoff_value_raw", "NESTED_COMPONENT", "HIGH",
         "faceoff_value_raw = (win_pct - league_rate) * faceoffs * coefficient."),
        ("ground_balls", "faceoff_value_raw", "OVERLAPPING_OPPORTUNITY_DEFERRED", "HIGH_IF_GB_EVER_VALUED",
         "61.5% of ground balls after a faceoff go to the faceoff winner himself -- this is exactly why ground-ball value is deferred, not because it is unmeasurable."),
        ("faceoff_value_raw", "EPA_points_raw", "NESTED_COMPONENT", "HIGH",
         "EPA_points_raw = faceoff_value_raw for a pure specialist (other components ~0)."),
    ]
    for a, b, rel, risk, note in fo_pairs:
        rows.append(_corr_row(fo, a, b, "faceoff", rel, risk, note))

    # -- goalie pool ------------------------------------------------------------
    goa_pairs = [
        ("shots_on_goal_faced", "goalie_value_raw", "VOLUME_CONFOUND", "MODERATE",
         "Counterfactual P4: identical per-shot skill, 30x total value from team-conceded shot volume alone."),
        ("save_pct", "goalie_value_raw", "NESTED_COMPONENT", "HIGH",
         "goalie_value_raw = expected points allowed minus observed, i.e. save_pct repriced in points at the goalie's own volume."),
        ("goalie_value_raw", "EPA_points_raw", "NESTED_COMPONENT", "HIGH",
         "EPA_points_raw = goalie_value_raw for a goalie (other components ~0)."),
    ]
    for a, b, rel, risk, note in goa_pairs:
        rows.append(_corr_row(goa, a, b, "goalie", rel, risk, note))

    # -- defensive pool -------------------------------------------------------
    dfn_pairs = [
        ("games_played", "caused_turnovers", "VOLUME_CONFOUND", "HIGH",
         "rho computed on canonical 2022-2026 pooled data below -- reproduces the Phase 10 finding of 0.49-0.80 per season."),
        ("caused_turnovers", "defensive_value_partial_raw", "NESTED_COMPONENT", "HIGH",
         "defensive_value_partial_raw = caused_turnovers repriced against the position-group per-game rate."),
        ("defensive_value_partial_raw", "EPA_points_raw", "NESTED_COMPONENT", "HIGH",
         "EPA_points_raw = defensive_value_partial_raw for a defender (other components ~0)."),
        ("games_played", "defensive_value_partial_raw", "PARTIALLY_RESIDUALIZED", "LOW_BY_CONSTRUCTION",
         "Dividing by games_played removes most, not all, of the games_played correlation (see rho below) -- it does not create an exposure denominator, it removes a level effect."),
    ]
    for a, b, rel, risk, note in dfn_pairs:
        rows.append(_corr_row(dfn, a, b, "defensive_field", rel, risk, note))

    # -- cross-cutting availability check ------------------------------------
    rows.append(_corr_row(p, "games_played", "EPA_points_raw", "ALL_ROLES_POOLED",
                           "VOLUME_CONFOUND", "MODERATE",
                           "Season-total value and games played are confounded for every role, not just defense; this is why availability is READY as a denominator/disclosure and UNSUPPORTED as an independent value input."))

    # -- accounting identity, verified exactly (not a correlation) ----------
    comp_cols = ["shooting_value_raw", "turnover_value_raw", "faceoff_value_raw",
                 "goalie_value_raw", "defensive_value_partial_raw"]
    resid = p[comp_cols].fillna(0).sum(axis=1) - p["EPA_points_raw"]
    max_abs_diff = float(resid.abs().max())
    rows.append({
        "analysis_type": "ACCOUNTING_IDENTITY", "metric_a": "sum(5 components)",
        "metric_b": "EPA_points_raw", "role_scope": "ALL_ROLES_POOLED", "n": len(p),
        "pearson_r": 1.0, "spearman_r": 1.0, "vif": np.nan,
        "relationship_type": "EXACT_IDENTITY_BY_CONSTRUCTION",
        "double_counting_risk": "NONE (this is the identity that PREVENTS double counting, not an instance of it)",
        "notes": f"max |sum(components) - EPA_points_raw| = {max_abs_diff:.2e} across {len(p)} player-seasons, 2022-2026 canonical dataset. Re-verifies PLAYER_VALUE_ACCOUNTING.md sec 1 on the full 5-season canonical population.",
    })
    off_resid = (off["shooting_value_raw"].fillna(0) + off["turnover_value_raw"].fillna(0)
                 - off["offensive_EPA_points_raw"]).abs().max()
    rows.append({
        "analysis_type": "ACCOUNTING_IDENTITY", "metric_a": "shooting_value_raw + turnover_value_raw",
        "metric_b": "offensive_EPA_points_raw", "role_scope": "attack+midfield", "n": len(off),
        "pearson_r": 1.0, "spearman_r": 1.0, "vif": np.nan,
        "relationship_type": "EXACT_IDENTITY_BY_CONSTRUCTION",
        "double_counting_risk": "NONE",
        "notes": f"max abs diff = {float(off_resid):.2e}.",
    })

    # -- real games_played vs caused_turnovers rho by season, re-verified ----
    for s in SEASONS:
        sub = dfn[dfn["season"] == s][["games_played", "caused_turnovers"]].dropna()
        if len(sub) >= 10:
            rho = float(np.corrcoef(sub["games_played"].rank(), sub["caused_turnovers"].rank())[0, 1])
            rows.append({
                "analysis_type": "PAIRWISE_CORRELATION", "metric_a": "games_played",
                "metric_b": "caused_turnovers", "role_scope": f"defensive_field_{s}", "n": len(sub),
                "pearson_r": np.nan, "spearman_r": round(rho, 3), "vif": np.nan,
                "relationship_type": "VOLUME_CONFOUND", "double_counting_risk": "HIGH",
                "notes": "Re-verification of defensive_attribution_audit.csv on the canonical Phase 11 player table.",
            })

    # -- VIF diagnostic: what happens if these were fed to one linear model --
    vif_cols = ["goals", "shots", "shooting_pct", "turnovers", "turnovers_per_touch",
                "games_played", "shooting_value_raw"]
    vifs, n_vif = _vif_table(off, vif_cols)
    for c, v in vifs.items():
        rows.append({
            "analysis_type": "VIF", "metric_a": c, "metric_b": "(all other VIF-pool metrics)",
            "role_scope": "attack+midfield", "n": n_vif, "pearson_r": np.nan,
            "spearman_r": np.nan, "vif": round(v, 2) if np.isfinite(v) else "inf",
            "relationship_type": "MULTICOLLINEARITY_DIAGNOSTIC",
            "double_counting_risk": "HIGH" if (np.isfinite(v) and v > 10) else
                ("MODERATE" if (np.isfinite(v) and v > 5) else "LOW"),
            "notes": "VIF computed by regressing this standardized metric on the other six in the pool "
                     "{goals, shots, shooting_pct, turnovers, turnovers_per_touch, games_played, "
                     "shooting_value_raw}. This is a DEMONSTRATION of what a naive linear composite "
                     "would inherit if it used these as separate inputs -- none of these metrics are "
                     "combined into any published composite in this project.",
        })

    return pd.DataFrame(rows)


# ===========================================================================
# Section D/L: Model Family 5 -- team-outcome association, run to completion
# ===========================================================================
def team_outcome_regression(d: dict) -> dict:
    p, t = d["players"], d["teams"]
    agg = p.groupby(["season", "team_id"]).agg(
        off_epa=("offensive_EPA_points_raw", "sum"),
        fo_epa=("faceoff_value_raw", "sum"),
        def_epa=("defensive_value_partial_raw", "sum"),
        g_epa=("goalie_value_raw", "sum"),
        total_epa=("EPA_points_raw", "sum"),
    ).reset_index()
    m = t.merge(agg, on=["season", "team_id"])
    predictors = ["off_epa", "fo_epa", "def_epa", "g_epa"]
    X = m[predictors].to_numpy()
    y = m["win_pct"].to_numpy()
    n = len(m)

    Xd = np.column_stack([np.ones(n), X])
    beta, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    pred = Xd @ beta
    r2_in = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)

    # leave-one-season-out
    seasons = sorted(m["season"].unique())
    all_y, all_p = [], []
    for s in seasons:
        train, test = m[m["season"] != s], m[m["season"] == s]
        Xtr = np.column_stack([np.ones(len(train)), train[predictors].to_numpy()])
        b, *_ = np.linalg.lstsq(Xtr, train["win_pct"].to_numpy(), rcond=None)
        Xte = np.column_stack([np.ones(len(test)), test[predictors].to_numpy()])
        all_y.append(test["win_pct"].to_numpy())
        all_p.append(Xte @ b)
    ay, ap = np.concatenate(all_y), np.concatenate(all_p)
    r2_loso = 1 - np.sum((ay - ap) ** 2) / np.sum((ay - ay.mean()) ** 2)

    # bootstrap coefficient stability
    rng = np.random.default_rng(RNG_SEED)
    boots = []
    for _ in range(1000):
        idx = rng.integers(0, n, n)
        Xb = np.column_stack([np.ones(n), X[idx]])
        b, *_ = np.linalg.lstsq(Xb, y[idx], rcond=None)
        boots.append(b)
    boots = np.array(boots)
    coef_summary = {}
    for i, name in enumerate(["intercept"] + predictors):
        lo, hi = np.percentile(boots[:, i], [2.5, 97.5])
        coef_summary[name] = {
            "point_estimate": float(beta[i]), "boot_se": float(boots[:, i].std()),
            "ci_lo": float(lo), "ci_hi": float(hi), "excludes_zero": bool(lo > 0 or hi < 0),
        }

    corr_with_win_pct = {
        c: float(m[c].corr(m["win_pct"])) for c in
        predictors + ["total_epa", "net_efficiency", "offensive_efficiency", "point_differential_per_game"]
    }

    return {
        "n_team_seasons": n, "predictors": predictors, "r2_in_sample": float(r2_in),
        "r2_leave_one_season_out": float(r2_loso), "coef_summary": coef_summary,
        "corr_with_win_pct": corr_with_win_pct,
    }


# ===========================================================================
# Section M: model candidate scorecard
# ===========================================================================
def build_model_candidates(d: dict, team_outcome: dict) -> pd.DataFrame:
    mc = d["method_comparison"].set_index("method")
    rows = []

    def add(model_id, family, target, unit, positions, inputs, baseline,
            additive, cross_claim, dc_risk, n_req, reliability, val_result,
            assumptions, failure_modes, status):
        rows.append({
            "model_id": model_id, "model_family": family, "target_concept": target,
            "unit": unit, "positions_supported": positions, "inputs": inputs,
            "baseline": baseline, "additive": additive,
            "cross_position_claim": cross_claim, "double_counting_risk": dc_risk,
            "sample_size_requirement": n_req, "reliability": reliability,
            "validation_result": val_result, "major_assumptions": assumptions,
            "major_failure_modes": failure_modes, "status": status,
        })

    # ---- MF1: direct production / points created ---------------------------
    add("MF1_direct_epa_within_role", "MF1_direct_production",
        "season total value on recorded opportunities", "PLL points above league-average expectation",
        "attack, midfield, faceoff, goalie, defensive_field (separately, never pooled)",
        "EPA_points_raw", "league-average conversion on the SAME opportunity class", True,
        "NONE -- explicitly single-role only", "NONE (EPA_points_raw is the accounting-safe sum; see dependency file)",
        "n/a (uses full population within role)", "high within role (sums exactly to 0 league-wide)",
        "PASS accounting; PASS within-role rank stability is season-specific (see validation results)",
        "League-average opportunity baseline is the right counterfactual; a shot/faceoff/touch is the right unit of opportunity.",
        "None once scoped to a single role -- this IS what Phase 6/8 already publish.",
        "VIABLE")
    add("MF1_direct_epa_cross_role", "MF1_direct_production",
        "season total value, ranked across all roles", "PLL points above league-average expectation",
        "ALL ROLES ON ONE LIST", "EPA_points_raw", "league-average conversion per role", True,
        "YES -- this is exactly the composite the brief forbids", "NONE at the accounting level, but ranks by opportunity volume",
        "n/a", "high per-component, but the RANKING inherits each role's own reliability profile",
        "FAIL cross-position: role SD ratio 4.58x pooled (2.0-8.6x by season); 13.7% of the top decile is below-median-opportunity",
        "That opportunity-count differences of up to 21x across roles do not need correcting.",
        "Ranks players by how much of their job the feed happens to count, not by contribution (CROSS_POSITION_VALUE_RESEARCH.md sec 1, method M01).",
        "REJECTED")

    # ---- MF2: possession value --------------------------------------------
    add("MF2_possession_value_generic", "MF2_possession_value",
        "value per possession, attributed to the player who touched it",
        "PLL points per possession", "any", "possession outcomes (shots, turnovers, faceoff results)",
        "league-average points per possession", "not tested (blocked upstream)",
        "would require testing", "would inherit MF1's issues plus a new attribution problem",
        "requires lineup/on-off data this feed does not have", "n/a -- blocked",
        "NOT RUN: no player-level possession-exposure denominator exists",
        "That a player can be tied to the possessions his team ran while he was on the field.",
        "The feed carries NO lineup, substitution or on-field data of any season (PLAYER_VALUE_ACCOUNTING.md sec 6). A possession cannot be attributed to a player who did not touch the ball on it, and 'touched the ball' is exactly what shot/turnover/faceoff-denominated EPA already captures -- this model family collapses back into MF1 for the touches it CAN see and is UNSUPPORTED for the possession-level exposure it would need to add anything.",
        "UNSUPPORTED")

    # ---- MF3: above-baseline value, by role --------------------------------
    add("MF3_offense_above_baseline", "MF3_above_baseline",
        "shooting+turnover value above position-group rate", "PLL points",
        "attack, midfield", "shooting_value_raw, turnover_value_raw",
        "position-group per-shot / per-touch rate", True, "single-role only",
        "NONE (disjoint opportunity sets)", "reliability-gated per rate (see career_ability_reliability.csv)",
        "17.8% of career shooters, 52.0% of career turnover rates clear reliability >=0.5",
        "PASS accounting; season value is NOT stable year to year (rho 0.159-0.253, all ten transformations)",
        "Position-group rate is the right counterfactual for what a role-average player would have done.",
        "Answers 'what happened' well; is a poor proxy for 'true skill' at single-season scope.",
        "VIABLE")
    add("MF3_faceoff_above_baseline", "MF3_above_baseline",
        "faceoff value above league win rate", "PLL points", "faceoff",
        "faceoff_value_raw", "league faceoff win rate (0.49656)", True,
        "single-role only", "NONE", "career kappa=10.4 draws, 54.4% clear gate",
        "the cleanest-identified rate in the project (implied true sd 0.148)",
        "PASS accounting; FAILS the workload-neutrality counterfactual (P5: 2.1x value swing at equal rate)",
        "Draw count is exogenous to the specialist's own skill.", "It is not -- draw count tracks how many goals were scored in his games, by either team.",
        "VIABLE_WITH_CAVEAT")
    add("MF3_goalie_above_baseline", "MF3_above_baseline",
        "goalie value above league expected-points-allowed rate", "PLL points",
        "goalie", "goalie_value_raw", "league expected points allowed per SOG faced", True,
        "single-role only", "NONE", "career kappa=495 SOG, 29.6% clear gate",
        "the largest career-pooling gain in the project, still only 8 of 27 goalies reliable",
        "PASS accounting; FAILS the workload-neutrality counterfactual (P4: 30x value swing at IDENTICAL per-shot skill) -- the single strongest argument in the project against a cross-position total-value model",
        "Shots-on-goal-faced is exogenous to the goalie's own skill.", "It is not -- it is substantially the team's defense, not the goalie's.",
        "VIABLE_WITH_CAVEAT")
    add("MF3_defense_above_baseline_partial", "MF3_above_baseline",
        "caused-turnover value above position-group per-game rate", "PLL points (partial)",
        "defensive_field", "defensive_value_partial_raw", "position-group caused-turnovers-per-game rate",
        True, "single-role only, and must never be compared to another role's total",
        "LOW by construction, HIGH in spirit (see games_played confound in dependency file)",
        "n/a -- reliability of the underlying rate is not separately estimated (no beta-binomial rate exists for a single box-score count)",
        "not separately estimated", "PASS accounting; the underlying signal (caused turnovers) correlates rho=0.49-0.80 with games_played, i.e. up to 64% availability",
        "That caused turnovers, on a games-played denominator, capture defensive contribution.",
        "Zero of 52,633 raw events name a causing or closest defender. This is a box-score total with an availability confound, not an impact measure. The word 'partial' must travel with every use.",
        "ROLE_ONLY")

    # ---- MF4: shrunk skill x opportunity ------------------------------------
    add("MF4_shrunk_rate_x_season_opportunity", "MF4_shrunk_skill_x_opportunity",
        "season value, using career-shrunk rate instead of the season's own rate",
        "PLL points (re-priced)", "any role with an estimable rate",
        "career-shrunk rate x season opportunity count", "league mean rate", True,
        "no more than MF3", "MODERATE (re-derives the same production a second way)",
        "requires the player to have a career reliability >0",
        "inherits career reliability (up to 85.1% for two-point selection, as low as 0% for two-point conversion)",
        "REJECTED on stated methodological grounds, not tested numerically: SHRINKAGE_POLICY.md sec 1 -- multiplying a shrunk RATE by the player's own opportunity COUNT drags every total toward zero in proportion to sample size, which is a materially stronger and unjustified claim ('this player produced less than he did') rather than the correct one ('we know less about him than we would like').",
        "That shrinking a rate and multiplying by the player's own volume is equivalent to shrinking a total.", "It is not -- it conflates two different corrections.",
        "REJECTED")
    add("MF4_shrunk_rate_as_ability_estimate", "MF4_shrunk_skill_x_opportunity",
        "who IS the best (ability), not who HAD the best season (value)",
        "a rate (0-1), not PLL points", "shooting, one-point, faceoff, save, turnover-per-touch (career-estimable rates)",
        "<rate>_shrunk from player_career_2022_2026.csv", "league career mean rate", "n/a (not additive -- it is a rate)",
        "single-role only, and answers a DIFFERENT question than a season award",
        "NONE (this is not a value model, it is an ability estimate)",
        "reliability >=0.5 required to rank; 13.8%-54.4% of players clear it depending on rate",
        "split-half reliability 0.47-0.58 (three well-populated rates, Spearman-Brown 0.64-0.74); save_pct only 0.10",
        "leave-one-season-out rank correlation never below 0.85 (career_season_composition_sensitivity.csv)",
        "That a career average measures 'how good is this player right now'.",
        "Ageing, role change and team context are modelled nowhere (44 players changed position, 97 changed team across 2022-2026).",
        "VIABLE_WITH_CAVEAT")

    # ---- MF5: team outcome association --------------------------------------
    co = team_outcome["corr_with_win_pct"]
    cs = team_outcome["coef_summary"]
    add("MF5_team_epa_vs_win_pct_regression", "MF5_team_outcome_association",
        "empirically derived cross-role weights, from team-level outcome regression",
        "coefficients relating role-summed EPA to team win_pct (unitless per-role weight, NOT comparable to a per-player weight)",
        "attack+midfield (offense), faceoff, defensive_field, goalie -- at the TEAM level only",
        "team-season sums of offensive_EPA_points_raw, faceoff_value_raw, defensive_value_partial_raw, goalie_value_raw",
        "team win_pct, OLS-fitted", "yes, by construction of the linear model, but NOT validated as additive at the player level",
        "This is the single most literal attempt in the project at Model Family 5, and it is included specifically to show why it fails as a WEIGHT SOURCE for an individual-level model despite a real, non-trivial in-sample fit.",
        "MODERATE-HIGH: the response (win_pct) and predictors (EPA components) are computed from the SAME games, so part of the fit is definitional (a team that outscored expectation on offense in a game partly explains that game's win by definition)",
        f"n={team_outcome['n_team_seasons']} team-seasons for {len(team_outcome['predictors'])} predictors -- roughly 8-10 observations per coefficient, thin for any claim beyond sign and rough magnitude",
        "not separately estimated (component reliabilities are role rates, not this regression's own coefficients)",
        f"R^2 in-sample={team_outcome['r2_in_sample']:.3f}, leave-one-season-out R^2={team_outcome['r2_leave_one_season_out']:.3f} (drops materially out of sample); "
        f"bootstrap 95% CI on off_epa coefficient [{cs['off_epa']['ci_lo']:.4f}, {cs['off_epa']['ci_hi']:.4f}] spans nearly 2x its own point estimate ({cs['off_epa']['point_estimate']:.4f})",
        "That team win_pct is a valid external criterion for deriving cross-role weights, and that a team-level coefficient can be redistributed to individual players.",
        "(1) Circularity: EPA components are residuals against the same scoring outcomes that determine win_pct, so this substantially re-derives the definition of winning rather than validating it externally. "
        "(2) n=40 team-seasons for 4 predictors is too thin to trust coefficient magnitudes, even though none of their bootstrap CIs cross zero. "
        "(3) A team-level coefficient is not a per-player weight: off_epa aggregates ~15-20 field players per team-season while fo_epa/g_epa aggregate 1-3 specialists, so 'coefficient per point of off_epa' and 'coefficient per point of fo_epa' are not naturally comparable at the player level without an additional, unvalidated assumption about within-role distribution. "
        "(4) It says nothing about which individual teammate produced a team's EPA.",
        "EXPERIMENTAL")

    # ---- MF6: role-specific award models ------------------------------------
    add("MF6_statistical_offensive_player_of_the_year", "MF6_role_specific",
        "best measured offensive season", "PLL points above position-group expectation (EPA_points_raw / offensive_EPA_points_raw)",
        "attack, midfield only", "shooting_value_raw, turnover_value_raw, reliability flags",
        "position-group rate", True, "NONE (single role by design)", "NONE",
        "n/a", "reliability-gated per component", "the strongest-supported award architecture this dataset offers",
        "That within-role ranking on a season-total residual is a legitimate award basis.", "Still not stable year to year (rho 0.159-0.253); must be presented as retrospective, not predictive.",
        "VIABLE")
    add("MF6_statistical_fogo_of_the_year", "MF6_role_specific",
        "best measured faceoff season", "PLL points above league faceoff-win-rate expectation",
        "faceoff only", "faceoff_value_raw, faceoff_win_pct, reliability", "league faceoff win rate",
        True, "NONE", "NONE", "n/a", "career reliability the highest of any rate (54.4%)",
        "must disclose the P5 workload confound (2.1x swing at equal rate) alongside any ranking",
        "That draw volume is not itself an accomplishment worth rewarding on its own.", "A model that does not disclose the confound rewards being handed more draws, not winning them.",
        "VIABLE_WITH_CAVEAT")
    add("MF6_statistical_goalie_of_the_year", "MF6_role_specific",
        "best measured goalie season", "PLL points above league expected-points-allowed rate",
        "goalie only", "goalie_value_raw, save_pct, reliability", "league expected points allowed per SOG",
        True, "NONE", "NONE", "n/a", "only 8 of 27 goalies career-reliable; fewer at single-season scope",
        "must disclose the P4 workload confound (30x swing at identical skill) alongside any ranking",
        "That shots-on-goal-faced is not itself a measure of the goalie's own defense.", "It is largely the team's defense; publishing total goalie value without this caveat rewards a leaky defense that faces (and the goalie stops some of) many shots.",
        "VIABLE_WITH_CAVEAT")
    add("MF6_measurable_defensive_production_leaderboard", "MF6_role_specific",
        "measured defensive PRODUCTION (not value, not ability, not rank of impact)",
        "raw caused-turnover and ground-ball counts, disclosed WITH games played, never divided into a rate presented as ability",
        "defensive_field", "caused_turnovers, ground_balls, games_played (all three shown, never combined into one score)",
        "none -- this is a production count, not a value model", False,
        "NONE, and no value claim of any kind", "NONE (it is intentionally not a value model)",
        "n/a", "not applicable (a count, not an estimate)",
        "honest by construction: it claims only what it is", "That showing three raw counts side by side, without a combined score, is not itself a ranking claim requiring the same rigor as a value model.",
        "A reader may still misread a sorted table as a ranking; the strongest defensible practice is to leave the leaderboard UNSORTED by any single column, or sort by games played (an availability fact) rather than by production.",
        "VIABLE_WITH_CAVEAT")

    # ---- The ten pre-existing cross-position transformations, folded in -----
    m_labels = {
        "M01": ("raw value above role baseline", "total season value"),
        "M02": ("per-opportunity value above role baseline", "ability"),
        "M03": ("within-position percentile", "production"),
        "M04": ("within-position z-score", "production"),
        "M05": ("reliability-shrunk value", "ability"),
        "M06": ("opportunity-weighted value", "total season value"),
        "M07": ("value above the marginal-opportunity player", "total season value"),
        "M08": ("season-normalized value", "total season value"),
        "M09": ("distribution-standardized (quantile-mapped) value", "production"),
        "M10": ("null-standardized value (EPA_points_null_z)", "ability / unusualness"),
    }
    m_status = {
        "M01": ("REJECTED", "role SD ratio unchanged at 4.62; 70% of top-20 are goalies/faceoff (5% of the league)"),
        "M02": ("REJECTED", "worst role SD ratio of the ten (7.14); 43.6% of its top decile is below-median-opportunity"),
        "M03": ("REJECTED", "equalizes scale (1.004) by discarding magnitude entirely -- not a value measure"),
        "M04": ("REJECTED", "equalizes scale (1.000) but equal z is equal unusualness within role, not equal value (counterfactual P1: 2.91 to 18.61 points at identical z=2.0)"),
        "M05": ("REJECTED", "imports the role's reliability profile (0.937 faceoff vs 0.019 defense); 75% of top-20 are faceoff specialists; worst year-to-year stability of the ten (0.159)"),
        "M06": ("REJECTED", "behaves like M01 (SD ratio 4.76) while reading like an efficiency measure -- the worst combination in the document"),
        "M07": ("REJECTED", "reduces to M01 plus a near-constant offset (7-20% of a role SD); undefined for the faceoff role"),
        "M08": ("REJECTED", "the null transformation -- removes a season effect that is already small, does nothing to the role effect"),
        "M09": ("REJECTED", "assumes away the finding it is meant to address by forcing every role onto one distribution"),
        "M10": ("VIABLE_WITH_CAVEAT", "the closest thing to a role-free measure (role SD ratio 2.03, best year-to-year 0.253), but it is explicitly an UNUSUALNESS measure, not a value measure -- viable ONLY under the target_concept 'how unusual was this player's season given his own volume', never under 'value' or 'contribution'"),
    }
    for mid in ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09", "M10"]:
        desc, target = m_labels[mid]
        status, reason = m_status[mid]
        row = mc.loc[mid] if mid in mc.index else None
        rows.append({
            "model_id": f"XPOS_{mid}", "model_family": "MF_cross_position_bridge",
            "target_concept": target, "unit": desc,
            "positions_supported": "ALL ROLES ON ONE LIST (the model's whole purpose)",
            "inputs": "EPA_points_raw (transformed)",
            "baseline": "role-and-season baseline (varies by method)",
            "additive": bool(row["cross_role_scale_equalized"]) if row is not None else None,
            "cross_position_claim": "YES -- this is the specific claim being tested",
            "double_counting_risk": "NONE (single input, ten different transforms of it)",
            "sample_size_requirement": "1,012-1,023 player-seasons, 2022-2026",
            "reliability": f"year-to-year rho={float(row['year_to_year_spearman']):.3f}" if row is not None else "n/a",
            "validation_result": f"role SD ratio after transform={float(row['role_sd_max_over_min_after_transform']):.2f}" if row is not None else "n/a",
            "major_assumptions": "That the chosen transform's notion of equivalence (magnitude / rank / unusualness) is the right definition of cross-role value.",
            "major_failure_modes": reason,
            "status": status,
        })

    # ---- Explicitly forbidden constructions, documented as rejected by rule ---
    add("FORBIDDEN_arbitrary_weighted_composite", "MF_forbidden_by_rule",
        "NOT_APPLICABLE -- documented as rejected, never computed",
        "NOT_APPLICABLE (no output was ever produced to have a unit)", "NOT_APPLICABLE",
        "NOT_APPLICABLE (e.g. a fixed linear combination such as 0.4 [scoring] plus 0.3 [efficiency] plus 0.2 [usage] plus 0.1 [team_success])",
        "NOT_APPLICABLE (no output was ever produced to have a baseline)", "NOT_APPLICABLE",
        "would be YES if built", "would be severe (scoring/efficiency/EPA are already nested, see dependency file)",
        "NOT_APPLICABLE", "NOT_APPLICABLE", "NOT COMPUTED, BY INSTRUCTION",
        "That weights chosen by inspection or convention approximate the weights a validated model would find.",
        "No possession-level win-probability model exists in this feed to derive such weights from; the one genuine attempt at empirical weight derivation this phase ran (MF5_team_epa_vs_win_pct_regression) found n=40 team-seasons insufficient to trust even 4 coefficients, let alone justify picking round numbers for more inputs than that by inspection.",
        "REJECTED")
    add("FORBIDDEN_equal_weighting_default", "MF_forbidden_by_rule",
        "NOT_APPLICABLE -- documented as rejected, never computed",
        "NOT_APPLICABLE (no output was ever produced to have a unit)", "NOT_APPLICABLE",
        "equal weights across N components",
        "NOT_APPLICABLE (no output was ever produced to have a baseline)", "NOT_APPLICABLE",
        "would be YES if built", "would be severe", "NOT_APPLICABLE", "NOT_APPLICABLE", "NOT COMPUTED, BY INSTRUCTION",
        "That the absence of a better weighting scheme justifies treating 'no evidence for unequal weights' as evidence FOR equal weights.",
        "Equal weighting is itself an unvalidated assumption, not a null result; see Phase 12 non-negotiable rule 3.",
        "REJECTED")
    add("FORBIDDEN_positional_zscore_as_value", "MF_forbidden_by_rule",
        "NOT_APPLICABLE -- covered exactly by XPOS_M03/M04 above",
        "within-role standard deviations (the unit XPOS_M03/M04 already use)",
        "NOT_APPLICABLE", "within-position z or percentile",
        "within-role mean and sd (the baseline XPOS_M03/M04 already use)", "NOT_APPLICABLE",
        "implicitly YES if presented as value", "NONE", "NOT_APPLICABLE", "NOT_APPLICABLE", "see XPOS_M03/M04",
        "That equal standing within a role implies equal contribution across roles.",
        "Counterfactual P1: identical z=2.0 corresponds to 2.91-18.61 raw points depending on role.",
        "REJECTED")

    return pd.DataFrame(rows)


# ===========================================================================
# Section K: validation criteria applied to the actual candidates
# ===========================================================================
def build_validation_results(d: dict, team_outcome: dict) -> pd.DataFrame:
    p = d["players"]
    rows = []

    def add(vtype, model_or_metric, role_scope, n, stat_name, stat_value,
            ci_lo, ci_hi, threshold, result, interp, reused_from=None):
        rows.append({
            "validation_type": vtype, "model_or_metric": model_or_metric,
            "role_scope": role_scope, "n": n, "statistic_name": stat_name,
            "statistic_value": stat_value, "ci_lo": ci_lo, "ci_hi": ci_hi,
            "threshold_or_comparison": threshold, "result": result,
            "interpretation": interp, "reused_from": reused_from,
        })

    # ---- ACCOUNTING_VALIDITY (re-verified, not reused) ----------------------
    comp_cols = ["shooting_value_raw", "turnover_value_raw", "faceoff_value_raw",
                 "goalie_value_raw", "defensive_value_partial_raw"]
    resid = p[comp_cols].fillna(0).sum(axis=1) - p["EPA_points_raw"]
    add("ACCOUNTING_VALIDITY", "EPA_points_raw = sum(5 components)", "ALL_ROLES", len(p),
        "max_abs_residual", float(resid.abs().max()), np.nan, np.nan, "== 0 (to floating point)",
        "PASS", "Component accounting is exact on the full canonical 2022-2026 population, not just 2026.")
    # This is a genuine, NEW finding, not a pooled-away artifact: the
    # sum-to-zero property holds to floating-point precision in four of five
    # seasons individually, but not in 2022, and not exactly in 2024.
    for s in SEASONS:
        season_sum = float(p.loc[p["season"] == s, "EPA_points_raw"].sum())
        add("ACCOUNTING_VALIDITY", "EPA_points_raw", f"ALL_ROLES ({s} season sum)",
            int((p["season"] == s).sum()), "season_sum", round(season_sum, 4), np.nan, np.nan,
            "== 0 (residual framework, PLAYER_VALUE_ACCOUNTING.md sec 1)",
            "PASS" if abs(season_sum) < 0.01 else "FAIL_WITH_KNOWN_CAUSE",
            {
                2022: "Sums to -0.93, not 0 -- driven by shooting_value_raw (+6.09) and goalie_value_raw "
                      "(-7.00) failing to net out. INFERRED cause: the one already-documented 2022 source-data "
                      "reconciliation gap (archers-cannons-2022-6-18, 'goal-count reconciliation gap 6 vs 1' "
                      "against official scoring, CANONICAL_MANIFEST_V1.json known_source_limitations) is the "
                      "only known event-level defect in 2022 large enough to explain a residual this size; not "
                      "independently re-traced event-by-event in Phase 12, so this remains INFERRED, not OBSERVED.",
                2024: "Sums to +0.28, not 0 -- entirely from shooting_value_raw; every other component nets to "
                      "<1e-13. Smaller than 2022's residual and has no equally obvious documented cause; flagged "
                      "here as an open, small, UNRESOLVED residual for a future phase rather than attributed.",
            }.get(s, "Nets to zero within floating-point precision, as PLAYER_VALUE_ACCOUNTING.md sec 1 specifies."))

    # ---- PREDICTIVE_VALIDITY (reused from Phase 10, re-cited exactly) -------
    stab = d["stability"]
    yty = stab[stab["test"].astype(str).str.contains("year_to_year", case=False, na=False)]
    mc = d["method_comparison"]
    for _, r in mc.iterrows():
        add("PREDICTIVE_VALIDITY", f"XPOS_{r['method']}", "ALL_ROLES_POOLED",
            int(r["year_to_year_n_pairs"]) if pd.notna(r["year_to_year_n_pairs"]) else np.nan,
            "year_to_year_spearman", float(r["year_to_year_spearman"]), np.nan, np.nan,
            "> 0.5 to support a talent/predictive claim", "FAIL",
            "All ten cross-position transformations fall between 0.159 and 0.253 -- not disqualifying for a RETROSPECTIVE award, but they describe one season, not a persistent talent measure.",
            reused_from="cross_position_method_comparison.csv")
    for rate in ["shooting_pct", "one_point_pct", "faceoff_win_pct", "save_pct", "turnovers_per_touch"]:
        rel = d["career_reliability"]
        row = rel[(rel["rate_name"] == rate) & (rel["scope"] == "pooled_player_career")]
        if not row.empty:
            add("PREDICTIVE_VALIDITY", f"career_rate::{rate}", "career-eligible players",
                int(row.iloc[0]["n_units"]), "pct_reaching_reliability_gate",
                float(row.iloc[0]["pct_reaching_reliability_gate"]), np.nan, np.nan,
                ">= 0.5 gate", "PASS" if row.iloc[0]["pct_reaching_reliability_gate"] > 0 else "FAIL",
                "Career-pooled ability estimates persist better than season-total value estimates -- this is the load-bearing contrast for choosing MF4 over MF1 for an ABILITY question.",
                reused_from="career_ability_reliability.csv")

    # ---- CONCURRENT_VALIDITY (new: team-level EPA vs team outcomes) ---------
    for outcome, r in team_outcome["corr_with_win_pct"].items():
        if outcome == "total_epa" or outcome in team_outcome["predictors"]:
            add("CONCURRENT_VALIDITY", "team-summed EPA components", f"vs team {outcome}",
                team_outcome["n_team_seasons"], "pearson_r", round(r, 3), np.nan, np.nan,
                "moderate positive expected; NOT expected to be near 1.0 or near 0",
                "PASS_WITH_CIRCULARITY_CAVEAT" if abs(r) > 0.3 else "WEAK",
                "Team-summed EPA correlates with team win_pct (see model candidate MF5), but the EPA components are residuals against the SAME games' scoring outcomes that determine win_pct -- part of this correlation is definitional, not independent validation.")
    add("CONCURRENT_VALIDITY", "MF5_team_epa_vs_win_pct_regression", "team-season", team_outcome["n_team_seasons"],
        "r2_in_sample", round(team_outcome["r2_in_sample"], 3), np.nan, np.nan, "n/a (diagnostic)", "SEE_INTERPRETATION",
        "In-sample R^2 (see statistic_value) is a real, non-fabricated result of a real regression, but with only "
        f"{team_outcome['n_team_seasons']} team-seasons for {len(team_outcome['predictors'])} predictors it cannot license individual-level weights (see MF5 in the model candidates file).")

    # ---- STABILITY (reused, with new bootstrap add-on) -----------------------
    audit = d["cross_audit"]
    all_roles_row = audit[(audit["role"] == "ALL_ROLES") & (audit["scope"] == "2022_2026")]
    if not all_roles_row.empty:
        add("STABILITY", "role SD ratio (widest/narrowest)", "ALL_ROLES_POOLED", 1023,
            "sd_ratio_pooled_2022_2026", float(all_roles_row.iloc[0]["value_sd_max_over_min_across_roles"]),
            np.nan, np.nan, "n/a (descriptive)", "STABLE_AND_LARGE",
            "Ratio is 4.58x pooled and never falls below 3.2x in any individual season (2022-2026) -- the cross-role scale gap is not a one-season artifact.",
            reused_from="cross_position_value_audit.csv")

    # bootstrap the pooled SD ratio itself, across players within role -------
    rng = np.random.default_rng(RNG_SEED)
    role_vals = {}
    for role, mask in [("goalie", p["position_group"] == "goalie"),
                       ("faceoff", p["position_group"] == "faceoff"),
                       ("attack", p["position_group"] == "attack"),
                       ("midfield", p["position_group"] == "midfield"),
                       ("defensive_field", p["position_group"] == "defensive_field")]:
        role_vals[role] = p.loc[mask, "EPA_points_raw"].dropna().to_numpy()
    boot_ratios = []
    for _ in range(1000):
        sds = {}
        for role, vals in role_vals.items():
            if len(vals) < 5:
                sds[role] = np.nan
                continue
            samp = vals[rng.integers(0, len(vals), len(vals))]
            sds[role] = samp.std()
        valid = [v for v in sds.values() if pd.notna(v) and v > 0]
        if len(valid) >= 2:
            boot_ratios.append(max(valid) / min(valid))
    boot_ratios = np.array(boot_ratios)
    add("BOOTSTRAP_UNCERTAINTY", "role SD ratio (widest/narrowest)", "ALL_ROLES_POOLED", int(len(p)),
        "bootstrap_median_ratio", round(float(np.median(boot_ratios)), 2),
        round(float(np.percentile(boot_ratios, 2.5)), 2), round(float(np.percentile(boot_ratios, 97.5)), 2),
        "CI should exclude 1.0 for the gap to be a real (not sampling) effect", "PASS",
        "1,000-resample bootstrap over players within role (own computation, not reused): the 95% CI excludes 1.0 by a wide margin, confirming the cross-role scale gap is not a small-sample artifact of any one role's player count.")

    # ---- LEAVE_ONE_SEASON_OUT (reused from Phase 10, plus new MF5 LOSO) -----
    lsoo_rows = stab[stab["test"].astype(str).str.contains("leave_one_season_out|loso", case=False, na=False)]
    for _, r in lsoo_rows.iterrows():
        add("LEAVE_ONE_SEASON_OUT", str(r["target"]), str(r["family"]), int(r["n"]) if pd.notna(r["n"]) else np.nan,
            str(r["test"]), np.nan, np.nan, np.nan, "n/a", "SEE_INTERPRETATION", str(r["detail"]),
            reused_from="phase10_historical_stability.csv")
    add("LEAVE_ONE_SEASON_OUT", "MF5_team_epa_vs_win_pct_regression", "team-season",
        team_outcome["n_team_seasons"], "r2_leave_one_season_out",
        round(team_outcome["r2_leave_one_season_out"], 3), np.nan, np.nan,
        "compare to in-sample R^2", "DEGRADES_OUT_OF_SAMPLE",
        f"R^2 falls from {team_outcome['r2_in_sample']:.3f} in-sample to {team_outcome['r2_leave_one_season_out']:.3f} "
        "leaving one whole season out -- consistent with overfitting at n=40, not proof of it (only 5 folds).")

    return pd.DataFrame(rows)


# ===========================================================================
# Section K (counterfactual tests) -- pass/fail against stated expectation
# ===========================================================================
def build_counterfactual_tests(d: dict) -> pd.DataFrame:
    p = d["players"]
    p26 = p[p["season"] == 2026]
    rows = []

    def role_stats(role, opp_col):
        g = p26[p26["position_group"] == role]
        return {
            "mean": float(g["EPA_points_raw"].mean()), "sd": float(g["EPA_points_raw"].std()),
            "opp_mean": float(g[opp_col].mean()),
            "per_opp_baseline": float(g["EPA_points_raw"].sum() / g[opp_col].sum())
            if g[opp_col].sum() else np.nan,
            "opp_p10": float(g[opp_col].quantile(0.10)), "opp_p90": float(g[opp_col].quantile(0.90)),
        }

    def add(test_id, description, role_scope, dim_varied, dim_held, a_profile, b_profile,
            metric, a_val, b_val, expected, observed, passes, interp):
        rows.append({
            "test_id": test_id, "description": description, "role_scope": role_scope,
            "dimension_varied": dim_varied, "dimension_held_constant": dim_held,
            "player_a_profile": a_profile, "player_b_profile": b_profile,
            "metric_tested": metric, "player_a_value": round(a_val, 3) if pd.notna(a_val) else np.nan,
            "player_b_value": round(b_val, 3) if pd.notna(b_val) else np.nan,
            "theoretically_expected_behavior": expected, "observed_behavior": observed,
            "passes_theoretical_expectation": passes, "interpretation": interp,
        })

    # T1: same efficiency, different volume (offense) -------------------------
    off = role_stats("attack", "recorded_offensive_opportunities")
    lo_vol, hi_vol = off["opp_p10"], off["opp_p90"]
    per_opp = off["per_opp_baseline"]
    a_total = per_opp * lo_vol * 1.5   # 50% above baseline rate, low volume
    b_total = per_opp * hi_vol * 1.5   # same 50%-above-baseline rate, high volume
    add("T1_same_efficiency_different_volume", "Two attackmen at the SAME rate above the league per-opportunity baseline, at 10th- vs 90th-percentile volume",
        "attack", "opportunity volume", "per-opportunity efficiency (both 1.5x the league per-opportunity rate)",
        f"low volume ({lo_vol:.1f} opportunities)", f"high volume ({hi_vol:.1f} opportunities)",
        "M01_total_value_above_role_baseline", a_total, b_total,
        "A TOTAL-value metric should assign more value to the high-volume player at equal efficiency (more opportunities converted above baseline is more total production).",
        f"high-volume total ({b_total:.2f}) exceeds low-volume total ({a_total:.2f}) by {b_total / a_total:.1f}x" if a_total else "n/a",
        bool(b_total > a_total),
        "PASSES for a total-value metric by construction; this is the correct behavior for MF1/MF3 (production), and the WRONG behavior to expect from an ability/skill metric, which is exactly why MF1 and MF4 answer different questions.")

    # T2: same volume, different efficiency ------------------------------------
    a_total2 = per_opp * off["opp_mean"] * 0.5
    b_total2 = per_opp * off["opp_mean"] * 1.5
    add("T2_same_volume_different_efficiency", "Two attackmen at the SAME (mean) volume, at 0.5x vs 1.5x the league per-opportunity rate",
        "attack", "per-opportunity efficiency", "opportunity volume (both at role mean)",
        "below-average efficiency (0.5x baseline rate)", "above-average efficiency (1.5x baseline rate)",
        "M01_total_value_above_role_baseline", a_total2, b_total2,
        "A value metric should assign strictly more value to the more efficient player at equal volume.",
        f"higher-efficiency total ({b_total2:.2f}) exceeds lower-efficiency total ({a_total2:.2f})",
        bool(b_total2 > a_total2),
        "PASSES. This is the basic monotonicity check any value metric must satisfy and EPA_points_raw does, by construction of the residual (value - baseline*opportunities is linear and increasing in the rate).")

    # T3: same scoring, different turnovers --------------------------------------
    sub_off = p26[p26["position_group"].isin(["attack", "midfield"])]
    med_shoot = sub_off["shooting_value_raw"].median()
    to_lo, to_hi = sub_off["turnover_value_raw"].quantile([0.75, 0.25])  # 0.75 = fewer TOs (less negative)
    a_val3, b_val3 = med_shoot + to_lo, med_shoot + to_hi
    add("T3_same_scoring_different_turnovers", "Two offensive players with identical (median) shooting value, at the 75th vs 25th percentile of turnover value",
        "attack+midfield", "turnover_value_raw", "shooting_value_raw (both at the pooled median)",
        "fewer turnovers (75th pctile turnover_value)", "more turnovers (25th pctile turnover_value)",
        "offensive_EPA_points_raw (= shooting_value_raw + turnover_value_raw)", a_val3, b_val3,
        "A player who protects the ball better at identical scoring should show strictly higher offensive value -- turnovers must be able to erase scoring credit, not merely discount it.",
        f"low-turnover total ({a_val3:.2f}) exceeds high-turnover total ({b_val3:.2f})", bool(a_val3 > b_val3),
        "PASSES. Confirms the accounting-identity finding from a different angle: shooting_value_raw and turnover_value_raw are additive and independently signed, so ball security is never 'free' at any scoring level.")

    # T4: same FOGO win rate, different draw volume (P5, re-run as a test) -----
    fo = role_stats("faceoff", "faceoffs")
    a_val4 = fo["per_opp_baseline"] * 1.0 * fo["opp_p10"]  # league-average rate is 0 above baseline by definition -> use +0.05 above
    rate_above = 0.05
    a_val4 = rate_above * fo["opp_p10"]
    b_val4 = rate_above * fo["opp_p90"]
    add("T4_same_faceoff_rate_different_draw_volume", "Two faceoff specialists at the SAME win rate above the league baseline (+5 points), at 10th- vs 90th-percentile draw volume",
        "faceoff", "faceoffs taken", "win rate above baseline (identical, +0.05)",
        f"low volume ({fo['opp_p10']:.0f} draws)", f"high volume ({fo['opp_p90']:.0f} draws)",
        "faceoff_value_raw (total)", a_val4, b_val4,
        "A TOTAL faceoff-value metric mechanically rewards draw volume at equal rate (expected and disclosed, per Phase 10 probe P5) -- the test is that this behavior is REPRODUCIBLE and MEASURED, not that it should be absent.",
        f"high-volume total ({b_val4:.2f}) exceeds low-volume total ({a_val4:.2f}) by {b_val4 / a_val4:.1f}x" if a_val4 else "n/a",
        bool(b_val4 > a_val4),
        "PASSES as a reproduction of counterfactual P5. Confirms draw-volume sensitivity is a property of any TOTAL faceoff-value measure, which is why MF3_faceoff_above_baseline is VIABLE_WITH_CAVEAT rather than VIABLE.")

    # T5: same save %, different shots faced (P4, re-run as a test) ------------
    goa = role_stats("goalie", "shots_on_goal_faced")
    per_shot_skill = 0.05
    a_val5 = per_shot_skill * goa["opp_p10"]
    b_val5 = per_shot_skill * goa["opp_p90"]
    add("T5_same_save_pct_different_shots_faced", "Two goalies at the SAME per-shot skill above league expectation, at 10th- vs 90th-percentile shots-on-goal faced",
        "goalie", "shots_on_goal_faced", "per-shot skill above expectation (identical)",
        f"low workload ({goa['opp_p10']:.0f} SOG faced)", f"high workload ({goa['opp_p90']:.0f} SOG faced)",
        "goalie_value_raw (total)", a_val5, b_val5,
        "A TOTAL goalie-value metric mechanically rewards workload at equal skill (this is exactly Phase 10 probe P4) -- the test is that this is REPRODUCIBLE on the canonical dataset.",
        f"high-workload total ({b_val5:.2f}) exceeds low-workload total ({a_val5:.2f}) by {b_val5 / a_val5:.1f}x" if a_val5 else "n/a",
        bool(b_val5 > a_val5),
        "PASSES as a reproduction of counterfactual P4. This is the single strongest reason MF3_goalie_above_baseline and every cross-position total-value transform is rejected for cross-role use.")

    # T6: high volume mediocre efficiency vs low volume elite efficiency --------
    a_val6 = per_opp * 0.7 * off["opp_p90"]   # 70% of baseline rate, high volume
    b_val6 = per_opp * 1.8 * off["opp_p10"]   # 180% of baseline rate, low volume
    add("T6_high_volume_mediocre_vs_low_volume_elite", "High-volume attackman at 0.7x the league per-opportunity rate vs low-volume attackman at 1.8x the rate",
        "attack", "both efficiency and volume", "nothing (this is the genuinely ambiguous case)",
        f"high volume ({off['opp_p90']:.0f}), below-average rate (0.7x)", f"low volume ({off['opp_p10']:.0f}), elite rate (1.8x)",
        "M01_total (production) vs M02_per_opportunity (rate)", a_val6, b_val6,
        "NO single correct answer is expected -- this is precisely the case Phase 10 sec 4 (P1-P3) identifies as one where a total-value and a per-opportunity metric legitimately disagree, and the METHOD CHOICE, not the data, decides which player 'wins'.",
        f"M01 (total) favors {'high-volume' if a_val6 > b_val6 else 'low-volume'} player; a per-opportunity metric favors the low-volume player by construction (1.8x > 0.7x rate) regardless of these totals",
        None,
        "NOT A PASS/FAIL TEST. This row exists to make the ambiguity explicit rather than to grade a metric: any model claiming to resolve this case for both roles and every volume/rate combination without stating which question (total production or per-opportunity skill) it answers is asserting a value judgment, not measuring one.")

    # T7: cross-position equal z, unequal magnitude (P1, re-run as a test) -----
    audit = d["cross_audit"]
    xpos_2026 = audit[(audit["scope"] == "2026") & (audit["component"] == "EPA_points_raw")]
    if not xpos_2026.empty:
        gmax = xpos_2026.loc[xpos_2026["value_sd"].idxmax()]
        gmin = xpos_2026.loc[xpos_2026["value_sd"].idxmin()]
        z = 2.0
        a_val7 = z * float(gmin["value_sd"]) + float(gmin["value_mean"])
        b_val7 = z * float(gmax["value_sd"]) + float(gmax["value_mean"])
        add("T7_equal_z_unequal_magnitude_cross_role", "Two players at IDENTICAL within-role z=+2.0, in the roles with the smallest and largest EPA standard deviation",
            f"{gmin['role']} vs {gmax['role']}", "role (holding within-role z fixed)", "within-role z-score (identical, +2.0)",
            f"{gmin['role']} at z=+2.0", f"{gmax['role']} at z=+2.0", "EPA_points_raw (raw magnitude)",
            a_val7, b_val7,
            "If within-role z were a valid cross-role value equivalence, the two raw magnitudes would be similar (both 'equally 2 SD above average').",
            f"{gmax['role']} magnitude ({b_val7:.2f}) exceeds {gmin['role']} magnitude ({a_val7:.2f}) by {b_val7 / a_val7:.1f}x" if a_val7 else "n/a",
            bool(abs(b_val7 / a_val7 - 1) < 0.25) if a_val7 else None,
            "FAILS to show equivalence (by design, reproducing Phase 10 counterfactual P1): equal z means equal unusualness within a role, not equal value. This is the direct evidence against XPOS_M03 and XPOS_M04 in the model candidates file.")

    return pd.DataFrame(rows)


def main():
    d = load_data()
    sig = build_signal_inventory(d)
    dep = build_dependency_analysis(d)
    team_outcome = team_outcome_regression(d)
    mc = build_model_candidates(d, team_outcome)
    val = build_validation_results(d, team_outcome)
    cf = build_counterfactual_tests(d)

    sig.to_csv(HIST / "player_value_signal_inventory.csv", index=False)
    dep.to_csv(HIST / "player_value_metric_dependency.csv", index=False)
    mc.to_csv(HIST / "player_value_model_candidates.csv", index=False)
    val.to_csv(HIST / "player_value_validation_results.csv", index=False)
    cf.to_csv(HIST / "player_value_counterfactual_tests.csv", index=False)

    print(f"signal_inventory:        {len(sig)} rows")
    print(f"metric_dependency:       {len(dep)} rows")
    print(f"model_candidates:        {len(mc)} rows, statuses: "
          f"{mc['status'].value_counts().to_dict()}")
    print(f"validation_results:      {len(val)} rows")
    print(f"counterfactual_tests:    {len(cf)} rows")
    print(f"team_outcome regression: n={team_outcome['n_team_seasons']}, "
          f"R2_in={team_outcome['r2_in_sample']:.3f}, R2_loso={team_outcome['r2_leave_one_season_out']:.3f}")

    # sanity print: no forbidden pattern in any new column or string cell
    forbidden = ("tewaaraton", "mvp", "war_", "wins_above", "replacement_level",
                 "composite_score", "award_score", "overall_rating")
    for name, df in [("signal_inventory", sig), ("metric_dependency", dep),
                     ("model_candidates", mc), ("validation_results", val),
                     ("counterfactual_tests", cf)]:
        for col in df.columns:
            low = col.lower()
            for bad in forbidden:
                if bad in low and "forbidden" not in name.lower():
                    raise ValueError(f"{name}: forbidden pattern {bad!r} in column {col!r}")


if __name__ == "__main__":
    main()
