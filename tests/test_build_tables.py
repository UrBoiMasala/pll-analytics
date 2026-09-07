"""
Phase 4.25 regression tests for scripts/pll_build_tables.py: participant
filtering on team_game_stats, and metric-specific eligibility for the
mislabeled-goal/real-saved-shot case.

Run with: python3 -m unittest tests.test_build_tables -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_build_tables as bt  # noqa: E402


def games_df_for(slugs_and_teams):
    rows = []
    for i, (slug, home, away) in enumerate(slugs_and_teams):
        rows.append({"game_id": i, "game_slug": slug, "home_team_id": home, "away_team_id": away})
    return pd.DataFrame(rows)


class TestTeamGameStatsParticipantFiltering(unittest.TestCase):
    def test_phantom_non_participant_row_is_rejected_with_reason(self):
        games_df = games_df_for([("g1", "WAT", "ATL")])

        def fake_load_raw(slug):
            return {"teams_stats": {"data": {"items": [
                {"officialId": "WAT", "goals": 16},
                {"officialId": "ATL", "goals": 9},
                {"officialId": "WHP", "goals": 0},  # phantom, didn't play
            ]}}}

        orig = bt.load_raw
        bt.load_raw = fake_load_raw
        try:
            tgs, exceptions = bt.build_team_game_stats(["g1"], games_df)
        finally:
            bt.load_raw = orig

        self.assertEqual(sorted(tgs["officialId"]), ["ATL", "WAT"])
        self.assertEqual(len(exceptions), 1)
        self.assertEqual(exceptions.iloc[0]["officialId"], "WHP")
        self.assertIn("not a participant", exceptions.iloc[0]["rejection_reason"])

    def test_duplicate_participant_row_is_rejected_not_double_counted(self):
        games_df = games_df_for([("g1", "WAT", "ATL")])

        def fake_load_raw(slug):
            return {"teams_stats": {"data": {"items": [
                {"officialId": "WAT", "goals": 16},
                {"officialId": "WAT", "goals": 16},  # exact duplicate
                {"officialId": "ATL", "goals": 9},
            ]}}}

        orig = bt.load_raw
        bt.load_raw = fake_load_raw
        try:
            tgs, exceptions = bt.build_team_game_stats(["g1"], games_df)
        finally:
            bt.load_raw = orig

        self.assertEqual(len(tgs), 2)
        self.assertEqual(len(exceptions), 1)
        self.assertIn("duplicate", exceptions.iloc[0]["rejection_reason"])

    def test_missing_participant_row_is_recorded_as_exception(self):
        games_df = games_df_for([("g1", "WAT", "ATL")])

        def fake_load_raw(slug):
            return {"teams_stats": {"data": {"items": [
                {"officialId": "WAT", "goals": 16},
            ]}}}  # ATL never showed up

        orig = bt.load_raw
        bt.load_raw = fake_load_raw
        try:
            tgs, exceptions = bt.build_team_game_stats(["g1"], games_df)
        finally:
            bt.load_raw = orig

        self.assertEqual(len(tgs), 1)
        self.assertEqual(len(exceptions), 1)
        self.assertIn("NO teams_stats row", exceptions.iloc[0]["rejection_reason"])

    def test_validate_team_game_stats_flags_wrong_participant_count(self):
        games_df = games_df_for([("g1", "WAT", "ATL"), ("g2", "WHP", "ARC")])
        tgs = pd.DataFrame([
            {"game_id": 0, "game_slug": "g1", "officialId": "WAT"},
            {"game_id": 0, "game_slug": "g1", "officialId": "ATL"},
            {"game_id": 1, "game_slug": "g2", "officialId": "WHP"},  # g2 missing ARC
        ])
        problems = bt.validate_team_game_stats(tgs, games_df)
        self.assertTrue(any("g2" in p for p in problems))

    def test_validate_team_game_stats_passes_on_clean_input(self):
        games_df = games_df_for([("g1", "WAT", "ATL")])
        tgs = pd.DataFrame([
            {"game_id": 0, "game_slug": "g1", "officialId": "WAT"},
            {"game_id": 0, "game_slug": "g1", "officialId": "ATL"},
        ])
        self.assertEqual(bt.validate_team_game_stats(tgs, games_df), [])


class TestGoalEventEligibility(unittest.TestCase):
    """
    Motivating case: 2026-ev-1's mislabeled 'goal' (really a saved shot)
    must stay analysis-eligible so shot/save metrics don't silently lose
    it. False-positive guard: an invalid PENALTY (which has no salvageable
    shot_outcome-style data) must still be excluded, and a hypothetical
    invalid goal with no resolvable shot_outcome at all must also still be
    excluded.
    """

    def _eligibility(self, df):
        invalid_goal_with_no_shot_data = (
            (df["event_type"] == "goal") & (df["is_valid_goal"] == False) & df["shot_outcome"].isna()  # noqa: E712
        )
        invalid_penalty = df["is_valid_penalty"] == False  # noqa: E712
        known_invalid = invalid_goal_with_no_shot_data | invalid_penalty
        return (
            df["include_in_league_analytics"].fillna(False)
            & ~df["is_duplicate_event"].fillna(False)
            & ~known_invalid.fillna(False)
        )

    def test_mislabeled_goal_with_shot_outcome_stays_eligible(self):
        df = pd.DataFrame([{
            "event_type": "goal", "is_valid_goal": False, "shot_outcome": "saved",
            "is_valid_penalty": None, "is_duplicate_event": False, "include_in_league_analytics": True,
        }])
        self.assertTrue(self._eligibility(df).iloc[0])

    def test_invalid_goal_with_no_shot_outcome_is_still_excluded(self):
        # False-positive guard: broadening eligibility must not accidentally
        # let through an invalid goal that carries no usable data at all.
        df = pd.DataFrame([{
            "event_type": "goal", "is_valid_goal": False, "shot_outcome": None,
            "is_valid_penalty": None, "is_duplicate_event": False, "include_in_league_analytics": True,
        }])
        self.assertFalse(self._eligibility(df).iloc[0])

    def test_invalid_penalty_is_still_excluded(self):
        df = pd.DataFrame([{
            "event_type": "penalty", "is_valid_goal": None, "shot_outcome": None,
            "is_valid_penalty": False, "is_duplicate_event": False, "include_in_league_analytics": True,
        }])
        self.assertFalse(self._eligibility(df).iloc[0])

    def test_valid_goal_is_eligible_as_before(self):
        df = pd.DataFrame([{
            "event_type": "goal", "is_valid_goal": True, "shot_outcome": "goal",
            "is_valid_penalty": None, "is_duplicate_event": False, "include_in_league_analytics": True,
        }])
        self.assertTrue(self._eligibility(df).iloc[0])


if __name__ == "__main__":
    unittest.main()
