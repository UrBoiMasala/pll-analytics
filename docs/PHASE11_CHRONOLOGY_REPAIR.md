# Phase 11 — Canonicalizing the 2023/2024 Faceoff-Chronology Repair

Phase 10 (`docs/2023_POSSESSION_REPAIR.md`) diagnosed and repaired a feed
ordering defect but deliberately left the canonical layer untouched, publishing
the repair alongside it as `possessions_repaired.csv` and recommending, in its
own Section 8, that "Phase 11 adopt V2_direct_and_timing into the canonical
layer... in a commit that does nothing else." This document records that
adoption.

## 1. Recomputed counts — **OBSERVED**

Recomputed from raw, independent of Phase 10's claimed numbers, using
`pll_phase10_possession_repair.detect_faceoff_order_defects` run over the
production event set (`pll_phase10_possession_repair.py`, unedited detection
logic apart from the duplicate-classification fix in
`docs/PHASE11_DUPLICATE_FACEOFF.md`):

| Season | DIRECT | DIRECT_TIMING | STRONGLY_INFERRED | UNRESOLVED | Applied |
|---|---|---|---|---|---|
| 2022 | 0 | 0 | 9 | 0 | 0 |
| 2023 | 199 | 57 | 26 | 9 | 256 |
| 2024 | 1 | 0 | 1 | 9 | 1 |
| 2025 | 0 | 0 | 1 | 0 | 0 |
| 2026 | 0 | 0 | 3 | 1 | 0 |

The 2023 counts (199/57/26/9, 291 total, 256 applied) match Phase 10's
published figures exactly — confirmed, not assumed. 2024's STRONGLY_INFERRED
count fell from Phase 10's reported 4 to 1 because 3 of those 4 are, on
closer evidence, DUPLICATE_FACEOFF_EVENT (see the duplicate-faceoff doc); this
is an evidence-classification correction, not a change to the reorder rule.

## 2. What changed in the codebase

- **`scripts/pll_chronology_repair.py`** (new): `repair_game_chronology(df)`
  applies the classification Phase 10 validated — imported from
  `pll_phase10_possession_repair.detect_faceoff_order_defects`, never
  reimplemented — to one game's cleaned event frame. Only `DIRECT` and
  `DIRECT_TIMING` are applied (Phase 10's own primary variant,
  `V2_direct_and_timing`); `STRONGLY_INFERRED` remains classified but
  unrepaired, matching Phase 10's own reasoning that its direction is argued
  (INFERRED) rather than proven (OBSERVED).
- **`scripts/pll_build_tables.py`**, `build_events_table`: calls
  `repair_game_chronology` (and `flag_duplicate_faceoffs`, see the companion
  doc) on each league-analytics game's event frame immediately after
  `pll_pbp_clean.clean()`, before `is_analysis_eligible_event` is computed.
  This is the earliest point in the canonical pipeline with everything the
  classification needs, and it is upstream of every consumer (possession
  reconstruction, Phase 5-10 stat layers) — none of them need to know a
  repair happened.
- All-star games are explicitly excluded from repair (matching the scope
  Phase 10's own classification was validated against, `include_in_league_
  analytics`) — their event order is never consumed by any possession/stat
  layer, so it is left exactly as the feed sent it.

## 3. Provenance — nothing is silently overwritten

Every game's events now carry, in `events.csv`:

| Column | Meaning |
|---|---|
| `event_number_raw`, `seconds_passed_raw` | the feed's own values, always present, untouched |
| `chronology_evidence_class` | `DIRECT` / `DIRECT_TIMING` / `STRONGLY_INFERRED` / `WEAKLY_INFERRED` / `DUPLICATE_FACEOFF_EVENT` / `UNRESOLVED` / null (not a candidate) |
| `chronology_repair_applied` | `True` only for `DIRECT`/`DIRECT_TIMING` rows whose `event_number`/`seconds_passed` were changed |
| `chronology_repair_rule_version` | `"phase11_chronology_v1"` |

`event_number`/`seconds_passed` themselves become the corrected values on
applied rows; every other row, and every row in a season with zero candidates
(2022, 2025, and all-but-one-sequence of 2026), is untouched. The original
feed order is always recoverable by restoring `event_number`/`seconds_passed`
from the `_raw` columns — this is exactly what
`pll_phase10_possession_repair.load_season()` and
`pll_validate_phase10.py::_eligible()` now do, so both scripts keep
independently re-deriving the classification from the ORIGINAL feed order
even though `events.csv` itself is now canonical-repaired.

## 4. What canonical `possessions.csv` changed to

| Season | Possessions before | Possessions after | Cause |
|---|---|---|---|
| 2022 | 3795 | 3795 | unchanged (zero candidates) |
| 2023 | 4460 | 4204 | 256 DIRECT/DIRECT_TIMING repairs |
| 2024 | 4047 | 4001 | 1 DIRECT repair (-2) + 36 duplicate faceoffs excluded (-44, see companion doc) |
| 2025 | 4009 | 4009 | unchanged (zero candidates) |
| 2026 | 4388 | 4388 | unchanged (zero candidates) |

Total points and total goals are unchanged in every season (verified,
`pll_validate_phase10.py` check 23 and `phase11_before_after_audit.csv`) — the
repair only reorders/retimes existing events, and duplicate exclusion only
ever removes a faceoff, never a goal. Zero of 40 team-season offensive-
efficiency ranks move.

## 5. Verification against Phase 10's own repaired layer

The canonical rebuild reproduces `possessions_repaired.csv` exactly for 2023
(4204 possessions, identical sums of duration/goals/points/shots/turnovers).
2024 differs from `possessions_repaired.csv` by design: that file only ever
applied the chronology reorder (V2), never the duplicate-faceoff exclusion —
canonical `possessions.csv` now applies both. See
`docs/PHASE11_DUPLICATE_FACEOFF.md` for that delta.

## 6. What did NOT change

Per the Phase 11 brief's explicit constraints, and verified by
`pll_validate_phase10.py` (24/24 PASS, re-run against the canonical layer) and
`tests/test_chronology_repair.py`: event existence, player identity, team
identity, event outcome, score value, goal value, faceoff winner, ground-ball
attribution, and every timestamp not on a repaired faceoff row.
