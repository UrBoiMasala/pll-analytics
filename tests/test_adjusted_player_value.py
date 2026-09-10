"""
Phase 7 tests for the usage / positional-normalization layer.

Every test here exists to protect a specific failure mode the Phase 7 brief
names, so a future change that reintroduces one fails a test rather than
quietly shipping:

  score leakage                    the Phase 6 shot model must stay leak-free
  assist double-counting           assists must stay out of the usage numerator
  faceoff double-counting          a faceoff must not be paid in both usage and
                                   value
  NULL -> 0 on unsupported value   a deferred component must never become zero
  low-volume players disappearing  228 in, 228 out
  position mapping drift           the map must reproduce from the box score
  raw / shrunk column confusion    both must exist and be separately named
  goalie normalization             goalies must never be scaled against field
                                   players
  partial defence relabelled       the word "partial" must survive
  play share as possession share   no possession-denominated column may appear
  two-point skill from tiny samples
  Phase 6 EPA changing unexpectedly

Run with: python3 -m unittest tests.test_adjusted_player_value -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_adjusted_value_models as models  # noqa: E402
import pll_adjusted_value_definitions as defs  # noqa: E402

ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str,
            "officialId": str, "teamId": str}

PHASE7_SQL = ["30_player_adjusted_base_views.sql", "player_position_mapping.sql",
              "player_play_shares.sql", "player_adjusted_core.sql",
              "player_positional_baselines.sql", "player_usage_adjusted_value.sql",
              "player_adjusted_value.sql"]


def _sql_text():
    return "\n".join((SQL_DIR / f).read_text() for f in PHASE7_SQL)


class TestIncompleteBeta(unittest.TestCase):
    """The posterior intervals are only meaningful if the special function
    underneath them is right. scipy is deliberately not a dependency of this
    repo, so the implementation is checked against closed forms."""

    def test_uniform_case_is_the_identity(self):
        for p in [0.05, 0.25, 0.5, 0.9]:
            self.assertAlmostEqual(models.betainc(1, 1, p), p, places=10)
            self.assertAlmostEqual(models.beta_quantile(1, 1, p), p, places=8)

    def test_known_closed_form(self):
        # I_x(2, 5) = 1 - (1-x)^5 (1 + 5x); at x = 0.3 that is 0.579825
        self.assertAlmostEqual(models.betainc(2, 5, 0.3), 0.579825, places=9)

    def test_symmetry(self):
        for a, b, x in [(2, 3, 0.4), (7, 7, 0.5), (0.5, 2.5, 0.2)]:
            self.assertAlmostEqual(models.betainc(a, b, x),
                                   1 - models.betainc(b, a, 1 - x), places=10)

    def test_quantile_inverts_the_cdf(self):
        for a, b in [(2, 5), (30, 70), (300, 700)]:
            for p in [0.025, 0.5, 0.975]:
                q = models.beta_quantile(a, b, p)
                self.assertAlmostEqual(models.betainc(a, b, q), p, places=7)

    def test_strong_prior_gives_a_narrow_interval(self):
        """The two-point case: a prior of a million trials must collapse the
        interval, not silently return garbage."""
        lo = models.beta_quantile(134330, 865670, 0.025)
        hi = models.beta_quantile(134330, 865670, 0.975)
        self.assertLess(hi - lo, 0.005)
        self.assertLess(lo, 0.13433)
        self.assertGreater(hi, 0.13433)


class TestNullVariance(unittest.TestCase):
    """The closed-form sampling variance is the backbone of Phase 7's
    'how unusual is this' question, so its structure is pinned down here."""

    def setUp(self):
        self.base = pd.read_csv(DATA_DIR / "player_value_baselines.csv")
        self.comp = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)

    def test_two_point_attempt_carries_four_times_the_bernoulli_variance(self):
        """A two-point attempt pays 2 points, so its variance is 4p(1-p), not
        p(1-p). Dropping the factor of 4 would understate the noise on every
        long-range shooter and make him look more distinguishable from chance
        than he is."""
        one = pd.DataFrame({"player_id": ["a"], "baseline_group": ["offensive_field"],
                            "one_point_attempts": [100], "two_point_attempts": [0],
                            "shots": [100], "touches": [0], "faceoffs": [0],
                            "games_played": [1], "shots_on_goal_faced": [0],
                            "one_point_shots_on_goal_faced": [0],
                            "two_point_shots_on_goal_faced": [0]})
        two = one.copy()
        two["one_point_attempts"], two["two_point_attempts"] = 0, 100
        v1 = models.null_variance_components(one, self.base)["shooting_value_null_variance"].iloc[0]
        v2 = models.null_variance_components(two, self.base)["shooting_value_null_variance"].iloc[0]
        p1 = float(self.base.loc[self.base.baseline_name ==
                                 "expected_points_per_one_point_attempt",
                                 "baseline_value"].iloc[0])
        p2 = float(self.base.loc[self.base.baseline_name ==
                                 "expected_points_per_two_point_attempt",
                                 "baseline_value"].iloc[0]) / 2
        self.assertAlmostEqual(v1, 100 * p1 * (1 - p1), places=10)
        self.assertAlmostEqual(v2, 100 * 4 * p2 * (1 - p2), places=10)
        self.assertGreater(v2, v1, "a two-point attempt must be the noisier bet")

    def test_variance_scales_linearly_with_opportunities(self):
        """Doubling the attempts doubles the variance and multiplies the
        standard deviation by sqrt(2). This is why a high-volume player's total
        can be large without being unusual."""
        small = pd.DataFrame({"player_id": ["a"], "baseline_group": ["offensive_field"],
                              "one_point_attempts": [50], "two_point_attempts": [0],
                              "shots": [50], "touches": [0], "faceoffs": [0],
                              "games_played": [1], "shots_on_goal_faced": [0],
                              "one_point_shots_on_goal_faced": [0],
                              "two_point_shots_on_goal_faced": [0]})
        big = small.copy()
        big["one_point_attempts"], big["shots"] = 100, 100
        vs = models.null_variance_components(small, self.base)["shooting_value_null_sd"].iloc[0]
        vb = models.null_variance_components(big, self.base)["shooting_value_null_sd"].iloc[0]
        self.assertAlmostEqual(vb / vs, np.sqrt(2.0), places=8)

    def test_null_variance_is_null_not_zero_without_opportunities(self):
        """A player who took no draws has an UNDEFINED faceoff sampling
        variance. Reporting 0 would say his faceoff value is known exactly."""
        n = models.null_variance_components(self.comp, self.base)
        m = self.comp.merge(n, on="player_id")
        no_fo = m[m["faceoffs"] == 0]
        self.assertGreater(len(no_fo), 0)
        self.assertTrue(no_fo["faceoff_value_null_variance"].isna().all())
        self.assertTrue(m.loc[m["shots_on_goal_faced"] == 0,
                              "goalie_value_null_variance"].isna().all())


class TestReliability(unittest.TestCase):
    def test_reliability_is_the_posterior_weight(self):
        rel = pd.read_csv(DATA_DIR / "player_rate_reliability.csv", dtype=ID_DTYPE)
        r = rel[rel["trials"] > 0]
        implied = r["trials"] / (r["trials"] + r["prior_strength_trials"])
        np.testing.assert_allclose(r["reliability"], implied, rtol=0, atol=1e-12)

    def test_reliability_increases_with_sample(self):
        rel = pd.read_csv(DATA_DIR / "player_rate_reliability.csv", dtype=ID_DTYPE)
        fo = rel[(rel["rate_name"] == "faceoff_win_pct") & (rel["trials"] > 0)]
        fo = fo.sort_values("trials")
        self.assertTrue((fo["reliability"].diff().dropna() >= -1e-12).all(),
                        "reliability must be monotone in the number of trials")

    def test_reliability_threshold_is_derived_not_a_round_number(self):
        """0.5 reliability corresponds to a DIFFERENT trial count for every
        rate, because each prior strength is estimated separately. If two rates
        ever share a threshold it means a constant has been hard-coded."""
        ident = pd.read_csv(DATA_DIR / "player_rate_identification.csv")
        finite = ident[ident["prior_strength_trials"] < 1e5]
        thresholds = sorted(round(x, 3) for x in finite["trials_for_reliability_0_5"])
        self.assertEqual(len(thresholds), len(set(thresholds)),
                         "every rate must have its own empirically estimated threshold")
        for t in thresholds:
            self.assertNotAlmostEqual(t % 10, 0.0, places=6,
                                      msg="a threshold landing on a round 10 is suspicious")


class TestUsageDefinition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        cls.usage = pd.read_csv(DATA_DIR / "player_play_shares.csv", dtype=ID_DTYPE)

    def test_assists_are_not_in_the_usage_numerator(self):
        """An assist attaches to a goal already counted as the shooter's shot.
        Including it would count one offensive sequence twice at team level."""
        opp = pd.read_csv(DATA_DIR / "player_opportunities.csv", dtype=ID_DTYPE)
        j = self.av.set_index("player_id").join(opp.set_index("player_id")[["official_assists"]],
                                                rsuffix="_o")
        expected = j["shots"] + j["turnovers"]
        pd.testing.assert_series_equal(
            j["recorded_offensive_opportunities"].astype(float), expected.astype(float),
            check_names=False)
        assisters = j[j["official_assists"] > 0]
        self.assertGreater(len(assisters), 0)
        self.assertTrue(
            (assisters["recorded_offensive_opportunities"]
             < assisters["shots"] + assisters["turnovers"] + assisters["official_assists"]).all(),
            "the usage numerator must be strictly smaller than an assist-inclusive one")

    def test_faceoffs_are_not_in_the_offensive_usage_numerator(self):
        """A faceoff win is already paid in faceoff_value. Counting it as an
        offensive opportunity as well would credit the same draw twice -- once
        as workload and once as production."""
        fo = self.av[self.av["faceoffs"] > 0]
        self.assertGreater(len(fo), 0)
        expected = fo["shots"] + fo["turnovers"]
        np.testing.assert_array_equal(
            fo["recorded_offensive_opportunities"].to_numpy(), expected.to_numpy())
        specialists = self.av[self.av["value_role"] == "faceoff"]
        self.assertTrue((specialists["recorded_offensive_opportunities"]
                         < specialists["faceoffs"]).all(),
                        "a specialist's offensive usage must not absorb his draws")

    def test_ground_balls_are_not_in_the_usage_numerator(self):
        gb = self.av[self.av["ground_balls"] > 0]
        self.assertGreater(len(gb), 0)
        np.testing.assert_array_equal(
            gb["recorded_offensive_opportunities"].to_numpy(),
            (gb["shots"] + gb["turnovers"]).to_numpy())

    def test_season_play_shares_sum_to_one_per_team(self):
        self.assertAlmostEqual(float(self.av["offensive_play_share_season"].sum()),
                               float(self.av["team_id"].nunique()), places=9)

    def test_play_share_is_never_called_a_possession_share(self):
        """The single most important naming rule in this phase: the feed has no
        lineup data, so nothing may be presented as possession participation."""
        banned = ["possession_share", "possessions_played", "on_field", "lineup",
                  "minutes", "time_on_field", "per_possession"]
        for frame in [self.av, self.usage,
                      pd.read_csv(DATA_DIR / "player_usage_adjusted_value.csv",
                                  dtype=ID_DTYPE)]:
            for c in frame.columns:
                for b in banned:
                    self.assertNotIn(b, c.lower())
        self.assertTrue(self.av["usage_proxy_only"].astype(bool).all())

    def test_no_duration_based_denominator_in_the_sql(self):
        text = _sql_text()
        for token in ["timeInPossesion", "duration_seconds", "seconds_passed"]:
            self.assertNotRegex(text, rf"\b{token}\b")

    def test_event_log_play_shares_reproduce_phase6_exactly(self):
        """Phase 7 audits the Phase 6 measure; it must not silently change it."""
        c6 = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
        j = self.av.set_index("player_id")["event_log_play_shares"]
        k = c6.set_index("player_id")["play_shares"].reindex(j.index)
        pd.testing.assert_series_equal(j.astype(float), k.astype(float), check_names=False)


class TestPositionMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pmap = pd.read_csv(DATA_DIR / "player_position_map.csv", dtype=ID_DTYPE)
        cls.av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)

    def test_every_player_is_mapped_exactly_once(self):
        self.assertEqual(len(self.pmap), 228)
        self.assertFalse(self.pmap["player_id"].duplicated().any())
        self.assertTrue(self.pmap["canonical_position"].notna().all())
        self.assertTrue(self.pmap["value_role"].notna().all())

    def test_unlabelled_players_are_unknown_not_guessed(self):
        unk = self.pmap[self.pmap["canonical_position"] == "unknown"]
        self.assertEqual(len(unk), 2)
        self.assertTrue((unk["mapping_confidence"] == "low").all())

    def test_every_mapping_carries_a_reason(self):
        self.assertTrue(self.pmap["mapping_reason"].str.len().gt(10).all())
        # a roster-based assignment must say so, so it can never be mistaken
        # for a measured one
        roster = self.pmap[self.pmap["mapping_reason"].str.startswith("roster_position")]
        self.assertGreater(len(roster), 0)
        self.assertTrue(roster["mapping_reason"].str.contains("roster_position").all())

    def test_faceoff_role_threshold_sits_in_an_empirical_gap(self):
        """The 50% team-faceoff-share rule is Lacrosse Reference's published
        threshold, and in 2026 it lands in a wide empty band. If a future
        season puts players in that band this test fails and the rule gets
        looked at deliberately rather than silently misclassifying someone."""
        fo = self.pmap[self.pmap["value_role"] == "faceoff"]["faceoff_team_share"]
        rest = self.pmap[self.pmap["value_role"] != "faceoff"]["faceoff_team_share"].dropna()
        self.assertEqual(len(fo), 13)
        self.assertGreater(fo.min(), 0.75)
        self.assertLess(rest.max(), 0.25)

    def test_goalie_role_comes_from_measured_opportunity(self):
        gk = self.pmap[self.pmap["value_role"] == "goalie"]
        measured = gk[gk["shots_on_goal_faced"] > 0]
        self.assertEqual(len(measured), 16)
        self.assertTrue(measured["mapping_reason"].str.startswith("measured_opportunity").all())
        # every measured goalie is also a rostered goalie: the two agree in 2026
        self.assertTrue((measured["canonical_position"] == "goalie").all())

    def test_offense_defense_split_is_labelled_as_roster_derived(self):
        """The honest part of the classifier. The feed measures one defensive
        act, so an opportunity-based offence/defence split is not supportable
        and the map must say the roster label was used."""
        field = self.pmap[self.pmap["value_role"].isin(["offensive_field", "defensive_field"])]
        self.assertGreater(len(field), 150)
        self.assertTrue(field["mapping_reason"].str.contains("roster_position").all())
        self.assertTrue(field["mapping_reason"].str.contains("caused turnovers").all())


class TestPhase6Immutability(unittest.TestCase):
    def test_raw_epa_is_identical_to_phase6(self):
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        c6 = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
        a, b = av.set_index("player_id"), c6.set_index("player_id")
        for new, old in [("EPA_points_raw", "total_player_value"),
                         ("shooting_value_raw", "shooting_value"),
                         ("turnover_value_raw", "turnover_value"),
                         ("faceoff_value_raw", "faceoff_value"),
                         ("goalie_value_raw", "goalie_value"),
                         ("defensive_value_partial_raw", "caused_turnover_value")]:
            with self.subTest(column=new):
                x, y = a[new], b[old].reindex(a.index)
                # exact, not approximate: these are carried across, not recomputed
                self.assertTrue(((x == y) | (x.isna() & y.isna())).all())

    def test_phase6_league_sum_identity_survives(self):
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        for col in ["shooting_value_raw", "turnover_value_raw", "faceoff_value_raw",
                    "goalie_value_raw", "defensive_value_partial_raw", "EPA_points_raw"]:
            with self.subTest(component=col):
                self.assertAlmostEqual(av[col].sum(), 0.0, places=6)

    def test_no_phase7_source_writes_a_phase6_output(self):
        text = _sql_text() + "\n".join(
            (REPO_ROOT / "scripts" / f).read_text() for f in
            ["pll_build_adjusted_player_value.py", "pll_adjusted_value_models.py",
             "pll_adjusted_value_sensitivity.py", "pll_adjusted_value_diagnostics.py"])
        for name in ["player_value_components.csv", "player_opportunities.csv",
                     "player_value_baselines.csv", "player_value_shrinkage.csv"]:
            self.assertNotRegex(text, rf"to_csv\([^)]*{re.escape(name)}")

    def test_score_leakage_guard_still_in_place(self):
        """Phase 6 fixed a target-leakage bug by lagging the score. Phase 7
        must not reintroduce a score-after-event feature anywhere."""
        text = _sql_text()
        for token in ["home_score_raw", "away_score_raw", "home_score_corrected",
                      "away_score_corrected"]:
            self.assertNotIn(token, text)


class TestNullDiscipline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)

    def test_no_player_is_dropped(self):
        c6 = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
        self.assertEqual(len(self.av), len(c6))
        self.assertEqual(set(self.av["player_id"]), set(c6["player_id"]))
        self.assertTrue(self.av["descriptive_eligible"].astype(bool).all())

    def test_low_volume_players_survive_with_flags_not_deletion(self):
        tiny = self.av[self.av["recorded_offensive_opportunities"] <= 1]
        self.assertGreater(len(tiny), 10)
        self.assertTrue(tiny["descriptive_eligible"].astype(bool).all())
        self.assertTrue(tiny["EPA_points_raw"].notna().all(),
                        "a flagged player must keep his observed value")
        # No offensive-rate leaderboard may admit them...
        self.assertFalse(tiny["offensive_rate_ranking_eligible"].astype(bool).any())
        # ...but a faceoff specialist with almost no offensive opportunities and
        # hundreds of draws IS well identified on the rate that defines his
        # role, and rate_ranking_eligible is role-specific by design. The two
        # gates exist precisely so that one does not license the other.
        eligible_tiny = tiny[tiny["rate_ranking_eligible"].astype(bool)]
        self.assertTrue((eligible_tiny["value_role"] == "faceoff").all())
        self.assertTrue((eligible_tiny["faceoffs"] > 15.9).all())

    def test_unsupported_components_do_not_become_zero(self):
        self.assertTrue(self.av.loc[self.av["faceoffs"] == 0,
                                    "faceoff_value_raw"].isna().all())
        self.assertTrue(self.av.loc[self.av["shots_on_goal_faced"] == 0,
                                    "goalie_value_raw"].isna().all())
        self.assertTrue(self.av.loc[self.av["recorded_offensive_opportunities"] == 0,
                                    "EPA_per_recorded_opportunity"].isna().all())

    def test_usage_expectation_is_null_outside_its_population(self):
        outside = self.av[~self.av["value_role"].isin(["offensive_field", "defensive_field"])]
        self.assertGreater(len(outside), 0)
        self.assertTrue(outside["expected_EPA_given_usage"].isna().all(),
                        "a goalie has no offensive-usage expectation; 0 would be a claim")


class TestStandardization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        cls.pb = pd.read_csv(DATA_DIR / "player_positional_baselines.csv")

    def test_goalies_are_not_normalized_against_field_players(self):
        """The headline cross-position rule. A goalie's EPA spread is 9.6
        against 3.9 for offensive field players; scaling them together would
        rank by opportunity structure, not by quality."""
        gk = self.av[self.av["value_role"] == "goalie"]
        own = (gk["EPA_points_raw"].rank(method="average") - 0.5) / len(gk) * 100
        np.testing.assert_allclose(gk["EPA_position_percentile"], own, atol=1e-9)
        league = ((self.av["EPA_points_raw"].rank(method="average") - 0.5)
                  / len(self.av) * 100).loc[gk.index]
        self.assertFalse(np.allclose(gk["EPA_position_percentile"], league, atol=1e-6),
                         "the goalie percentile must not coincide with a league percentile")
        gk_sd = float(self.pb.loc[(self.pb.baseline_scope == "role")
                                  & (self.pb.baseline_group == "goalie")
                                  & (self.pb.metric_name == "EPA_points_raw"), "sd"].iloc[0])
        of_sd = float(self.pb.loc[(self.pb.baseline_scope == "role")
                                  & (self.pb.baseline_group == "offensive_field")
                                  & (self.pb.metric_name == "EPA_points_raw"), "sd"].iloc[0])
        self.assertGreater(gk_sd / of_sd, 2.0,
                           "if the two spreads ever converge, revisit the separation")

    def test_faceoff_specialists_are_normalized_within_their_role(self):
        fo = self.av[self.av["value_role"] == "faceoff"]
        own = (fo["EPA_points_raw"].rank(method="average") - 0.5) / len(fo) * 100
        np.testing.assert_allclose(fo["EPA_position_percentile"], own, atol=1e-9)

    def test_small_groups_get_no_z_score(self):
        # Suppression is per (group, metric): `attack` is suppressed for
        # save_rate because almost no attackman faces a shot on goal, while its
        # EPA baseline is fine. The EPA z-score is gated by the EPA row only.
        supp = set(self.pb.loc[(self.pb.baseline_scope == "position")
                               & (self.pb.metric_name == "EPA_points_raw")
                               & (~self.pb.sd_is_publishable), "baseline_group"])
        self.assertIn("unknown", supp)
        leaked = self.av[self.av["position_group"].isin(supp)
                         & self.av["EPA_position_z"].notna()]
        self.assertEqual(len(leaked), 0)

    def test_percentiles_are_in_range_and_centred(self):
        for c in ["EPA_position_percentile", "usage_position_percentile",
                  "efficiency_position_percentile"]:
            v = self.av[c].dropna()
            self.assertGreaterEqual(v.min(), 0.0)
            self.assertLessEqual(v.max(), 100.0)
            self.assertAlmostEqual(v.mean(), 50.0, delta=1.0)

    def test_robust_z_resists_an_outlier_the_ordinary_z_does_not(self):
        """The reason both are published. A single extreme value inflates the
        sd and shrinks everyone else's ordinary z; the MAD is unmoved."""
        clean = np.array([0.0, 1.0, -1.0, 0.5, -0.5, 0.2, -0.2, 0.8, -0.8, 0.1])
        spiked = np.append(clean, 50.0)
        z_clean = (clean[1] - clean.mean()) / clean.std(ddof=1)
        z_spiked = (spiked[1] - spiked.mean()) / spiked.std(ddof=1)
        rz_clean = models.robust_z(clean)[1]
        rz_spiked = models.robust_z(spiked)[1]
        ordinary_shift = abs(z_spiked - z_clean) / abs(z_clean)
        robust_shift = abs(rz_spiked - rz_clean) / abs(rz_clean)
        # The outlier costs the ordinary z about 70% of its magnitude and the
        # robust z about 20%. The claim is relative resistance, not immunity:
        # adding an eleventh point does move the median and the MAD a little.
        self.assertGreater(ordinary_shift, 0.6)
        self.assertLess(robust_shift, 0.3)
        self.assertLess(robust_shift, 0.5 * ordinary_shift)


class TestPartialDefence(unittest.TestCase):
    def test_partial_label_survives_in_the_column_name(self):
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        self.assertIn("defensive_value_partial_raw", av.columns)
        self.assertTrue(av["defense_partial"].astype(bool).all())
        self.assertTrue(av["defensive_value_scope"].dropna().str.contains("partial").all())
        exempt = {"defense_partial", "defensive_value_scope"}
        for c in av.columns:
            if "defensive" in c and c not in exempt:
                self.assertIn("partial", c,
                              f"{c} reads as a comprehensive defensive metric")

    def test_zero_defensive_value_is_not_documented_as_average_defender(self):
        d = {r["metric_name"]: r for r in defs.ADJUSTED_DEFINITIONS}
        blob = d["defense_partial"]["known_limitations"].lower()
        self.assertIn("does not mean", blob.replace("not mean", "not mean"))
        self.assertIn("unmeasured", blob + d["value_role"]["known_limitations"].lower())

    def test_defensive_caveat_is_carried_on_defender_rows(self):
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        dfd = av[av["value_role"] == "defensive_field"]
        self.assertGreater(len(dfd), 50)
        self.assertTrue(dfd["role_interpretation_caveat"].str.contains("PARTIAL").all())


class TestTwoPointSkill(unittest.TestCase):
    def test_two_point_reliability_is_effectively_zero_for_everyone(self):
        """Locked in. If a future season makes two-point shooting measurable,
        this fails and the decision gets revisited deliberately."""
        rel = pd.read_csv(DATA_DIR / "player_rate_reliability.csv", dtype=ID_DTYPE)
        tp = rel[rel["rate_name"] == "two_point_pct"]
        self.assertGreater(float(tp["prior_strength_trials"].iloc[0]), 1e5)
        self.assertLess(float(tp["reliability"].dropna().max()), 0.001)

    def test_two_point_never_gates_a_rate_leaderboard(self):
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        self.assertNotIn("two_point", set(av["role_rate_name"]))

    def test_two_point_is_documented_unsupported(self):
        d = {r["metric_name"]: r for r in defs.ADJUSTED_DEFINITIONS}
        self.assertEqual(d["two_point_reliability"]["status"], "unsupported")


class TestRawVersusShrunk(unittest.TestCase):
    def test_both_forms_exist_and_are_separately_named(self):
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        for stem in ["shooting_rate", "one_point_rate", "two_point_rate",
                     "faceoff_rate", "save_rate"]:
            self.assertIn(f"{stem}_raw", av.columns)
            self.assertIn(f"{stem}_shrunk", av.columns)
        ambiguous = [c for c in av.columns if c.endswith("_rate")]
        self.assertEqual(ambiguous, [],
                         "a bare '<x>_rate' column leaves the reader guessing which it is")

    def test_shrunk_rates_are_not_substituted_into_raw_value(self):
        """The Phase 6 discipline, re-asserted. Raw value must be built from
        observed conversion, so replacing the shooting component with a
        shrunk-rate version must actually change it."""
        sens = pd.read_csv(DATA_DIR / "player_adjusted_value_sensitivity.csv", dtype=ID_DTYPE)
        s = sens[(sens["family"] == "shrinkage_treatment")
                 & (sens["metric"] == "shooting_value_raw")].dropna(subset=["difference"])
        self.assertGreater(len(s), 100)
        self.assertGreater(s["difference"].abs().max(), 1.0)
        self.assertGreater(int((s["rank_change"] != 0).sum()), 100,
                           "shrinkage must be shown to move ranks, not quietly agree")


class TestNoAwardModel(unittest.TestCase):
    def test_no_composite_column_exists_anywhere(self):
        banned = {"tewaaraton", "mvp", "composite", "rating", "war", "replacement", "score"}
        for f in sorted(DATA_DIR.glob("player_adjusted*.csv")) + \
                sorted(DATA_DIR.glob("player_usage*.csv")):
            for c in pd.read_csv(f, nrows=0).columns:
                tokens = set(re.split(r"[^a-z]+", c.lower()))
                self.assertEqual(tokens & banned, set(), f"{f.name}:{c}")

    def test_no_weighting_appears_in_the_phase7_sql(self):
        text = _sql_text().lower()
        for token in ["award_weight", "mvp", "tewaaraton"]:
            self.assertNotIn(token, text)

    def test_usage_is_never_multiplied_into_value(self):
        """The specific thing the brief forbids: rewarding usage for being
        usage. No published column may equal value x usage."""
        av = pd.read_csv(DATA_DIR / "player_adjusted_value.csv", dtype=ID_DTYPE)
        product = av["EPA_points_raw"] * av["offensive_play_share"]
        for c in av.select_dtypes(include=[np.number]).columns:
            if av[c].isna().all():
                continue
            both = av[[c]].join(product.rename("p")).dropna()
            if len(both) < 50:
                continue
            self.assertFalse(np.allclose(both[c], both["p"], atol=1e-9),
                             f"{c} equals EPA x usage")


class TestDefinitions(unittest.TestCase):
    def test_metric_names_unique(self):
        names = [r["metric_name"] for r in defs.ADJUSTED_DEFINITIONS]
        self.assertEqual(len(names), len(set(names)))

    def test_every_definition_has_limitations_and_a_valid_status(self):
        valid = {"production", "production_partial", "diagnostic", "descriptive",
                 "reference_reproduction", "deferred", "unsupported"}
        for row in defs.ADJUSTED_DEFINITIONS:
            self.assertIn(row["status"], valid, row["metric_name"])
            self.assertTrue(row["known_limitations"].strip(), row["metric_name"])
            self.assertTrue(row["interpretation"].strip(), row["metric_name"])

    def test_no_replacement_level_or_war_language(self):
        for row in defs.ADJUSTED_DEFINITIONS:
            blob = (row["definition"] + row["interpretation"] + row["baseline"]).lower()
            self.assertNotIn("above replacement", blob, row["metric_name"])
            self.assertNotIn("war", blob.split(), row["metric_name"])

    def test_lacrosse_reference_reproductions_are_labelled_as_such(self):
        """Reproducing someone else's operation is not the same as adopting it.
        Anything that reproduces Lacrosse Reference must say so in its status."""
        d = {r["metric_name"]: r for r in defs.ADJUSTED_DEFINITIONS}
        for name in ["event_log_play_shares", "uaEPA_per_event_log_play_share"]:
            self.assertEqual(d[name]["status"], "reference_reproduction")
            self.assertIn("lacrosse reference", d[name]["definition"].lower()
                          + d[name]["interpretation"].lower())


class TestUsageModel(unittest.TestCase):
    def test_constant_model_wins_when_there_is_no_relationship(self):
        """The model selector must be able to say 'usage tells you nothing'.
        A selector that always picks a slope would manufacture a usage effect
        out of noise."""
        rng = np.random.default_rng(0)
        x = rng.uniform(0, 0.2, 300)
        y = rng.normal(0, 3, 300)
        cv, fitted, coef, degree = models.fit_usage_model(x, y)
        self.assertEqual(degree, 0)
        self.assertAlmostEqual(float(np.std(fitted)), 0.0, places=9)

    def test_a_real_linear_relationship_is_detected(self):
        rng = np.random.default_rng(1)
        x = rng.uniform(0, 0.2, 300)
        y = 40 * x + rng.normal(0, 0.5, 300)
        cv, fitted, coef, degree = models.fit_usage_model(x, y)
        self.assertGreaterEqual(degree, 1)
        self.assertGreater(coef[1], 30)

    def test_published_fit_is_the_constant_in_2026(self):
        """The 2026 finding, locked in: usage does not predict the MEAN of
        measured value. If this changes the methodology text must change with
        it."""
        cv = pd.read_csv(DATA_DIR / "player_usage_model.csv")
        pub = cv[cv["weighting"].str.startswith("unweighted")]
        selected = pub.loc[pub["selected_model"], "model"].tolist()
        self.assertEqual(selected, ["constant"])
        self.assertLess(abs(float(pub["pearson_r_usage_vs_offensive_EPA"].iloc[0])), 0.20)

    def test_variance_grows_with_usage_even_though_the_mean_does_not(self):
        """The other half of the finding, and the reason the usage adjustment
        is a scale adjustment rather than a mean adjustment."""
        prof = pd.read_csv(DATA_DIR / "player_usage_variance_profile.csv")
        self.assertGreater(prof["sd_offensive_EPA"].iloc[-1],
                           3 * prof["sd_offensive_EPA"].iloc[0])


if __name__ == "__main__":
    unittest.main()
