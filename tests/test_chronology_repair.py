"""
Phase 11 tests: canonicalizing the Phase 10 faceoff-chronology repair
(`pll_chronology_repair.py`) into the production event-building pipeline.

Two kinds, matching tests/test_phase10.py's established shape:
1. Unit tests on `repair_game_chronology` against constructed single-game
   event frames (the function's actual calling convention in
   pll_build_tables.build_events_table).
2. Integration tests over the real five-season corpus, asserting the
   canonical pipeline reproduces Phase 10's own validated counts exactly:
   199 DIRECT / 57 DIRECT_TIMING / 26 STRONGLY_INFERRED / 9 UNRESOLVED in
   2023, and that 2022/2025/2026 are untouched.

Run with: python3 -m pytest tests/test_chronology_repair.py -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_build_tables as bt                                   # noqa: E402
import pll_chronology_repair as cr                               # noqa: E402


def _ev(rows):
    base = dict(game_id=1, game_slug="G", period=1, team_id="AAA",
                player_id=None, secondary_player_id=None, gb_player_id=None,
                event_type="shot", shot_type="1_PT", shot_outcome="missed",
                is_valid_goal=False, is_duplicate_event=False,
                is_duplicate_faceoff=False, include_in_league_analytics=True,
                home_score_corrected=0, away_score_corrected=0)
    out = []
    for i, r in enumerate(rows):
        d = dict(base)
        d.update(r)
        d["event_number"] = i
        out.append(d)
    return pd.DataFrame(out)


class TestRepairGameChronologyUnit(unittest.TestCase):

    def test_direct_sequence_is_repaired_with_full_provenance(self):
        e = _ev([
            dict(event_id="9000", event_type="faceoff", seconds_passed=260,
                 player_id="000409", gb_player_id="000409", shot_outcome=None),
            dict(event_id="shot-8900", event_type="goal", seconds_passed=260,
                 is_valid_goal=True, shot_outcome="goal"),
            dict(event_id="groundball-9100", event_type="groundball",
                 seconds_passed=266, player_id="000409", shot_outcome=None),
        ])
        out = cr.repair_game_chronology(e)
        # corrected order/timestamp
        self.assertEqual(list(out["event_id"]), ["shot-8900", "9000", "groundball-9100"])
        self.assertEqual(list(out["seconds_passed"]), [260, 266, 266])
        # original values fully recoverable
        raw = out.set_index("event_id")
        self.assertEqual(raw.loc["9000", "event_number_raw"], 0)
        self.assertEqual(raw.loc["9000", "seconds_passed_raw"], 260)
        self.assertEqual(raw.loc["9000", "chronology_evidence_class"], "DIRECT")
        self.assertTrue(raw.loc["9000", "chronology_repair_applied"])
        self.assertEqual(raw.loc["9000", "chronology_repair_rule_version"], cr.RULE_VERSION)
        # The swapped goal also changed event number; its timestamp is unchanged.
        self.assertTrue(raw.loc["shot-8900", "chronology_repair_applied"])
        self.assertEqual(raw.loc["shot-8900", "seconds_passed_raw"],
                         raw.loc["shot-8900", "seconds_passed"])

    def test_strongly_inferred_is_classified_but_never_repaired(self):
        e = _ev([
            dict(event_id="9000", event_type="faceoff", seconds_passed=260,
                 player_id="000409", shot_outcome=None),
            dict(event_id="shot-8900", event_type="goal", seconds_passed=260,
                 is_valid_goal=True, shot_outcome="goal"),
        ])
        out = cr.repair_game_chronology(e)
        row = out[out["event_id"] == "9000"].iloc[0]
        self.assertEqual(row["chronology_evidence_class"], "STRONGLY_INFERRED")
        self.assertFalse(row["chronology_repair_applied"])
        # order unchanged
        self.assertEqual(list(out["event_id"]), ["9000", "shot-8900"])

    def test_a_clean_game_with_no_candidates_is_untouched(self):
        e = _ev([
            dict(event_id="100", event_type="faceoff", seconds_passed=10,
                 player_id="000409", gb_player_id="000409", shot_outcome=None),
            dict(event_id="groundball-200", event_type="groundball",
                 seconds_passed=10, player_id="000409", shot_outcome=None),
            dict(event_id="shot-300", event_type="goal", seconds_passed=40,
                 is_valid_goal=True, shot_outcome="goal"),
        ])
        out = cr.repair_game_chronology(e)
        self.assertEqual(list(out["event_id"]), list(e["event_id"]))
        self.assertEqual(list(out["seconds_passed"]), list(e["seconds_passed"]))
        self.assertEqual(out["chronology_repair_applied"].sum(), 0)
        self.assertTrue(out["chronology_evidence_class"].isna().all())

    def test_no_two_events_ever_end_up_with_the_same_event_number(self):
        """A transpose is a pure swap of two existing values -- it must never
        collide, no matter how many DIRECT candidates a game has."""
        rows = []
        for k in range(5):
            base_t = 260 + 100 * k
            rows.append(dict(event_id=f"9000{k}", event_type="faceoff",
                             seconds_passed=base_t, player_id="000409",
                             gb_player_id="000409", shot_outcome=None))
            rows.append(dict(event_id=f"shot-8900{k}", event_type="goal",
                             seconds_passed=base_t, is_valid_goal=True,
                             shot_outcome="goal"))
            rows.append(dict(event_id=f"groundball-9100{k}", event_type="groundball",
                             seconds_passed=base_t + 6, player_id="000409",
                             shot_outcome=None))
        e = _ev(rows)
        out = cr.repair_game_chronology(e)
        self.assertEqual(out["event_number"].nunique(), len(out))
        self.assertEqual(out["chronology_repair_applied"].sum(), 10)


class TestChronologyRepairIntegration(unittest.TestCase):
    """Reproduces Phase 10's own validated per-season evidence counts exactly,
    run through the production pipeline (pll_build_tables.build_events_table),
    not through pll_phase10_possession_repair.py directly."""

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

    def test_2023_reproduces_phase10_exactly(self):
        vc = self.by_year[2023]["chronology_evidence_class"].value_counts().to_dict()
        self.assertEqual(vc.get("DIRECT"), 199)
        self.assertEqual(vc.get("DIRECT_TIMING"), 57)
        self.assertEqual(vc.get("STRONGLY_INFERRED"), 26)
        self.assertEqual(vc.get("UNRESOLVED"), 9)
        self.assertEqual(vc.get("DUPLICATE_FACEOFF_EVENT"), None)
        self.assertEqual(self.by_year[2023]["chronology_repair_applied"].sum(), 455)

    def test_2022_2025_2026_are_byte_identical_by_construction(self):
        for year in (2022, 2025, 2026):
            applied = self.by_year[year]["chronology_repair_applied"].sum()
            self.assertEqual(applied, 0, f"{year} should have zero repairs applied")

    def test_2024_duplicate_count_is_36_across_exactly_3_games(self):
        ev = self.by_year[2024]
        dup = ev[ev["chronology_evidence_class"] == "DUPLICATE_FACEOFF_EVENT"]
        self.assertEqual(len(dup), 36)
        self.assertEqual(sorted(dup["game_slug"].unique()),
                         ["2024_game_10", "2024_game_12", "2024_game_31"])


if __name__ == "__main__":
    unittest.main()
