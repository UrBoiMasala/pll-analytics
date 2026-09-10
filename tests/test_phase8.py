"""
Phase 8 tests for the 2026 comprehensive statistical layer.

Three kinds of test, in the same shape as Phases 5-7:

1. Catalog invariants, tested on the catalog data structure directly. The
   catalog is the contract every other artifact is checked against, so a
   catalog that is internally inconsistent invalidates the whole layer.

2. Unit tests on the Phase 8 SQL rules, run against small SYNTHETIC tables so a
   rule is verified in isolation rather than merely observed to hold in 2026.
   These catch a definition that is wrong but currently unexercised -- the
   floating-point rank-tie rule in particular passes on most metrics and was
   silently wrong on one.

3. Integration tests against the real 2026 outputs, asserting the specific
   evidence-based decisions this phase made and, crucially, the things it
   REFUSED to do: no composite, no two-point ability ranking, no shrunk value
   substituted into a raw column, no leaderboard row without a denominator.

Run with: python3 -m unittest tests.test_phase8 -v
"""
import math
import sys
import unittest
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_metric_catalog as mc  # noqa: E402
from pll_build_phase8_stats import (  # noqa: E402
    UNIT_BOUNDS, FLAG_SPEC, declared_bounds, NON_METRIC_COLUMNS,
)
from pll_player_value_models import beta_prior_by_moments  # noqa: E402


def _con():
    return duckdb.connect()


def _load(name, **kw):
    return pd.read_csv(DATA_DIR / name, **kw)


# ---------------------------------------------------------------------------
# 1. Catalog invariants
# ---------------------------------------------------------------------------
class TestCatalogInvariants(unittest.TestCase):
    def test_entity_level_and_name_are_unique_together(self):
        keys = [(r["entity_level"], r["metric_name"]) for r in mc.CATALOG]
        self.assertEqual(len(keys), len(set(keys)))

    def test_games_played_exists_at_both_levels(self):
        """The one name that legitimately repeats -- proof the key is the pair,
        not a duplicate that slipped through."""
        self.assertIn(("team_season", "games_played"), mc.CATALOG_BY_KEY)
        self.assertIn(("player_season", "games_played"), mc.CATALOG_BY_KEY)

    def test_every_row_has_every_column(self):
        for r in mc.CATALOG:
            self.assertEqual(set(r), set(mc.CATALOG_COLUMNS)
                             if hasattr(mc, "CATALOG_COLUMNS") else set(r))

    def test_statuses_come_from_the_closed_vocabulary(self):
        for r in mc.CATALOG:
            self.assertIn(r["publication_status"], mc.PUBLICATION_STATUSES)
            self.assertIn(r["freeze_classification"], mc.FREEZE_CLASSIFICATIONS)
            self.assertIn(str(r["higher_is_better"]), mc.DIRECTIONS)

    def test_no_core_metric_is_do_not_use(self):
        for r in mc.CATALOG:
            if r["publication_status"] == "CORE":
                self.assertNotEqual(r["freeze_classification"], "DO_NOT_USE",
                                    r["metric_name"])

    def test_unsupported_and_deferred_metrics_state_a_reason(self):
        for r in mc.CATALOG:
            if r["publication_status"] in ("UNSUPPORTED", "DEFERRED"):
                self.assertGreater(len(r["known_limitations"]), 60, r["metric_name"])

    def test_duplicate_metric_name_is_rejected(self):
        rows = [dict(mc.CATALOG[0]), dict(mc.CATALOG[0])]
        with self.assertRaises(ValueError):
            mc._validate(rows)

    def test_a_composite_named_metric_must_be_unsupported(self):
        bad = dict(mc.CATALOG[0])
        bad["metric_name"] = "mvp_score"
        bad["publication_status"] = "CORE"
        with self.assertRaises(ValueError):
            mc._validate([bad])

    def test_identical_redundancy_must_point_at_a_real_metric(self):
        bad = dict(mc.CATALOG_BY_KEY[("team_season", "turnover_rate")])
        bad["redundancy_class"] = "IDENTICAL(a_metric_that_does_not_exist)"
        with self.assertRaises(ValueError):
            mc._validate([bad])

    def test_the_composite_is_catalogued_as_unsupported(self):
        row = mc.CATALOG_BY_KEY[("player_season",
                                 "statistical_tewaaraton_or_mvp_composite")]
        self.assertEqual(row["publication_status"], "UNSUPPORTED")
        self.assertEqual(row["freeze_classification"], "DO_NOT_USE")

    def test_two_point_ability_metrics_carry_the_non_identification_caveat(self):
        row = mc.CATALOG_BY_KEY[("player_season", "two_point_rate_shrunk")]
        self.assertIn("NOT IDENTIFIABLE", row["known_limitations"].upper())


# ---------------------------------------------------------------------------
# 2. SQL rule unit tests on synthetic data
# ---------------------------------------------------------------------------
class TestRankingRules(unittest.TestCase):
    """RANK() is competition ranking on a value rounded to 12 decimals."""

    def _rank(self, values, higher_is_better=True):
        con = _con()
        con.register("m", pd.DataFrame({"v": values}))
        return [r[0] for r in con.execute(f"""
            SELECT RANK() OVER (ORDER BY ROUND({'-v' if higher_is_better else 'v'}, 12))
            FROM m ORDER BY {'v DESC' if higher_is_better else 'v'}""").fetchall()]

    def test_competition_ranking_skips_after_a_tie(self):
        self.assertEqual(self._rank([10.0, 10.0, 5.0]), [1, 1, 3])

    def test_lower_is_better_inverts_the_order(self):
        self.assertEqual(self._rank([1.0, 2.0, 3.0], higher_is_better=False),
                         [1, 2, 3])

    def test_values_differing_below_1e12_tie(self):
        """The defect this rule exists for. Phase 7 computes (rate*g)/g, so two
        players with identical records can differ in the last ULP; ranking the
        raw doubles split 40 identical defensive values into 8 + 32."""
        a = -0.030957118585139
        b = float(np.nextafter(a, 0.0))
        self.assertNotEqual(a, b, "the test values must actually differ as doubles")
        self.assertEqual(self._rank([a, b]), [1, 1])

    def test_real_differences_are_still_ordered(self):
        self.assertEqual(self._rank([0.30001, 0.30000], True), [1, 2])


class TestWilsonInterval(unittest.TestCase):
    """The two-point audit's interval must not collapse at the boundary."""

    def _wilson(self, k, n):
        con = _con()
        return con.execute(f"""
            SELECT (({k}.0 + 1.9208) - 1.96 * SQRT({k}.0 * (1 - {k}.0 / {n}.0) + 0.9604))
                       / ({n}.0 + 3.8416),
                   (({k}.0 + 1.9208) + 1.96 * SQRT({k}.0 * (1 - {k}.0 / {n}.0) + 0.9604))
                       / ({n}.0 + 3.8416)""").fetchone()

    def _reference(self, k, n, z=1.96):
        den = n + z * z
        centre = (k + z * z / 2) / den
        half = z / den * math.sqrt(k * (n - k) / n + z * z / 4)
        return centre - half, centre + half

    def test_matches_the_closed_form(self):
        for k, n in ((0, 14), (7, 29), (72, 536), (3, 69)):
            got, ref = self._wilson(k, n), self._reference(k, n)
            self.assertAlmostEqual(got[0], ref[0], places=12, msg=f"{k}/{n} low")
            self.assertAlmostEqual(got[1], ref[1], places=12, msg=f"{k}/{n} high")

    def test_zero_for_n_still_has_width(self):
        lo, hi = self._wilson(0, 14)
        self.assertAlmostEqual(lo, 0.0, places=9)
        self.assertGreater(hi, 0.2, "a 0-for-14 cell must not report zero uncertainty")

    def test_wald_se_collapses_where_wilson_does_not(self):
        """Documents why both are published: the Wald SE is zero at 0-for-n."""
        p = 0.0
        wald = 2 * math.sqrt(p * (1 - p) / 14)
        self.assertEqual(wald, 0.0)
        self.assertGreater(self._wilson(0, 14)[1], 0.0)


class TestQualificationArithmetic(unittest.TestCase):
    """reliability = n / (n + kappa) >= 0.5 <=> n >= kappa. No round numbers."""

    def test_reliability_half_is_exactly_kappa_trials(self):
        for kappa in (15.90343, 70.7824, 300.340358, 108.82):
            self.assertAlmostEqual(kappa / (kappa + kappa), 0.5, places=12)

    def test_reliability_is_monotone_in_trials(self):
        kappa = 70.7824
        rel = [n / (n + kappa) for n in (1, 10, 100, 1000)]
        self.assertEqual(rel, sorted(rel))

    def test_turnover_prior_uses_phase_6_estimator_and_is_reproducible(self):
        opps = _load("player_opportunities.csv")
        a, b = beta_prior_by_moments(opps["turnovers"].to_numpy(),
                                     opps["touches"].to_numpy())
        thr = _load("_phase8_scratch/phase8_thresholds.csv")
        self.assertAlmostEqual(a + b, float(thr["turnover_rate_kappa"].iloc[0]),
                               places=9)
        self.assertAlmostEqual(float(thr["turnover_rate_min_touches"].iloc[0]),
                               a + b, places=9)

    def test_a_prior_with_no_detectable_spread_is_capped(self):
        """The two-point case, reproduced on synthetic data: when the observed
        between-player spread is no wider than binomial noise alone predicts,
        the estimator caps kappa and every shrunk rate becomes the league mean.
        Constructed with every player on the SAME rate, so the observed spread
        is exactly zero and the excess is unambiguously negative."""
        n = np.full(200, 4)
        k = np.full(200, 1)
        a, b = beta_prior_by_moments(k, n)
        self.assertGreater(a + b, 1e5)
        shrunk = (k + a) / (n + a + b)
        self.assertLess(float(np.std(shrunk)), 1e-9,
                        "a capped prior must shrink every player to one value")


class TestBoundsAreCatalogDriven(unittest.TestCase):
    def test_percentage_means_zero_to_one(self):
        self.assertEqual(UNIT_BOUNDS["percentage"], (0.0, 1.0))

    def test_percentile_means_zero_to_one_hundred(self):
        self.assertEqual(UNIT_BOUNDS["percentile 0-100"], (0.0, 100.0))

    def test_a_count_per_possession_rate_is_not_bounded_by_one(self):
        """turnover_rate is turnovers per possession. A name-based rule would
        have bounds-checked it at 1.0 and been wrong."""
        self.assertIsNone(declared_bounds("team_season", "turnover_rate"))
        self.assertIsNone(declared_bounds("team_season", "shots_per_possession"))

    def test_a_bounded_ratio_without_a_pct_suffix_is_still_checked(self):
        """possession_span_coverage_ratio is bounded below at 0 and does not end
        in "_pct". A name-based rule would have skipped it entirely."""
        b = declared_bounds("team_season", "possession_span_coverage_ratio")
        self.assertIsNotNone(b)
        self.assertEqual(b[0], 0.0)
        self.assertIsNone(b[1], "a coverage ratio is not capped at 1 by definition")


class TestFlagSpec(unittest.TestCase):
    def test_every_flag_carries_a_classification_from_the_brief(self):
        for code, (cls, sev, desc) in FLAG_SPEC.items():
            self.assertIn(cls, set("ABCDE"), code)
            self.assertIn(sev, {"error", "warn", "info"}, code)
            self.assertGreater(len(desc), 40, code)

    def test_only_class_e_is_an_error(self):
        for code, (cls, sev, _) in FLAG_SPEC.items():
            if sev == "error":
                self.assertEqual(cls, "E", f"{code} is an error but not class E")


# ---------------------------------------------------------------------------
# 3. Integration tests against the real 2026 outputs
# ---------------------------------------------------------------------------
class TestPublishedTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.team = _load("team_stats_2026.csv", dtype={"team_id": str})
        cls.player = _load("player_stats_2026.csv",
                           dtype={"player_id": str, "team_id": str})
        cls.tlb = _load("team_leaderboards_2026.csv", dtype={"team_id": str})
        cls.plb = _load("player_leaderboards_2026.csv",
                        dtype={"player_id": str, "team_id": str})
        cls.two_pt = _load("two_point_audit_2026.csv")
        cls.flags = _load("metric_sanity_flags_2026.csv")
        cls.audit = _load("metric_distribution_audit_2026.csv")
        cls.report = _load("phase8_validation_report.csv")
        cls.games = _load("games.csv")

    def test_eight_teams_and_two_hundred_twenty_eight_players(self):
        self.assertEqual(len(self.team), 8)
        self.assertEqual(len(self.player), 228)

    def test_player_scoring_points_sum_to_the_league_score(self):
        eg = self.games[self.games["is_completed"]
                        & self.games["include_in_league_analytics"]
                        & ~self.games["is_all_star"]]
        league = float(eg["home_score"].sum() + eg["away_score"].sum())
        self.assertAlmostEqual(float(self.player["scoring_points"].sum()), league,
                               places=6)
        self.assertAlmostEqual(float(self.team["points_scored"].sum()), league,
                               places=6)

    def test_scoring_points_is_goal_points_and_not_goals_plus_assists(self):
        """PLL's own `points` column includes assists. Confusing the two is the
        single easiest way to publish a wrong scoring leaderboard."""
        expected = (self.player["one_point_goals"]
                    + 2 * self.player["two_point_goals"])
        pd.testing.assert_series_equal(self.player["scoring_points"], expected,
                                       check_names=False)
        with_assists = expected + self.player["official_assists"]
        self.assertGreater(int((with_assists != self.player["scoring_points"]).sum()),
                           100, "the two conventions must actually differ in 2026")

    def test_every_leaderboard_row_carries_a_named_denominator(self):
        for df in (self.tlb, self.plb):
            self.assertEqual(int(df["denominator_name"].isna().sum()), 0)

    def test_every_player_leaderboard_row_carries_a_position(self):
        self.assertEqual(int(self.plb["canonical_position"].isna().sum()), 0)

    def test_every_player_leaderboard_row_carries_a_position_rank(self):
        self.assertEqual(int(self.plb["position_rank"].isna().sum()), 0)
        self.assertTrue((self.plb["position_rank"]
                         <= self.plb["position_n_ranked"]).all())

    def test_qualified_is_a_subset_of_all(self):
        for metric in self.plb["metric_name"].unique():
            a = set(self.plb[(self.plb["metric_name"] == metric)
                             & (self.plb["scope"] == "ALL")]["player_id"])
            q = set(self.plb[(self.plb["metric_name"] == metric)
                             & (self.plb["scope"] == "QUALIFIED")]["player_id"])
            self.assertTrue(q <= a, metric)

    def test_no_null_value_is_ever_ranked(self):
        for df in (self.tlb, self.plb):
            self.assertEqual(int(df["metric_value"].isna().sum()), 0)

    def test_every_qualification_rule_has_a_reason(self):
        self.assertEqual(int(self.plb["qualification_reason"].isna().sum()), 0)

    def test_validation_report_is_all_pass(self):
        self.assertEqual(int((self.report["status"] != "PASS").sum()), 0,
                         self.report[self.report["status"] != "PASS"].to_string())
        self.assertGreaterEqual(len(self.report), 24)


class TestPhase8RefusedToDo(unittest.TestCase):
    """The tests that matter most: what Phase 8 did NOT build."""

    @classmethod
    def setUpClass(cls):
        cls.player = _load("player_stats_2026.csv", dtype={"player_id": str})
        cls.team = _load("team_stats_2026.csv", dtype={"team_id": str})
        cls.plb = _load("player_leaderboards_2026.csv", dtype={"player_id": str})
        cls.tlb = _load("team_leaderboards_2026.csv", dtype={"team_id": str})
        cls.catalog = _load("metric_catalog_2026.csv")

    def test_no_composite_award_or_replacement_level_metric_is_published(self):
        surfaces = (list(self.player.columns) + list(self.team.columns)
                    + list(self.plb["metric_name"].unique())
                    + list(self.tlb["metric_name"].unique()))
        for name in surfaces:
            for bad in mc.FORBIDDEN_IN_PUBLISHED:
                self.assertNotIn(bad, str(name).lower(), f"{name} contains {bad}")

    def test_the_catalog_names_the_composite_only_to_refuse_it(self):
        rows = self.catalog[self.catalog["metric_name"].str.lower()
                            .str.contains("|".join(mc.FORBIDDEN_IN_PUBLISHED))]
        self.assertGreater(len(rows), 0, "the refusal must be documented, not silent")
        self.assertTrue((rows["publication_status"] == "UNSUPPORTED").all())

    def test_no_qualified_two_point_ability_leaderboard_exists(self):
        q = self.plb[(self.plb["metric_name"] == "two_point_conversion_pct")
                     & (self.plb["scope"] == "QUALIFIED")]
        self.assertEqual(len(q), 0,
                         "individual two-point ability is not identifiable in 2026")

    def test_every_two_point_row_is_labelled_descriptive(self):
        rows = self.plb[self.plb["metric_name"] == "two_point_conversion_pct"]
        self.assertTrue((rows["category"] == "two_point_descriptive").all())
        self.assertTrue((rows["qualification_rule"] == "NOT_QUALIFIABLE_TWO_POINT").all())

    def test_two_point_shrinkage_is_fully_collapsed(self):
        v = self.player["two_point_rate_shrunk"].dropna()
        self.assertLess(float(v.std()), 1e-6)
        self.assertLess(float(self.player["two_point_reliability"].max()), 0.001)

    def test_shrunk_rates_are_never_substituted_into_a_raw_column(self):
        for raw, shrunk in (("shooting_rate_raw", "shooting_rate_shrunk"),
                            ("faceoff_rate_raw", "faceoff_rate_shrunk"),
                            ("save_rate_raw", "save_rate_shrunk"),
                            ("one_point_rate_raw", "one_point_rate_shrunk")):
            both = self.player[[raw, shrunk]].dropna()
            self.assertFalse(np.allclose(both[raw], both[shrunk], atol=1e-12),
                             f"{shrunk} is identical to {raw}")

    def test_raw_and_shrunk_rows_carry_each_other(self):
        paired = self.plb[self.plb["metric_name"].isin(
            ["shooting_pct", "shooting_rate_shrunk", "faceoff_win_pct",
             "faceoff_rate_shrunk", "save_pct", "save_rate_shrunk"])]
        self.assertEqual(int(paired["companion_metric_name"].isna().sum()), 0)

    def test_defensive_value_keeps_the_word_partial(self):
        from pll_build_phase8_stats import NON_METRIC_COLUMNS
        for col in self.player.columns:
            if col in NON_METRIC_COLUMNS:
                continue  # defensive_value_scope is the caveat text, not a value
            if "defensive" in col and ("value" in col or "EPA" in col):
                self.assertIn("partial", col, col)
        self.assertTrue(self.player["defense_partial"].all())

    def test_no_clearing_or_riding_efficiency_was_manufactured(self):
        """Raw counts only. Phase 5 established the events do not exist."""
        for col in self.team.columns:
            low = col.lower()
            if "clear" in low or "ride" in low:
                self.assertNotIn("pct", low, col)
                self.assertNotIn("rate", low, col)
                self.assertNotIn("efficiency", low, col)

    def test_no_reconstructed_time_of_possession_is_published(self):
        top = [c for c in self.team.columns if "time_of_possession" in c]
        self.assertGreater(len(top), 0)
        for c in top:
            self.assertIn("official", c,
                          "only the OFFICIAL time of possession may be published")

    def test_no_span_based_duration_is_published_as_a_statistic(self):
        for c in self.team.columns:
            self.assertNotIn("mean_measurable_span", c)
            self.assertNotIn("median_complete_possession_duration", c)

    def test_no_assist_value_or_ground_ball_value_column_exists(self):
        for c in self.player.columns:
            self.assertNotIn(c, ("assist_value", "ground_ball_value"))
        self.assertTrue(self.player["assist_value_status"].astype(str)
                        .str.contains("deferred").all())
        self.assertTrue(self.player["ground_ball_value_status"].astype(str)
                        .str.contains("deferred").all())

    def test_no_opponent_adjustment_is_claimed(self):
        row = self.catalog[self.catalog["metric_name"] == "opponent_adjusted_value"]
        self.assertEqual(len(row), 1)
        self.assertIn(row["publication_status"].iloc[0], ("DEFERRED", "UNSUPPORTED"))


class TestValueAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.player = _load("player_stats_2026.csv", dtype={"player_id": str})
        cls.adj = _load("player_adjusted_value.csv", dtype={"player_id": str})
        cls.comp = _load("player_value_components.csv", dtype={"player_id": str})

    def test_epa_points_raw_is_the_sum_of_its_components(self):
        s = (self.player["shooting_value_raw"].fillna(0)
             + self.player["turnover_value_raw"].fillna(0)
             + self.player["faceoff_value_raw"].fillna(0)
             + self.player["goalie_value_raw"].fillna(0)
             + self.player["defensive_value_partial_raw"].fillna(0))
        np.testing.assert_allclose(self.player["EPA_points_raw"], s, atol=1e-9)

    def test_phase_6_shooting_value_is_carried_bit_for_bit(self):
        a = self.player.set_index("player_id")["shooting_value_raw"]
        b = self.comp.set_index("player_id")["shooting_value"].reindex(a.index)
        np.testing.assert_array_equal(a.to_numpy(), b.to_numpy())

    def test_phase_7_epa_is_carried_bit_for_bit(self):
        a = self.player.set_index("player_id")["EPA_points_raw"]
        b = self.adj.set_index("player_id")["EPA_points_raw"].reindex(a.index)
        np.testing.assert_array_equal(a.to_numpy(), b.to_numpy())

    def test_goalie_save_rate_uses_the_official_trial_base(self):
        g = self.player[self.player["saves"] + self.player["goals_allowed"] > 0]
        np.testing.assert_allclose(
            g["save_pct"], g["saves"] / (g["saves"] + g["goals_allowed"]), atol=1e-12)

    def test_shots_on_goal_faced_is_a_different_and_larger_base(self):
        """Documented in the qualification rule; asserted here so a future
        rename cannot quietly conflate them."""
        self.assertGreater(int(self.player["shots_on_goal_faced"].sum()),
                           int((self.player["saves"]
                                + self.player["goals_allowed"]).sum()))


class TestSanityFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flags = _load("metric_sanity_flags_2026.csv")
        cls.plb = _load("player_leaderboards_2026.csv", dtype={"player_id": str})
        cls.team = _load("team_stats_2026.csv", dtype={"team_id": str})
        cls.player = _load("player_stats_2026.csv", dtype={"player_id": str})

    def test_no_class_e_flag_survives(self):
        e = self.flags[self.flags["classification"] == "E"]
        self.assertEqual(len(e), 0, e.to_string())

    def test_the_unattributed_turnover_gap_is_reported(self):
        f = self.flags[self.flags["flag_code"] == "UNATTRIBUTED_TURNOVER_EXPOSURE"]
        self.assertEqual(len(f), 1)
        gap = 1 - float(self.player["turnovers"].sum()) / float(self.team["turnovers"].sum())
        self.assertGreater(gap, 0.15, "the ~19% gap must still be present and reported")

    def test_small_sample_leaders_are_flagged_not_removed(self):
        f = self.flags[self.flags["flag_code"] == "SMALL_SAMPLE_LEADER"]
        self.assertGreater(len(f), 0)
        # the flagged players must still be on the ALL leaderboard: the
        # unqualified scope is the descriptive record and is not censored
        for _, r in f.head(10).iterrows():
            rows = self.plb[(self.plb["metric_name"] == r["metric_name"])
                            & (self.plb["scope"] == "ALL")
                            & (self.plb["player_id"] == str(r["entity_id"]).zfill(6))]
            self.assertEqual(len(rows), 1, r["metric_name"])

    def test_the_faceoff_draw_residual_is_class_d_not_a_bug(self):
        f = self.flags[self.flags["flag_code"] == "OFFICIAL_SOURCE_DISAGREEMENT"]
        self.assertGreater(len(f), 0)
        self.assertTrue((f["classification"] == "D").all())
        resid = (self.team["faceoffs"] - self.team["faceoff_wins"]
                 - self.team["faceoff_losses"]).sum()
        self.assertEqual(int(resid), 18)

    def test_the_empty_two_point_qualified_scope_is_reported_as_a_finding(self):
        f = self.flags[self.flags["flag_code"] == "TWO_POINT_UNIDENTIFIED"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f["classification"].iloc[0], "D")

    def test_the_single_row_goalie_leaderboard_is_reported(self):
        f = self.flags[(self.flags["flag_code"] == "SINGLE_ROW_QUALIFIED_SCOPE")
                       & (self.flags["metric_name"] == "save_pct")]
        self.assertEqual(len(f), 1)


class TestTwoPointAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = _load("two_point_audit_2026.csv")
        cls.team = _load("team_stats_2026.csv", dtype={"team_id": str})

    def test_league_row_matches_the_official_team_totals(self):
        lg = self.a[self.a["scope"] == "LEAGUE"].iloc[0]
        self.assertEqual(int(lg["two_point_attempts"]),
                         int(self.team["two_point_attempts"].sum()))
        self.assertEqual(int(lg["two_point_goals"]),
                         int(self.team["two_point_goals"].sum()))
        self.assertEqual(int(lg["total_attempts"]), int(self.team["shots"].sum()))

    def test_the_return_difference_is_two_p_minus_q(self):
        r = self.a.dropna(subset=["two_point_minus_one_point_return"])
        expected = (2 * r["two_point_goals"] / r["two_point_attempts"]
                    - r["one_point_goals"] / r["one_point_attempts"])
        np.testing.assert_allclose(r["two_point_minus_one_point_return"], expected,
                                   atol=1e-12)

    def test_every_scope_key_is_unique(self):
        self.assertEqual(int(self.a.duplicated(["scope", "scope_key"]).sum()), 0)

    def test_player_scope_is_production_only(self):
        """No conversion rate in the player scope may be presented with a
        sample status better than 'thin'."""
        p = self.a[self.a["scope"] == "PLAYER"]
        self.assertGreater(len(p), 0)
        self.assertNotIn("adequate_for_a_group_estimate",
                         set(p["two_point_sample_status"]))


class TestDistributionAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = _load("metric_distribution_audit_2026.csv")
        cls.team = _load("team_stats_2026.csv", dtype={"team_id": str})
        cls.player = _load("player_stats_2026.csv", dtype={"player_id": str})

    def test_no_metric_is_out_of_its_declared_bounds(self):
        self.assertEqual(int(self.audit["out_of_bounds_rows"].sum()), 0)

    def test_every_audited_metric_is_catalogued(self):
        self.assertTrue(self.audit["in_catalog"].all(),
                        self.audit[~self.audit["in_catalog"]]["metric_name"].tolist())

    def test_identifiers_are_not_audited_as_metrics(self):
        for c in ("team_id", "player_id", "canonical_position"):
            self.assertNotIn(c, set(self.audit["metric_name"]))
            self.assertIn(c, NON_METRIC_COLUMNS)

    def test_extremes_carry_a_holder_and_a_denominator(self):
        rated = self.audit[self.audit["denominator_name"].notna()
                           & self.audit["max"].notna()]
        self.assertEqual(int(rated["max_holder"].isna().sum()), 0)


if __name__ == "__main__":
    unittest.main()
