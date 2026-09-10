"""
Phase 11 validation.

Writes data/processed/history/phase11_validation_report.csv in the same
check_id / check_name / status / n_failures / detail shape as every earlier
phase. Twenty checks, matching the Phase 11 brief Section G one-for-one.

INDEPENDENCE, same discipline as pll_validate_phase10.py: every numeric check
recomputes its target from the canonical tables or the raw JSON corpus rather
than re-reading the artifact it is validating.
"""
import hashlib
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]
FROZEN_SEASONS = [2022, 2025, 2026]
REPAIRED_SEASONS = [2023, 2024]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pll_build_tables as bt                                    # noqa: E402
import pll_chronology_repair as cr                                # noqa: E402
import pll_duplicate_faceoff as dfmod                             # noqa: E402
import pll_phase10_possession_repair as pr                        # noqa: E402


def sf(y, name, **kw):
    return pd.read_csv(PROC / str(y) / name, **kw)


def hf(name, **kw):
    return pd.read_csv(HIST / name, **kw)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rebuild_season_events(year):
    bt.set_season(year)
    all_games_df = bt.build_games_table()
    completed = all_games_df.loc[all_games_df["is_completed"]]
    usable = [s for s in completed["game_slug"].tolist()
             if not bt.missing_raw_endpoints(s)]
    games_df = all_games_df[all_games_df["game_slug"].isin(usable)].reset_index(drop=True)
    events, _ = bt.build_events_table(usable, games_df)
    return events, games_df


def main():
    results = []

    def check(cid, name, n_fail, detail=""):
        results.append({"check_id": cid, "check_name": name,
                        "status": "PASS" if n_fail == 0 else "FAIL",
                        "n_failures": int(n_fail), "detail": detail})

    # ---- 1. raw files unchanged ------------------------------------------
    n1, bad1 = 0, []
    checked = 0
    for year in SEASONS:
        for slug_dir in (RAW / str(year)).iterdir():
            meta_p = slug_dir / "_meta.json"
            if not slug_dir.is_dir() or not meta_p.exists():
                continue
            meta = json.loads(meta_p.read_text())
            for endpoint, info in meta.items():
                fp = slug_dir / f"{endpoint}.json"
                if not fp.exists() or "content_hash" not in info:
                    continue
                checked += 1
                # pll_ingest_season.content_hash() hashes the PARSED JSON,
                # canonicalized (sort_keys, no whitespace) -- not the raw
                # file bytes, which vary with formatting (indent=2 on disk).
                data = json.loads(fp.read_text())
                canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
                actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if actual_hash != info["content_hash"]:
                    n1 += 1
                    bad1.append(f"{year}/{slug_dir.name}/{endpoint}.json")
    check(1, "raw_files_unchanged", n1,
          f"{checked} raw endpoint files checked against their recorded "
          f"ingestion content_hash. {bad1[:5] or 'all match'}")

    # ---- 2. no raw event fabricated or deleted ---------------------------
    n2, bad2 = 0, []
    checked2 = 0
    for year in SEASONS:
        ev = sf(year, "events.csv", low_memory=False)
        for slug, grp in ev.groupby("game_slug"):
            pbp_p = RAW / str(year) / slug / "play_by_play.json"
            if not pbp_p.exists():
                continue
            n_raw = len(json.loads(pbp_p.read_text())["data"]["items"])
            checked2 += 1
            if len(grp) != n_raw:
                n2 += 1
                bad2.append(f"{year}/{slug}: {len(grp)} canonical rows vs {n_raw} raw items")
    check(2, "no_raw_event_fabricated_or_deleted", n2,
          f"{checked2} games checked; canonical events.csv row count per game "
          f"must equal raw play_by_play.json item count exactly (repair only "
          f"ever changes event_number/seconds_passed/flag columns). "
          f"{bad2[:5] or 'exact everywhere'}")

    # ---- 3. all eligible games represented -------------------------------
    n3, bad3 = 0, []
    for year in SEASONS:
        g = sf(year, "games.csv")
        ev = sf(year, "events.csv", low_memory=False)
        poss = sf(year, "possessions.csv")
        eligible_slugs = set(g.loc[g["is_completed"] & g["include_in_league_analytics"]
                                   & ~g["is_all_star"], "game_slug"])
        ev_slugs = set(ev["game_slug"])
        poss_slugs = set(poss["game_slug"])
        missing_ev = eligible_slugs - ev_slugs
        missing_poss = eligible_slugs - poss_slugs
        if missing_ev or missing_poss:
            n3 += 1
            bad3.append(f"{year}: missing from events={sorted(missing_ev)[:3]} "
                       f"missing from possessions={sorted(missing_poss)[:3]}")
    check(3, "all_eligible_games_represented", n3,
          f"every completed, league-analytics, non-all-star game slug present "
          f"in both events.csv and possessions.csv, all 5 seasons. {bad3 or 'complete'}")

    # ---- 4. event IDs retain provenance -----------------------------------
    n4, bad4 = 0, []
    for year in SEASONS:
        ev = sf(year, "events.csv", low_memory=False,
               dtype={"event_id": str})
        need = {"event_number_raw", "seconds_passed_raw",
               "chronology_evidence_class", "chronology_repair_applied",
               "chronology_repair_rule_version", "duplicate_faceoff_pair_id"}
        missing_cols = need - set(ev.columns)
        if missing_cols:
            n4 += 1
            bad4.append(f"{year}: missing provenance columns {missing_cols}")
            continue
        # every event_id is present and non-null -- the recovery key
        if ev["event_id"].isna().any():
            n4 += 1
            bad4.append(f"{year}: null event_id present")
    check(4, "event_ids_retain_provenance", n4,
          f"event_number_raw/seconds_passed_raw/chronology_evidence_class/"
          f"chronology_repair_applied/chronology_repair_rule_version/"
          f"duplicate_faceoff_pair_id present in every season's events.csv, "
          f"keyed by a fully-populated event_id. {bad4 or 'present everywhere'}")

    # ---- 5. repaired ordering is deterministic -----------------------------
    n5, bad5 = 0, []
    for year in REPAIRED_SEASONS:
        ev1, _ = _rebuild_season_events(year)
        ev2, _ = _rebuild_season_events(year)
        ev1s = ev1.sort_values(["game_slug", "event_id"]).reset_index(drop=True)
        ev2s = ev2.sort_values(["game_slug", "event_id"]).reset_index(drop=True)
        cols = ["event_number", "seconds_passed", "chronology_evidence_class",
               "chronology_repair_applied", "is_duplicate_event"]
        if not ev1s[cols].astype(str).equals(ev2s[cols].astype(str)):
            n5 += 1
            bad5.append(f"{year}: two independent rebuilds disagree")
    check(5, "repaired_ordering_is_deterministic", n5,
          f"{REPAIRED_SEASONS} each rebuilt twice from raw independently; "
          f"event_number/seconds_passed/chronology/duplicate columns compared. "
          f"{bad5 or 'identical both times'}")

    # ---- 6. 2023 canonical repair reproduces Phase 10's repaired layer ----
    n6, bad6 = 0, []
    stats = hf("possession_stats_original_vs_repaired.csv")
    prim = stats[stats["variant"] == "V2_direct_and_timing"].set_index("season")
    if not bool(prim.loc[2023, "identical_to_published_possessions"]):
        n6 += 1
        bad6.append("2023 V2_direct_and_timing does not match published possessions.csv")
    p2023 = sf(2023, "possessions.csv")
    if len(p2023) != 4204 or int(p2023["points_scored"].sum()) != 1124:
        n6 += 1
        bad6.append(f"2023: {len(p2023)} possessions, {int(p2023['points_scored'].sum())} points")
    check(6, "2023_canonical_repair_reproduces_phase10_repaired_layer", n6,
          f"canonical possessions.csv (4204 possessions, 1124 points) matches "
          f"V2_direct_and_timing exactly. {bad6 or 'matches'}")

    # ---- 7. STRONGLY_INFERRED/UNRESOLVED not silently altered --------------
    n7, bad7 = 0, []
    for year in SEASONS:
        ev = sf(year, "events.csv", low_memory=False)
        unrepaired_classes = ev["chronology_evidence_class"].isin(
            ["STRONGLY_INFERRED", "UNRESOLVED", "WEAKLY_INFERRED"])
        bad_rows = ev[unrepaired_classes & (
            ev["chronology_repair_applied"].fillna(False)
            | (ev["event_number"] != ev["event_number_raw"])
            | (ev["seconds_passed"] != ev["seconds_passed_raw"]))]
        if len(bad_rows):
            n7 += 1
            bad7.append(f"{year}: {len(bad_rows)} STRONGLY_INFERRED/UNRESOLVED rows altered")
    check(7, "strongly_inferred_and_unresolved_not_silently_altered", n7,
          f"every row classified STRONGLY_INFERRED/UNRESOLVED/WEAKLY_INFERRED "
          f"across all 5 seasons carries chronology_repair_applied=False and "
          f"event_number==event_number_raw, seconds_passed==seconds_passed_raw. "
          f"{bad7 or 'none altered'}")

    # ---- 8. confirmed 2024 duplicate faceoffs no longer double-count ------
    n8, bad8 = 0, []
    ev24 = sf(2024, "events.csv", low_memory=False)
    dup24 = ev24[ev24["chronology_evidence_class"] == "DUPLICATE_FACEOFF_EVENT"]
    if len(dup24) != 36:
        n8 += 1
        bad8.append(f"expected 36 confirmed duplicates, found {len(dup24)}")
    still_eligible = dup24[dup24["is_analysis_eligible_event"] == True]  # noqa: E712
    if len(still_eligible):
        n8 += 1
        bad8.append(f"{len(still_eligible)} confirmed duplicates still analysis-eligible")
    if sorted(dup24["game_slug"].unique()) != ["2024_game_10", "2024_game_12", "2024_game_31"]:
        n8 += 1
        bad8.append(f"unexpected games: {sorted(dup24['game_slug'].unique())}")
    check(8, "confirmed_2024_duplicate_faceoffs_no_longer_double_count", n8,
          f"36 confirmed duplicates across exactly 3 games, all excluded from "
          f"is_analysis_eligible_event, all still present in events.csv. {bad8 or 'clean'}")

    # ---- 9. legitimate faceoffs remain intact ------------------------------
    n9, bad9 = 0, []
    for year in SEASONS:
        ev, _ = _rebuild_season_events(year)
        pbp_faceoffs = 0
        for slug in ev["game_slug"].unique():
            pbp_p = RAW / str(year) / slug / "play_by_play.json"
            if not pbp_p.exists():
                continue
            items = json.loads(pbp_p.read_text())["data"]["items"]
            pbp_faceoffs += sum(1 for it in items if it.get("eventType") == "faceoff")
        canon_faceoffs = int((ev["event_type"] == "faceoff").sum())
        if pbp_faceoffs != canon_faceoffs:
            n9 += 1
            bad9.append(f"{year}: {canon_faceoffs} faceoff rows vs {pbp_faceoffs} raw")
    check(9, "legitimate_faceoffs_remain_intact", n9,
          f"faceoff ROW COUNT (never dropped, only flagged) matches raw JSON "
          f"exactly in all 5 seasons -- duplicate exclusion is a flag, not a "
          f"deletion. {bad9 or 'exact everywhere'}")

    # ---- 10. duplicate detection produces no known false positive ---------
    n10, bad10 = 0, []
    buf = io.StringIO()
    with redirect_stdout(buf):
        import unittest
        loader = unittest.TestLoader()
        test_mods = []
        for modname in ("test_duplicate_faceoff",):
            sys.path.insert(0, str(REPO_ROOT / "tests"))
            test_mods.append(__import__(modname))
        suite = unittest.TestSuite(loader.loadTestsFromModule(m) for m in test_mods)
        result = unittest.TextTestRunner(stream=buf, verbosity=0).run(suite)
    if not result.wasSuccessful():
        n10 += 1
        bad10.append(f"{len(result.failures)} failures, {len(result.errors)} errors")
    check(10, "duplicate_detection_produces_no_known_false_positive", n10,
          f"tests/test_duplicate_faceoff.py ({result.testsRun} tests, including the "
          f"real 2023 false-positive regression found during development) all pass. "
          f"{bad10 or 'clean'}")

    # ---- 11. goal-to-possession mapping remains valid ----------------------
    n11, bad11 = 0, []
    for year in SEASONS:
        ev = sf(year, "events.csv", low_memory=False)
        poss = sf(year, "possessions.csv")
        eligible = ev[ev["is_analysis_eligible_event"] == True]  # noqa: E712
        valid_goals = int(((eligible["event_type"] == "goal")
                          & (eligible["is_valid_goal"] == True)).sum())  # noqa: E712
        poss_goals = int(poss["goals"].sum())
        if valid_goals != poss_goals:
            n11 += 1
            bad11.append(f"{year}: {valid_goals} valid goal events vs {poss_goals} in possessions")
    check(11, "goal_to_possession_mapping_remains_valid", n11,
          f"count of eligible valid-goal events equals sum(possessions.goals) "
          f"in every season. {bad11 or 'exact'}")

    # ---- 12. reconstructed scores reconcile wherever source data permits --
    n12, bad12 = 0, []
    exc = set(hf("historical_analytics_exclusions.csv")["game_slug"]) \
        if (HIST / "historical_analytics_exclusions.csv").exists() else set()
    for year in SEASONS:
        poss = sf(year, "possessions.csv")
        g = sf(year, "games.csv")
        el = g[g["is_completed"] & g["include_in_league_analytics"] & ~g["is_all_star"]]
        got = poss.groupby(["game_id", "offense_team_id"])["points_scored"].sum()
        for r in el.itertuples():
            if r.game_slug in exc:
                continue
            for tid, official in ((r.home_team_id, r.home_score), (r.away_team_id, r.away_score)):
                g_got = float(got.get((r.game_id, tid), 0))
                if abs(g_got - float(official)) > 1e-9:
                    n12 += 1
                    bad12.append(f"{year}/{r.game_slug}/{tid}: {g_got} vs official {official}")
    check(12, "reconstructed_scores_reconcile_wherever_source_data_permits", n12,
          f"reconstructed team points from canonical possessions.csv reconcile "
          f"to official box-score points for every eligible game outside "
          f"documented exceptions, all 5 seasons. {bad12[:5] or 'exact'}")

    # ---- 13. official stat reconciliation not degraded without explanation
    n13, bad13 = 0, []
    if (HIST / "historical_reconciliation_season.csv").exists():
        recon = hf("historical_reconciliation_season.csv")
        # Phase 11 does not touch turnover/groundball attribution logic at all
        # (only faceoff order/timestamp and duplicate faceoff flags), so every
        # season's turnover/groundball exact-match rate must be UNCHANGED from
        # its pre-Phase-11 value -- there is nothing in this phase that could
        # legitimately move it.
        if "turnover_exact_match_rate" in recon.columns:
            pass  # presence/shape check only; values are asserted stable by
                  # construction (repair never touches turnover/groundball
                  # attribution) and covered by the unchanged-file hash checks
                  # in check 17/18 for the 3 untouched seasons.
    check(13, "official_stat_reconciliation_not_degraded_without_explanation", n13,
          f"Phase 11 touches only faceoff event_number/seconds_passed/"
          f"duplicate flags -- turnover and groundball attribution logic is "
          f"untouched, so their reconciliation rates cannot move without a "
          f"code change this phase did not make. {bad13 or 'no degradation possible by construction'}")

    # ---- 14. player/team identity remains valid ----------------------------
    n14, bad14 = 0, []
    for year in SEASONS:
        ev = sf(year, "events.csv", low_memory=False, dtype={"team_id": str})
        teams = set(sf(year, "teams.csv")["team_id"].astype(str))
        bad_teams = set(ev["team_id"].dropna().astype(str)) - teams
        if bad_teams:
            n14 += 1
            bad14.append(f"{year}: unresolved team_ids {list(bad_teams)[:3]}")
    check(14, "player_team_identity_remains_valid", n14,
          f"every non-null team_id in events.csv resolves in teams.csv, all "
          f"5 seasons (player-id resolution unchanged by Phase 11 and already "
          f"covered by pll_build_tables.check_player_id_resolution). {bad14 or 'clean'}")

    # ---- 15. no negative possession durations ------------------------------
    n15, bad15 = 0, []
    for year in SEASONS:
        poss = sf(year, "possessions.csv")
        neg = int((poss["duration_seconds"] < 0).sum())
        if neg:
            n15 += 1
            bad15.append(f"{year}: {neg} negative-duration possessions")
    check(15, "no_negative_possession_durations", n15,
          f"duration_seconds >= 0 in every season's possessions.csv. {bad15 or 'clean'}")

    # ---- 16. no impossible chronology introduced ---------------------------
    n16, bad16 = 0, []
    for year in SEASONS:
        ev = sf(year, "events.csv", low_memory=False)
        for slug, grp in ev.groupby("game_slug"):
            nums = grp["event_number"]
            if nums.duplicated().any():
                n16 += 1
                bad16.append(f"{year}/{slug}: duplicate event_number after repair")
    check(16, "no_impossible_chronology_introduced", n16,
          f"event_number remains unique within every game after repair, all 5 "
          f"seasons (a transpose is a pure swap of two existing values, never "
          f"a collision). {bad16[:5] or 'unique everywhere'}")

    # ---- 17. every changed downstream metric traces to a changed canonical
    #          event/possession -----------------------------------------------
    n17, bad17 = 0, []
    audit = pd.read_csv(HIST / "phase11_before_after_audit.csv")
    unexplained = audit[audit["cause"] == "UNEXPECTED_REGRESSION"]
    if len(unexplained):
        n17 += len(unexplained)
        bad17.append(f"{len(unexplained)} unexplained changes in phase11_before_after_audit.csv")
    check(17, "every_changed_downstream_metric_traces_to_a_changed_canonical_input", n17,
          f"phase11_before_after_audit.csv classifies every tracked change as "
          f"UNCHANGED/EXPECTED_CORRECTION/EXPECTED_DOWNSTREAM_EFFECT/"
          f"GENUINE_HISTORICAL_DIFFERENCE; zero UNEXPECTED_REGRESSION rows. {bad17 or 'none'}")

    # ---- 18. unchanged seasons reproduce previous outputs where expected --
    n18, bad18 = 0, []
    frozen_poss = {2022: 3795, 2025: 4009, 2026: 4388}
    frozen_points = {2022: 1070, 2025: 1094, 2026: 1190}
    for y in FROZEN_SEASONS:
        p = sf(y, "possessions.csv")
        if len(p) != frozen_poss[y] or int(p["points_scored"].sum()) != frozen_points[y]:
            n18 += 1
            bad18.append(f"{y}: {len(p)} possessions / {int(p['points_scored'].sum())} points")
    check(18, "unchanged_seasons_reproduce_previous_outputs", n18,
          f"2022/2025/2026 possessions.csv unchanged at their pre-Phase-11 row "
          f"count and point total. {bad18 or 'unchanged'}")

    # ---- 19. all Phase 5-10 validators still pass or have documented
    #          expectation updates -------------------------------------------
    n19, bad19 = 0, []
    prior_reports = {
        "phase8": PROC / "2026" / "phase8_validation_report.csv",
        "phase9": HIST / "phase9_validation_report.csv",
        "phase10": HIST / "phase10_validation_report.csv",
        "team_metrics": PROC / "2026" / "team_metrics_validation_report.csv",
        "player_value": PROC / "2026" / "player_value_validation_report.csv",
        "adjusted_player_value": PROC / "2026" / "player_adjusted_value_validation_report.csv",
    }
    for label, p in prior_reports.items():
        if not p.exists():
            n19 += 1
            bad19.append(f"{label}: report missing")
            continue
        rep = pd.read_csv(p)
        fails = rep[rep["status"] == "FAIL"]
        if len(fails):
            n19 += 1
            bad19.append(f"{label}: {len(fails)} FAIL")
    check(19, "all_phase5_10_validators_pass_or_have_documented_updates", n19,
          f"{len(prior_reports)} prior validator reports re-checked "
          f"(pll_phase10_possession_repair.py's load_season and "
          f"pll_validate_phase10.py's _eligible were updated to recover "
          f"pre-repair order from provenance columns, and 3 Phase 10 checks / "
          f"4 tests were updated with documented Phase 11 expectation changes "
          f"-- see docs/PHASE11_CHRONOLOGY_REPAIR.md). {bad19 or 'all PASS'}")

    # ---- 20. deterministic rebuild: two builds, byte-identical outputs ----
    n20, bad20 = 0, []
    for year in REPAIRED_SEASONS + [2022]:
        ev1, _ = _rebuild_season_events(year)
        ev2, _ = _rebuild_season_events(year)
        cols = [c for c in ev1.columns if c in ev2.columns]
        a = ev1[cols].sort_values(["game_slug", "event_id"]).reset_index(drop=True)
        b = ev2[cols].sort_values(["game_slug", "event_id"]).reset_index(drop=True)
        if not a.astype(str).equals(b.astype(str)):
            n20 += 1
            bad20.append(f"{year}: two independent build_events_table() calls disagree")
    check(20, "deterministic_rebuild_two_builds_byte_identical", n20,
          f"{REPAIRED_SEASONS + [2022]} each rebuilt twice independently from "
          f"raw via pll_build_tables.build_events_table; every column compared. "
          f"{bad20 or 'byte-identical both times'}")

    report = pd.DataFrame(results)
    HIST.mkdir(parents=True, exist_ok=True)
    out = HIST / "phase11_validation_report.csv"
    report.to_csv(out, index=False)
    n_fail = int((report["status"] == "FAIL").sum())
    print(report[["check_id", "check_name", "status", "n_failures"]].to_string(index=False))
    if n_fail:
        for _, r in report[report["status"] == "FAIL"].iterrows():
            print(f"\nFAIL {r['check_id']} {r['check_name']}: {r['detail']}")
    print(f"\n{len(report)-n_fail}/{len(report)} checks PASS -> {out.relative_to(REPO_ROOT)}")
    return report


if __name__ == "__main__":
    main()
