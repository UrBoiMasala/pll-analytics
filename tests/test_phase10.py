"""
Phase 10 tests: possession repair, career ability, cross-position research.

Three kinds, matching the repository's established shape:

1. Unit tests on the Phase 10 RULES against SYNTHETIC events, so each repair
   rule is verified in isolation rather than merely observed to hold in the
   data. The plausible false positives matter as much as the motivating case:
   a rule that fires on a genuine faceoff-then-goal sequence, or on a
   multi-event scramble, would corrupt real possessions.

2. Integration tests over the real five-season corpus.

3. Regression tests that Phase 10 did not move Phase 8 or Phase 9, and that no
   forbidden composite artifact was introduced under any name.

Run with: python3 -m unittest tests.test_phase10 -v
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

import pll_phase10_possession_repair as pr        # noqa: E402
import pll_phase10_cross_position as cp           # noqa: E402
from pll_metric_catalog import FORBIDDEN_IN_PUBLISHED  # noqa: E402
from pll_player_value_models import beta_prior_by_moments  # noqa: E402

SEASONS = [2022, 2023, 2024, 2025, 2026]
TOL = 1e-9


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def sf(y, name, **kw):
    return pd.read_csv(PROC / str(y) / name, **kw)


def _ev(rows):
    """Build a synthetic eligible-event frame in the canonical column shape."""
    base = dict(game_id=1, game_slug="G", period=1, team_id="AAA",
                player_id=None, secondary_player_id=None, gb_player_id=None,
                event_type="shot", shot_type="1_PT", shot_outcome="missed",
                is_valid_goal=False, is_two_point_attempt=False,
                is_man_up_shot=False, home_score_corrected=0,
                away_score_corrected=0)
    out = []
    for i, r in enumerate(rows):
        d = dict(base)
        d.update(r)
        d["event_number"] = i
        out.append(d)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# 1. Unit tests on the repair rules
# ---------------------------------------------------------------------------
class TestRepairRuleUnit(unittest.TestCase):
    """Each rule against constructed events, including the false positives."""

    def test_marker_seq_reads_the_feeds_own_sequence_number(self):
        self.assertEqual(pr.marker_seq("shot-8900"), 8900.0)
        self.assertEqual(pr.marker_seq("9000"), 9000.0)
        self.assertEqual(pr.marker_seq("groundball-1023900"), 1023900.0)
        self.assertTrue(np.isnan(pr.marker_seq("pregame")))
        self.assertTrue(np.isnan(pr.marker_seq("gameEnd")))

    def test_direct_fires_on_the_motivating_pattern(self):
        # the real championship-2023-9-22 shape: faceoff(9000) before its own
        # goal(8900), with the faceoff's companion ground ball after the goal
        e = _ev([
            dict(event_id="turnover-7910", event_type="turnover",
                 seconds_passed=223, shot_outcome=None),
            dict(event_id="9000", event_type="faceoff", seconds_passed=260,
                 player_id="000409", gb_player_id="000409", shot_outcome=None),
            dict(event_id="shot-8900", event_type="goal", seconds_passed=260,
                 is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="groundball-9100", event_type="groundball",
                 seconds_passed=266, player_id="000409", shot_outcome=None),
        ])
        det = pr.detect_faceoff_order_defects(e)
        self.assertEqual(len(det), 1)
        self.assertEqual(det.iloc[0]["evidence_class"], "DIRECT")
        self.assertEqual(det.iloc[0]["repair_action"], "transpose_and_retime")
        self.assertEqual(det.iloc[0]["repaired_faceoff_seconds_passed"], 266)
        self.assertTrue(det.iloc[0]["marker_seq_contradicts_array_order"])

    def test_repair_transposes_and_retimes_and_changes_nothing_else(self):
        e = _ev([
            dict(event_id="9000", event_type="faceoff", seconds_passed=260,
                 player_id="000409", gb_player_id="000409", shot_outcome=None),
            dict(event_id="shot-8900", event_type="goal", seconds_passed=260,
                 is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="groundball-9100", event_type="groundball",
                 seconds_passed=266, player_id="000409", shot_outcome=None),
        ])
        det = pr.detect_faceoff_order_defects(e)
        out = pr.apply_repair(e, det, {"DIRECT"})
        self.assertEqual(list(out["event_id"]),
                         ["shot-8900", "9000", "groundball-9100"])
        self.assertEqual(list(out["seconds_passed"]), [260, 266, 266])
        # nothing but order and the faceoff's timestamp may move
        for col in ("team_id", "event_type", "player_id", "is_valid_goal",
                    "shot_type"):
            self.assertEqual(sorted(map(str, out[col])), sorted(map(str, e[col])),
                             col)
        self.assertEqual(len(out), len(e))

    def test_false_positive_a_real_faceoff_then_goal_is_not_repaired(self):
        """A team wins a draw and scores 30 seconds later. markerId AGREES with
        the array order, so nothing fires -- this is ordinary lacrosse."""
        e = _ev([
            dict(event_id="100", event_type="faceoff", seconds_passed=100,
                 player_id="000409", gb_player_id="000409", shot_outcome=None),
            dict(event_id="groundball-200", event_type="groundball",
                 seconds_passed=100, player_id="000409", shot_outcome=None),
            dict(event_id="shot-900", event_type="goal", seconds_passed=130,
                 is_valid_goal=True, shot_outcome="goal"),
        ])
        det = pr.detect_faceoff_order_defects(e)
        self.assertEqual(len(det), 0)

    def test_false_positive_a_multi_event_scramble_is_unresolved(self):
        """The real playoffs-quarterfinal-2-2023-9-1 p2 shape. markerId puts
        three events between the faceoff and its companion ground ball, so the
        displacement is wider than one event and a two-event transposition
        would strand the faceoff after events markerId puts before it. Must NOT
        be repaired."""
        e = _ev([
            dict(event_id="1023800", event_type="faceoff", seconds_passed=1436,
                 player_id="000925", gb_player_id="000925", shot_outcome=None),
            dict(event_id="shot-1023700", event_type="goal",
                 seconds_passed=1436, is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="shotclockexpired-1023400",
                 event_type="shotclockexpired", seconds_passed=1436,
                 shot_outcome=None),
            dict(event_id="turnover-1023410", event_type="turnover",
                 seconds_passed=1436, shot_outcome=None),
            dict(event_id="groundball-1023900", event_type="groundball",
                 seconds_passed=1439, player_id="000925", shot_outcome=None),
        ])
        det = pr.detect_faceoff_order_defects(e)
        self.assertEqual(len(det), 1)
        self.assertEqual(det.iloc[0]["evidence_class"], "UNRESOLVED")
        self.assertEqual(det.iloc[0]["repair_action"], "none")
        out = pr.apply_repair(e, det, pr.VARIANTS[pr.PRIMARY_VARIANT])
        self.assertEqual(list(out["event_id"]), list(e["event_id"]))

    def test_false_positive_a_duplicated_faceoff_is_reported_not_repaired(self):
        """The real 2024_game_10 shape: the SAME faceoff twice. The repair for
        that is de-duplication, which Phase 10 does not perform."""
        e = _ev([
            dict(event_id="1000", event_type="faceoff", seconds_passed=151,
                 player_id="000365", secondary_player_id="003004",
                 gb_player_id="000365", shot_outcome=None),
            dict(event_id="shot-900", event_type="goal", seconds_passed=151,
                 is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="1100", event_type="faceoff", seconds_passed=158,
                 player_id="000365", secondary_player_id="003004",
                 gb_player_id="000365", shot_outcome=None),
            dict(event_id="groundball-1200", event_type="groundball",
                 seconds_passed=158, player_id="000365", shot_outcome=None),
        ])
        det = pr.detect_faceoff_order_defects(e)
        classes = set(det["evidence_class"])
        self.assertIn("DUPLICATE_FACEOFF_EVENT", classes)
        applied = det[det["evidence_class"].isin(pr.VARIANTS[pr.PRIMARY_VARIANT])]
        self.assertEqual(len(applied), 0)
        out = pr.apply_repair(e, det, pr.VARIANTS[pr.PRIMARY_VARIANT])
        self.assertEqual(list(out["event_id"]), list(e["event_id"]))

    def test_direct_timing_retimes_but_never_reorders(self):
        e = _ev([
            dict(event_id="100", event_type="faceoff", seconds_passed=0,
                 player_id="000409", gb_player_id="000409", shot_outcome=None),
            dict(event_id="groundball-200", event_type="groundball",
                 seconds_passed=6, player_id="000409", shot_outcome=None),
        ])
        det = pr.detect_faceoff_order_defects(e)
        self.assertEqual(det.iloc[0]["evidence_class"], "DIRECT_TIMING")
        out = pr.apply_repair(e, det, {"DIRECT_TIMING"})
        self.assertEqual(list(out["event_id"]), list(e["event_id"]))
        self.assertEqual(list(out["seconds_passed"]), [6, 6])

    def test_strongly_inferred_is_not_applied_by_the_primary_variant(self):
        e = _ev([
            dict(event_id="9000", event_type="faceoff", seconds_passed=260,
                 player_id="000409", shot_outcome=None),
            dict(event_id="shot-8900", event_type="goal", seconds_passed=260,
                 is_valid_goal=True, shot_outcome="goal"),
        ])
        det = pr.detect_faceoff_order_defects(e)
        self.assertEqual(det.iloc[0]["evidence_class"], "STRONGLY_INFERRED")
        same = pr.apply_repair(e, det, pr.VARIANTS[pr.PRIMARY_VARIANT])
        self.assertEqual(list(same["event_id"]), list(e["event_id"]))
        moved = pr.apply_repair(e, det, {"STRONGLY_INFERRED"})
        self.assertEqual(list(moved["event_id"]), ["shot-8900", "9000"])

    def test_a_repair_never_produces_a_backwards_step_in_time(self):
        """The invariant the single-displacement precondition exists to keep."""
        for y in SEASONS:
            rp = sf(y, "possessions_repaired.csv")
            self.assertEqual(int((rp["duration_seconds"] < 0).sum()), 0, y)
            self.assertEqual(
                int((rp["end_seconds_passed"] < rp["start_seconds_passed"]).sum()),
                0, y)


# ---------------------------------------------------------------------------
# 2. Integration: the repaired layer over the real corpus
# ---------------------------------------------------------------------------
class TestRepairOverTheCorpus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev = hf("possession_repair_evidence_2022_2026.csv")
        cls.stats = hf("possession_stats_original_vs_repaired.csv")
        cls.audit = hf("2023_possession_repair_audit.csv")

    def test_every_applied_repair_carries_direct_evidence(self):
        applied = self.ev[self.ev["evidence_class"].isin(
            pr.VARIANTS[pr.PRIMARY_VARIANT])]
        self.assertGreater(len(applied), 0)
        for _, r in applied.iterrows():
            if r["repair_action"].startswith("transpose"):
                self.assertTrue(r["marker_seq_contradicts_array_order"],
                                r["faceoff_event_id"])
                self.assertGreater(r["faceoff_marker_seq"], r["goal_marker_seq"])
            if r["repair_action"].endswith("retime"):
                self.assertTrue(pd.notna(r["companion_gb_event_id"]))
            self.assertTrue(pd.notna(r["faceoff_seconds_passed"]))

    def test_no_repair_was_applied_outside_the_two_direct_classes(self):
        applied = self.audit[
            self.audit["repair_applied_in_primary_variant"] == True]  # noqa: E712
        self.assertEqual(set(applied["evidence_class"]),
                         {"DIRECT", "DIRECT_TIMING"})

    def test_the_2023_layer_is_the_canonicalized_phase11_repair(self):
        """Phase 11 update: Phase 10 published possessions.csv unchanged and
        kept the repair in a parallel possessions_repaired.csv (see the
        docstring of pll_phase10_possession_repair.py, "WHAT THIS MODULE DOES
        NOT DO"). Phase 11 adopted V2_direct_and_timing into the canonical
        layer per docs/research/2023_POSSESSION_REPAIR.md Section 8's own
        recommendation (docs/PHASE11_CHRONOLOGY_REPAIR.md), so
        possessions.csv now HAS the repair: 4460 -> 4204 possessions. Points
        are exactly unchanged (the repair reorders/retimes events; it never
        creates, deletes or reattributes a goal)."""
        p = sf(2023, "possessions.csv")
        self.assertEqual(len(p), 4204)
        self.assertEqual(int(p["points_scored"].sum()), 1124)

    def test_scoring_reconciles_exactly_in_the_repaired_layer(self):
        exc = set(hf("historical_analytics_exclusions.csv")["game_slug"])
        for y in SEASONS:
            rp = sf(y, "possessions_repaired.csv")
            g = sf(y, "games.csv")
            el = g[g["is_completed"] & g["include_in_league_analytics"]
                   & ~g["is_all_star"]]
            got = rp.groupby(["game_id", "offense_team_id"])["points_scored"].sum()
            for r in el.itertuples():
                if r.game_slug in exc:
                    continue
                for tid, official in ((r.home_team_id, r.home_score),
                                      (r.away_team_id, r.away_score)):
                    self.assertAlmostEqual(float(got.get((r.game_id, tid), 0)),
                                           float(official), places=9,
                                           msg=f"{y}/{r.game_slug}/{tid}")

    def test_the_repair_is_canonical_in_2023_and_2024(self):
        """Phase 11 update: PRIMARY_VARIANT (V2_direct_and_timing) is now
        canonicalized into possessions.csv for every season (see
        pll_chronology_repair.py), so it reproduces `published` everywhere --
        2022/2025/2026 trivially (zero repairable candidates, so V2 == V0
        there too), 2023/2024 because that IS what's now published."""
        prim = self.stats[self.stats["variant"] == pr.PRIMARY_VARIANT].set_index("season")
        for y in SEASONS:
            self.assertTrue(bool(prim.loc[y, "identical_to_published_possessions"]),
                            f"{y}: canonical possessions.csv no longer matches "
                            f"the primary repair variant")

    def test_the_v0_rebuild_reproduces_the_published_layer_only_where_untouched(self):
        """Phase 11 update: V0 (this script's from-scratch rebuild on the RAW,
        pre-chronology-repair event order -- see load_season) reproduces
        canonical `published` only in the 3 seasons with zero repairable
        candidates. For 2023/2024, published now HAS the repair baked in, so
        V0 diverging from it is the expected, by-design signature that the
        repair actually did something -- not a regression."""
        v0 = self.stats[self.stats["variant"] == "V0_original"].set_index("season")
        for y in (2022, 2025, 2026):
            self.assertTrue(bool(v0.loc[y, "v0_rebuild_reproduces_published"]), y)
            self.assertTrue(bool(v0.loc[y, "identical_to_published_possessions"]), y)
        for y in (2023, 2024):
            self.assertFalse(bool(v0.loc[y, "v0_rebuild_reproduces_published"]), y)
            self.assertFalse(bool(v0.loc[y, "identical_to_published_possessions"]), y)

    def test_the_repair_never_changes_total_points(self):
        prim = self.stats[self.stats["variant"] == pr.PRIMARY_VARIANT].set_index("season")
        orig = self.stats[self.stats["variant"] == "V0_original"].set_index("season")
        for y in SEASONS:
            self.assertAlmostEqual(prim.loc[y, "total_points_scored"],
                                   orig.loc[y, "total_points_scored"], places=9)

    def test_repaired_2023_moves_inside_the_five_season_range(self):
        """Reported, not asserted as the reason for the repair: cross-season
        similarity is a POST-repair diagnostic here, never a criterion."""
        s = self.stats
        prim = s[s["variant"] == pr.PRIMARY_VARIANT].set_index("season")
        others = prim.drop(index=2023)["possessions_per_game"]
        self.assertLess(prim.loc[2023, "possessions_per_game"],
                        s[(s["season"] == 2023)
                          & (s["variant"] == "V0_original")]["possessions_per_game"].iloc[0])
        # within 5% of the widest other season, having been 8%+ outside it
        self.assertLess(prim.loc[2023, "possessions_per_game"] / others.max(), 1.05)

    def test_no_possession_boundary_points_at_a_nonexistent_event(self):
        for y in SEASONS:
            rp = sf(y, "possessions_repaired.csv",
                    dtype={"start_event_id": str, "end_event_id": str})
            ev = sf(y, "events.csv", low_memory=False, dtype={"event_id": str})
            known = set(ev["event_id"])
            self.assertTrue(set(rp["start_event_id"]) <= known, y)
            self.assertTrue(set(rp["end_event_id"]) <= known, y)


# ---------------------------------------------------------------------------
# 3. Career ability
# ---------------------------------------------------------------------------
class TestCareerAbility(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.career = hf("player_career_2022_2026.csv", dtype={"player_id": str})
        cls.career["player_id"] = cls.career["player_id"].str.zfill(6)
        cls.est = hf("career_rate_estimates.csv", dtype={"player_id": str})
        cls.est["player_id"] = cls.est["player_id"].str.zfill(6)
        cls.rel = hf("career_ability_reliability.csv")
        cls.pooled = pd.read_csv(HIST / "player_stats_2022_2026.csv",
                                 low_memory=False, dtype={"player_id": str})
        cls.pooled["player_id"] = cls.pooled["player_id"].str.zfill(6)

    def test_one_career_per_player_and_no_player_is_missing(self):
        self.assertEqual(len(self.career), self.career["player_id"].nunique())
        self.assertEqual(set(self.career["player_id"]),
                         set(self.pooled["player_id"]))

    def test_career_totals_equal_the_sum_of_the_season_rows(self):
        cols = ["games_played", "goals", "shots", "faceoffs", "faceoff_wins",
                "saves", "goals_allowed", "touches", "turnovers"]
        want = self.pooled.groupby("player_id")[cols].sum()
        got = self.career.set_index("player_id")[cols].reindex(want.index)
        for c in cols:
            np.testing.assert_allclose(got[c].to_numpy(float),
                                       want[c].to_numpy(float), atol=TOL,
                                       err_msg=c)

    def test_raw_career_rates_recompute_from_the_published_columns(self):
        c = self.career
        m = c["shots"] > 0
        np.testing.assert_allclose(
            c.loc[m, "shooting_pct_raw"].to_numpy(float),
            (c.loc[m, "goals"] / c.loc[m, "shots"]).to_numpy(float), atol=1e-12)
        m = c["faceoffs"] > 0
        np.testing.assert_allclose(
            c.loc[m, "faceoff_win_pct_raw"].to_numpy(float),
            (c.loc[m, "faceoff_wins"] / c.loc[m, "faceoffs"]).to_numpy(float),
            atol=1e-12)

    def test_shrinkage_recomputes_from_the_imported_estimator(self):
        for rate, succ, tri in (("shooting_pct", "goals", "shots"),
                                ("faceoff_win_pct", "faceoff_wins", "faceoffs"),
                                ("turnovers_per_touch", "turnovers", "touches")):
            ident = hf("career_identity_audit.csv", dtype={"player_id": str})
            ident["player_id"] = ident["player_id"].str.zfill(6)
            safe = set(ident.loc[ident["safe_to_aggregate_career"], "player_id"])
            agg = self.pooled.groupby("player_id")[[succ, tri]].sum()
            agg = agg[agg.index.isin(safe)]
            a, b = beta_prior_by_moments(agg[succ].to_numpy(float),
                                         agg[tri].to_numpy(float))
            kappa = a + b
            row = self.rel[(self.rel["rate_name"] == rate)
                           & (self.rel["scope"] == "pooled_player_career")]
            self.assertAlmostEqual(float(row["kappa"].iloc[0]), kappa,
                                   delta=1e-6 * max(kappa, 1.0), msg=rate)
            e = self.est[self.est["rate_name"] == rate].set_index("player_id")
            sub = agg[agg[tri] > 0]
            want = ((sub[succ] + a) / (sub[tri] + kappa)).reindex(e.index).dropna()
            np.testing.assert_allclose(
                e.loc[want.index, "career_rate_shrunk"].to_numpy(float),
                want.to_numpy(float), atol=1e-9, err_msg=rate)

    def test_reliability_is_n_over_n_plus_kappa(self):
        e = self.est[self.est["career_trials"] > 0]
        want = e["career_trials"] / (e["career_trials"]
                                     + e["prior_strength_trials_kappa"])
        np.testing.assert_allclose(e["reliability"].to_numpy(float),
                                   want.to_numpy(float), atol=1e-12)

    def test_no_impossible_rate_anywhere(self):
        e = self.est
        self.assertEqual(int((e["career_successes"] > e["career_trials"] + TOL).sum()), 0)
        for c in ("career_rate_raw", "career_rate_shrunk", "reliability"):
            v = pd.to_numeric(e[c], errors="coerce").dropna()
            self.assertGreaterEqual(v.min(), -TOL, c)
            self.assertLessEqual(v.max(), 1 + TOL, c)

    def test_posterior_intervals_are_ordered_and_contain_the_estimate(self):
        e = self.est.dropna(subset=["posterior_ci_lo", "posterior_ci_hi"])
        self.assertEqual(int((e["posterior_ci_lo"] > e["posterior_ci_hi"]).sum()), 0)
        self.assertEqual(int((
            (e["career_rate_shrunk"] < e["posterior_ci_lo"] - 1e-6)
            | (e["career_rate_shrunk"] > e["posterior_ci_hi"] + 1e-6)).sum()), 0)

    def test_career_pooling_beats_a_single_season_where_phase_9_said_it_would(self):
        cmp_ = hf("career_scope_comparison.csv").set_index("rate_name")
        for rate in ("shooting_pct", "one_point_pct", "save_pct",
                     "faceoff_win_pct", "turnovers_per_touch"):
            self.assertTrue(bool(cmp_.loc[rate, "career_beats_single_season"]),
                            rate)
        # and pooling player-SEASONS as rows does not, for the rates Phase 9
        # measured that on
        for rate in ("shooting_pct", "one_point_pct", "save_pct"):
            self.assertFalse(
                bool(cmp_.loc[rate, "pooling_seasons_beats_single_season"]), rate)

    def test_multi_role_careers_keep_every_role_they_played(self):
        c = self.career
        multi = c[c["career_position_is_single_role"] == False]  # noqa: E712
        self.assertGreater(len(multi), 0)
        self.assertTrue(
            multi["career_position_representation"].str.contains(",").all())


# ---------------------------------------------------------------------------
# 4. Two-point ability stays unsupported
# ---------------------------------------------------------------------------
class TestTwoPointRemainsUnsupported(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tp = hf("career_two_point_identification.csv")

    def test_not_identifiable_at_any_scope_including_the_career(self):
        tp = self.tp[self.tp["rate_name"] == "two_point_pct"]
        self.assertIn("pooled_player_career", set(tp["scope"]))
        self.assertFalse(tp["identifiable"].any())
        self.assertTrue((tp["classification"] == "UNSUPPORTED / DO_NOT_USE").all())

    def test_observed_variance_is_below_binomial_noise_everywhere(self):
        tp = self.tp[self.tp["rate_name"] == "two_point_pct"]
        self.assertTrue((tp["excess_variance"] < 0).all())
        self.assertTrue((tp["kappa"] >= 1e5).all())

    def test_the_one_point_reference_IS_identifiable_on_the_same_players(self):
        """The control that makes the two-point verdict a finding rather than
        an artefact of the estimator."""
        ref = self.tp[self.tp["rate_name"] == "one_point_pct_reference"]
        self.assertEqual(len(ref), 1)
        self.assertTrue(bool(ref["identifiable"].iloc[0]))
        self.assertGreater(float(ref["excess_variance"].iloc[0]), 0)

    def test_the_published_career_two_point_shrunk_rate_is_collapsed(self):
        c = hf("player_career_2022_2026.csv")
        v = pd.to_numeric(c["two_point_pct_shrunk"], errors="coerce").dropna()
        self.assertGreater(len(v), 0)
        self.assertLess((v.max() - v.min()) / abs(v.mean()), 1e-3)

    def test_two_point_production_is_still_published(self):
        c = hf("player_career_2022_2026.csv")
        for col in ("two_point_goals", "two_point_attempts", "two_point_pct_raw"):
            self.assertIn(col, c.columns)
        self.assertGreater(int(c["two_point_goals"].sum()), 0)


# ---------------------------------------------------------------------------
# 5. Cross-position research
# ---------------------------------------------------------------------------
class TestCrossPosition(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mc = hf("cross_position_method_comparison.csv").set_index("method")
        cls.audit = hf("cross_position_value_audit.csv")
        cls.cf = hf("cross_position_counterfactuals.csv")
        cls.base = hf("positional_baselines.csv")

    def test_all_ten_candidate_methods_were_evaluated(self):
        self.assertEqual(len(self.mc), 10)
        for m in cp.METHODS:
            self.assertIn(m, self.mc.index)
        for col in ("mathematical_definition", "required_assumptions",
                    "measures", "interpretability", "known_biases",
                    "spearman_with_role_opportunities",
                    "spearman_with_games_played",
                    "role_sd_max_over_min_after_transform",
                    "year_to_year_spearman", "cross_position_verdict"):
            self.assertIn(col, self.mc.columns)
            self.assertEqual(int(self.mc[col].isna().sum()), 0, col)

    def test_role_scales_really_do_differ_by_an_order_of_magnitude(self):
        hl = self.audit[self.audit["role"] == "ALL_ROLES"]
        self.assertGreater(
            float(hl.loc[hl["scope"] == "2022_2026",
                         "value_sd_max_over_min_across_roles"].iloc[0]), 2.0)
        self.assertGreater(
            float(hl.loc[hl["scope"] == "2022_2026",
                         "opportunity_mean_max_over_min_across_roles"].iloc[0]), 10.0)
        # and in every individual season, not just pooled
        per = hl[hl["scope"] != "2022_2026"]["value_sd_max_over_min_across_roles"]
        self.assertEqual(len(per), 5)
        self.assertGreater(per.min(), 2.0)

    def test_only_standardizing_methods_equalize_the_scale(self):
        eq = self.mc[self.mc["cross_role_scale_equalized"] == True]  # noqa: E712
        self.assertIn("M04_within_position_z", eq.index)
        self.assertIn("M03_within_position_percentile", eq.index)
        self.assertNotIn("M01_raw_value_above_role_baseline", eq.index)
        self.assertNotIn("M10_null_standardized_value", eq.index)

    def test_the_counterfactual_shows_equal_z_is_not_equal_value(self):
        p1 = self.cf[self.cf["probe"] == "P1_equally_elite_within_role"]
        self.assertEqual(len(p1), 5)
        z = pd.to_numeric(p1["M04_within_position_z"], errors="coerce")
        np.testing.assert_allclose(z.to_numpy(float), 2.0, atol=1e-9)
        v = pd.to_numeric(p1["M01_raw_value_above_role_baseline"],
                          errors="coerce")
        self.assertGreater(v.max() / v.min(), 3.0)

    def test_positional_baselines_recompute_from_the_pooled_table(self):
        p = pd.read_csv(HIST / "player_stats_2022_2026.csv", low_memory=False)
        for role in cp.ROLES:
            want = pd.to_numeric(
                p.loc[p["position_group"] == role, "EPA_points_raw"],
                errors="coerce").dropna()
            row = self.base[(self.base["baseline_scope"] == "position")
                            & (self.base["baseline_key"] == role)
                            & (self.base["component"] == "EPA_points_raw")
                            & (self.base["denominated_per_opportunity"] == False)]  # noqa: E712
            self.assertEqual(len(row), 1, role)
            self.assertAlmostEqual(float(row["baseline_mean"].iloc[0]),
                                   float(want.mean()), places=9, msg=role)

    def test_defensive_attribution_is_measured_not_asserted(self):
        d = hf("defensive_attribution_audit.csv")
        self.assertEqual(len(d), 5)
        self.assertEqual(int(d["turnover_events_naming_a_causing_defender"].sum()), 0)
        self.assertEqual(int(d["events_naming_a_closest_defender"].sum()), 0)
        self.assertGreater(int(d["raw_events"].sum()), 40000)
        self.assertTrue(d["defender_actions_completely_absent_from_the_feed"]
                        .str.contains("minutes").all())

    def test_the_partial_wording_survives_everywhere(self):
        for y in SEASONS:
            cols = list(pd.read_csv(PROC / str(y) / f"player_stats_{y}.csv",
                                    nrows=0).columns)
            # only the columns that CARRY a defensive value; the descriptive
            # `defensive_value_scope` states the limitation in its content
            defcols = [c for c in cols
                       if (c.startswith("defensive_value")
                           or c.startswith("defensive_EPA"))
                       and not c.endswith("_scope")]
            self.assertGreater(len(defcols), 0, y)
            for c in defcols:
                self.assertIn("partial", c.lower(), f"{y}.{c}")


# ---------------------------------------------------------------------------
# 6. Readiness table
# ---------------------------------------------------------------------------
class TestReadiness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = hf("mvp_input_readiness.csv")

    def test_every_input_the_brief_names_is_classified(self):
        required = {
            "scoring_production", "shooting_value", "turnover_value",
            "faceoff_value", "goalie_value", "defensive_value_partial",
            "usage", "career_ability", "two_point_production",
            "two_point_ability", "possession_efficiency",
            "opponent_adjustment", "availability_games_played",
            "positional_normalization"}
        self.assertEqual(required - set(self.r["input_name"]), set())

    def test_classes_come_from_the_closed_vocabulary(self):
        valid = {"READY", "READY_WITH_CAVEAT", "EXPERIMENTAL",
                 "NOT_COMPARABLE", "UNSUPPORTED"}
        self.assertTrue(set(self.r["readiness_class"]) <= valid)

    def test_every_classification_carries_evidence(self):
        for col in ("supporting_statistic", "justification",
                    "caveat_that_must_travel_with_it", "evidence_files"):
            self.assertEqual(int(self.r[col].isna().sum()), 0, col)
            self.assertGreater(self.r[col].str.len().min(), 10, col)

    def test_two_point_ability_is_unsupported_and_production_is_not(self):
        cls = self.r.set_index("input_name")["readiness_class"]
        self.assertEqual(cls["two_point_ability"], "UNSUPPORTED")
        self.assertNotEqual(cls["two_point_production"], "UNSUPPORTED")

    def test_cross_position_inputs_are_not_ready(self):
        cls = self.r.set_index("input_name")["readiness_class"]
        for k in ("positional_normalization", "goalie_value", "faceoff_value",
                  "defensive_value_partial"):
            self.assertEqual(cls[k], "NOT_COMPARABLE", k)

    def test_the_readiness_table_classifies_and_never_scores(self):
        self.assertEqual(
            list(self.r.select_dtypes(include=[np.number]).columns), [])

    def test_both_scope_questions_are_answered(self):
        s = hf("phase10_measurement_scope.csv")
        self.assertGreaterEqual(int(s["answer_id"].str.startswith("CAN_MEASURE").sum()), 3)
        self.assertGreaterEqual(int(s["answer_id"].str.startswith("CANNOT_MEASURE").sum()), 4)
        for f in s["evidence_file"].dropna().unique():
            self.assertTrue(
                (HIST / f).exists()
                or any((PROC / str(y) / f).exists() for y in SEASONS), f)


# ---------------------------------------------------------------------------
# 7. Nothing forbidden was built
# ---------------------------------------------------------------------------
class TestNoCompositeArtifactExists(unittest.TestCase):
    """These fail if a Statistical Tewaaraton, MVP score, WAR, replacement-level
    composite, award score or cross-position ranking is ever introduced --
    under that name or under any other."""

    def test_no_forbidden_column_name_in_any_phase10_or_pooled_output(self):
        names = []
        for f in sorted(HIST.glob("*.csv")):
            names += [(f.name, c) for c in pd.read_csv(f, nrows=0).columns]
        for y in SEASONS:
            p = PROC / str(y) / "possessions_repaired.csv"
            if p.exists():
                names += [(p.name, c) for c in pd.read_csv(p, nrows=0).columns]
        for where, n in names:
            for bad in FORBIDDEN_IN_PUBLISHED:
                self.assertNotIn(bad, str(n).lower(), f"{where}.{n}")

    def test_no_cross_position_file_is_keyed_by_player(self):
        """A per-player cross-position table IS the forbidden artifact, whatever
        its columns are called."""
        for f in ("cross_position_method_comparison.csv",
                  "cross_position_value_audit.csv",
                  "cross_position_counterfactuals.csv",
                  "cross_position_replacement_level.csv",
                  "positional_baselines.csv", "mvp_input_readiness.csv",
                  "phase10_measurement_scope.csv"):
            cols = set(pd.read_csv(HIST / f, nrows=0).columns)
            self.assertNotIn("player_id", cols, f)
            self.assertNotIn("player_name", cols, f)

    def test_the_career_table_carries_no_single_summary_value(self):
        c = pd.read_csv(HIST / "player_career_2022_2026.csv", nrows=0)
        banned = {"total_value", "overall_value", "player_score", "value_score",
                  "rating", "rank", "overall_rank", "score"}
        for col in c.columns:
            self.assertNotIn(col.lower(), banned, col)
            for bad in FORBIDDEN_IN_PUBLISHED:
                self.assertNotIn(bad, col.lower(), col)

    def test_no_phase10_module_writes_a_per_player_cross_position_value(self):
        """The method values are computed in memory and consumed by the
        diagnostics; if one is ever persisted, this fails."""
        for f in sorted(HIST.glob("*.csv")):
            cols = set(pd.read_csv(f, nrows=0).columns)
            if "player_id" not in cols and "player_name" not in cols:
                continue
            for m in cp.METHODS:
                self.assertNotIn(m, cols, f"{f.name} publishes {m} per player")

    def test_no_new_script_defines_an_award_or_composite_entry_point(self):
        for p in sorted((REPO_ROOT / "scripts").glob("pll_phase10_*.py")):
            src = p.read_text().lower()
            for bad in ("def build_mvp", "def build_tewaaraton", "def award_score",
                        "def composite_score", "def build_war"):
                self.assertNotIn(bad, src, f"{p.name}: {bad}")


# ---------------------------------------------------------------------------
# 8. Regression: Phase 8 and Phase 9 did not move
# ---------------------------------------------------------------------------
class TestPhase10ChangedNothingFrozen(unittest.TestCase):

    def test_2026_headline_totals_are_exactly_phase_8s(self):
        t = sf(2026, "team_stats_2026.csv")
        p = sf(2026, "player_stats_2026.csv")
        self.assertEqual(len(t), 8)
        self.assertEqual(len(p), 228)
        self.assertEqual(int(t["points_scored"].sum()), 1190)
        self.assertEqual(int(t["shots"].sum()), 4106)
        self.assertEqual(int(t["two_point_attempts"].sum()), 536)
        self.assertEqual(int(t["two_point_goals"].sum()), 72)

    def test_published_possession_counts_match_the_frozen_phase11_baseline(self):
        """Phase 11 update: this asserted Phase 10's frozen (pre-canonicalization)
        possessions.csv counts, unchanged in every season. Phase 11 adopted
        the chronology repair (2023: 4460 -> 4204, 2024: 4047 -> 4001, the
        latter also reflecting the 36 confirmed duplicate faceoffs excluded
        by pll_duplicate_faceoff.py) into canonical possessions.csv; 2022,
        2025 and 2026 remain byte-identical, as documented in
        docs/PHASE11_BEFORE_AFTER_AUDIT.md."""
        for y, n in ((2022, 3795), (2023, 4204), (2024, 4001), (2025, 4009),
                     (2026, 4388)):
            self.assertEqual(len(sf(y, "possessions.csv")), n, y)

    def test_phase9_validation_still_passes(self):
        r = hf("phase9_validation_report.csv")
        self.assertEqual(int((r["status"] != "PASS").sum()), 0, r.to_string())

    def test_phase10_validation_passes(self):
        r = hf("phase10_validation_report.csv")
        self.assertEqual(int((r["status"] != "PASS").sum()), 0, r.to_string())
        self.assertGreaterEqual(len(r), 24)


if __name__ == "__main__":
    unittest.main()
