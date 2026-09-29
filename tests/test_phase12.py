"""
Phase 12 tests: player value model research, without building an award.

Two kinds, matching the repository's established shape:

1. Integration tests over the five new research CSVs and the Phase 12
   validator's own recomputation logic.
2. Regression tests that Phase 12 introduced no MVP/Tewaaraton/award/
   composite/replacement-level artifact under any name, changed no canonical
   or raw data, and that every non-negotiable rule in the Phase 12 brief
   holds on the actual published files.

Run with: python3 -m unittest tests.test_phase12 -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED       # noqa: E402
import pll_phase12_player_value_research as p12             # noqa: E402
import pll_validate_phase12 as v12                          # noqa: E402

SEASONS = [2022, 2023, 2024, 2025, 2026]


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


# ---------------------------------------------------------------------------
# 1. Signal inventory
# ---------------------------------------------------------------------------
class TestSignalInventory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sig = hf("player_value_signal_inventory.csv")

    def test_every_category_the_brief_names_is_present(self):
        required = {"scoring", "shooting", "ball security", "usage",
                    "faceoff", "goalie", "defense", "team context"}
        present = set()
        for c in self.sig["category"]:
            present.add(str(c).split(" (")[0].strip())
        for r in required:
            self.assertTrue(any(r in p for p in present), r)

    def test_no_signal_row_is_missing_its_classification_fields(self):
        for col in ("definition", "measures_type", "season_award_suitability"):
            self.assertEqual(int(self.sig[col].isna().sum()), 0, col)

    def test_two_point_conversion_is_flagged_unsupported_somewhere_on_its_row(self):
        row = self.sig[self.sig["signal_name"].str.contains(
            "two_point_conversion", case=False, na=False)]
        self.assertFalse(row.empty)
        combined = " ".join(row.iloc[0].astype(str)).lower()
        self.assertIn("unsupported", combined)

    def test_two_point_attempt_share_is_flagged_highly_identifiable(self):
        row = self.sig[self.sig["signal_name"].str.contains(
            "two_point_attempt_share", na=False)]
        self.assertFalse(row.empty)
        self.assertGreaterEqual(
            float(row.iloc[0]["career_pct_reaching_reliability_gate"]), 80.0)

    def test_games_played_is_denominator_not_value(self):
        row = self.sig[self.sig["signal_name"].str.contains(
            "games_played", na=False)]
        self.assertFalse(row.empty)
        self.assertIn("NOT as a value", " ".join(row.iloc[0].astype(str)))


# ---------------------------------------------------------------------------
# 2. Dependency / double counting
# ---------------------------------------------------------------------------
class TestDependencyAnalysis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dep = hf("player_value_metric_dependency.csv")
        cls.players = hf("player_stats_2022_2026.csv",
                         dtype={"player_id": str, "team_id": str})

    def test_accounting_identity_holds_exactly_on_canonical_data(self):
        comp_cols = ["shooting_value_raw", "turnover_value_raw",
                    "faceoff_value_raw", "goalie_value_raw",
                    "defensive_value_partial_raw"]
        resid = self.players[comp_cols].fillna(0).sum(axis=1) \
            - self.players["EPA_points_raw"]
        self.assertLess(float(resid.abs().max()), 1e-9)
        row = self.dep[(self.dep["analysis_type"] == "ACCOUNTING_IDENTITY") &
                       (self.dep["metric_a"] == "sum(5 components)")]
        self.assertFalse(row.empty)
        self.assertEqual(row.iloc[0]["double_counting_risk"], "NONE (this is the identity that PREVENTS double counting, not an instance of it)")

    def test_nested_components_are_flagged_high_or_moderate_double_counting_risk(self):
        nested = self.dep[self.dep["relationship_type"] == "NESTED_COMPONENT"]
        self.assertGreater(len(nested), 5)
        self.assertTrue(nested["double_counting_risk"].isin(["HIGH", "MODERATE"]).all())

    def test_vif_diagnostic_shows_goals_and_shots_highly_collinear(self):
        vif = self.dep[self.dep["analysis_type"] == "VIF"].set_index("metric_a")
        self.assertGreater(float(vif.loc["goals", "vif"]), 10)
        self.assertGreater(float(vif.loc["shots", "vif"]), 10)

    def test_disjoint_pairs_carry_no_double_counting_risk(self):
        disjoint = self.dep[self.dep["relationship_type"] == "DISJOINT_BY_CONSTRUCTION"]
        self.assertGreater(len(disjoint), 0)
        self.assertTrue((disjoint["double_counting_risk"] == "NONE").all())

    def test_games_played_vs_caused_turnovers_reproduces_phase10_finding(self):
        rows = self.dep[self.dep["role_scope"].astype(str).str.startswith(
            "defensive_field_")]
        self.assertGreaterEqual(len(rows), 4)
        for _, r in rows.iterrows():
            self.assertGreaterEqual(float(r["spearman_r"]), 0.4)


# ---------------------------------------------------------------------------
# 3. Model candidates -- the non-negotiable rules, checked directly
# ---------------------------------------------------------------------------
class TestModelCandidates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mc = hf("player_value_model_candidates.csv")

    def test_every_row_has_a_unit_and_a_baseline(self):
        for col in ("unit", "baseline"):
            self.assertEqual(int(self.mc[col].isna().sum()), 0, col)
            self.assertTrue((self.mc[col].astype(str).str.len() > 0).all())

    def test_status_vocabulary_is_closed(self):
        allowed = {"VIABLE", "VIABLE_WITH_CAVEAT", "ROLE_ONLY", "EXPERIMENTAL",
                  "REJECTED", "UNSUPPORTED"}
        self.assertTrue(set(self.mc["status"]) <= allowed)

    def test_rejected_and_unsupported_rows_carry_a_real_reason(self):
        terminal = self.mc[self.mc["status"].isin(["REJECTED", "UNSUPPORTED"])]
        self.assertGreater(len(terminal), 0)
        self.assertTrue((terminal["major_failure_modes"].astype(str).str.len() >= 20).all())

    def test_no_cross_role_model_candidate_is_marked_viable_without_caveat(self):
        cross = self.mc[self.mc["cross_position_claim"].astype(str).str.contains(
            "YES", na=False)]
        self.assertGreater(len(cross), 0)
        self.assertFalse((cross["status"] == "VIABLE").any(),
                         "a cross-position claim was marked VIABLE outright")

    def test_arbitrary_and_equal_weighting_are_explicitly_rejected(self):
        for mid in ("FORBIDDEN_arbitrary_weighted_composite",
                   "FORBIDDEN_equal_weighting_default",
                   "FORBIDDEN_positional_zscore_as_value"):
            row = self.mc[self.mc["model_id"] == mid]
            self.assertFalse(row.empty, mid)
            self.assertEqual(row.iloc[0]["status"], "REJECTED", mid)

    def test_within_position_z_and_percentile_are_rejected(self):
        for mid in ("XPOS_M03", "XPOS_M04"):
            row = self.mc[self.mc["model_id"] == mid]
            self.assertFalse(row.empty, mid)
            self.assertEqual(row.iloc[0]["status"], "REJECTED", mid)

    def test_model_family_5_team_outcome_regression_ran_to_completion(self):
        row = self.mc[self.mc["model_id"] == "MF5_team_epa_vs_win_pct_regression"]
        self.assertFalse(row.empty)
        self.assertIn("R^2", row.iloc[0]["validation_result"])
        self.assertEqual(row.iloc[0]["status"], "EXPERIMENTAL")

    def test_no_model_candidate_is_keyed_by_player(self):
        self.assertNotIn("player_id", self.mc.columns)
        self.assertNotIn("player_name", self.mc.columns)


# ---------------------------------------------------------------------------
# 4. Validation results
# ---------------------------------------------------------------------------
class TestValidationResults(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.val = hf("player_value_validation_results.csv")

    def test_all_six_validation_families_present(self):
        required = {"ACCOUNTING_VALIDITY", "PREDICTIVE_VALIDITY",
                   "CONCURRENT_VALIDITY", "STABILITY",
                   "BOOTSTRAP_UNCERTAINTY", "LEAVE_ONE_SEASON_OUT"}
        self.assertEqual(required - set(self.val["validation_type"]), set())

    def test_row_level_accounting_identity_is_exact_pass(self):
        row = self.val[self.val["model_or_metric"] ==
                       "EPA_points_raw = sum(5 components)"]
        self.assertFalse(row.empty)
        self.assertTrue((row["result"] == "PASS").all())

    def test_season_level_accounting_exceptions_are_documented_not_hidden(self):
        rows = self.val[(self.val["validation_type"] == "ACCOUNTING_VALIDITY") &
                        (self.val["model_or_metric"] == "EPA_points_raw")]
        fails = rows[rows["result"] != "PASS"]
        self.assertGreater(len(fails), 0, "expected the known 2022/2024 residual to be present")
        for _, r in fails.iterrows():
            interp = str(r["interpretation"])
            self.assertTrue("INFERRED cause" in interp or "UNRESOLVED residual" in interp,
                           interp)

    def test_cross_position_predictive_validity_reproduces_phase10_range(self):
        rows = self.val[(self.val["validation_type"] == "PREDICTIVE_VALIDITY") &
                        (self.val["model_or_metric"].astype(str).str.startswith("XPOS_"))]
        self.assertEqual(len(rows), 10)
        for v in rows["statistic_value"]:
            self.assertGreaterEqual(float(v), 0.1)
            self.assertLessEqual(float(v), 0.3)


# ---------------------------------------------------------------------------
# 5. Counterfactual tests
# ---------------------------------------------------------------------------
class TestCounterfactuals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cf = hf("player_value_counterfactual_tests.csv")

    def test_all_deterministic_tests_pass_their_stated_expectation(self):
        expected = {
            "T1_same_efficiency_different_volume": True,
            "T2_same_volume_different_efficiency": True,
            "T3_same_scoring_different_turnovers": True,
            "T4_same_faceoff_rate_different_draw_volume": True,
            "T5_same_save_pct_different_shots_faced": True,
            "T7_equal_z_unequal_magnitude_cross_role": False,
        }
        idx = self.cf.set_index("test_id")
        for tid, exp in expected.items():
            self.assertIn(tid, idx.index)
            actual = idx.loc[tid, "passes_theoretical_expectation"]
            self.assertEqual(bool(actual), exp, tid)

    def test_ambiguous_probe_carries_no_boolean_verdict(self):
        idx = self.cf.set_index("test_id")
        t6 = idx.loc["T6_high_volume_mediocre_vs_low_volume_elite",
                    "passes_theoretical_expectation"]
        self.assertTrue(pd.isna(t6))


# ---------------------------------------------------------------------------
# 6. Nothing forbidden was built, and nothing canonical moved
# ---------------------------------------------------------------------------
class TestNoCompositeArtifactExists(unittest.TestCase):
    """These fail if a Statistical Tewaaraton, MVP score, WAR, replacement-level
    composite, award score or cross-position ranking is ever introduced into
    Phase 12's outputs -- under that name or under any other."""

    PHASE12_OUTPUTS = [
        "player_value_signal_inventory.csv",
        "player_value_metric_dependency.csv",
        "player_value_model_candidates.csv",
        "player_value_validation_results.csv",
        "player_value_counterfactual_tests.csv",
    ]

    def test_no_forbidden_column_name_in_any_phase12_output(self):
        for f in self.PHASE12_OUTPUTS:
            for c in pd.read_csv(HIST / f, nrows=0).columns:
                for bad in FORBIDDEN_IN_PUBLISHED:
                    self.assertNotIn(bad, str(c).lower(), f"{f}.{c}")

    def test_no_phase12_output_is_keyed_by_player(self):
        for f in self.PHASE12_OUTPUTS:
            cols = list(pd.read_csv(HIST / f, nrows=0).columns)
            self.assertNotIn("player_id", cols, f)
            self.assertNotIn("player_name", cols, f)

    def test_phase12_docs_contain_no_forbidden_leaderboard_prose(self):
        # Matches pll_validate_phase12.py check 4's negation-aware scan --
        # a doc that says "no MVP score is built here" (this project's own
        # established convention) must not trip this test.
        docs_dir = REPO_ROOT / "docs"
        negations = ("no ", "no.", "not ", "none ", "never ", "nor ",
                    "forbid", "reject", "must not", "should not",
                    "explicitly not", "does not", "did not")
        forbidden_prose = ("statistical tewaaraton ranking", "mvp leaderboard",
                          "mvp score", "award score", "composite score",
                          "wins above replacement", "replacement-level score")
        for docname in ("research/PLAYER_VALUE_DEFINITION.md", "research/PLAYER_VALUE_MODEL_RESEARCH.md",
                        "research/OFFENSIVE_VALUE_RESEARCH.md", "research/FACEOFF_VALUE_RESEARCH.md",
                        "research/GOALIE_VALUE_RESEARCH.md", "research/DEFENSIVE_VALUE_FEASIBILITY.md",
                        "history/CROSS_POSITION_VALUE_PHASE12.md",
                        "research/STATISTICAL_TEWAARATON_SPECIFICATION.md",
                        "history/PHASE12_VALIDATION.md"):
            fp = docs_dir / docname
            self.assertTrue(fp.exists(), docname)
            text = fp.read_text().lower()
            for bad in forbidden_prose:
                start = 0
                while True:
                    idx = text.find(bad, start)
                    if idx == -1:
                        break
                    window = text[max(0, idx - 60):idx]
                    self.assertTrue(any(neg in window for neg in negations),
                                   f"{docname}: {bad!r} with no adjacent negation")
                    start = idx + 1


class TestPhase12ChangedNothingCanonical(unittest.TestCase):

    def test_canonical_manifest_artifacts_still_hash_match(self):
        report = v12.main()
        row = report[report["check_id"] == 1]
        self.assertEqual(int(row.iloc[0]["n_failures"]), 0)

    def test_raw_data_unchanged(self):
        report = v12.main()
        row = report[report["check_id"] == 2]
        self.assertEqual(int(row.iloc[0]["n_failures"]), 0)

    def test_full_phase12_validator_passes(self):
        report = v12.main()
        self.assertTrue((report["status"] == "PASS").all(),
                        report[report["status"] != "PASS"].to_string())

    def test_deterministic_rebuild(self):
        p12.main()
        import hashlib
        before = {f: hashlib.sha256((HIST / f).read_bytes()).hexdigest()
                 for f in TestNoCompositeArtifactExists.PHASE12_OUTPUTS}
        p12.main()
        after = {f: hashlib.sha256((HIST / f).read_bytes()).hexdigest()
                for f in TestNoCompositeArtifactExists.PHASE12_OUTPUTS}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
