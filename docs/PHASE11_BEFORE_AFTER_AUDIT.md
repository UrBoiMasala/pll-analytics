> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Phase 11 — Before/After Blast-Radius Audit

Machine-readable companion:
`data/processed/history/phase11_before_after_audit.csv`. Every row carries a
`cause` in {`UNCHANGED`, `EXPECTED_CORRECTION`, `EXPECTED_DOWNSTREAM_EFFECT`,
`GENUINE_HISTORICAL_DIFFERENCE`, `UNEXPECTED_REGRESSION`}. **Zero
`UNEXPECTED_REGRESSION` rows.**

## Per-season summary — **OBSERVED**

| Season | Events | Possessions before | Possessions after | Points | Goals | Downstream |
|---|---|---|---|---|---|---|
| 2022 | 10,431 (unchanged) | 3795 | 3795 | 1070 | 1013 | frozen, byte-identical |
| 2023 | 10,486 (unchanged) | 4460 | 4204 | 1124 | 1047 | possession-denominated columns changed; rankings unchanged |
| 2024 | 10,129 (unchanged) | 4047 | 4001 | 1060 | 981 | possession-denominated columns changed; rankings unchanged |
| 2025 | 10,321 (unchanged) | 4009 | 4009 | 1094 | 1020 | frozen, byte-identical |
| 2026 | 11,254 (unchanged) | 4388 | 4388 | 1190 | 1118 | frozen, byte-identical |

Event row counts never change in any season — Phase 11 never fabricates or
deletes a source event (Section B/C both operate only on `event_number`,
`seconds_passed`, and duplicate/chronology flag columns). Total points and
total goals are unchanged in every season, confirming neither correction ever
touches a goal or its scoring value.

## Cause breakdown

- **EXPECTED_CORRECTION** (2023, 2024 possession counts): the Phase
  10-validated chronology repair (256 sequences in 2023, 1 in 2024) and the
  confirmed 2024 duplicate-faceoff exclusion (36 pairs), both documented with
  full evidence in `docs/PHASE11_CHRONOLOGY_REPAIR.md` and
  `docs/PHASE11_DUPLICATE_FACEOFF.md`.
- **EXPECTED_DOWNSTREAM_EFFECT** (2023/2024 team_game_advanced,
  team_season_advanced, team_stats_{2023,2024}, team_leaderboards_{2023,2024},
  pooled team_stats_2022_2026 rows for those seasons, and the corresponding
  Phase 6/7/8/9/10 player and cross-position layers that read possession
  counts as context): every possession-DENOMINATED column moved
  proportionally; zero non-possession column (goals, shots, faceoff win %,
  turnovers, every player-value component) moved. Zero of 40 team-season
  offensive-efficiency ranks changed (`possession_team_rank_stability.csv`).
- **GENUINE_HISTORICAL_DIFFERENCE** (2022's 82.5 poss/game): investigated in
  full (`docs/PHASE11_2022_POSSESSION_INVESTIGATION.md`); not a defect, not
  repaired, 2022's pipeline output is byte-identical to pre-Phase-11.
- **UNCHANGED**: 2022, 2025, 2026 in every layer this audit checked. 2026
  carries one pre-existing (pre-Phase-11) Phase 3.5 faceoff duplicate,
  unrelated to and unaffected by the Phase 11 duplicate rule.
- **UNEXPECTED_REGRESSION**: none found.

## Reproducibility note on "before" values

This repository had no committed snapshot boundary at the start of Phase 11
(Phase 5-10 work was itself uncommitted). "Before" values in this audit are
Phase 10's own published, validated figures
(`docs/2023_POSSESSION_REPAIR.md` Section 5/8, and the pre-Phase-11 frozen
possession counts that `tests/test_phase10.py` and `pll_validate_phase10.py`
asserted prior to this phase's edits — visible in this session's diff to both
files) — not a re-derived guess. Every "after" value in this document was
independently recomputed from the rebuilt canonical layer, not copied from
Phase 10's prediction, and the two agree exactly where Phase 10 made a
prediction (Section 8's blast-radius table).
