"""
Phase 4.25 regression tests: newly-completed-game discovery, and
raw-to-processed event coverage.

Run with: python3 -m unittest tests.test_coverage -v
"""
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_ingest_season as ing  # noqa: E402


def schedule_with(statuses):
    return {"data": {"items": [
        {"slugname": f"g{i}", "eventStatus": s} for i, s in enumerate(statuses)
    ]}}


class TestNewlyCompletedGameDiscovery(unittest.TestCase):
    def test_a_game_flipping_from_upcoming_to_completed_is_picked_up(self):
        before = schedule_with([3, 3, 0])   # g2 not yet played
        after = schedule_with([3, 3, 3])    # g2 just completed

        completed_before, upcoming_before, _ = ing.classify_games(before)
        completed_after, upcoming_after, _ = ing.classify_games(after)

        self.assertEqual({g["slugname"] for g in completed_before}, {"g0", "g1"})
        self.assertEqual({g["slugname"] for g in upcoming_before}, {"g2"})
        self.assertEqual({g["slugname"] for g in completed_after}, {"g0", "g1", "g2"})
        self.assertEqual(upcoming_after, [])

    def test_schedule_is_never_treated_as_immutable_cache(self):
        # Unlike per-game raw data, fetch_schedule's non-offline path always
        # writes what it fetched — there is no "already cached, skip"
        # branch for the schedule itself, which is what makes newly-
        # completed-game discovery possible on every run.
        import inspect
        src = inspect.getsource(ing.fetch_schedule)
        self.assertNotIn("already_cached", src)


class TestRawToProcessedCoverage(unittest.TestCase):
    """Integration check against the actual repo data: every raw PBP event
    for every completed game must be represented in the canonical
    events.csv (Phase 4.25 requirement: 'All cached raw PBP events are
    represented in the canonical events table')."""

    def setUp(self):
        games_path = REPO_ROOT / "data" / "processed" / "2026" / "games.csv"
        events_path = REPO_ROOT / "data" / "processed" / "2026" / "events.csv"
        if not games_path.exists() or not events_path.exists():
            self.skipTest("processed tables not built in this environment")
        import pandas as pd
        self.pd = pd
        self.games = pd.read_csv(games_path)
        self.events = pd.read_csv(events_path, low_memory=False, dtype={"event_id": str})

    def test_every_completed_games_raw_event_count_matches_events_csv(self):
        slugs = self.games.loc[self.games["is_completed"], "game_slug"].tolist()
        total_raw = 0
        mismatches = []
        for slug in slugs:
            raw = json.loads((REPO_ROOT / "data" / "raw" / "2026" / slug / "play_by_play.json").read_text())
            n_raw = len(raw["data"]["items"])
            n_events = int((self.events["game_slug"] == slug).sum())
            total_raw += n_raw
            if n_raw != n_events:
                mismatches.append((slug, n_raw, n_events))
        self.assertEqual(mismatches, [], f"raw/events.csv event count mismatches: {mismatches}")
        self.assertEqual(total_raw, len(self.events),
                          "total raw PBP events across all completed games must equal len(events.csv)")

    def test_every_raw_marker_id_appears_in_events_csv_for_its_game(self):
        # Spot-check a handful of games (not all 51, to keep this test fast)
        # for exact marker-id-level coverage, not just matching row counts.
        slugs = self.games.loc[self.games["is_completed"], "game_slug"].tolist()[:5]
        for slug in slugs:
            raw = json.loads((REPO_ROOT / "data" / "raw" / "2026" / slug / "play_by_play.json").read_text())
            raw_ids = {it.get("markerId") for it in raw["data"]["items"]}
            event_ids = set(self.events.loc[self.events["game_slug"] == slug, "event_id"])
            self.assertEqual(raw_ids, event_ids, f"marker ID mismatch for {slug}")


if __name__ == "__main__":
    unittest.main()
