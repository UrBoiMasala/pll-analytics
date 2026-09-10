"""
Phase 11 tests: the in-stream duplicate-faceoff fix (`pll_duplicate_faceoff.py`)
and the underlying classification-rule correction in
`pll_phase10_possession_repair.detect_faceoff_order_defects`.

Phase 10's original `duplicate_copy` rule required first locating the
faceoff's companion ground ball (`gb_j`) and then looking for a matching
faceoff between the goal and that ground ball. That missed any duplicate
whose draw carries no ground-ball tag on either copy (3 real 2024 cases),
because `gb_j` was never found. The Phase 11 fix checks the position
immediately after the goal directly, with FULL content identity including
`gb_player_id` (so two genuinely different faceoffs between the same two
players, minutes or seconds apart, are never conflated -- see the false
positive regression test below, found and rejected during Phase 11
development on real 2023 data before this rule was finalized).

Run with: python3 -m pytest tests/test_duplicate_faceoff.py -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROC = REPO_ROOT / "data" / "processed"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_build_tables as bt                      # noqa: E402
import pll_duplicate_faceoff as df_mod              # noqa: E402
import pll_phase10_possession_repair as pr          # noqa: E402


def _ev(rows):
    base = dict(game_id=1, game_slug="G", period=1, team_id="AAA",
                player_id=None, secondary_player_id=None, gb_player_id=None,
                event_type="shot", shot_type="1_PT", shot_outcome="missed",
                is_valid_goal=False, is_duplicate_event=False,
                is_duplicate_faceoff=False, home_score_corrected=0,
                away_score_corrected=0)
    out = []
    for i, r in enumerate(rows):
        d = dict(base)
        d.update(r)
        d["event_number"] = i
        out.append(d)
    return pd.DataFrame(out)


class TestDuplicateFaceoffUnit(unittest.TestCase):

    def test_classic_duplicate_with_a_shared_ground_ball_tag_is_flagged(self):
        """The real 2024_game_10 shape (33 of the 36 confirmed pairs)."""
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
        out = df_mod.flag_duplicate_faceoffs(e)
        flagged = out[out["event_id"] == "1000"].iloc[0]
        self.assertTrue(flagged["is_duplicate_event"])
        self.assertTrue(flagged["is_duplicate_faceoff"])
        self.assertEqual(flagged["duplicate_faceoff_pair_id"], "1100")
        # the real copy is never flagged, and no row is dropped
        real = out[out["event_id"] == "1100"].iloc[0]
        self.assertFalse(real["is_duplicate_faceoff"])
        self.assertEqual(len(out), len(e))

    def test_duplicate_with_no_ground_ball_tag_on_either_copy_is_still_caught(self):
        """The 3 real 2024 pairs Phase 10's original window-bounded search
        missed: no gb_player_id anywhere, but the two faceoffs otherwise
        share every field and sit in the classic goal-sandwiched shape."""
        e = _ev([
            dict(event_id="faceoff-1008600", event_type="faceoff",
                 seconds_passed=997, player_id="003004",
                 secondary_player_id="003018", shot_outcome=None),
            dict(event_id="shot-1008500", event_type="goal",
                 seconds_passed=997, is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="1008600", event_type="faceoff",
                 seconds_passed=1008, player_id="003004",
                 secondary_player_id="003018", shot_outcome=None),
            dict(event_id="shot-1009300", event_type="shot",
                 seconds_passed=1031, shot_outcome="missed"),
        ])
        out = df_mod.flag_duplicate_faceoffs(e)
        flagged = out[out["event_id"] == "faceoff-1008600"].iloc[0]
        self.assertTrue(flagged["is_duplicate_faceoff"])
        self.assertEqual(flagged["duplicate_faceoff_pair_id"], "1008600")

    def test_two_distinct_real_faceoffs_between_the_same_two_players_are_not_flagged(self):
        """FALSE POSITIVE REGRESSION -- found on real data
        (playoffs-quarterfinal-3-2023-9-1) during Phase 11 development. Same
        two players face off twice, 10 seconds apart, for two DIFFERENT goals
        -- each independently evidenced by its own companion ground ball.
        This is ordinary lacrosse (a FOGO matchup repeating), not a duplicate,
        and must never be flagged."""
        e = _ev([
            dict(event_id="18900", event_type="faceoff", seconds_passed=697,
                 player_id="001812", secondary_player_id="003018",
                 gb_player_id=None, shot_outcome=None),
            dict(event_id="shot-18800", event_type="goal", seconds_passed=697,
                 is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="19400", event_type="faceoff", seconds_passed=707,
                 player_id="001812", secondary_player_id="003018",
                 gb_player_id="001812", shot_outcome=None),
            dict(event_id="shot-19300", event_type="goal", seconds_passed=707,
                 is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="groundball-19500", event_type="groundball",
                 seconds_passed=709, player_id="001812", shot_outcome=None),
        ])
        out = df_mod.flag_duplicate_faceoffs(e)
        self.assertFalse(out["is_duplicate_faceoff"].any(),
                         "two independently-evidenced real faceoffs were "
                         "incorrectly flagged as duplicates of each other")
        # and the classifier still correctly resolves each on its own merits
        det = pr.detect_faceoff_order_defects(e)
        classes = dict(zip(det["faceoff_event_id"], det["evidence_class"]))
        self.assertEqual(classes.get("19400"), "DIRECT")

    def test_never_drops_a_row(self):
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
        out = df_mod.flag_duplicate_faceoffs(e)
        self.assertEqual(set(out["event_id"]), set(e["event_id"]))


class TestDuplicateFaceoffIntegration(unittest.TestCase):
    """Real corpus, run through the production pipeline end to end."""

    @classmethod
    def setUpClass(cls):
        cls.by_year = {}
        for year in (2022, 2023, 2024, 2025, 2026):
            bt.set_season(year)
            all_games_df = bt.build_games_table()
            completed = all_games_df.loc[all_games_df["is_completed"]]
            usable = [s for s in completed["game_slug"].tolist()
                     if not bt.missing_raw_endpoints(s)]
            games_df = all_games_df[all_games_df["game_slug"].isin(usable)].reset_index(drop=True)
            events, _ = bt.build_events_table(usable, games_df)
            cls.by_year[year] = events

    def test_confirmed_2024_duplicates_are_excluded_from_analysis(self):
        ev = self.by_year[2024]
        dup = ev[ev["chronology_evidence_class"] == "DUPLICATE_FACEOFF_EVENT"]
        self.assertEqual(len(dup), 36)
        eligible = (ev["include_in_league_analytics"].fillna(False)
                   & ~ev["is_duplicate_event"].fillna(False))
        # every phantom copy is excluded, but nothing else about that game's
        # eligibility collapses
        self.assertFalse(eligible[dup.index].any())

    def test_no_duplicates_found_outside_2024(self):
        for year in (2022, 2023, 2025, 2026):
            dup = self.by_year[year][
                self.by_year[year]["chronology_evidence_class"] == "DUPLICATE_FACEOFF_EVENT"]
            self.assertEqual(len(dup), 0, f"unexpected duplicate faceoffs found in {year}")

    def test_legitimate_repeat_faceoffs_are_not_swept_up_anywhere(self):
        """Every event flagged is_duplicate_faceoff must have a real pair
        partner recorded, and that partner must itself never be flagged --
        i.e. de-duplication is asymmetric and traceable, never a blanket
        content-match sweep."""
        for year, ev in self.by_year.items():
            dup = ev[ev["is_duplicate_faceoff"] == True]  # noqa: E712
            if len(dup) == 0:
                continue
            pair_ids = set(dup["duplicate_faceoff_pair_id"].dropna())
            partners = ev[ev["event_id"].isin(pair_ids)]
            self.assertFalse(partners["is_duplicate_faceoff"].any(),
                             f"{year}: a duplicate's paired partner was itself flagged")


if __name__ == "__main__":
    unittest.main()
