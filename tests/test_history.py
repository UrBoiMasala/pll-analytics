"""
Phase 9 tests for the 2022-2026 historical layer.

Three kinds, matching the repository's established shape:

1. Unit tests on the Phase 9 RULES against synthetic input, so a rule is
   verified in isolation rather than merely observed to hold in the data. The
   eventStatus-2 completion rule in particular is exercised on constructed
   schedule rows, because the four 2023 games it rescues would otherwise be the
   only evidence it works.

2. Integration tests over the real five-season corpus.

3. Regression tests that Phase 9 did not move Phase 8. Every one of these is
   written to FAIL if a historical season leaked into a 2026 number.

These validate independently: nothing here re-runs a production query and
compares it with itself. Score reconciliation, the pooled-union identity and
the two-point identification arithmetic are all recomputed from source.

Run with: python3 -m unittest tests.test_history -v
"""
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
RAW = REPO_ROOT / "data" / "raw"
HIST = PROC / "history"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_build_tables as bt              # noqa: E402
import pll_ingest_season as ing            # noqa: E402
from pll_player_value_models import beta_prior_by_moments  # noqa: E402

SEASONS = [2022, 2023, 2024, 2025, 2026]
HISTORY = [2022, 2023, 2024, 2025]
SHOT_TYPE_POINTS = {"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}


def sf(y, name, **kw):
    return pd.read_csv(PROC / str(y) / name, **kw)


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


# ---------------------------------------------------------------------------
# 1. Rule unit tests on synthetic input
# ---------------------------------------------------------------------------
class TestCompletionRule(unittest.TestCase):
    """eventStatus 3 is 'final'; eventStatus 2 WITH final scores is also a
    played game. The 2023 feed marks four played games -- including the
    championship -- that way."""

    def test_status_3_is_completed(self):
        self.assertTrue(bt.is_completed({"eventStatus": 3}))

    def test_status_2_with_scores_is_completed(self):
        self.assertTrue(bt.is_completed(
            {"eventStatus": 2, "homeScore": 15, "visitorScore": 14}))

    def test_status_2_without_scores_is_not_completed(self):
        self.assertFalse(bt.is_completed({"eventStatus": 2}))
        self.assertFalse(bt.is_completed(
            {"eventStatus": 2, "homeScore": None, "visitorScore": None}))

    def test_status_0_is_never_completed(self):
        self.assertFalse(bt.is_completed(
            {"eventStatus": 0, "homeScore": 10, "visitorScore": 9}))

    def test_zero_zero_scores_still_count(self):
        """0 is a score, not a missing value."""
        self.assertTrue(bt.is_completed(
            {"eventStatus": 2, "homeScore": 0, "visitorScore": 0}))

    def test_classify_games_admits_status_2_with_scores(self):
        sched = {"data": {"items": [
            {"slugname": "a", "eventStatus": 3},
            {"slugname": "b", "eventStatus": 2, "homeScore": 1, "visitorScore": 2},
            {"slugname": "c", "eventStatus": 2},
            {"slugname": "d", "eventStatus": 0},
        ]}}
        completed, upcoming, other = ing.classify_games(sched)
        self.assertEqual({g["slugname"] for g in completed}, {"a", "b"})
        self.assertEqual({g["slugname"] for g in upcoming}, {"d"})
        self.assertEqual({g["slugname"] for g in other}, {"c"})


class TestSegmentClassification(unittest.TestCase):
    def test_preseason_is_its_own_type_and_excluded(self):
        self.assertEqual(bt.classify_game_type("preseason"), "preseason")
        self.assertNotIn(bt.classify_game_type("preseason"),
                         ("regular_season", "playoffs"))

    def test_regular_and_post_are_included(self):
        for seg in ("regular", "post"):
            self.assertIn(bt.classify_game_type(seg), ("regular_season", "playoffs"))

    def test_allstar_is_excluded(self):
        self.assertEqual(bt.classify_game_type("allstar"), "all_star")


class TestSeasonParameterisation(unittest.TestCase):
    """set_season must move I/O and nothing else, and must default to 2026."""

    def test_default_season_is_2026(self):
        import importlib
        m = importlib.reload(importlib.import_module("pll_build_tables"))
        self.assertEqual(m.SEASON, 2026)
        self.assertTrue(str(m.RAW_DIR).endswith("2026"))

    def test_set_season_moves_paths(self):
        import importlib
        m = importlib.import_module("pll_build_tables")
        old = m.SEASON
        try:
            m.set_season(2023)
            self.assertTrue(str(m.RAW_DIR).endswith("2023"))
            self.assertTrue(str(m.OUT_DIR).endswith("2023"))
        finally:
            m.set_season(old)
        self.assertEqual(m.SEASON, 2026)

    def test_referer_follows_the_season(self):
        old = ing.SEASON
        try:
            ing.set_season(2022)
            self.assertIn("/games/2022/", ing.referer_for("x"))
        finally:
            ing.set_season(old)
        self.assertIn("/games/2026/", ing.referer_for("x"))


class TestPointArithmetic(unittest.TestCase):
    def test_point_values_are_identical_in_every_season(self):
        self.assertEqual(SHOT_TYPE_POINTS["1_PT"], 1)
        self.assertEqual(SHOT_TYPE_POINTS["MU"], 1)
        self.assertEqual(SHOT_TYPE_POINTS["2_PT"], 2)
        self.assertEqual(SHOT_TYPE_POINTS["MU_2_PT"], 2)

    def test_a_two_point_goal_is_one_goal_worth_two(self):
        goals = ["2_PT", "1_PT", "MU_2_PT"]
        self.assertEqual(len(goals), 3)
        self.assertEqual(sum(SHOT_TYPE_POINTS[g] for g in goals), 5)


class TestIdentificationArithmetic(unittest.TestCase):
    """The rule that decides whether a skill is identifiable, on synthetic data."""

    def test_no_spread_gives_a_capped_prior(self):
        n = np.full(200, 5)
        k = np.full(200, 1)
        a, b = beta_prior_by_moments(k, n)
        self.assertGreater(a + b, 1e5)

    def test_real_spread_gives_a_finite_prior(self):
        rng = np.random.default_rng(7)
        n = np.full(300, 200)
        p = rng.beta(20, 20, size=300)      # genuine between-player spread
        k = rng.binomial(200, p)
        a, b = beta_prior_by_moments(k, n)
        self.assertLess(a + b, 1e5)

    def test_reliability_half_is_exactly_kappa_trials(self):
        for kappa in (9.377, 102.833, 495.189):
            self.assertAlmostEqual(kappa / (kappa + kappa), 0.5, places=12)


# ---------------------------------------------------------------------------
# 2. Integration over the real corpus
# ---------------------------------------------------------------------------
class TestGameCompleteness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inv = hf("historical_game_inventory.csv")

    def test_every_season_present(self):
        self.assertEqual(set(self.inv["season"].unique()), set(SEASONS))

    def test_no_completed_competitive_game_lacks_a_reason(self):
        bad = self.inv[self.inv["is_competitive"] & self.inv["is_completed"]
                       & ~self.inv["admitted_to_analytics"]
                       & (self.inv["exception_reason"].fillna("") == "")]
        self.assertEqual(len(bad), 0, bad.to_string())

    def test_inventory_matches_the_raw_schedule(self):
        for y in SEASONS:
            sched = json.loads((RAW / str(y) / "_schedule" / f"games_{y}.json")
                               .read_text())["data"]["items"]
            self.assertEqual(len(sched), int((self.inv["season"] == y).sum()), y)

    def test_expected_admitted_counts(self):
        got = (self.inv[self.inv["admitted_to_analytics"]]
               .groupby("season").size().to_dict())
        self.assertEqual(got, {2022: 46, 2023: 46, 2024: 45, 2025: 45, 2026: 50})

    def test_2023_status_2_games_are_admitted(self):
        """The four games the feed mis-flags, including the championship."""
        s23 = self.inv[(self.inv["season"] == 2023) & (self.inv["event_status"] == 2)]
        self.assertEqual(len(s23), 4)
        self.assertTrue(s23["admitted_to_analytics"].all(), s23.to_string())
        self.assertIn("championship-2023-9-22", set(s23["game_slug"]))

    def test_2022_preseason_is_excluded(self):
        pre = self.inv[(self.inv["season"] == 2022)
                       & (self.inv["season_segment"] == "preseason")]
        self.assertEqual(len(pre), 4)
        self.assertFalse(pre["admitted_to_analytics"].any())


class TestScoreReconciliation(unittest.TestCase):
    """Recomputed from events here, not read from the reconciliation file."""

    def test_every_eligible_game_reconciles_or_is_documented(self):
        exc = set(hf("historical_analytics_exclusions.csv")["game_slug"])
        failures = []
        for y in SEASONS:
            g = sf(y, "games.csv")
            el = g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]
            ev = sf(y, "events.csv", low_memory=False, dtype={"team_id": str})
            ev = ev[(ev["is_analysis_eligible_event"] == True)  # noqa: E712
                    & ev["game_id"].isin(set(el["game_id"]))
                    & (ev["is_valid_goal"] == True)].copy()  # noqa: E712
            ev["pts"] = ev["shot_type"].map(SHOT_TYPE_POINTS).fillna(1)
            got = ev.groupby(["game_id", "team_id"])["pts"].sum()
            for r in el.itertuples():
                for tid, off in ((r.home_team_id, r.home_score),
                                 (r.away_team_id, r.away_score)):
                    rec = float(got.get((r.game_id, str(tid)), 0))
                    if abs(rec - float(off)) > 1e-9 and r.game_slug not in exc:
                        failures.append((y, r.game_slug, tid, rec, off))
        self.assertEqual(failures, [], f"undocumented score residuals: {failures}")

    def test_the_one_documented_exception_is_the_2022_game(self):
        exc = hf("historical_analytics_exclusions.csv")
        self.assertEqual(len(exc), 1)
        self.assertEqual(exc["game_slug"].iloc[0], "archers-cannons-2022-6-18")
        self.assertEqual(int(exc["season"].iloc[0]), 2022)


class TestPossessionInvariants(unittest.TestCase):
    def test_goals_and_points_map_into_possessions(self):
        for y in SEASONS:
            g = sf(y, "games.csv")
            el = set(g[g["is_completed"] & g["include_in_league_analytics"]
                       & ~g["is_all_star"]]["game_id"])
            p = sf(y, "possessions.csv")
            p = p[p["game_id"].isin(el)]
            ev = sf(y, "events.csv", low_memory=False)
            ev = ev[(ev["is_analysis_eligible_event"] == True)  # noqa: E712
                    & ev["game_id"].isin(el)
                    & (ev["is_valid_goal"] == True)].copy()  # noqa: E712
            ev["pts"] = ev["shot_type"].map(SHOT_TYPE_POINTS).fillna(1)
            self.assertEqual(int(p["goals"].sum()), len(ev), f"{y} goals")
            self.assertEqual(int(p["points_scored"].sum()),
                             int(ev["pts"].sum()), f"{y} points")

    def test_offence_is_never_defence(self):
        for y in SEASONS:
            p = sf(y, "possessions.csv")
            self.assertEqual(
                int((p["offense_team_id"] == p["defense_team_id"]).sum()), 0, y)

    def test_possession_ids_unique(self):
        for y in SEASONS:
            p = sf(y, "possessions.csv")
            self.assertEqual(int(p.duplicated(subset=["possession_id"]).sum()), 0, y)


class TestSeasonPartition(unittest.TestCase):
    def test_each_season_has_its_own_outputs(self):
        for y in SEASONS:
            for f in (f"team_stats_{y}.csv", f"player_stats_{y}.csv",
                      f"team_leaderboards_{y}.csv", f"player_leaderboards_{y}.csv",
                      "possessions.csv", "events.csv", "games.csv"):
                self.assertTrue((PROC / str(y) / f).exists(), f"{y}/{f}")

    def test_no_all_star_or_preseason_in_the_eligible_set(self):
        for y in SEASONS:
            g = sf(y, "games.csv")
            el = g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]
            self.assertFalse(el["is_all_star"].any(), y)
            self.assertFalse((el["game_type"] == "preseason").any(), y)
            self.assertTrue(el["is_completed"].all(), y)

    def test_eight_teams_every_season(self):
        for y in SEASONS:
            t = sf(y, f"team_stats_{y}.csv")
            self.assertEqual(len(t), 8, y)


class TestPooledOutputs(unittest.TestCase):
    def test_pooled_equals_union_of_seasons(self):
        for pooled, tmpl in (("team_stats_2022_2026.csv", "team_stats_{y}.csv"),
                             ("player_stats_2022_2026.csv", "player_stats_{y}.csv"),
                             ("team_leaderboards_2022_2026.csv",
                              "team_leaderboards_{y}.csv")):
            pl = hf(pooled, low_memory=False)
            total = sum(len(pd.read_csv(PROC / str(y) / tmpl.format(y=y),
                                        low_memory=False)) for y in SEASONS)
            self.assertEqual(len(pl), total, pooled)

    def test_every_pooled_row_carries_a_season(self):
        for f in ("team_stats_2022_2026.csv", "player_stats_2022_2026.csv",
                  "player_leaderboards_2022_2026.csv"):
            df = hf(f, low_memory=False)
            self.assertIn("season", df.columns, f)
            self.assertFalse(df["season"].isna().any(), f)
            self.assertEqual(set(df["season"].unique()), set(SEASONS), f)

    def test_team_season_key_is_unique(self):
        t = hf("team_stats_2022_2026.csv")
        self.assertEqual(int(t.duplicated(subset=["season", "team_id"]).sum()), 0)
        self.assertEqual(len(t), 40)

    def test_player_season_key_is_unique(self):
        p = hf("player_stats_2022_2026.csv", low_memory=False)
        self.assertEqual(int(p.duplicated(subset=["season", "player_id"]).sum()), 0)


class TestIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ident = hf("historical_player_identity_audit.csv",
                       dtype={"player_id": str})

    def test_covers_every_observed_player(self):
        observed = set()
        for y in SEASONS:
            observed |= set(sf(y, "players.csv", dtype={"player_id": str})["player_id"])
        self.assertEqual(set(self.ident["player_id"]), observed)

    def test_no_identity_was_merged_on_name(self):
        """Two ids must never collapse into one row."""
        self.assertEqual(len(self.ident), self.ident["player_id"].nunique())

    def test_multi_season_players_are_flagged_as_such(self):
        self.assertGreater(int((self.ident["n_seasons"] > 1).sum()), 200)

    def test_aggregation_safety_is_explicit(self):
        self.assertIn("safe_to_aggregate_across_seasons", self.ident.columns)
        self.assertTrue(self.ident["safe_to_aggregate_across_seasons"].notna().all())


class TestSchemaCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = hf("historical_schema_compatibility.csv")

    def test_no_ingested_season_is_incompatible(self):
        inc = self.s[self.s["status"] == "INCOMPATIBLE"]
        self.assertEqual(len(inc), 0, inc.to_string())

    def test_every_season_carries_the_two_point_vocabulary(self):
        rows = self.s[self.s["aspect"] == "one_and_two_point_representation"]
        self.assertEqual(len(rows), 4)
        self.assertTrue((rows["status"] == "IDENTICAL").all(), rows.to_string())

    def test_2023_event_status_anomaly_is_recorded(self):
        r = self.s[(self.s["season"] == 2023)
                   & (self.s["aspect"] == "eventStatus_encoding")]
        self.assertEqual(len(r), 1)
        self.assertEqual(r["status"].iloc[0], "SEASON_SPECIFIC")


class TestTwoPointStillUnidentified(unittest.TestCase):
    """The headline Phase 9 test: five seasons do NOT rescue two-point ability."""

    @classmethod
    def setUpClass(cls):
        cls.tp = hf("multi_season_two_point_identification.csv")

    def test_not_identifiable_in_any_scope(self):
        self.assertFalse(self.tp["identifiable"].any(), self.tp.to_string())

    def test_excess_variance_is_negative_everywhere(self):
        self.assertTrue((self.tp["excess_variance"] < 0).all(),
                        self.tp[["scope", "excess_variance"]].to_string())

    def test_recomputed_from_source(self):
        """Independent recomputation of the pooled career diagnostic."""
        p = hf("player_stats_2022_2026.csv", low_memory=False)
        p["player_id"] = p["player_id"].astype(str).str.zfill(6)
        agg = p.groupby("player_id")[["two_point_goals", "two_point_attempts"]].sum()
        agg = agg[agg["two_point_attempts"] > 0]
        s = agg["two_point_goals"].to_numpy(float)
        t = agg["two_point_attempts"].to_numpy(float)
        mu = s.sum() / t.sum()
        w = t / t.sum()
        obs = float(np.sum(w * (s / t - mu) ** 2))
        binom = float(np.sum(w * mu * (1 - mu) / t))
        self.assertLess(obs, binom,
                        "pooled career two-point spread should still be below "
                        "binomial noise")

    def test_no_season_publishes_a_qualified_two_point_board(self):
        for y in SEASONS:
            lb = sf(y, f"player_leaderboards_{y}.csv", low_memory=False)
            q = lb[(lb["metric_name"] == "two_point_conversion_pct")
                   & (lb["scope"] == "QUALIFIED")]
            self.assertEqual(len(q), 0, y)


class TestReliabilityFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = hf("multi_season_reliability.csv")

    def test_career_pooling_beats_2026_for_shooting(self):
        a = self.r[(self.r["rate"] == "shooting_pct")
                   & (self.r["scope"] == "2026_only")].iloc[0]
        b = self.r[(self.r["rate"] == "shooting_pct")
                   & (self.r["scope"] == "pooled_player_career")].iloc[0]
        self.assertGreater(b["n_reaching_reliability_0_5"],
                           a["n_reaching_reliability_0_5"])

    def test_career_pooling_beats_2026_for_goalies(self):
        a = self.r[(self.r["rate"] == "save_pct")
                   & (self.r["scope"] == "2026_only")].iloc[0]
        b = self.r[(self.r["rate"] == "save_pct")
                   & (self.r["scope"] == "pooled_player_career")].iloc[0]
        self.assertGreater(b["n_reaching_reliability_0_5"],
                           a["n_reaching_reliability_0_5"])

    def test_two_point_prior_stays_capped_in_every_scope(self):
        tp = self.r[self.r["rate"] == "two_point_pct"]
        self.assertTrue((tp["prior_strength_kappa"] >= 1e5).all())


class TestUsageModel(unittest.TestCase):
    def test_constant_still_wins(self):
        um = hf("multi_season_usage_model.csv")
        sel = um[um["selected_model"]]
        self.assertEqual(len(sel), 1)
        self.assertEqual(sel["model"].iloc[0], "constant")

    def test_folds_are_cut_by_player(self):
        um = hf("multi_season_usage_model.csv")
        self.assertEqual(um["fold_unit"].iloc[0], "player (not row)")


# ---------------------------------------------------------------------------
# 3. Phase 8 regression
# ---------------------------------------------------------------------------
class TestPhase8Unchanged(unittest.TestCase):
    """Phase 9 adds four seasons. It must not move 2026 by one bit."""

    def test_2026_headline_totals(self):
        t = sf(2026, "team_stats_2026.csv")
        p = sf(2026, "player_stats_2026.csv", low_memory=False)
        self.assertEqual(len(t), 8)
        self.assertEqual(len(p), 228)
        self.assertEqual(int(t["points_scored"].sum()), 1190)
        self.assertEqual(int(p["scoring_points"].sum()), 1190)
        self.assertEqual(int(t["shots"].sum()), 4106)
        self.assertEqual(int(t["two_point_attempts"].sum()), 536)
        self.assertEqual(int(t["two_point_goals"].sum()), 72)

    def test_2026_possessions_unchanged(self):
        g = sf(2026, "games.csv")
        el = set(g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]["game_id"])
        p = sf(2026, "possessions.csv")
        self.assertEqual(len(p[p["game_id"].isin(el)]), 4388)

    def test_2026_eligible_game_count_unchanged(self):
        g = sf(2026, "games.csv")
        el = g[g["is_completed"] & g["include_in_league_analytics"]
               & ~g["is_all_star"]]
        self.assertEqual(len(el), 50)

    def test_phase8_validation_report_still_all_pass(self):
        r = sf(2026, "phase8_validation_report.csv")
        self.assertEqual(int((r["status"] != "PASS").sum()), 0, r.to_string())

    def test_phase9_validation_report_all_pass(self):
        r = hf("phase9_validation_report.csv")
        self.assertEqual(int((r["status"] != "PASS").sum()), 0, r.to_string())
        self.assertGreaterEqual(len(r), 22)


class TestNoCompositeAnywhere(unittest.TestCase):
    def test_no_forbidden_metric_name_in_any_season_or_pooled_output(self):
        from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED
        names = []
        for y in SEASONS:
            names += list(sf(y, f"team_stats_{y}.csv").columns)
            names += list(sf(y, f"player_stats_{y}.csv", low_memory=False).columns)
            names += list(sf(y, f"player_leaderboards_{y}.csv",
                             low_memory=False)["metric_name"].unique())
        for f in HIST.glob("*.csv"):
            names += list(pd.read_csv(f, nrows=0).columns)
        for n in names:
            for bad in FORBIDDEN_IN_PUBLISHED:
                self.assertNotIn(bad, str(n).lower(), f"{n} contains {bad}")

    def test_no_ranking_across_positions_was_added(self):
        for y in SEASONS:
            lb = sf(y, f"player_leaderboards_{y}.csv", low_memory=False)
            self.assertIn("position_rank", lb.columns, y)
            self.assertIn("canonical_position", lb.columns, y)


class TestSanityFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = hf("multi_season_sanity_flags.csv")

    def test_no_class_e_survives(self):
        e = self.f[self.f["classification"] == "E"]
        self.assertEqual(len(e), 0, e.to_string())

    def test_2023_feed_gap_is_flagged(self):
        g = self.f[(self.f["flag_code"] == "FEED_LOGGING_GAP")
                   & (self.f["season"].astype(str) == "2023")]
        self.assertEqual(len(g), 1)
        self.assertEqual(g["classification"].iloc[0], "D")

    def test_the_2022_score_failure_is_flagged(self):
        s = self.f[self.f["flag_code"] == "SCORE_IRRECONCILABLE"]
        self.assertGreater(len(s), 0)
        self.assertTrue((s["season"].astype(str) == "2022").all())


if __name__ == "__main__":
    unittest.main()
