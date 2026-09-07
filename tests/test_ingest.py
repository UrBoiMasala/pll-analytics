"""
Phase 4.25 regression tests for scripts/pll_ingest_season.py.

Run with: python3 -m unittest tests.test_ingest -v
(run from the repo root so the `scripts` package on sys.path resolves)
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pll_ingest_season as ing  # noqa: E402


def game_meta_payload(home_score=10, away_score=8):
    return {
        "data": {
            "homeTeam": {"officialId": "AAA"},
            "awayTeam": {"officialId": "BBB"},
            "homeScore": home_score,
            "visitorScore": away_score,
        }
    }


def items_payload(n=1):
    return {"data": {"items": [{"markerId": f"m{i}", "v": i} for i in range(n)]}}


class TestValidatePayload(unittest.TestCase):
    def test_nonempty_envelope_with_empty_items_is_not_ok(self):
        # This is the core "nonempty JSON envelope is not sufficient" case.
        status, _ = ing.validate_payload("players_stats", {"data": {"items": []}})
        self.assertEqual(status, "empty_feed")

    def test_empty_pbp_is_its_own_distinct_status(self):
        status, _ = ing.validate_payload("play_by_play", {"data": {"items": []}})
        self.assertEqual(status, "unavailable_pbp")

    def test_well_formed_items_payload_is_ok(self):
        status, _ = ing.validate_payload("teams_stats", items_payload(2))
        self.assertEqual(status, "ok")

    def test_game_meta_missing_score_on_completed_game_is_malformed(self):
        payload = game_meta_payload()
        payload["data"]["homeScore"] = None
        status, _ = ing.validate_payload("game_meta", payload, is_completed_game=True)
        self.assertEqual(status, "malformed")

    def test_game_meta_missing_score_on_upcoming_game_is_ok(self):
        # An upcoming game legitimately has no score yet.
        payload = game_meta_payload()
        payload["data"]["homeScore"] = None
        payload["data"]["visitorScore"] = None
        status, _ = ing.validate_payload("game_meta", payload, is_completed_game=False)
        self.assertEqual(status, "ok")

    def test_missing_data_key_is_malformed(self):
        status, _ = ing.validate_payload("teams_stats", {"unexpected": True})
        self.assertEqual(status, "malformed")


class TestForceRefresh(unittest.TestCase):
    """
    Covers: 'forced refresh replacing cached responses' and 'invalid/empty
    responses and failed-download preservation' from the Phase 4.25 test
    checklist.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patcher_root = mock.patch.object(ing, "REPO_ROOT", self.tmp)
        self.patcher_root.start()
        # raw_dir_for/meta_path_for reference REPO_ROOT at call time via the
        # module-level name, so patching the module attribute is sufficient.
        self.slug = "2026-ev-999"
        (self.tmp / "data" / "raw" / "2026" / self.slug).mkdir(parents=True)

    def tearDown(self):
        self.patcher_root.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_cached(self, name, payload):
        path = self.tmp / "data" / "raw" / "2026" / self.slug / f"{name}.json"
        path.write_text(json.dumps(payload))

    def test_force_actually_redownloads_and_replaces_cached_file(self):
        old_payload = items_payload(3)
        new_payload = items_payload(5)
        self._write_cached("teams_stats", old_payload)

        with mock.patch.object(ing, "fetch_json", return_value=new_payload):
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=True, is_completed_game=True)

        self.assertEqual(result["outcome"], "changed")
        on_disk = json.loads((self.tmp / "data" / "raw" / "2026" / self.slug / "teams_stats.json").read_text())
        self.assertEqual(on_disk, new_payload)

    def test_without_force_a_valid_cache_hit_makes_no_network_call(self):
        self._write_cached("teams_stats", items_payload(3))
        with mock.patch.object(ing, "fetch_json") as m:
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=False, is_completed_game=True)
        m.assert_not_called()
        self.assertEqual(result["outcome"], "skipped_cached")

    def test_empty_items_cache_is_not_treated_as_a_valid_hit(self):
        # A nonempty JSON envelope ({"data": {"items": []}}) is not
        # sufficient to be considered a valid cache — must re-fetch.
        self._write_cached("teams_stats", {"data": {"items": []}})
        with mock.patch.object(ing, "fetch_json", return_value=items_payload(2)) as m:
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=False, is_completed_game=True)
        m.assert_called_once()
        self.assertEqual(result["outcome"], "ok")

    def test_invalid_download_does_not_clobber_valid_cache(self):
        good_payload = items_payload(4)
        self._write_cached("teams_stats", good_payload)

        with mock.patch.object(ing, "fetch_json", return_value={"data": {"items": []}}):
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=True, is_completed_game=True)

        self.assertEqual(result["outcome"], "empty_feed")
        on_disk = json.loads((self.tmp / "data" / "raw" / "2026" / self.slug / "teams_stats.json").read_text())
        self.assertEqual(on_disk, good_payload, "a rejected/invalid refresh must never replace valid cached data")

    def test_network_failure_does_not_clobber_valid_cache(self):
        good_payload = items_payload(4)
        self._write_cached("teams_stats", good_payload)

        with mock.patch.object(ing, "fetch_json", side_effect=ConnectionError("boom")):
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=True, is_completed_game=True)

        self.assertEqual(result["outcome"], "incomplete_download")
        on_disk = json.loads((self.tmp / "data" / "raw" / "2026" / self.slug / "teams_stats.json").read_text())
        self.assertEqual(on_disk, good_payload)

    def test_unchanged_content_on_force_does_not_create_a_snapshot(self):
        payload = items_payload(3)
        self._write_cached("teams_stats", payload)
        with mock.patch.object(ing, "fetch_json", return_value=payload):
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=True, is_completed_game=True)
        self.assertEqual(result["outcome"], "unchanged")
        snap_dir = self.tmp / "data" / "raw" / "2026" / self.slug / "_snapshots"
        self.assertFalse(snap_dir.exists() and any(snap_dir.iterdir()))

    def test_changed_content_on_force_preserves_old_version_as_snapshot(self):
        old_payload = items_payload(2)
        new_payload = items_payload(6)
        self._write_cached("teams_stats", old_payload)
        with mock.patch.object(ing, "fetch_json", return_value=new_payload):
            result = ing.ingest_endpoint(self.slug, "teams_stats", "games/{slug}/teams/stats",
                                          force=True, is_completed_game=True)
        self.assertEqual(result["outcome"], "changed")
        self.assertIsNotNone(result["snapshot"])
        snap_path = self.tmp / result["snapshot"]
        self.assertTrue(snap_path.exists())
        self.assertEqual(json.loads(snap_path.read_text()), old_payload)


class TestPlayByPlayDiff(unittest.TestCase):
    def test_added_removed_changed_are_correctly_classified(self):
        old = {"data": {"items": [
            {"markerId": "a", "x": 1},
            {"markerId": "b", "x": 2},
            {"markerId": "c", "x": 3},
        ]}}
        new = {"data": {"items": [
            {"markerId": "a", "x": 1},       # unchanged
            {"markerId": "b", "x": 999},     # changed (official correction)
            {"markerId": "d", "x": 4},       # added
        ]}}  # "c" removed
        diff = ing.diff_play_by_play(old, new)
        self.assertEqual(diff["added"], ["d"])
        self.assertEqual(diff["removed"], ["c"])
        self.assertEqual(diff["changed"], ["b"])


if __name__ == "__main__":
    unittest.main()
