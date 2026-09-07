"""
Phase 4.25 regression tests for scripts/pll_pbp_clean.py.

Covers:
  - the confirmed mislabeled-goal/real-saved-shot case (2026-ev-1) staying
    correctly classified (is_valid_goal=False, shot_outcome='saved')
  - locking in the Phase 4.25 investigation's rejection of a wider
    groundball-duplicate timing window (see FULL_SEASON_ANOMALIES.md §7):
    a same-player groundball pair a few seconds apart must NOT be flagged
    as a duplicate, because that pattern was shown to also occur between
    genuinely distinct, officially-counted ground balls (2026-ev-4/-8/-12/
    -21/-22).

Run with: python3 -m unittest tests.test_pbp_clean -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_pbp_clean as clean_mod  # noqa: E402


BASE_ROW = {
    "game_id": "g1", "event_id": None, "event_number": 0, "period": 1,
    "clock": "00:00", "seconds_passed": 0, "team_id": None, "team": None,
    "player_id": None, "player": None, "secondary_player_id": None, "secondary_player": None,
    "event_type": None, "shot_type": None, "description": "", "home_score_raw": 0, "away_score_raw": 0,
    "gb_player_id": None, "goalie_id": None, "goalie": None, "shot_on_goal": None, "shot_saved": None,
    "save_type": None, "penalty_length_sec": None, "penalty_description": None,
    "away_win_prob": None, "home_win_prob": None,
}


def row(**overrides):
    r = dict(BASE_ROW)
    r.update(overrides)
    return r


def make_df(rows):
    for i, r in enumerate(rows):
        r.setdefault("event_number", i)
    return pd.DataFrame(rows)


class TestMislabeledGoalIsRealSave(unittest.TestCase):
    def test_ev1_style_mislabeled_goal_is_reclassified_as_saved_shot(self):
        df = make_df([
            row(event_type="pregame", home_score_raw=0, away_score_raw=0),
            row(event_type="goal", team_id="ARC", shot_type="1_PT", description="",
                home_score_raw=5, away_score_raw=9,  # unchanged from pregame -> no real score delta
                shot_on_goal=True, shot_saved=True, event_id="shot-3004600"),
            row(event_type="gameEnd", home_score_raw=5, away_score_raw=9),
        ])
        out = clean_mod.clean(df)
        bad = out[out["event_id"] == "shot-3004600"].iloc[0]
        self.assertFalse(bad["is_valid_goal"])
        self.assertEqual(bad["shot_outcome"], "saved")
        self.assertIn("shot_saved_true", bad["goal_invalid_reason"])
        self.assertIn("empty_description", bad["goal_invalid_reason"])

    def test_a_real_goal_with_matching_delta_and_description_is_valid(self):
        df = make_df([
            row(event_type="pregame", home_score_raw=0, away_score_raw=0),
            row(event_type="goal", team_id="ARC", shot_type="1_PT", description="GOAL by X.",
                home_score_raw=0, away_score_raw=1, shot_on_goal=True, shot_saved=False,
                event_id="goal-1"),
            row(event_type="gameEnd", home_score_raw=0, away_score_raw=1),
        ])
        out = clean_mod.clean(df)
        good = out[out["event_id"] == "goal-1"].iloc[0]
        self.assertTrue(good["is_valid_goal"])
        self.assertEqual(good["shot_outcome"], "goal")


class TestGroundballDedupWindowStaysStrict(unittest.TestCase):
    """
    Phase 4.25 tested widening the 1-second groundball dedup window to 5s
    (still requiring same player/team/period and zero intervening events)
    and found it would falsely flag ground balls in games where the
    official box score counts both as real, distinct events. This test
    locks in that the window was NOT widened.
    """

    def _adjacent_groundball_pair(self, gap_seconds):
        return make_df([
            row(event_type="groundball", team_id="CAN", description="Groundball picked up by C. Mackesy.",
                seconds_passed=1533, period=3, event_id="groundball-2002500"),
            row(event_type="groundball", team_id="CAN", description="Groundball picked up by C. Mackesy.",
                seconds_passed=1533 + gap_seconds, period=3, event_id="groundball-2002600"),
        ])

    def test_one_second_gap_is_still_flagged_as_duplicate(self):
        out = clean_mod.clean(self._adjacent_groundball_pair(1))
        self.assertTrue(bool(out.iloc[1]["is_duplicate_event"]))

    def test_four_second_gap_is_the_motivating_ev42_case_but_not_flagged(self):
        # This is literally the 2026-ev-42 groundball-2002500/-2002600 pair
        # from the Phase 4.25 investigation (FULL_SEASON_ANOMALIES.md §7).
        out = clean_mod.clean(self._adjacent_groundball_pair(4))
        self.assertFalse(bool(out.iloc[1]["is_duplicate_event"]))

    def test_false_positive_guard_two_distinct_recoveries_are_not_flagged(self):
        # Plausible false positive: same player legitimately recovers two
        # separate ground balls a few seconds apart later in a scramble.
        # Must not be treated as a duplicate at the current (1s) threshold.
        out = clean_mod.clean(self._adjacent_groundball_pair(3))
        self.assertFalse(bool(out.iloc[1]["is_duplicate_event"]))


if __name__ == "__main__":
    unittest.main()
