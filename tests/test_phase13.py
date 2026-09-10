"""
Phase 13 tests: production role-specific player value models.

Two kinds, matching the repository's established shape:

1. Integration tests over the actual published 2026/historical outputs.
2. Regression tests that Phase 13 introduced no MVP/Tewaaraton/award/
   composite/cross-position artifact under any name, changed no canonical
   or Phase 12 data, and that every accounting identity the brief requires
   holds exactly on the real files.

Run with: python3 -m unittest tests.test_phase13 -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
DOCS = REPO_ROOT / "docs"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED   # noqa: E402
import pll_validate_phase13 as v13                       # noqa: E402


def p26(name, **kw):
    return pd.read_csv(PROC / "2026" / name, **kw)


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


# ---------------------------------------------------------------------------
# 1. Model spec was frozen before ranking
# ---------------------------------------------------------------------------
class TestModelSpec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spec = hf("player_value_model_spec_v1.csv")

    def test_all_four_models_specified(self):
        self.assertEqual(set(self.spec["model_name"]),
                         {"offensive_value_v1", "faceoff_value_v1",
                          "goalie_value_v1", "defensive_production_v1"})

    def test_every_row_has_a_phase12_evidence_reference(self):
        self.assertEqual(int(self.spec["phase12_evidence_reference"].isna().sum()), 0)
        self.assertTrue((self.spec["phase12_evidence_reference"].str.len() > 10).all())

    def test_two_point_conversion_is_never_a_component(self):
        self.assertFalse(self.spec["component"].str.contains(
            "conversion", case=False, na=False).any())

    def test_defensive_model_publishes_no_value_baseline(self):
        defn = self.spec[self.spec["model_name"] == "defensive_production_v1"]
        self.assertTrue((defn["baseline"].str.startswith("NONE")).all())


# ---------------------------------------------------------------------------
# 2. Leaderboards and decompositions
# ---------------------------------------------------------------------------
class TestOffensiveValue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lb = p26("offensive_value_2026.csv")
        cls.comp = p26("offensive_value_components.csv")

    def test_decomposition_is_exact(self):
        self.assertLess(float(self.comp["accounting_check"].max()), 1e-6)

    def test_ranked_by_offensive_value_descending(self):
        self.assertTrue((self.lb["offensive_value"].diff().dropna() <= 1e-9).all())

    def test_bootstrap_ci_contains_point_estimate(self):
        self.assertTrue((self.lb["value_ci_lo"] <= self.lb["offensive_value"] + 1e-6).all())
        self.assertTrue((self.lb["value_ci_hi"] >= self.lb["offensive_value"] - 1e-6).all())

    def test_top10_inclusion_frequency_bounded(self):
        self.assertTrue((self.lb["top10_inclusion_frequency"] >= 0).all())
        self.assertTrue((self.lb["top10_inclusion_frequency"] <= 1).all())

    def test_qualification_state_is_from_closed_vocabulary(self):
        allowed = {"QUALIFIED", "SMALL_SAMPLE", "DESCRIPTIVE_ONLY", "INSUFFICIENT_EVIDENCE"}
        self.assertTrue(set(self.lb["qualification_state"]) <= allowed)

    def test_no_two_point_ability_column(self):
        self.assertFalse(any("two_point" in c.lower() and "ability" in c.lower()
                            for c in self.lb.columns))
        self.assertFalse(any("two_point" in c.lower() and "shrunk" in c.lower()
                            for c in self.lb.columns))

    def test_role_scope_is_attack_midfield_only(self):
        self.assertTrue(set(self.lb["position_group"]) <= {"attack", "midfield"})


class TestFaceoffValue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lb = p26("faceoff_value_2026.csv")
        cls.comp = p26("faceoff_value_components.csv")

    def test_rate_volume_decomposition_is_exact(self):
        self.assertLess(float(self.comp["accounting_check"].max()), 1e-6)

    def test_workload_vs_skill_is_binary_label(self):
        self.assertTrue(set(self.lb["workload_vs_skill"]) <= {"RATE_DRIVEN", "VOLUME_DRIVEN"})

    def test_publication_caveat_mentions_the_draw_volume_confound(self):
        self.assertTrue(self.lb["publication_caveat"].str.contains(
            "draw count", case=False, na=False).all())


class TestGoalieValue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lb = p26("goalie_value_2026.csv")
        cls.comp = p26("goalie_value_components.csv")

    def test_rate_workload_decomposition_is_exact(self):
        self.assertLess(float(self.comp["accounting_check"].max()), 1e-6)

    def test_not_shot_quality_adjusted_caveat_present(self):
        self.assertTrue(self.lb["publication_caveat"].str.contains(
            "shot-quality", case=False, na=False).all())

    def test_expected_minus_observed_equals_value(self):
        recon = self.lb["expected_points_allowed"] - self.lb["observed_points_allowed"]
        self.assertLess(float((recon - self.lb["goalie_value_total"]).abs().max()), 1e-6)


class TestDefensiveProduction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.df = p26("defensive_production_2026.csv")

    def test_no_value_column_exists(self):
        self.assertFalse(any("value" in c.lower() and "partial" not in c.lower()
                            for c in self.df.columns))

    def test_role_only_status_on_every_row(self):
        self.assertTrue(self.df["publication_status"].str.contains("ROLE_ONLY").all())

    def test_data_coverage_disclosed_on_every_row(self):
        self.assertEqual(int(self.df["data_coverage"].isna().sum()), 0)
        self.assertTrue((self.df["data_coverage"].str.len() > 50).all())


# ---------------------------------------------------------------------------
# 3. Team accounting
# ---------------------------------------------------------------------------
class TestTeamAccounting(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.acct = p26("player_value_team_accounting.csv")

    def test_unconditional_identity_passes_every_row(self):
        self.assertTrue((self.acct["unconditional_accounting_result"] == "PASS").all(),
                        self.acct[self.acct["unconditional_accounting_result"] != "PASS"].to_string())

    def test_coverage_gap_is_reported_not_hidden(self):
        self.assertEqual(int(self.acct["role_leaderboard_coverage_gap"].isna().sum()), 0)

    def test_league_total_rows_present_for_every_season(self):
        league = self.acct[self.acct["team_id"] == "LEAGUE_TOTAL"]
        self.assertEqual(set(league["season"]), {2022, 2023, 2024, 2025, 2026})


# ---------------------------------------------------------------------------
# 4. Historical backtest, sensitivity, counterfactuals, dominance
# ---------------------------------------------------------------------------
class TestHistoricalBacktest(unittest.TestCase):

    def test_one_model_definition_across_all_seasons(self):
        off = hf("offensive_value_2022_2026.csv")
        diff = (off["offensive_EPA_points_raw"] - off["offensive_value"]).abs()
        self.assertLess(float(diff.max()), 1e-6)

    def test_no_historical_universal_mvp_ranking_exists(self):
        for f in ["offensive_value_2022_2026.csv", "faceoff_value_2022_2026.csv",
                 "goalie_value_2022_2026.csv"]:
            cols = [c.lower() for c in pd.read_csv(HIST / f, nrows=0).columns]
            self.assertNotIn("overall_rank", cols)
            self.assertNotIn("cross_role_rank", cols)


class TestSensitivityAndCounterfactuals(unittest.TestCase):

    def test_sensitivity_never_recommends_an_alternative(self):
        sens = hf("player_value_sensitivity.csv")
        self.assertGreater(len(sens), 0)
        # descriptive columns only -- no "adopted_alternative" or similar
        self.assertNotIn("adopted", [c.lower() for c in sens.columns])

    def test_all_deterministic_counterfactuals_pass(self):
        cf = hf("player_value_counterfactual_tests_v1.csv")
        determinate = cf[cf["passes_theoretical_expectation"].notna()]
        self.assertGreater(len(determinate), 0)
        self.assertTrue(determinate["passes_theoretical_expectation"].astype(bool).all(),
                        determinate[~determinate["passes_theoretical_expectation"].astype(bool)].to_string())


class TestDominanceDiagnostic(unittest.TestCase):

    def test_never_combined_across_roles(self):
        dom = hf("within_role_dominance_diagnostic.csv")
        self.assertTrue(dom["cross_role_comparison_note"].str.contains(
            "NEVER", na=False).all())
        self.assertNotIn("universal_score", [c.lower() for c in dom.columns])
        self.assertNotIn("combined_rank", [c.lower() for c in dom.columns])


# ---------------------------------------------------------------------------
# 5. Nothing forbidden was built, and nothing prior moved
# ---------------------------------------------------------------------------
class TestNoCompositeArtifactExists(unittest.TestCase):

    PHASE13_FILES = [
        (PROC / "2026", ["offensive_value_2026.csv", "faceoff_value_2026.csv",
                         "goalie_value_2026.csv", "defensive_production_2026.csv",
                         "player_value_team_accounting.csv"]),
        (HIST, ["offensive_value_2022_2026.csv", "faceoff_value_2022_2026.csv",
               "goalie_value_2022_2026.csv", "within_role_dominance_diagnostic.csv",
               "player_value_sensitivity.csv", "player_value_counterfactual_tests_v1.csv"]),
    ]

    def test_no_forbidden_column_name(self):
        for base, files in self.PHASE13_FILES:
            for f in files:
                for c in pd.read_csv(base / f, nrows=0).columns:
                    for bad in FORBIDDEN_IN_PUBLISHED:
                        self.assertNotIn(bad, str(c).lower(), f"{f}.{c}")

    def test_no_file_carries_a_cross_role_score(self):
        for base, files in self.PHASE13_FILES:
            for f in files:
                cols = [c.lower() for c in pd.read_csv(base / f, nrows=0).columns]
                for bad_col in ("overall_rank", "universal_value", "combined_value",
                               "mvp_rank", "cross_role_rank"):
                    self.assertNotIn(bad_col, cols, f)


class TestPhase13ChangedNothingPrior(unittest.TestCase):

    def test_full_phase13_validator_passes(self):
        report = v13.main()
        self.assertTrue((report["status"] == "PASS").all(),
                        report[report["status"] != "PASS"].to_string())

    def test_phase12_and_phase11_still_pass(self):
        report = v13.main()
        row3 = report[report["check_id"] == 3]
        row4 = report[report["check_id"] == 4]
        self.assertEqual(int(row3.iloc[0]["n_failures"]), 0)
        self.assertEqual(int(row4.iloc[0]["n_failures"]), 0)


if __name__ == "__main__":
    unittest.main()
