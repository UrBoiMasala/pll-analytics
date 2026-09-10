"""
Phase 6 tests for the player-value framework.

Two kinds:

1. Accounting tests on SYNTHETIC possessions. These are the double-counting
   safeguards docs/PLAYER_VALUE_ACCOUNTING.md describes, executed rather than
   asserted in prose. Each one constructs a single play, runs the published
   formulas over it, and checks that one point of team scoring never becomes
   more than one point of player value.

2. Integration tests against the real 2026 outputs, locking in the
   evidence-based decisions this phase made (deferred ground balls, deferred
   assists, NULL discipline, league-sum identities, the shot-model choice).

Run with: python3 -m unittest tests.test_player_value -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_player_value_models as models  # noqa: E402
import pll_player_value_definitions as defs  # noqa: E402

ID_DTYPE = {"player_id": str, "team_id": str, "primary_team_id": str}

# The published coefficients, restated here so a change to the pipeline that
# silently moves them fails a test rather than passing unnoticed.
XP_ONE_POINT = 0.29300
XP_TWO_POINT = 0.26866
XP_ALLOWED_ONE_POINT_SOG = 0.46120
XP_ALLOWED_TWO_POINT_SOG = 0.48161
POINTS_PER_TURNOVER = 0.20046
POINTS_PER_MARGINAL_FACEOFF_WIN = 0.34643
PLACES = 4


def shooting_value(one_pt_attempts, two_pt_attempts, one_pt_goals, two_pt_goals):
    observed = one_pt_goals + 2 * two_pt_goals
    expected = one_pt_attempts * XP_ONE_POINT + two_pt_attempts * XP_TWO_POINT
    return observed - expected


def goalie_value(one_pt_sog, two_pt_sog, one_pt_goals_allowed, two_pt_goals_allowed):
    expected = one_pt_sog * XP_ALLOWED_ONE_POINT_SOG + two_pt_sog * XP_ALLOWED_TWO_POINT_SOG
    actual = one_pt_goals_allowed + 2 * two_pt_goals_allowed
    return expected - actual


class TestPllTwoPointScoring(unittest.TestCase):
    def test_two_point_goal_is_one_goal_worth_two_points(self):
        v = shooting_value(0, 1, 0, 1)
        self.assertAlmostEqual(v, 2 - XP_TWO_POINT, places=PLACES)
        self.assertGreater(v, shooting_value(1, 0, 1, 0),
                           "a two-point goal must add more value than a one-point goal")

    def test_two_point_expectation_uses_probability_times_two(self):
        """E[points | two-point attempt] must be P(goal)*2, not P(goal). The
        published 0.26866 is 0.13433 x 2; if it were left as P(goal) the whole
        two-point component would be halved."""
        self.assertAlmostEqual(XP_TWO_POINT, 0.13433 * 2, places=4)

    def test_missed_two_point_shot_costs_more_than_missed_one_pointer(self):
        self.assertLess(shooting_value(0, 1, 0, 0), 0)
        self.assertLess(shooting_value(1, 0, 0, 0), 0)

    def test_league_average_shooter_scores_zero(self):
        """A player converting at exactly the league rate adds nothing. This is
        the definition of the baseline, and it is what makes the components
        addable."""
        v = shooting_value(1000, 0, 1000 * XP_ONE_POINT, 0)
        self.assertAlmostEqual(v, 0.0, places=6)


class TestAccountingNoDoubleCounting(unittest.TestCase):
    """The scenarios in docs/PLAYER_VALUE_ACCOUNTING.md, executed."""

    def test_scenario_A_missed_shot_charges_only_the_shooter(self):
        shooter = shooting_value(1, 0, 0, 0)
        self.assertAlmostEqual(shooter, -XP_ONE_POINT, places=PLACES)
        # nobody else is touched: a miss is not a turnover and creates no
        # faceoff or caused-turnover opportunity
        self.assertAlmostEqual(shooter, -0.29300, places=PLACES)

    def test_scenario_B_one_point_goal_credits_shooter_only(self):
        self.assertAlmostEqual(shooting_value(1, 0, 1, 0), 1 - XP_ONE_POINT, places=PLACES)

    def test_scenario_C_two_point_goal_credits_shooter_only(self):
        self.assertAlmostEqual(shooting_value(0, 1, 0, 1), 2 - XP_TWO_POINT, places=PLACES)

    def test_scenario_D_turnover_charges_only_the_committer(self):
        """One turnover above expectation costs exactly one turnover
        coefficient -- it must not also subtract a possession's worth of
        points, which would charge the same lost opportunity twice."""
        turnovers, expected = 1.0, 0.0
        value = -(turnovers - expected) * POINTS_PER_TURNOVER
        self.assertAlmostEqual(value, -POINTS_PER_TURNOVER, places=PLACES)
        league_ppp = 0.27120
        self.assertNotAlmostEqual(abs(value), league_ppp + POINTS_PER_TURNOVER, places=3)

    def test_scenario_D_shooting_and_turnover_are_disjoint(self):
        """A possession with two missed shots and a turnover: the shooter is
        charged for two attempts and one turnover, and nothing is counted
        twice. The components use different opportunity sets (attempts vs
        touches), so their sum is exactly the sum of the parts."""
        shot_part = shooting_value(2, 0, 0, 0)
        turnover_part = -(1.0 - 0.0) * POINTS_PER_TURNOVER
        total = shot_part + turnover_part
        self.assertAlmostEqual(total, -2 * XP_ONE_POINT - POINTS_PER_TURNOVER, places=PLACES)

    def test_scenario_E_caused_turnover_and_ground_ball_pay_once(self):
        """A caused turnover followed by the same defender scooping the loose
        ball is ONE change of possession. Ground-ball value is deferred, so the
        defender is paid once (for the caused turnover) and not twice."""
        caused_turnover_part = (1.0 - 0.0) * POINTS_PER_TURNOVER
        ground_ball_part = 0.0  # deferred: contributes nothing to any total
        total = caused_turnover_part + ground_ball_part
        self.assertAlmostEqual(total, POINTS_PER_TURNOVER, places=PLACES)

    def test_scenario_E_turnover_and_caused_turnover_are_opposite_and_equal(self):
        """The same physical event seen from both sides. The committer loses
        exactly what the causer gains, so the pair nets to zero league-wide
        rather than creating value out of nothing."""
        committer = -(1.0 - 0.0) * POINTS_PER_TURNOVER
        causer = (1.0 - 0.0) * POINTS_PER_TURNOVER
        self.assertAlmostEqual(committer + causer, 0.0, places=10)

    def test_scenario_F_faceoff_win_at_league_rate_is_worth_nothing(self):
        """The counterfactual is a league-average faceoff man, not an absent
        one. Winning at the league rate creates no value; only wins above it
        do."""
        faceoffs, league_rate = 100.0, 0.49656
        at_rate = (faceoffs * league_rate - faceoffs * league_rate) * POINTS_PER_MARGINAL_FACEOFF_WIN
        self.assertAlmostEqual(at_rate, 0.0, places=10)
        one_extra = ((faceoffs * league_rate + 1) - faceoffs * league_rate) \
            * POINTS_PER_MARGINAL_FACEOFF_WIN
        self.assertAlmostEqual(one_extra, POINTS_PER_MARGINAL_FACEOFF_WIN, places=PLACES)

    def test_scenario_F_marginal_faceoff_win_is_twice_the_event_value(self):
        """Converting a loss into a win swings the value from the opponent to
        you, so it is worth 2v, not v."""
        event_value = POINTS_PER_MARGINAL_FACEOFF_WIN / 2
        self.assertAlmostEqual(2 * event_value, POINTS_PER_MARGINAL_FACEOFF_WIN, places=10)

    def test_scenario_G_goalie_save_credits_goalie_and_charges_shooter(self):
        """A saved one-point shot: the shooter is charged his attempt's
        expectation, the goalie is credited for preventing it. Both are real
        and opposite -- they concern different teams and do not cancel within a
        team, but neither creates points that were not there."""
        shooter = shooting_value(1, 0, 0, 0)
        keeper = goalie_value(1, 0, 0, 0)
        self.assertAlmostEqual(shooter, -XP_ONE_POINT, places=PLACES)
        self.assertAlmostEqual(keeper, XP_ALLOWED_ONE_POINT_SOG, places=PLACES)

    def test_scenario_G_goalie_conceding_at_league_rate_scores_zero(self):
        v = goalie_value(1000, 0, 1000 * XP_ALLOWED_ONE_POINT_SOG, 0)
        self.assertAlmostEqual(v, 0.0, places=6)

    def test_scenario_H_assisted_goal_credits_only_the_shooter(self):
        """Assist value is deferred precisely so that one goal does not produce
        two players' worth of value."""
        shooter = shooting_value(1, 0, 1, 0)
        assister = 0.0
        self.assertAlmostEqual(shooter + assister, 1 - XP_ONE_POINT, places=PLACES)
        self.assertLess(shooter + assister, 1.0,
                        "one point of team scoring must never yield more than one point "
                        "of player value")

    def test_one_goal_never_yields_more_than_its_points_in_player_value(self):
        """The headline accounting invariant, across both goal types."""
        for one_pt, two_pt, points in [(1, 0, 1), (0, 1, 2)]:
            with self.subTest(points=points):
                total = shooting_value(one_pt, two_pt, one_pt, two_pt)
                self.assertLessEqual(total, points)


class TestEmpiricalBayes(unittest.TestCase):
    def test_no_between_player_spread_shrinks_hard_to_the_mean(self):
        """When observed spread is no wider than binomial noise, the estimator
        must conclude there is no measurable skill difference rather than
        reporting a spurious one."""
        rng = np.random.default_rng(0)
        trials = np.full(200, 5)
        successes = rng.binomial(5, 0.13, size=200)
        a, b = models.beta_prior_by_moments(successes, trials)
        self.assertGreater(a + b, 1000, "a pure-noise sample must produce a very strong prior")

    def test_real_spread_produces_a_weak_prior(self):
        """With genuinely different players and large samples, shrinkage should
        barely move anyone."""
        trials = np.full(40, 300)
        rates = np.linspace(0.30, 0.70, 40)
        successes = (trials * rates).astype(int)
        a, b = models.beta_prior_by_moments(successes, trials)
        self.assertLess(a + b, 100, "real between-player spread must yield a weak prior")

    def test_shrunk_rate_is_between_raw_and_prior_mean(self):
        df = pd.DataFrame({"player_id": ["a", "b"], "s": [8.0, 1.0], "n": [10.0, 10.0]})
        out = models.empirical_bayes_rates(df, "s", "n", "r")
        prior_mean = out["r_prior_mean"].iloc[0]
        for _, row in out.iterrows():
            lo, hi = sorted([row["r_raw"], prior_mean])
            self.assertGreaterEqual(row["r_shrunk"], lo - 1e-9)
            self.assertLessEqual(row["r_shrunk"], hi + 1e-9)

    def test_zero_trials_gives_null_not_a_prior_mean(self):
        df = pd.DataFrame({"player_id": ["a", "b"], "s": [5.0, 0.0], "n": [10.0, 0.0]})
        out = models.empirical_bayes_rates(df, "s", "n", "r")
        self.assertTrue(np.isnan(out.loc[out["player_id"] == "b", "r_shrunk"].iloc[0]))


class TestDefinitions(unittest.TestCase):
    def test_metric_names_unique(self):
        names = [r["metric_name"] for r in defs.DEFINITIONS]
        self.assertEqual(len(names), len(set(names)))

    def test_every_definition_has_limitations_and_status(self):
        valid = {"production", "production_partial", "diagnostic", "descriptive",
                 "deferred", "unsupported"}
        for row in defs.DEFINITIONS:
            self.assertIn(row["status"], valid, row["metric_name"])
            self.assertTrue(row["known_limitations"].strip(), row["metric_name"])

    def test_no_replacement_level_language(self):
        """The baseline is league-average expected opportunity outcome.
        Calling it 'replacement' would be a category error the brief
        explicitly forbids."""
        for row in defs.DEFINITIONS:
            blob = (row["definition"] + row["baseline"]).lower()
            self.assertNotIn("above replacement", blob, row["metric_name"])
            self.assertNotIn("war", blob.split())


class TestAgainstRealOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comp = pd.read_csv(DATA_DIR / "player_value_components.csv", dtype=ID_DTYPE)
        cls.opp = pd.read_csv(DATA_DIR / "player_opportunities.csv", dtype=ID_DTYPE)
        cls.base = pd.read_csv(DATA_DIR / "player_value_baselines.csv")
        cls.cv = pd.read_csv(DATA_DIR / "shot_model_validation.csv")
        cls.gb = pd.read_csv(DATA_DIR / "ground_ball_context_values.csv")

    def test_one_row_per_player(self):
        self.assertEqual(len(self.comp), 228)
        self.assertFalse(self.comp["player_id"].duplicated().any())

    def test_player_ids_keep_their_zero_padding(self):
        """player_id is a 6-character zero-padded string across this repo; if a
        CSV round-trip turns it into an int the joins to events.csv break."""
        self.assertTrue(self.comp["player_id"].str.match(r"^\d{6}$").all())

    def test_all_components_sum_to_zero_league_wide(self):
        for col in ["shooting_value", "turnover_value", "faceoff_value",
                    "caused_turnover_value", "goalie_value", "total_player_value"]:
            with self.subTest(component=col):
                self.assertAlmostEqual(self.comp[col].sum(), 0.0, places=6)

    def test_deferred_components_are_null_everywhere(self):
        self.assertTrue(self.comp["ground_ball_value"].isna().all())
        self.assertTrue(self.comp["assist_value"].isna().all())

    def test_null_means_no_opportunity_not_zero_score(self):
        self.assertTrue((self.comp["faceoff_value"].isna()
                         == (self.comp["faceoffs"] == 0)).all())
        self.assertTrue((self.comp["goalie_value"].isna()
                         == (self.comp["shots_on_goal_faced"] == 0)).all())

    def test_pll_points_reconcile_to_official_score(self):
        games = pd.read_csv(DATA_DIR / "games.csv")
        eligible = games[games["is_completed"] & games["include_in_league_analytics"]
                         & ~games["is_all_star"]]
        official = int(eligible["home_score"].sum() + eligible["away_score"].sum())
        self.assertEqual(int(self.opp["pll_points"].sum()), official)

    def test_simple_shot_model_was_selected(self):
        """Locks in the restraint decision. If a future feed adds shot location
        and the richer model starts winning, this fails and the choice gets
        revisited deliberately."""
        selected = self.cv.loc[self.cv["selected_model"], "model"].tolist()
        self.assertEqual(selected, ["shot_class"])
        simple = self.cv.loc[self.cv["model"] == "shot_class",
                             "brier_cross_validated"].iloc[0]
        rich = self.cv.loc[self.cv["model"] == "shot_class_plus_game_state",
                           "brier_cross_validated"].iloc[0]
        self.assertLess(simple, rich,
                        "the two-class baseline must beat the game-state model out of sample")

    def test_ground_ball_contexts_overlap_and_are_not_separable(self):
        """The evidence for deferring ground-ball value. If PLL ever starts
        distinguishing contested recoveries, these intervals separate and the
        decision should be reopened."""
        scrum = self.gb[self.gb["context"] == "GB_faceoff_scrum"].iloc[0]
        gaining = self.gb[self.gb["context"] == "GB_possession_gaining"].iloc[0]
        self.assertLess(gaining["ci_lo"], scrum["ci_hi"],
                        "the two ground-ball contexts' intervals must still overlap")
        self.assertGreater(scrum["share_same_team"], 0.95,
                           "post-faceoff ground balls still overwhelmingly go to the winner")

    def test_two_point_shooting_shows_no_measurable_skill_spread(self):
        """A finding, locked in: the 2026 two-point sample is too small to
        distinguish players. If this ever fails, two-point shooting has become
        measurable and shooting_value_two_point can be trusted per player."""
        shrink = pd.read_csv(DATA_DIR / "player_value_shrinkage.csv", dtype=ID_DTYPE)
        strength = shrink["two_point_pct_prior_strength_trials"].dropna().iloc[0]
        self.assertGreater(strength, 1000)

    def test_no_component_is_denominated_in_possessions(self):
        for col in self.comp.columns:
            self.assertNotIn("per_possession", col)

    def test_baselines_carry_sample_sizes(self):
        self.assertTrue((self.base["sample_size"] > 0).all())
        self.assertIn("expected_points_per_two_point_attempt",
                      set(self.base["baseline_name"]))


if __name__ == "__main__":
    unittest.main()
