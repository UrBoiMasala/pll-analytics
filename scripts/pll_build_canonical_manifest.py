"""
Phase 11 part H: the canonical dataset freeze manifest.

Produces data/processed/history/CANONICAL_MANIFEST_V1.json: a single,
reproducible, machine-readable statement of what "canonical" means for the
2022-2026 historical dataset after Phase 11 -- which raw inputs, which
transformation rule versions, which validation results, and which
limitations/anomalies remain open. No data is duplicated; this is a manifest
over files already on disk, hashed in place.

Usage:
    python3 pll_build_canonical_manifest.py
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "data" / "raw"
PROC = REPO_ROOT / "data" / "processed"
HIST = PROC / "history"
SEASONS = [2022, 2023, 2024, 2025, 2026]

CANONICAL_VERSION = "v1.0.0-phase11"

CANONICAL_ARTIFACTS = (
    [f"{y}/{f}" for y in SEASONS for f in
     ("games.csv", "teams.csv", "players.csv", "events.csv", "possessions.csv")]
    + ["history/possession_repair_evidence_2022_2026.csv",
       "history/2023_possession_repair_audit.csv",
       "history/possession_stats_original_vs_repaired.csv",
       "history/possession_team_rank_stability.csv",
       "history/possession_repair_residual_by_game.csv",
       "history/phase11_before_after_audit.csv",
       "history/phase11_validation_report.csv",
       "history/phase10_validation_report.csv",
       "history/phase9_validation_report.csv",
       "history/historical_game_inventory.csv",
       "history/historical_ingestion_report.csv"]
)


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def raw_manifest_for_season(year: int) -> dict:
    """One content_hash-of-content_hashes per season, from the ingestion
    _meta.json files already on disk -- not a re-hash of every raw byte, which
    the ingester already recorded at fetch time (pll_ingest_season.content_hash)."""
    season_dir = RAW / str(year)
    if not season_dir.exists():
        return {"n_games": 0, "raw_hash": None}
    entries = []
    for slug_dir in sorted(season_dir.iterdir()):
        meta_p = slug_dir / "_meta.json"
        if not slug_dir.is_dir() or not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text())
        for endpoint in sorted(meta):
            h = meta[endpoint].get("content_hash")
            if h:
                entries.append(f"{slug_dir.name}/{endpoint}:{h}")
    combined = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return {"n_games": len(set(e.split("/")[0] for e in entries)),
           "n_raw_endpoint_files": len(entries),
           "raw_manifest_hash": combined}


def main():
    manifest = {
        "canonical_version": CANONICAL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seasons": SEASONS,
        "definition": (
            "The canonical 2022-2026 historical PLL dataset is the output of "
            "the Phase 1-11 pipeline (ingestion -> pll_pbp_clean.clean() -> "
            "pll_duplicate_faceoff.flag_duplicate_faceoffs() -> "
            "pll_chronology_repair.repair_game_chronology() -> "
            "pll_build_possessions -> Phase 5-10 statistical layers), run "
            "against the raw JSON hashed below, with zero manual edits to any "
            "derived file. 'Canonical' means: this is the ONE possession/event "
            "layer per season; there is no competing 'repaired' vs 'original' "
            "file distinction for chronology any more (possessions_repaired.csv "
            "is retained only as Phase 10's original sensitivity-analysis "
            "artifact, superseded by canonical possessions.csv for anything "
            "downstream)."
        ),
        "raw_data": {str(y): raw_manifest_for_season(y) for y in SEASONS},
        "transformation_rule_versions": {
            "chronology_repair": "phase11_chronology_v1",
            "duplicate_faceoff": "phase11_duplicate_faceoff_v1",
            "possession_state_machine": "phase4_unmodified",
            "event_cleaning": "phase3_5_unmodified",
        },
        "corrections_applied_this_freeze": [
            {"scope": "2023", "type": "chronology_reorder", "n_sequences": 256,
             "detail": "199 DIRECT + 57 DIRECT_TIMING, possessions.csv 4460 -> 4204"},
            {"scope": "2024", "type": "chronology_reorder", "n_sequences": 1,
             "detail": "1 DIRECT"},
            {"scope": "2024", "type": "duplicate_faceoff_exclusion", "n_sequences": 36,
             "detail": "36 confirmed duplicate faceoffs across 3 games "
                       "(2024_game_10, 2024_game_12, 2024_game_31), "
                       "possessions.csv 4047 -> 4001 combined with the "
                       "chronology reorder above"},
        ],
        "known_source_limitations": [
            "2023 playoffs-quarterfinal-1-2023-9-1: 13-goal faceoff shortfall, "
            "genuinely missing raw events, not recoverable by reordering "
            "(classified UNRESOLVED_MISSING_FACEOFF_EVENTS)",
            "2023: 91 of 1047 goals (8.7%) still have no faceoff logged after "
            "them post-repair, vs 3.5% in 2026 -- residual, not fully resolved",
            "archers-cannons-2022-6-18: goal-count reconciliation gap (6 vs 1) "
            "against official scoring, isolated to this one game",
        ],
        "known_unresolved_anomalies": [
            "9 STRONGLY_INFERRED and 9 UNRESOLVED 2023 sequences, and the "
            "equivalent per-season counts in 2022/2025/2026, are classified "
            "but deliberately never repaired (evidence insufficient or "
            "contradictory) -- see docs/PHASE11_CHRONOLOGY_REPAIR.md",
            "2022's 82.5 possessions/game is a documented GENUINE_HISTORICAL_"
            "DIFFERENCE (docs/PHASE11_2022_POSSESSION_INVESTIGATION.md), not "
            "a defect, and is NOT repaired",
        ],
        "explicitly_out_of_scope": [
            "No MVP score, Statistical Tewaaraton, award ranking, WAR, "
            "replacement level, cross-position composite, or fantasy-like "
            "scoring system exists anywhere in this dataset (verified by "
            "pll_validate_phase10.py check 22 and pll_metric_catalog."
            "FORBIDDEN_IN_PUBLISHED).",
        ],
        "validation_status": {},
        "artifact_hashes": {},
    }

    for name, rel in [("phase8", "2026/phase8_validation_report.csv"),
                      ("phase9", "history/phase9_validation_report.csv"),
                      ("phase10", "history/phase10_validation_report.csv"),
                      ("phase11", "history/phase11_validation_report.csv")]:
        p = PROC / rel
        if p.exists():
            rep = pd.read_csv(p)
            manifest["validation_status"][name] = {
                "n_checks": len(rep), "n_pass": int((rep["status"] == "PASS").sum()),
                "n_fail": int((rep["status"] == "FAIL").sum()),
            }

    for rel in CANONICAL_ARTIFACTS:
        p = PROC / rel
        if p.exists():
            manifest["artifact_hashes"][rel] = _sha256(p)
        else:
            manifest["artifact_hashes"][rel] = None

    out = HIST / "CANONICAL_MANIFEST_V1.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=False))
    print(f"Wrote {out.relative_to(REPO_ROOT)}")
    print(f"  {len(manifest['artifact_hashes'])} artifacts hashed, "
         f"{sum(v is None for v in manifest['artifact_hashes'].values())} missing")
    for name, v in manifest["validation_status"].items():
        print(f"  {name}: {v['n_pass']}/{v['n_checks']} PASS")
    return manifest


if __name__ == "__main__":
    main()
