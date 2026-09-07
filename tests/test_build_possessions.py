"""
Phase 4.25 regression tests for scripts/pll_build_possessions.py.

Covers the new faceoff-violation/redraw rule: two faceoff events back to
back (same period, zero intervening events) close the first, empty
possession cleanly (end_reason='faceoff_violation_redraw', is_ambiguous=
False) instead of flagging it 'ambiguous_control_change'. See
POSSESSION_METHODOLOGY.md "Faceoff redraw handling" and
FULL_SEASON_ANOMALIES.md for the evidence (2026-ev-28 faceoff-3018500/
faceoff-3019000, 2026-ev-42 faceoff-100/faceoff-400 — the only 2
occurrences in the full 2026 season).

Run with: python3 -m unittest tests.test_build_possessions -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_build_possessions as bp  # noqa: E402

HOME, AWAY = "HOME", "AWAY"

BASE = {
    "event_id": None, "shot_type": None, "shot_outcome": None, "is_valid_goal": None,
    "is_two_point_attempt": None, "is_man_up_shot": None,
}


def ev(event_number, event_type, team_id, seconds_passed, period=1, **overrides):
    r = dict(BASE)
    r.update({
        "event_number": event_number, "event_type": event_type, "team_id": team_id,
        "period": period, "seconds_passed": seconds_passed, "event_id": overrides.pop("event_id", f"{event_type}-{event_number}"),
    })
    r.update(overrides)
    return r


class TestFaceoffRedraw(unittest.TestCase):
    def _run(self, rows):
        df = pd.DataFrame(rows)
        return bp.build_possessions_for_game("g1", "2026-ev-test", HOME, AWAY, df)

    def test_ev42_style_back_to_back_faceoffs_resolve_cleanly(self):
        # Mirrors 2026-ev-42 faceoff-100 (HOME wins) -> faceoff-400 (AWAY
        # wins, GB) -> goal, with zero events between the two faceoffs.
        rows = [
            ev(1, "faceoff", HOME, 6),
            ev(2, "faceoff", AWAY, 20),
            ev(3, "goal", AWAY, 41, shot_outcome="goal", is_valid_goal=True, shot_type="1_PT"),
        ]
        poss = self._run(rows)
        first = poss[0]
        self.assertEqual(first["end_reason"], "faceoff_violation_redraw")
        self.assertFalse(first["is_ambiguous"])
        self.assertEqual(first["offense_team_id"], HOME)
        second = poss[1]
        self.assertEqual(second["start_reason"], "faceoff_win")
        self.assertFalse(second["is_ambiguous"])
        self.assertEqual(second["offense_team_id"], AWAY)

    def test_false_positive_guard_groundball_then_faceoff_stays_ambiguous(self):
        # Plausible false positive: a team demonstrably RECOVERS the ball
        # (a groundball event, real evidence of possession) and is
        # immediately followed by a faceoff with nothing else logged. This
        # is NOT the same evidence as two consecutive faceoffs (the ball
        # was actually gained here, unlike a pure redraw) and must still be
        # flagged ambiguous, not silently resolved.
        rows = [
            ev(1, "groundball", HOME, 1135),
            ev(2, "faceoff", AWAY, 1173),
            ev(3, "groundball", AWAY, 1173),
        ]
        poss = self._run(rows)
        first = poss[0]
        self.assertEqual(first["end_reason"], "ambiguous_control_change")
        self.assertTrue(first["is_ambiguous"])

    def test_false_positive_guard_faceoff_with_a_shot_in_between_is_not_a_redraw(self):
        # A faceoff-started possession that DID see a real play (a shot)
        # before the next faceoff must not be treated as an empty redraw.
        rows = [
            ev(1, "faceoff", HOME, 6),
            ev(2, "shot", HOME, 15, shot_outcome="missed", shot_type="1_PT"),
            ev(3, "faceoff", AWAY, 40),
        ]
        poss = self._run(rows)
        first = poss[0]
        self.assertEqual(first["end_reason"], "ambiguous_control_change")
        self.assertTrue(first["is_ambiguous"])


if __name__ == "__main__":
    unittest.main()
