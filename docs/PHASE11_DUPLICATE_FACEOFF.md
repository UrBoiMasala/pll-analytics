> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Phase 11 — The 2024 Duplicate-Faceoff Defect

## 1. Correcting the Phase 10 claim — **OBSERVED**

`docs/2023_POSSESSION_REPAIR.md` Section 9 claimed "33 such pairs exist in 4
games of 2024, and one in 2023." Recomputed from raw and independently
cross-checked (a raw-JSON pairwise scan across every game 2022-2026, and a
from-scratch reimplementation of the classification rule), both counts are
wrong:

- **True count: 36 pairs, in exactly 3 games** — `2024_game_10`,
  `2024_game_12`, `2024_game_31`. No 4th 2024 game has a matching pair.
- **The "one in 2023" claim does not hold.** The nearest 2023 candidate
  (`playoffs-quarterfinal-3-2023-9-1`, two faceoffs between the same two
  players 10 seconds apart) is two independently-evidenced REAL faceoffs —
  each has its own valid companion ground ball and its own distinct goal —
  not a duplicate. It is now a regression test
  (`tests/test_duplicate_faceoff.py::test_two_distinct_real_faceoffs_between_the_same_two_players_are_not_flagged`)
  specifically because an earlier, looser version of this rule flagged it
  during development and had to be tightened.
- **3 of the 36 pairs were previously misclassified as `STRONGLY_INFERRED`**
  by Phase 10's own detector, because that draw carries no ground-ball tag on
  either copy, and the original rule could only find a duplicate by first
  locating a companion ground ball. Root cause and fix below.

## 2. The defect

The feed logs the same faceoff twice: once mis-stamped with the PRECEDING
goal's own clock and placed before that goal in array order, once correctly,
immediately after the goal. Both copies agree on team, winner, loser and
declared ground-ball recoverer (`gb_player_id` on the faceoff row itself,
including both being untagged). Canonical example (`2024_game_10`, period 1):

```
markerId 1000  151s  CHA faceoff  N.Rowlett (vs M.Sisselberger)  GB J.Rowlett
markerId  900  151s  ARC GOAL     M.O'Keefe
markerId 1100  158s  CHA faceoff  N.Rowlett (vs M.Sisselberger)  GB J.Rowlett   <-- identical
markerId 1200  158s  CHA groundball  J.Rowlett
```

Raw-JSON comparison of matched pairs found zero field differences beyond
`markerId`, the clock fields, and the independently-known-unreliable
`homeScore`/`visitorScore` placeholders — consistent with a re-transmitted
record, not two real draws.

## 3. Why the existing Phase 3.5 rule misses it, and why it must not be loosened

`pll_pbp_clean._flag_duplicate_same_type` requires (a) strict raw adjacency —
any differently-typed event between two same-type candidates resets its
tracking, and a goal always intervenes here — and (b) a clock difference of
at most 1 second, where these pairs differ by up to 7s. Both conditions are
true of what that rule was built to catch (22 turnover pairs, 10 groundball
pairs, 3 penalty pairs, 1 faceoff pair, validated against all 51 2026 games)
and both are false of this pattern.

Loosening that rule (allow one intervening event, widen clock tolerance to
10s) was tested directly: it sweeps in 89 new pairs across every event type
and season — 35 faceoff, 33 groundball, 18 shot, 4 turnover — almost all
legitimate repeated plays with coincidentally similar descriptions. **The
general rule must not be loosened.** The fix is a new, faceoff-specific rule
with no analog for other event types.

## 4. The rule — **DIRECT** evidence, generic, not keyed to any game/event ID

Reuses `pll_phase10_possession_repair.detect_faceoff_order_defects`'s existing
per-sequence classification (imported, not reimplemented — the same function
`pll_chronology_repair.py` uses for the reorder repair). A faceoff at array
index `i` is the phantom copy of the faceoff `k` immediately following the
next goal when ALL of:

1. `i`'s own markerId sequence number is greater than the following goal's —
   the feed's own order contradicts array position (`seq_inverted`).
2. `k` is the event immediately after that goal (`k = j + 1`, exact
   adjacency — not a window search).
3. `k` is itself a `faceoff` with **full content identity** to `i`: same
   `team_id`, `player_id` (winner), `secondary_player_id` (loser),
   `gb_player_id` (declared recoverer, including both being untagged), and
   `period`.

### The bug that caused the 3 missed cases, and the fix

The original rule (`duplicate_copy` in `detect_faceoff_order_defects`) found
`k` by first searching for `i`'s companion ground ball (`gb_j`) and then
looking for a matching faceoff between the goal and `gb_j`. When neither copy
carries a `gb_player_id` tag, `gb_j` is never found, so the duplicate check
never ran and the sequence fell through to `STRONGLY_INFERRED`. The fix
checks position `k = j + 1` directly, independent of whether a companion
ground ball exists for either copy.

### The false positive found and rejected during development

An earlier version of this rule matched on `team_id`/`player_id`/
`secondary_player_id`/`period` alone (no `gb_player_id`), searched a small
window rather than the exact next position, and produced 34 false positives
in 2023 alone — genuine, independently-evidenced DIRECT sequences 10 seconds
apart between the same two players, misread as duplicates of each other.
Requiring **exact position `j+1`** and **`gb_player_id` equality** (including
both-null) eliminates every one of those false positives while still catching
all 36 confirmed real duplicates. Both the false-positive case and the
missed-case fix are permanent regression tests
(`tests/test_duplicate_faceoff.py`).

## 5. What the module does

`scripts/pll_duplicate_faceoff.py`, `flag_duplicate_faceoffs(df)`: flags the
phantom copy `is_duplicate_event`/`is_duplicate_faceoff = True` (OR-merged
into whatever Phase 3.5 already set — never unset, never dropped). The row
remains in `events.csv`, fully preserved, excluded from
`is_analysis_eligible_event` exactly like any other confirmed duplicate.
`duplicate_faceoff_pair_id` records which authoritative faceoff it duplicates,
for audit. Runs before `pll_chronology_repair.py` in
`pll_build_tables.build_events_table`, since the duplicate rule keys on the
raw array position immediately after a goal.

## 6. Run across all seasons, 2022-2026 — **OBSERVED**

| Season | Confirmed duplicates | Games |
|---|---|---|
| 2022 | 0 | — |
| 2023 | 0 | — |
| 2024 | 36 | `2024_game_10`, `2024_game_12`, `2024_game_31` |
| 2025 | 0 | — |
| 2026 | 0 (1 unrelated pre-existing Phase 3.5 faceoff duplicate, unaffected by this rule) | — |

Zero false positives against the full corpus (every flagged row's paired
partner is independently verified never itself flagged — see
`tests/test_duplicate_faceoff.py::test_legitimate_repeat_faceoffs_are_not_swept_up_anywhere`).

## 7. Downstream effect

2024 canonical `possessions.csv`: 4047 → 4001. Of the 46-possession drop, 2
are attributable to the 1 chronology (DIRECT) repair in 2024 and 44 to the 36
duplicate-faceoff exclusions (a phantom faceoff can both end the prior
possession early and start a spurious one, so removing it merges boundaries
rather than 1:1 with pair count). Total points, total goals, and every other
event type's count are unchanged.
