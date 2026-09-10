"""
Phase 8: build the 2026 comprehensive statistical layer.

Phase 8 CONSOLIDATES. It does not re-derive a single Phase 5/6/7 metric: it
loads their validated outputs, joins them into publication-ready tables, and
adds only arithmetic that is genuinely new at the publication level (per-game
context, differentials, two-point return economics, leaderboard ranks,
distribution summaries, sanity flags). Every added column is registered in the
Phase 8 metric catalog, and `pll_validate_phase8.py` fails if any Phase 5/6/7
file changes.

Reads (none of them modified):
    data/processed/2026/{games,teams,players,events,possessions}.csv
    data/processed/2026/{player_game_stats,team_game_stats}.csv
    data/processed/2026/team_season_advanced.csv          (Phase 5)
    data/processed/2026/team_game_advanced.csv            (Phase 5)
    data/processed/2026/team_rankings.csv                 (Phase 5)
    data/processed/2026/possession_length_splits.csv      (Phase 5)
    data/processed/2026/team_metric_sensitivity.csv       (Phase 5)
    data/processed/2026/player_opportunities.csv          (Phase 6)
    data/processed/2026/player_value_components.csv       (Phase 6)
    data/processed/2026/player_value_baselines.csv        (Phase 6)
    data/processed/2026/player_adjusted_value.csv         (Phase 7)
    data/processed/2026/player_usage_adjusted_value.csv   (Phase 7)
    data/processed/2026/player_position_map.csv           (Phase 7)
    data/processed/2026/player_positional_baselines.csv   (Phase 7)
    data/processed/2026/player_rate_identification.csv    (Phase 7)

Writes:
    data/processed/2026/team_stats_2026.csv
    data/processed/2026/player_stats_2026.csv
    data/processed/2026/team_leaderboards_2026.csv
    data/processed/2026/player_leaderboards_2026.csv
    data/processed/2026/two_point_audit_2026.csv
    data/processed/2026/metric_catalog_2026.csv
    data/processed/2026/metric_distribution_audit_2026.csv
    data/processed/2026/metric_redundancy_2026.csv
    data/processed/2026/metric_sanity_flags_2026.csv
    data/processed/2026/phase8_qualification_rules.csv

Deterministic: every query carries an explicit ORDER BY, the one estimated
quantity (the turnovers-per-touch prior strength) is a closed-form method-of-
moments fit with no sampling, and reruns produce byte-identical CSVs.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pll_metric_catalog import catalog_rows, CATALOG_BY_KEY  # noqa: E402
from pll_phase8_catalog_core import CATALOG_COLUMNS  # noqa: E402
# Phase 6's own estimator, imported rather than reimplemented so the one prior
# strength Phase 8 estimates is consistent with every other gate in the system.
from pll_player_value_models import beta_prior_by_moments  # noqa: E402

# Scratch lives beside the data, not in /tmp, because the qualification SQL
# reads it and a rerun must be reproducible from the repo alone.
SCRATCH_DIR = DATA_DIR / "_phase8_scratch"

# Phase 9: the season tag that appears in this layer's output filenames.
# Defaults to 2026 so every existing path, test and validator is untouched;
# the historical driver sets it so 2022 produces team_stats_2022.csv rather
# than a file called team_stats_2026.csv sitting in the 2022 directory.
SEASON_TAG = "2026"


def set_season(year, data_dir=None):
    """Point this builder at a season. The SQL is season-agnostic already --
    it takes {data_dir} -- so this only moves the I/O."""
    global DATA_DIR, SCRATCH_DIR, SEASON_TAG
    SEASON_TAG = str(year)
    DATA_DIR = Path(data_dir) if data_dir else (
        REPO_ROOT / "data" / "processed" / str(year))
    SCRATCH_DIR = DATA_DIR / "_phase8_scratch"


def tagged(name):
    """Rewrite a 2026-tagged output filename for the active season."""
    return name.replace("_2026.csv", f"_{SEASON_TAG}.csv")

PIPELINE = [
    ("40_phase8_base_views.sql", None, None),
    ("41_phase8_qualification.sql", "p8_qualification_rules", "phase8_qualification_rules.csv"),
    ("team_stats_2026.sql", "team_stats_2026", "team_stats_2026.csv"),
    ("player_stats_2026.sql", "player_stats_2026", "player_stats_2026.csv"),
    ("two_point_audit_2026.sql", "two_point_audit_2026", "two_point_audit_2026.csv"),
    ("team_leaderboards_2026.sql", "team_leaderboards_2026", "team_leaderboards_2026.csv"),
    ("player_leaderboards_2026.sql", "player_leaderboards_2026", "player_leaderboards_2026.csv"),
]

# Columns that are identifiers, labels or flags rather than statistics. They are
# excluded from the distribution audit because a summary of a team_id is noise.
NON_METRIC_COLUMNS = {
    "team_id", "team_name", "player_id", "player_name", "n_teams",
    "roster_position_code", "canonical_position", "position_group", "value_role",
    "baseline_group", "components_supported", "ground_ball_value_status",
    "assist_value_status", "defensive_value_scope", "role_rate_name",
    "position_baseline_note", "unsupported_components", "role_interpretation_caveat",
    "mapping_reason", "descriptive_eligible", "rate_ranking_eligible",
    "offensive_rate_ranking_eligible", "reliability_adjusted_eligible",
    "future_award_input_eligible", "small_sample",
    "chance_variation_exceeds_peer_spread", "defense_partial", "usage_proxy_only",
}

# Bounds come from the CATALOG's declared unit, not from the column name. A
# name-based rule gets this wrong in both directions: `turnover_rate` is a count
# per possession and is not bounded by 1, while `possession_span_coverage_ratio`
# is bounded and does not end in "_pct". Driving it from the unit means the
# audit is checking the data against the published contract rather than against
# a naming convention.
UNIT_BOUNDS = {
    "percentage": (0.0, 1.0),      # this repo stores percentages as fractions
    "probability": (0.0, 1.0),
    "percentile 0-100": (0.0, 100.0),
    "ratio": (0.0, None),
}

# Columns whose NULLs are a published decision rather than a gap. Each names the
# decision, so an added NULL cannot hide behind an existing exemption.
DELIBERATE_NULL = {
    "expected_EPA_given_usage":
        "Phase 7 fitted the usage model on field players (value_role "
        "offensive_field / defensive_field) with at least one recorded "
        "offensive opportunity. NULL for everyone else -- not zero, because "
        "zero would be a claim.",
    "EPA_vs_usage_expectation":
        "Defined only where expected_EPA_given_usage is defined.",
    "EPA_vs_usage_expectation_z":
        "Defined only where expected_EPA_given_usage is defined.",
}


# ---------------------------------------------------------------------------
# SQL plumbing
# ---------------------------------------------------------------------------
def run_sql_file(con, path: Path):
    """Execute a .sql file, substituting the directory placeholders. DuckDB runs
    a multi-statement script in one call, so no semicolon parsing is needed."""
    sql = (path.read_text()
           .replace("{data_dir}", str(DATA_DIR))
           .replace("{scratch_dir}", str(SCRATCH_DIR)))
    con.execute(sql)


def export(con, table: str, out_name: str) -> int:
    df = con.execute(f"SELECT * FROM {table}").df()
    df.to_csv(DATA_DIR / out_name, index=False)
    return len(df)


# ---------------------------------------------------------------------------
# The one threshold Phase 8 estimates itself
# ---------------------------------------------------------------------------
def write_thresholds() -> pd.DataFrame:
    """Estimate the turnovers-per-touch prior strength.

    Phases 6 and 7 published a prior strength for shooting, one-point, two-point,
    faceoff and save rates but never for turnovers per touch, because no Phase
    6/7 leaderboard was gated on it. Phase 8 publishes a turnover-rate
    leaderboard and therefore needs the gate. It is estimated with Phase 6's own
    `beta_prior_by_moments`, imported above, so it is the same estimator that set
    every other gate; reliability 0.5 then implies `touches >= kappa`.

    This does NOT modify any Phase 6/7 output. It is a Phase 8 quantity written
    to Phase 8's own scratch file.
    """
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    opps = pd.read_csv(DATA_DIR / "player_opportunities.csv")
    a, b = beta_prior_by_moments(opps["turnovers"].to_numpy(),
                                 opps["touches"].to_numpy())
    kappa = a + b
    df = pd.DataFrame([{
        "rate_name": "turnovers_per_touch",
        "turnover_rate_prior_alpha": a,
        "turnover_rate_prior_beta": b,
        "turnover_rate_prior_mean": a / (a + b),
        "turnover_rate_kappa": kappa,
        # reliability = n / (n + kappa) >= 0.5  <=>  n >= kappa
        "turnover_rate_min_touches": kappa,
        "n_players_with_touches": int((opps["touches"] > 0).sum()),
        "n_players_clearing_gate": int((opps["touches"] >= kappa).sum()),
        "estimator": "pll_player_value_models.beta_prior_by_moments (Phase 6)",
    }])
    df.to_csv(SCRATCH_DIR / "phase8_thresholds.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# Metric catalog export
# ---------------------------------------------------------------------------
def write_catalog() -> int:
    import csv
    with (DATA_DIR / tagged("metric_catalog_2026.csv")).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CATALOG_COLUMNS)
        w.writeheader()
        for row in catalog_rows():
            w.writerow(row)
    return len(catalog_rows())


# ---------------------------------------------------------------------------
# Distribution audit
# ---------------------------------------------------------------------------
def declared_bounds(level: str, metric: str):
    """(lo, hi) the catalog says this metric must lie within, or None."""
    cat = CATALOG_BY_KEY.get((level, metric))
    if cat is None:
        return None
    return UNIT_BOUNDS.get(cat["unit"])


def distribution_audit(team: pd.DataFrame, player: pd.DataFrame) -> pd.DataFrame:
    """Summarise every published numeric column of both statistical tables.

    The point is not the summary statistics themselves -- it is that a metric
    whose distribution is degenerate (all one value, a spike at zero, an
    interquartile range of nothing with a long tail) is visible as data instead
    of being discovered by someone plotting it later. The extremes carry the
    holder's name and the metric's own denominator, because the single most
    common way a leaderboard misleads is an extreme rate on three attempts.
    """
    rows = []
    for level, df, id_col, name_col, den_map in (
        ("team_season", team, "team_id", "team_name", _team_denominators(team)),
        ("player_season", player, "player_id", "player_name", _player_denominators(player)),
    ):
        for col in df.columns:
            if col in NON_METRIC_COLUMNS or not pd.api.types.is_numeric_dtype(df[col]):
                continue
            s = pd.to_numeric(df[col], errors="coerce")
            v = s.dropna()
            cat = CATALOG_BY_KEY.get((level, col))
            den_name, den_series = den_map.get(col, (None, None))
            row = {
                "entity_level": level,
                "metric_name": col,
                "in_catalog": cat is not None,
                "publication_status": cat["publication_status"] if cat else "NOT_CATALOGUED",
                "category": cat["category"] if cat else None,
                "higher_is_better": cat["higher_is_better"] if cat else None,
                "n_rows": len(s),
                "n_non_null": int(v.size),
                "n_null": int(s.isna().sum()),
                "n_zero": int((v == 0).sum()),
                "n_negative": int((v < 0).sum()),
                "n_non_finite": int(np.isinf(s.to_numpy(dtype="float64",
                                                        na_value=np.nan)).sum()),
                "denominator_name": den_name,
            }
            if v.empty:
                rows.append({**row, "min": None, "max": None, "mean": None})
                continue
            bounds = declared_bounds(level, col)
            q = v.quantile([0.05, 0.25, 0.50, 0.75, 0.95])
            iqr = q[0.75] - q[0.25]
            sd = float(v.std(ddof=0))
            mean = float(v.mean())
            lo_i, hi_i = v.idxmin(), v.idxmax()
            row.update({
                "min": float(v.min()),
                "p05": float(q[0.05]),
                "q1": float(q[0.25]),
                "median": float(q[0.50]),
                "q3": float(q[0.75]),
                "p95": float(q[0.95]),
                "max": float(v.max()),
                "mean": mean,
                "sd": sd,
                "iqr": float(iqr),
                "coefficient_of_variation": (sd / abs(mean)) if mean not in (0,) else None,
                "skewness": float(v.skew()) if v.size > 2 else None,
                # NULL rather than 0 when the interquartile range is zero. Half
                # the player-level counting stats are role-specific and more than
                # 79% zero (only 16 of 228 players face a shot), so q1 = q3 = 0
                # and the Tukey rule degenerates: reporting "0 outliers" for a
                # column whose maximum is 332 would be actively misleading.
                "n_iqr_outliers": (int(((v < q[0.25] - 1.5 * iqr) |
                                        (v > q[0.75] + 1.5 * iqr)).sum())
                                   if iqr > 0 else None),
                "outlier_rule_applicable": bool(iqr > 0),
                "min_holder": df.loc[lo_i, name_col],
                "max_holder": df.loc[hi_i, name_col],
                "min_holder_denominator": _den_at(den_series, lo_i),
                "max_holder_denominator": _den_at(den_series, hi_i),
                "declared_bounds": f"[{bounds[0]}, {bounds[1]}]" if bounds else None,
                "out_of_bounds_rows": _out_of_bounds(v, bounds),
                "is_degenerate": bool(v.nunique() <= 1),
                "zero_share": float((v == 0).mean()),
            })
            rows.append(row)
    out = pd.DataFrame(rows).sort_values(["entity_level", "metric_name"])
    return out.reset_index(drop=True)


def _out_of_bounds(v: pd.Series, bounds) -> int:
    if bounds is None:
        return 0
    lo, hi = bounds
    bad = pd.Series(False, index=v.index)
    if lo is not None:
        bad |= v < lo
    if hi is not None:
        bad |= v > hi
    return int(bad.sum())


def _den_at(den_series, idx):
    if den_series is None:
        return None
    try:
        val = den_series.loc[idx]
    except KeyError:
        return None
    return None if pd.isna(val) else float(val)


def _team_denominators(t: pd.DataFrame) -> dict:
    """Map team metric -> (denominator name, denominator values).

    Only the metrics whose extremes are meaningfully sample-limited need one;
    everything else reports its denominator as games_played, which is the
    smallest honest denominator a season figure has.
    """
    g = t["games_played"]
    op = t["offensive_possessions"]
    dp = t["defensive_possessions"]
    d = {c: ("games_played", g) for c in t.columns}
    for c in t.columns:
        if c.endswith("_per_possession") or c in ("offensive_efficiency",
                                                  "goals_per_possession",
                                                  "turnover_rate",
                                                  "possession_ending_turnover_rate",
                                                  "shot_clock_expiration_rate",
                                                  "two_point_possession_rate",
                                                  "faceoff_start_possession_share"):
            d[c] = ("offensive_possessions", op)
    for c in ("defensive_efficiency", "shots_allowed_per_possession",
              "turnovers_forced_per_defensive_possession"):
        if c in t.columns:
            d[c] = ("defensive_possessions", dp)
    for c, den in (("shooting_pct", "shots"), ("points_per_shot", "shots"),
                   ("shots_on_goal_pct", "shots"),
                   ("goals_per_shot_on_goal", "shots_on_goal"),
                   ("two_point_conversion_pct", "two_point_attempts"),
                   ("points_per_two_point_attempt", "two_point_attempts"),
                   ("two_point_minus_one_point_return", "two_point_attempts"),
                   ("two_point_attempt_rate", "shots"),
                   ("one_point_conversion_pct", "one_point_attempts"),
                   ("points_per_one_point_attempt", "one_point_attempts"),
                   ("faceoff_win_pct", "faceoffs"),
                   ("save_pct_official", "shots_on_goal_allowed"),
                   ("save_pct_vs_shots_on_goal", "shots_on_goal_allowed"),
                   ("opponent_shooting_pct", "shots_allowed"),
                   ("opponent_shooting_pct_on_goal", "shots_on_goal_allowed"),
                   ("man_up_shooting_pct", "man_up_shots"),
                   ("man_up_goals_per_opportunity", "man_up_opportunities"),
                   ("man_up_points_per_opportunity", "man_up_opportunities"),
                   ("man_up_shots_per_opportunity", "man_up_opportunities"),
                   ("man_down_goals_allowed_per_opportunity", "man_down_opportunities")):
        if c in t.columns and den in t.columns:
            d[c] = (den, t[den])
    return d


def _player_denominators(p: pd.DataFrame) -> dict:
    g = p["games_played"]
    d = {c: ("games_played", g) for c in p.columns}
    pairs = [
        ("shooting_pct", "shots"), ("points_per_shot", "shots"),
        ("shots_on_goal_pct", "shots"), ("shooting_rate_raw", "shots"),
        ("shooting_rate_shrunk", "shots"), ("shooting_reliability", "shots"),
        ("shooting_value_raw", "shots"), ("shooting_EPA_per_shot", "shots"),
        ("shooting_value_null_z", "shots"),
        ("one_point_conversion_pct", "one_point_attempts"),
        ("one_point_rate_raw", "one_point_attempts"),
        ("one_point_rate_shrunk", "one_point_attempts"),
        ("one_point_reliability", "one_point_attempts"),
        ("two_point_conversion_pct", "two_point_attempts"),
        ("two_point_rate_raw", "two_point_attempts"),
        ("two_point_rate_shrunk", "two_point_attempts"),
        ("two_point_reliability", "two_point_attempts"),
        ("faceoff_win_pct", "faceoffs"), ("faceoff_rate_raw", "faceoffs"),
        ("faceoff_rate_shrunk", "faceoffs"), ("faceoff_reliability", "faceoffs"),
        ("faceoff_value_raw", "faceoffs"), ("faceoff_EPA_per_faceoff", "faceoffs"),
        ("faceoff_value_null_z", "faceoffs"),
        ("save_pct", "shots_on_goal_faced"), ("save_rate_raw", "shots_on_goal_faced"),
        ("save_rate_shrunk", "shots_on_goal_faced"),
        ("save_reliability", "shots_on_goal_faced"),
        ("goalie_value_raw", "shots_on_goal_faced"),
        ("goalie_EPA_per_SOG", "shots_on_goal_faced"),
        ("goalie_value_null_z", "shots_on_goal_faced"),
        ("points_allowed_per_sog_faced", "shots_on_goal_faced"),
        ("turnovers_per_touch", "touches"), ("turnover_value_raw", "touches"),
        ("EPA_per_recorded_opportunity", "recorded_offensive_opportunities"),
        ("offensive_EPA_points_raw", "recorded_offensive_opportunities"),
        ("EPA_vs_usage_expectation", "recorded_offensive_opportunities"),
        ("expected_EPA_given_usage", "recorded_offensive_opportunities"),
        ("offensive_play_share", "recorded_offensive_opportunities"),
    ]
    for c, den in pairs:
        if c in p.columns and den in p.columns:
            d[c] = (den, p[den])
    return d


# ---------------------------------------------------------------------------
# Redundancy analysis
# ---------------------------------------------------------------------------
def redundancy_analysis(team: pd.DataFrame, player: pd.DataFrame) -> pd.DataFrame:
    """Empirical redundancy: which published metrics carry the same information?

    The catalog already declares a redundancy_class per metric from the
    definitions. This measures it. Declared and measured are BOTH reported,
    because they disagree in informative ways: two metrics can be
    algebraically distinct and empirically identical at 2026's sample (which is
    a finding about the season, not about the definitions), and two metrics can
    be algebraically related and still rank teams differently.

    Pearson on 8 teams is fragile, so Spearman is reported alongside and the
    verdict requires BOTH to be extreme.
    """
    rows = []
    for level, df in (("team_season", team), ("player_season", player)):
        num = df.select_dtypes(include=[np.number]).drop(
            columns=[c for c in NON_METRIC_COLUMNS if c in df.columns],
            errors="ignore")
        # Only catalogued, publishable metrics -- a diagnostic being redundant
        # with a statistic is not a finding about the statistic.
        keep = [c for c in num.columns
                if (level, c) in CATALOG_BY_KEY
                and CATALOG_BY_KEY[(level, c)]["publication_status"]
                in ("CORE", "CONTEXTUAL", "EXPERIMENTAL")]
        num = num[keep]
        # a constant column has no correlation with anything
        num = num.loc[:, num.nunique(dropna=True) > 1]
        pear = num.corr(method="pearson", min_periods=5)
        spear = num.corr(method="spearman", min_periods=5)
        cols = list(num.columns)
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                r, rho = pear.loc[a, b], spear.loc[a, b]
                if pd.isna(r) or pd.isna(rho):
                    continue
                if abs(r) < 0.95 and abs(rho) < 0.95:
                    continue
                n_pair = int((num[a].notna() & num[b].notna()).sum())
                both = abs(r) >= 0.99 and abs(rho) >= 0.99
                rows.append({
                    "entity_level": level,
                    "metric_a": a,
                    "metric_b": b,
                    "n_pairs": n_pair,
                    "pearson_r": float(r),
                    "spearman_rho": float(rho),
                    "declared_class_a": CATALOG_BY_KEY[(level, a)]["redundancy_class"],
                    "declared_class_b": CATALOG_BY_KEY[(level, b)]["redundancy_class"],
                    "measured_verdict": (
                        "EMPIRICALLY_INTERCHANGEABLE" if both
                        else "HIGHLY_OVERLAPPING"),
                    "note": (
                        "|r| >= 0.99 AND |rho| >= 0.99 at n=%d. Publishing both "
                        "as separate findings double-counts one fact." % n_pair
                        if both else
                        "|r| or |rho| >= 0.95 at n=%d. Related, but they can "
                        "still order the table differently." % n_pair),
                })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return (out.sort_values(["entity_level", "metric_a", "metric_b"])
               .reset_index(drop=True))


# ---------------------------------------------------------------------------
# Sanity flags
# ---------------------------------------------------------------------------
# Every flag carries the Phase 8 brief's classification:
#   A real performance   B sample-size artifact   C role/opportunity artifact
#   D known feed limitation   E implementation/data bug
# Only E is ever "fixed". A-D are reported.
FLAG_SPEC = {
    "SMALL_SAMPLE_LEADER": ("B", "warn",
        "Leads an unqualified (scope=ALL) rate leaderboard on a denominator "
        "below the metric's own reliability-0.5 trial count. The rank is real; "
        "the implied ability claim is not."),
    "DEGENERATE_RATE_EXTREME": ("B", "warn",
        "A rate of exactly 0 or exactly 1. At these denominators that is a "
        "small-sample boundary, not a skill level."),
    "OUT_OF_BOUNDS": ("E", "error",
        "A proportion outside [0, 1]. This is arithmetic, not a finding."),
    "NON_FINITE": ("E", "error",
        "inf or -inf in a published column, which means a division guarded "
        "nowhere reached a zero denominator."),
    "NULL_WITH_POSITIVE_DENOMINATOR": ("E", "error",
        "NULL where the denominator is positive, so the metric was computable "
        "and was not computed."),
    "EMPTY_QUALIFIED_SCOPE": ("D", "info",
        "No player clears this metric's evidence gate. Where this is the "
        "documented consequence of 2026 sample sizes it is the finding."),
    "SINGLE_ROW_QUALIFIED_SCOPE": ("D", "info",
        "Exactly one entity clears the evidence gate, so the 'leaderboard' is "
        "a single name and ranks nobody."),
    "RAW_SHRUNK_ORDER_FLIP": ("B", "warn",
        "The raw leader is not the shrunk leader. Both are correct answers to "
        "different questions; the gap is the small-sample premium."),
    "SHRINKAGE_FULLY_COLLAPSED": ("D", "info",
        "Every shrunk value is the league mean: the estimator found no "
        "detectable between-player spread at 2026 samples."),
    "POSITION_CONCENTRATED_TOP10": ("C", "info",
        "The top 10 is one position group. Expected for a role-specific metric; "
        "a warning that the metric is not a general ranking."),
    "EXTREME_Z": ("A", "info",
        "More than 3 SD from the scope mean. Usually a real outlier season; "
        "traced individually in the sanity audit."),
    "UNATTRIBUTED_TURNOVER_EXPOSURE": ("D", "warn",
        "Player turnover totals sum to materially less than the official team "
        "total because the feed attributes some turnovers to no player."),
    "TWO_POINT_UNIDENTIFIED": ("D", "warn",
        "Individual two-point ability is not identifiable from 2026; the metric "
        "is published as production only and no QUALIFIED scope exists."),
    "IDENTITY_MISMATCH": ("E", "error",
        "A definitional identity between published columns does not hold."),
    "VALUE_ON_EMPTY_NAMED_BASE": ("C", "warn",
        "A value total is non-zero while the opportunity base named on its row "
        "is zero, because the total sums components whose bases differ. Read "
        "the component, not the named denominator."),
    "OFFICIAL_SOURCE_DISAGREEMENT": ("D", "warn",
        "The official box score does not internally reconcile. Reported, never "
        "corrected: the official figure is the published figure."),
}


def _touch_count(player: pd.DataFrame, player_id) -> float:
    hit = player.loc[player["player_id"] == player_id, "touches"]
    return float(hit.iloc[0]) if len(hit) else float("nan")


def sanity_flags(con, team, player, tlb, plb, thresholds) -> pd.DataFrame:
    rows = []

    def flag(code, level, entity_id, entity_name, metric, value, denominator,
             detail):
        cls, sev, desc = FLAG_SPEC[code]
        rows.append({
            "flag_code": code,
            "classification": cls,
            "severity": sev,
            "entity_level": level,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "metric_name": metric,
            "metric_value": value,
            "denominator_value": denominator,
            "flag_description": desc,
            "detail": detail,
        })

    # -- reliability-0.5 trial counts, from Phase 7's published table plus the
    #    one Phase 8 estimate. Used to decide what "small sample" means for each
    #    rate rather than picking a number.
    ident = pd.read_csv(DATA_DIR / "player_rate_identification.csv")
    trials_for_half = dict(zip(ident["rate_name"], ident["trials_for_reliability_0_5"]))
    trials_for_half["turnovers_per_touch"] = float(
        thresholds["turnover_rate_kappa"].iloc[0])
    METRIC_TO_RATE = {
        "shooting_pct": "shooting_pct", "points_per_shot": "shooting_pct",
        "shots_on_goal_pct": "shooting_pct",
        "one_point_conversion_pct": "one_point_pct",
        "two_point_conversion_pct": "two_point_pct",
        "faceoff_win_pct": "faceoff_win_pct", "save_pct": "save_pct",
        "turnovers_per_touch": "turnovers_per_touch",
    }

    # ---- 1. bounds, finiteness, nulls with a live denominator -------------
    for level, df, id_col, name_col, den_map in (
        ("team_season", team, "team_id", "team_name", _team_denominators(team)),
        ("player_season", player, "player_id", "player_name", _player_denominators(player)),
    ):
        for col in df.columns:
            if col in NON_METRIC_COLUMNS or not pd.api.types.is_numeric_dtype(df[col]):
                continue
            s = pd.to_numeric(df[col], errors="coerce")
            den_name, den = den_map.get(col, (None, None))
            bounds = declared_bounds(level, col)
            if bounds is not None:
                lo, hi = bounds
                bad = s.dropna()
                bad = bad[((bad < lo) if lo is not None else False) |
                          ((bad > hi) if hi is not None else False)]
                cat_unit = CATALOG_BY_KEY[(level, col)]["unit"]
                for idx, v in bad.items():
                    flag("OUT_OF_BOUNDS", level, df.loc[idx, id_col],
                         df.loc[idx, name_col], col, float(v), _den_at(den, idx),
                         f"catalogued unit {cat_unit!r} implies [{lo}, {hi}]; "
                         f"value is {v:.6g}")
            arr = s.to_numpy(dtype="float64", na_value=np.nan)
            for idx in s.index[np.isinf(arr)]:
                flag("NON_FINITE", level, df.loc[idx, id_col], df.loc[idx, name_col],
                     col, float(s.loc[idx]), _den_at(den, idx), "non-finite value")
            if den is not None and den_name != "games_played" \
                    and col not in DELIBERATE_NULL:
                live = s.isna() & (pd.to_numeric(den, errors="coerce") > 0)
                for idx in s.index[live]:
                    flag("NULL_WITH_POSITIVE_DENOMINATOR", level, df.loc[idx, id_col],
                         df.loc[idx, name_col], col, None, _den_at(den, idx),
                         f"NULL with {den_name} = {_den_at(den, idx)}")

    # ---- 2. small-sample leaders on unqualified rate leaderboards ---------
    for metric, rate in METRIC_TO_RATE.items():
        need = trials_for_half.get(rate)
        if need is None or not np.isfinite(need):
            continue
        top = plb[(plb["metric_name"] == metric) & (plb["scope"] == "ALL") &
                  (plb["rank"] <= 3)]
        for _, r in top.iterrows():
            den = r["denominator_value"]
            if pd.notna(den) and den < need:
                flag("SMALL_SAMPLE_LEADER", "player_season", r["player_id"],
                     r["player_name"], metric, r["metric_value"], den,
                     f"rank {int(r['rank'])} of {int(r['n_ranked'])} on "
                     f"{den:.0f} {r['denominator_name']}; reliability 0.5 for "
                     f"{rate} needs {need:.1f}")

    # ---- 3. degenerate rate extremes -------------------------------------
    for metric in ("shooting_pct", "faceoff_win_pct", "save_pct",
                   "one_point_conversion_pct", "two_point_conversion_pct",
                   "turnovers_per_touch"):
        sub = plb[(plb["metric_name"] == metric) & (plb["scope"] == "ALL")]
        for _, r in sub.iterrows():
            v = r["metric_value"]
            if pd.notna(v) and v in (0.0, 1.0) and pd.notna(r["denominator_value"]):
                flag("DEGENERATE_RATE_EXTREME", "player_season", r["player_id"],
                     r["player_name"], metric, v, r["denominator_value"],
                     f"exactly {v:.0f} on {r['denominator_value']:.0f} "
                     f"{r['denominator_name']}")

    # ---- 3b. value totals earned on a base the row does not name ----------
    # offensive_EPA_points_raw = shooting_value (base: shots) + turnover_value
    # (base: TOUCHES). recorded_offensive_opportunities is shots + turnovers, so
    # a player with no shots and no turnovers has a zero named base and can
    # still carry a positive turnover value for having handled the ball without
    # losing it. That is Phase 6 working correctly; the row's single named
    # denominator is what cannot express it.
    empty_base = plb[(plb["qualification_rule"] == "DESCRIPTIVE_VALUE_TOTAL")
                     & (plb["scope"] == "ALL")
                     & (plb["denominator_value"] == 0)
                     & (plb["metric_value"].abs() > 1e-12)]
    for _, r in empty_base.iterrows():
        flag("VALUE_ON_EMPTY_NAMED_BASE", "player_season", r["player_id"],
             r["player_name"], r["metric_name"], r["metric_value"], 0.0,
             f"{r['denominator_name']} = 0 but the total is "
             f"{r['metric_value']:+.4f}; the value comes from a component "
             f"denominated on touches ({_touch_count(player, r['player_id'])})")

    # ---- 4. qualification-scope pathologies ------------------------------
    all_metrics = plb[["category", "metric_name", "qualification_rule"]].drop_duplicates()
    qual_counts = (plb[plb["scope"] == "QUALIFIED"]
                   .groupby("metric_name").size().to_dict())
    for _, m in all_metrics.iterrows():
        n = qual_counts.get(m["metric_name"], 0)
        if m["qualification_rule"] == "NONE_COUNTING":
            continue
        if n == 0:
            code = ("TWO_POINT_UNIDENTIFIED"
                    if m["qualification_rule"] == "NOT_QUALIFIABLE_TWO_POINT"
                    else "EMPTY_QUALIFIED_SCOPE")
            flag(code, "player_season", None, None, m["metric_name"], None, None,
                 f"qualification rule {m['qualification_rule']} admits 0 players")
        elif n == 1:
            who = plb[(plb["scope"] == "QUALIFIED") &
                      (plb["metric_name"] == m["metric_name"])].iloc[0]
            flag("SINGLE_ROW_QUALIFIED_SCOPE", "player_season", who["player_id"],
                 who["player_name"], m["metric_name"], who["metric_value"],
                 who["denominator_value"],
                 f"qualification rule {m['qualification_rule']} admits exactly 1 player")

    # ---- 5. raw vs shrunk leader flips ------------------------------------
    for raw_m, shrunk_m in (("shooting_pct", "shooting_rate_shrunk"),
                            ("faceoff_win_pct", "faceoff_rate_shrunk"),
                            ("save_pct", "save_rate_shrunk")):
        a = plb[(plb["metric_name"] == raw_m) & (plb["scope"] == "ALL") &
                (plb["rank"] == 1)]
        b = plb[(plb["metric_name"] == shrunk_m) & (plb["scope"] == "ALL") &
                (plb["rank"] == 1)]
        if a.empty or b.empty:
            continue
        if set(a["player_id"]) != set(b["player_id"]):
            ar, br = a.iloc[0], b.iloc[0]
            flag("RAW_SHRUNK_ORDER_FLIP", "player_season", ar["player_id"],
                 ar["player_name"], raw_m, ar["metric_value"],
                 ar["denominator_value"],
                 f"raw leader {ar['player_name']} ({ar['metric_value']:.3f} on "
                 f"{ar['denominator_value']:.0f}); shrunk leader "
                 f"{br['player_name']} ({br['metric_value']:.3f} on "
                 f"{br['denominator_value']:.0f})")

    # ---- 6. fully collapsed shrinkage ------------------------------------
    for col in ("shooting_rate_shrunk", "one_point_rate_shrunk",
                "two_point_rate_shrunk", "faceoff_rate_shrunk", "save_rate_shrunk"):
        v = pd.to_numeric(player[col], errors="coerce").dropna()
        if v.empty:
            continue
        # Not `nunique() == 1`: a capped prior of 1e6 leaves the shrunk rates
        # differing in the 5th decimal of a relative sense (127 two-point rates
        # span 0.1343265 to 0.1343315), which is 32 distinct doubles and zero
        # distinct estimates. The test is whether the spread is negligible
        # against the mean, not whether the doubles are bit-equal.
        spread = float(v.max() - v.min())
        if spread / max(abs(float(v.mean())), 1e-12) < 1e-3:
            flag("SHRINKAGE_FULLY_COLLAPSED", "player_season", None, None, col,
                 float(v.mean()), float(v.size),
                 f"all {v.size} shrunk values lie within {spread:.2e} of "
                 f"{v.mean():.6f} -- a relative spread of "
                 f"{spread / abs(v.mean()):.1e}, i.e. every player is the league "
                 f"mean and no ability ordering exists")

    # ---- 7. position concentration in the top 10 -------------------------
    for metric in sorted(plb["metric_name"].unique()):
        top = plb[(plb["metric_name"] == metric) & (plb["scope"] == "ALL") &
                  (plb["rank"] <= 10)]
        if len(top) < 10:
            continue
        groups = top["position_group"].dropna().unique()
        if len(groups) == 1:
            flag("POSITION_CONCENTRATED_TOP10", "player_season", None, None, metric,
                 None, None,
                 f"top 10 is entirely {groups[0]}")

    # ---- 8. extreme z on the two class-A standardized measures ------------
    for col in ("EPA_points_null_z", "shooting_value_null_z", "faceoff_value_null_z",
                "goalie_value_null_z"):
        s = pd.to_numeric(player[col], errors="coerce")
        for idx in s.index[s.abs() > 3]:
            flag("EXTREME_Z", "player_season", player.loc[idx, "player_id"],
                 player.loc[idx, "player_name"], col, float(s.loc[idx]),
                 float(player.loc[idx, "games_played"]),
                 f"{s.loc[idx]:.2f} SD from what chance alone produces")

    # ---- 9. unattributed turnovers ---------------------------------------
    player_to = float(player["turnovers"].sum())
    team_to = float(team["turnovers"].sum())
    if team_to > 0 and player_to < team_to:
        flag("UNATTRIBUTED_TURNOVER_EXPOSURE", "league", None, "league", "turnovers",
             player_to, team_to,
             f"player sum {player_to:.0f} vs official team total {team_to:.0f} "
             f"({(1 - player_to / team_to) * 100:.1f}% attributed to no player)")

    # ---- 10. published identities ----------------------------------------
    # These MUST hold. A residual here is arithmetic, not a finding, so every
    # one of them is classified E and is fixed rather than reported.
    ident_checks = [
        ("team_season", "wins + losses + ties = games_played",
         team["wins"] + team["losses"] + team["ties"] - team["games_played"]),
        ("team_season", "one_point_points + two_point_points = points",
         team["one_point_points"] + team["two_point_points"] - team["points"]),
        ("team_season", "one_point_attempts + two_point_attempts = shots",
         team["one_point_attempts"] + team["two_point_attempts"] - team["shots"]),
        ("team_season", "one_point_goals + two_point_goals = goals",
         team["one_point_goals"] + team["two_point_goals"] - team["goals"]),
        ("team_season", "points_scored - points_allowed = point_differential",
         team["points_scored"] - team["points_allowed"] - team["point_differential"]),
        ("player_season", "one_point_goals + two_point_goals = goals",
         player["one_point_goals"] + player["two_point_goals"] - player["goals"]),
        # scoring_points is PLL POINTS FROM GOALS (a two-pointer counts twice).
        # It is NOT goals+assists: PLL does not use the NCAA points convention,
        # which is exactly the kind of thing the Lacrosse Reference mapping
        # document exists to keep straight.
        ("player_season", "one_point_goals + 2*two_point_goals = scoring_points",
         player["one_point_goals"] + 2 * player["two_point_goals"]
         - player["scoring_points"]),
        ("player_season", "one_point_attempts + two_point_attempts = shots",
         player["one_point_attempts"] + player["two_point_attempts"]
         - player["shots"]),
    ]
    for level, label, resid in ident_checks:
        bad = resid[resid.abs() > 1e-9]
        for idx in bad.index:
            df = team if level == "team_season" else player
            flag("IDENTITY_MISMATCH", level,
                 df.loc[idx, "team_id" if level == "team_season" else "player_id"],
                 df.loc[idx, "team_name" if level == "team_season" else "player_name"],
                 label, float(resid.loc[idx]), None,
                 f"residual {resid.loc[idx]:+g}")

    # The faceoff identity is NOT in the list above, at either level, and the
    # reason is a finding rather than an omission. PLL's official box score
    # counts more faceoffs than it counts wins plus losses, symmetrically for
    # both teams, in 8 of the 50 eligible games: 18 league-wide draws (0.7%) are
    # credited to neither side. Every rate in this system divides by `faceoffs`,
    # so the denominator is the count of draws TAKEN and a specialist's win
    # percentage is very slightly conservative. This is a property of the
    # source, so it is reported at class D and never "corrected".
    for level, df, id_col, name_col in (
        ("team_season", team, "team_id", "team_name"),
        ("player_season", player, "player_id", "player_name"),
    ):
        resid = df["faceoffs"] - df["faceoff_wins"] - df["faceoff_losses"]
        for idx in resid.index[resid.abs() > 1e-9]:
            flag("OFFICIAL_SOURCE_DISAGREEMENT", level, df.loc[idx, id_col],
                 df.loc[idx, name_col], "faceoff_wins + faceoff_losses = faceoffs",
                 float(resid.loc[idx]), float(df.loc[idx, "faceoffs"]),
                 f"official box score records {resid.loc[idx]:.0f} more faceoffs "
                 f"than wins plus losses; faceoff_win_pct divides by the larger "
                 f"denominator and is therefore slightly conservative")

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    sev_order = {"error": 0, "warn": 1, "info": 2}
    out["_s"] = out["severity"].map(sev_order)
    out = (out.sort_values(["_s", "flag_code", "entity_level", "metric_name",
                            "entity_id"], na_position="last")
              .drop(columns="_s").reset_index(drop=True))
    return out


# ---------------------------------------------------------------------------
def main():
    thresholds = write_thresholds()
    print(f"  turnovers-per-touch prior strength kappa = "
          f"{thresholds['turnover_rate_kappa'].iloc[0]:.2f} touches "
          f"({int(thresholds['n_players_clearing_gate'].iloc[0])} players clear it)")

    con = duckdb.connect()
    for sql_name, table, out_name in PIPELINE:
        run_sql_file(con, SQL_DIR / sql_name)
        if out_name:
            out_name = tagged(out_name)
            n = export(con, table, out_name)
            print(f"  {out_name:36s} {n:6d} rows")

    n = write_catalog()
    print(f"  {tagged('metric_catalog_2026.csv'):36s} {n:6d} rows")

    team = pd.read_csv(DATA_DIR / tagged("team_stats_2026.csv"))
    player = pd.read_csv(DATA_DIR / tagged("player_stats_2026.csv"))
    tlb = pd.read_csv(DATA_DIR / tagged("team_leaderboards_2026.csv"))
    plb = pd.read_csv(DATA_DIR / tagged("player_leaderboards_2026.csv"))

    audit = distribution_audit(team, player)
    audit.to_csv(DATA_DIR / tagged("metric_distribution_audit_2026.csv"), index=False)
    print(f"  {tagged('metric_distribution_audit_2026.csv'):36s} {len(audit):6d} rows")

    red = redundancy_analysis(team, player)
    red.to_csv(DATA_DIR / tagged("metric_redundancy_2026.csv"), index=False)
    print(f"  {tagged('metric_redundancy_2026.csv'):36s} {len(red):6d} rows")

    flags = sanity_flags(con, team, player, tlb, plb, thresholds)
    flags.to_csv(DATA_DIR / tagged("metric_sanity_flags_2026.csv"), index=False)
    print(f"  {tagged('metric_sanity_flags_2026.csv'):36s} {len(flags):6d} rows")
    if not flags.empty:
        for sev, n in flags["severity"].value_counts().items():
            print(f"      {sev:6s} {n}")
    return con


if __name__ == "__main__":
    main()
