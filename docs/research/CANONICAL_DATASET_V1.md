> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Canonical Historical Dataset — v1.0.0-phase11

Machine-readable companion: `data/processed/history/CANONICAL_MANIFEST_V1.json`
(regenerate with `python3 scripts/pll_build_canonical_manifest.py`).

## What "canonical" means

The canonical 2022-2026 historical PLL dataset is the single, reproducible
output of the Phase 1-11 pipeline — raw JSON ingestion, `pll_pbp_clean.clean()`,
`pll_duplicate_faceoff.flag_duplicate_faceoffs()`,
`pll_chronology_repair.repair_game_chronology()`, `pll_build_possessions`, then
the Phase 5-10 statistical layers — run with zero manual edits to any derived
file. There is exactly ONE possession/event layer per season: no competing
"repaired" vs "original" file for chronology. `possessions_repaired.csv`
(2023/2024) is retained only as Phase 10's original sensitivity-analysis
artifact (it also carries the V1/V3/V4 non-canonical variants for comparison);
every downstream consumer reads canonical `possessions.csv`, which now equals
the `V2_direct_and_timing` variant.

**Reproducibility, not duplication.** No raw or derived file is copied for
this freeze. The manifest is a hash-and-version record over files already on
disk (`data/processed/<year>/`, `data/processed/history/`), and raw JSON under
`data/raw/<year>/<slug>/` is the single, byte-preserved source of truth
(verified unchanged, `pll_validate_phase11.py` check 1).

## Seasons and raw-data provenance

2022, 2023, 2024, 2025, 2026. Every raw endpoint file's ingestion-time
`content_hash` (`pll_ingest_season.py`) is re-verified byte-for-byte at
freeze time; the manifest's `raw_data.<season>.raw_manifest_hash` is a single
hash over every `game/endpoint:content_hash` triple for that season, so any
future re-fetch or edit of a raw file is detectable by comparing that one
value.

## Transformation rule versions

| Component | Version | Status |
|---|---|---|
| Event cleaning (`pll_pbp_clean.py`) | `phase3_5_unmodified` | validated Phase 2/3.5, untouched this phase |
| Chronology repair (`pll_chronology_repair.py`) | `phase11_chronology_v1` | new this phase |
| Duplicate-faceoff exclusion (`pll_duplicate_faceoff.py`) | `phase11_duplicate_faceoff_v1` | new this phase |
| Possession state machine (`pll_build_possessions.py`) | `phase4_unmodified` | validated Phase 4, untouched this phase |

## Corrections applied in this freeze

| Season | Correction | Count | Effect |
|---|---|---|---|
| 2023 | Chronology reorder (DIRECT + DIRECT_TIMING) | 256 sequences | possessions.csv 4460 → 4204 |
| 2024 | Chronology reorder | 1 sequence | −2 possessions |
| 2024 | Duplicate-faceoff exclusion | 36 pairs, 3 games | −44 possessions (combined with the above: 4047 → 4001) |
| 2022, 2025, 2026 | none | 0 | byte-identical to pre-Phase-11 |

Full evidence and derivation: `docs/PHASE11_CHRONOLOGY_REPAIR.md`,
`docs/PHASE11_DUPLICATE_FACEOFF.md`.

## Known source limitations (documented, not repaired)

- `playoffs-quarterfinal-1-2023-9-1`: a 13-goal faceoff shortfall — genuinely
  missing raw events, not recoverable by reordering.
- 2023: 91 of 1047 goals (8.7%) still carry no faceoff logged after them
  post-repair, versus 3.5% in 2026 — a residual, not fully resolved.
- `archers-cannons-2022-6-18`: an isolated goal-count reconciliation gap (6 vs
  1) against official scoring.

## Known unresolved anomalies (documented, not repaired)

- Every STRONGLY_INFERRED/UNRESOLVED chronology sequence (9+9 in 2023; smaller
  counts elsewhere) is classified but deliberately left unrepaired — the
  evidence is insufficient (STRONGLY_INFERRED) or contradictory (UNRESOLVED).
- 2022's 82.5 possessions/game is a documented **GENUINE_HISTORICAL_DIFFERENCE**
  (`docs/PHASE11_2022_POSSESSION_INVESTIGATION.md`): official-stat
  reconciliation and possession-ambiguity rate for 2022 are as good as or
  better than later seasons; the gap traces to genuinely longer average
  possessions (fewer shot-clock expirations and turnovers per game), not a
  defect. Not repaired.

## Explicitly out of scope

No MVP score, Statistical Tewaaraton, award ranking, WAR, replacement level,
cross-position composite, positional-percentile composite, or fantasy-like
scoring system exists anywhere in this dataset. Verified by
`pll_validate_phase10.py` check 22 (scans every Phase 10/pooled surface's
column names for forbidden patterns) and unchanged by Phase 11, which added no
new statistical-layer code.

## Validation status at freeze

| Suite | Result |
|---|---|
| `pll_validate_phase8.py` | 24/24 PASS |
| `pll_validate_phase9.py` | 22/22 PASS |
| `pll_validate_phase10.py` | 24/24 PASS |
| `pll_validate_phase11.py` | 20/20 PASS |
| `pytest tests/` | 351/351 PASS |

## Exact artifacts included

36 files hashed in the manifest: `games.csv`/`teams.csv`/`players.csv`/
`events.csv`/`possessions.csv` for each of 2022-2026, plus 11 cross-season
history artifacts (evidence, audit, validation-report and manifest files
under `data/processed/history/`). See `CANONICAL_MANIFEST_V1.json` for the
complete list with SHA-256 hashes.

## Reproducing this freeze

```
python3 scripts/pll_build_history.py --years 2022,2023,2024,2025,2026
python3 scripts/pll_phase10_possession_repair.py
python3 scripts/pll_build_history_stats.py --years 2022,2023,2024,2025,2026
python3 scripts/pll_phase10_cross_position.py
python3 scripts/pll_phase10_career.py
python3 scripts/pll_phase10_readiness.py
python3 scripts/pll_validate_phase10.py
python3 scripts/pll_validate_phase11.py
python3 scripts/pll_build_canonical_manifest.py
python3 -m pytest tests/ -q
```

Two independent runs of the events/possessions rebuild produce byte-identical
derived output (`pll_validate_phase11.py` check 20).
