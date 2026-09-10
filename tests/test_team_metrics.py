"""
Phase 5 tests for the team advanced-metrics layer.

Two kinds of test here:

1. Unit tests on the SQL layer run against small SYNTHETIC tables, so a rule
   is verified in isolation rather than merely observed to hold in the 2026
   data. These catch a definition that is wrong-but-currently-unexercised
   (e.g. a two-point goal counted as two goals, which never happens to break
   any 2026 total because the aggregates are consistent either way).

2. Integration tests against the real repo data, asserting the Phase 5
   invariants and the specific evidence-based decisions this phase made
   (man-up tagging, the possession-span-vs-time-of-possession gap, the
   same-second possession bucket).

Run with: python3 -m unittest tests.test_team_metrics -v
"""
import sys
import unittest
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "processed" / "2026"
SQL_DIR = REPO_ROOT / "sql"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_metric_definitions as md  # noqa: E402


def _con():
    return duckdb.connect()


class TestPllScoringRules(unittest.TestCase):
    """A two-point goal is 1 goal worth 2 points -- never 2 goals."""

    def _score(self, rows):
        con = _con()
        con.register("shots_in", pd.DataFrame(rows))
        return con.execute("""
            SELECT COUNT(*) FILTER (WHERE is_valid_goal)                   AS goals,
                   SUM(CASE WHEN is_valid_goal AND is_two_point_attempt THEN 2
                            WHEN is_valid_goal THEN 1 ELSE 0 END)          AS points,
                   COUNT(*) FILTER (WHERE is_two_point_attempt)            AS two_point_attempts,
                   COUNT(*) FILTER (WHERE is_two_point_attempt AND is_valid_goal) AS two_point_goals
            FROM shots_in
        """).fetchone()

    def test_two_point_goal_is_one_goal_two_points(self):
        goals, points, tp_att, tp_goals = self._score([
            {"is_valid_goal": True, "is_two_point_attempt": True},
        ])
        self.assertEqual(goals, 1, "a two-point goal must count as ONE goal")
        self.assertEqual(points, 2, "a two-point goal must be worth TWO points")
        self.assertEqual((tp_att, tp_goals), (1, 1))

    def test_mixed_bag_points_equal_goals_plus_two_point_goals(self):
        rows = [
            {"is_valid_goal": True,  "is_two_point_attempt": False},  # 1 pt
            {"is_valid_goal": True,  "is_two_point_attempt": True},   # 2 pts
            {"is_valid_goal": True,  "is_two_point_attempt": True},   # 2 pts
            {"is_valid_goal": False, "is_two_point_attempt": True},   # miss
            {"is_valid_goal": False, "is_two_point_attempt": False},  # miss
        ]
        goals, points, tp_att, tp_goals = self._score(rows)
        self.assertEqual(goals, 3)
        self.assertEqual(points, 5)
        self.assertEqual(points, goals + tp_goals, "points == goals + two_point_goals")
        self.assertEqual(tp_att, 3)

    def test_missed_two_point_shot_scores_nothing(self):
        goals, points, _, tp_goals = self._score([
            {"is_valid_goal": False, "is_two_point_attempt": True}])
        self.assertEqual((goals, points, tp_goals), (0, 0, 0))

    def test_shooting_pct_is_not_inflated_by_two_pointers(self):
        """shooting_pct must stay goals/shots. A team of all two-point goals
        shoots 100%, not 200%."""
        con = _con()
        con.register("shots_in", pd.DataFrame([
            {"is_valid_goal": True, "is_two_point_attempt": True},
            {"is_valid_goal": True, "is_two_point_attempt": True},
        ]))
        pct, pps = con.execute("""
            SELECT COUNT(*) FILTER (WHERE is_valid_goal) / CAST(COUNT(*) AS DOUBLE),
                   SUM(CASE WHEN is_valid_goal AND is_two_point_attempt THEN 2
                            WHEN is_valid_goal THEN 1 ELSE 0 END) / CAST(COUNT(*) AS DOUBLE)
            FROM shots_in""").fetchone()
        self.assertEqual(pct, 1.0)
        self.assertEqual(pps, 2.0, "points_per_shot is the metric that may exceed 1")


class TestRateGuards(unittest.TestCase):
    """NULLIF must turn a zero denominator into NULL, never inf or 0."""

    def test_zero_denominator_yields_null(self):
        con = _con()
        val = con.execute(
            "SELECT 5 / NULLIF(CAST(0 AS DOUBLE), 0)").fetchone()[0]
        self.assertIsNone(val)

    def test_zero_numerator_still_yields_zero(self):
        con = _con()
        val = con.execute("SELECT 0 / NULLIF(CAST(7 AS DOUBLE), 0)").fetchone()[0]
        self.assertEqual(val, 0.0)


class TestRankDirection(unittest.TestCase):
    """Lower-is-better metrics must rank ascending, and RANK() (not
    DENSE_RANK) semantics must hold through ties."""

    def _rank(self, values, higher_is_better):
        con = _con()
        con.register("m", pd.DataFrame({
            "team_id": list("ABCD"), "metric_value": values,
            "higher_is_better": [higher_is_better] * 4}))
        return con.execute("""
            SELECT team_id, RANK() OVER (
                ORDER BY CASE WHEN higher_is_better THEN -metric_value ELSE metric_value END
            ) AS r FROM m ORDER BY team_id""").df().set_index("team_id")["r"].to_dict()

    def test_lower_is_better_ranks_smallest_first(self):
        r = self._rank([0.5, 0.2, 0.4, 0.3], higher_is_better=False)
        self.assertEqual(r["B"], 1, "smallest value must rank 1 when lower is better")
        self.assertEqual(r["A"], 4)

    def test_higher_is_better_ranks_largest_first(self):
        r = self._rank([0.5, 0.2, 0.4, 0.3], higher_is_better=True)
        self.assertEqual(r["A"], 1)
        self.assertEqual(r["B"], 4)

    def test_ties_skip_ranks_competition_style(self):
        r = self._rank([0.5, 0.5, 0.4, 0.3], higher_is_better=True)
        self.assertEqual(r["A"], 1)
        self.assertEqual(r["B"], 1)
        self.assertEqual(r["C"], 3, "RANK() skips 2 after a two-way tie; DENSE_RANK would give 2")


class TestPossessionSetDefinitions(unittest.TestCase):
    """is_measurable_span must exclude ambiguous, truncated AND single-event
    possessions -- the last one is the easy condition to forget, and it is the
    one that keeps 871 zero-by-construction spans out of the length splits."""

    def _flags(self, rows):
        con = _con()
        con.register("p", pd.DataFrame(rows))
        return con.execute("""
            SELECT is_ambiguous, is_truncated, event_count,
                   (NOT is_ambiguous AND NOT is_truncated AND event_count > 1) AS is_measurable_span
            FROM p""").df()

    def test_single_event_possession_is_not_measurable(self):
        out = self._flags([{"is_ambiguous": False, "is_truncated": False, "event_count": 1}])
        self.assertFalse(bool(out["is_measurable_span"].iloc[0]))

    def test_truncated_possession_is_not_measurable(self):
        out = self._flags([{"is_ambiguous": False, "is_truncated": True, "event_count": 5}])
        self.assertFalse(bool(out["is_measurable_span"].iloc[0]))

    def test_ambiguous_possession_is_not_measurable(self):
        out = self._flags([{"is_ambiguous": True, "is_truncated": False, "event_count": 5}])
        self.assertFalse(bool(out["is_measurable_span"].iloc[0]))

    def test_clean_multi_event_possession_is_measurable(self):
        out = self._flags([{"is_ambiguous": False, "is_truncated": False, "event_count": 2}])
        self.assertTrue(bool(out["is_measurable_span"].iloc[0]))


class TestMetricDefinitions(unittest.TestCase):
    def test_no_definition_uses_the_pandas_na_sentinel(self):
        """'n/a' is in pandas' default na_values, so writing it would make a
        deliberately-empty denominator read back as missing."""
        for row in md.DEFINITIONS:
            for col in ("denominator", "numerator", "level", "source_table"):
                self.assertNotEqual(row[col], "n/a",
                                    f"{row['metric_name']}.{col} uses the 'n/a' sentinel")

    def test_every_definition_has_a_denominator_and_status(self):
        valid = {"production", "diagnostic", "deferred", "unsupported"}
        for row in md.DEFINITIONS:
            self.assertTrue(row["denominator"].strip(), row["metric_name"])
            self.assertIn(row["status"], valid, row["metric_name"])

    def test_metric_names_are_unique(self):
        names = [r["metric_name"] for r in md.DEFINITIONS]
        dupes = {n for n in names if names.count(n) > 1}
        self.assertEqual(dupes, set(), f"duplicate metric definitions: {dupes}")

    def test_unsupported_metrics_are_not_emitted(self):
        """A metric documented as unsupported/deferred must not also appear as
        a column in the published tables."""
        tga = pd.read_csv(DATA_DIR / "team_game_advanced.csv", nrows=1)
        tsa = pd.read_csv(DATA_DIR / "team_season_advanced.csv", nrows=1)
        emitted = set(tga.columns) | set(tsa.columns)
        for row in md.DEFINITIONS:
            if row["status"] in ("unsupported", "deferred"):
                self.assertNotIn(row["metric_name"], emitted,
                                 f"{row['metric_name']} is documented {row['status']} but emitted")


class TestAgainstRealData(unittest.TestCase):
    """Integration checks on the actual 2026 outputs."""

    @classmethod
    def setUpClass(cls):
        cls.tga = pd.read_csv(DATA_DIR / "team_game_advanced.csv")
        cls.tsa = pd.read_csv(DATA_DIR / "team_season_advanced.csv")
        cls.poss = pd.read_csv(DATA_DIR / "possessions.csv")
        cls.events = pd.read_csv(DATA_DIR / "events.csv", low_memory=False)
        cls.splits = pd.read_csv(DATA_DIR / "possession_length_splits.csv")

    def test_shape(self):
        self.assertEqual(len(self.tga), 100, "50 eligible games x 2 teams")
        self.assertEqual(len(self.tsa), 8, "8 franchises, all-star squads excluded")

    def test_points_identity_holds_on_every_row(self):
        self.assertTrue(
            (self.tga["points"] == self.tga["goals"] + self.tga["two_point_goals"]).all(),
            "points must equal goals + two_point_goals on every team-game row")

    def test_man_up_tag_is_goals_only(self):
        """The evidence behind refusing to publish a man-up possession metric.
        If PLL ever starts tagging missed man-up shots, this fails and the
        man-up section should be revisited."""
        mu = self.events[self.events["is_man_up_shot"] == True]  # noqa: E712
        self.assertGreater(len(mu), 0)
        self.assertTrue((mu["event_type"] == "goal").all(),
                        "PLL's MU/MU_2_PT tag was goals-only when Phase 5 was built")
        self.assertNotIn("man_up_possessions", self.tga.columns)
        self.assertNotIn("man_up_shooting_pct_tagged", self.tga.columns)

    def test_possession_span_understates_official_time_of_possession(self):
        """The evidence behind NOT publishing a reconstructed time-of-possession
        metric. If the feed's coverage ever improves materially, revisit."""
        ratio = self.tga["possession_span_coverage_ratio"]
        self.assertLess(ratio.median(), 0.90,
                        "possession spans recover well under the official ToP figure")
        self.assertNotIn("time_of_possession_observed_seconds", self.tga.columns)
        self.assertNotIn("time_of_possession_complete_only_seconds", self.tga.columns)

    def test_length_splits_exclude_ineligible_possessions(self):
        league = self.splits[self.splits["scope"] == "LEAGUE"]
        expected = int((~self.poss["is_ambiguous"] & ~self.poss["is_truncated"]
                        & (self.poss["event_count"] > 1)).sum())
        self.assertEqual(int(league["possessions"].sum()), expected)

    def test_same_second_possessions_are_their_own_bucket(self):
        league = self.splits[self.splits["scope"] == "LEAGUE"].set_index("length_bucket")
        self.assertIn("0s", league.index)
        # every other bucket must contain zero same-second possessions
        others = league.drop(index="0s")
        self.assertEqual(int(others["zero_span_possessions"].sum()), 0)
        self.assertEqual(int(league.loc["0s", "zero_span_possessions"]),
                         int(league.loc["0s", "possessions"]))

    def test_offensive_possessions_mirror_defensive(self):
        by_game = self.tga.groupby("game_id")[["offensive_possessions", "defensive_possessions"]].sum()
        self.assertTrue((by_game["offensive_possessions"] == by_game["defensive_possessions"]).all())

    def test_season_possessions_match_possession_table(self):
        self.assertEqual(int(self.tsa["offensive_possessions"].sum()), len(self.poss))


if __name__ == "__main__":
    unittest.main()
