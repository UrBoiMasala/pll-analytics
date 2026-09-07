# Validation Methodology (Phase 3.5)

How the 2026 PLL dataset is cleaned, validated, and classified. Reproducible
and conservative by design: every rule here was derived from evidence found
by hand in the raw JSON, verified against the official PLL box score, and
checked for false positives across the full season before being trusted.

## Raw vs. cleaned philosophy

Two layers, strictly separated:

1. **Raw layer** (`data/raw/2026/<slug>/*.json`) — PLL's API responses,
   byte-for-byte, never modified, never deleted. This is ground truth for
   "what did PLL's API actually return."
2. **Cleaned/processed layer** (`data/processed/2026/*.csv`) — every raw
   field is preserved unchanged alongside new, clearly-named derived
   columns. Nothing is renamed or overwritten in place — e.g.
   `home_score_raw` sits next to `home_score_corrected`; `event_type` is
   never reinterpreted (no `event_type_cleaned` exists, because event_type
   itself is never modified — validity concerns live entirely in the
   `is_valid_*`/`is_duplicate_*` flag columns, per the rule "don't create a
   duplicate column for a field that hasn't actually changed").

No row is ever deleted from `events.csv` for being suspicious. Anomalies
are flagged; exclusion, if ever needed, happens by filtering on a flag in a
downstream analysis-specific view.

## Cleaning rules (`scripts/pll_pbp_clean.py`)

### Goal validation (`is_valid_goal`)
A `goal` event is valid only if: (1) its score delta matches its
`shot_type`'s point value (1 or 2) on exactly one side, (2) `description`
is non-empty, (3) `shot_saved` is not `True`. Any goal failing this is
flagged invalid (never deleted) with a `goal_invalid_reason`. Verified: in
every one of the 51 completed games, reconstructing the running score from
`pregame`/`gameEnd`/`shot`/valid-`goal` events only reproduces the official
final score exactly.

### Penalty validation (`is_valid_penalty`)
A `penalty` event is valid only if `penalty_length_sec` is not null. One
malformed event per season observed so far (null length, near-empty
description).

### Score reconstruction (`home_score_corrected`/`away_score_corrected`)
The raw `homeScore`/`visitorScore` fields are placeholder values (observed
to equal the eventual final score) on `faceoff`/`groundball`/`turnover`/
`penalty`/`shotclockexpired` events — confirmed systemic across all 51
games. Corrected scores forward-fill from `pregame`/`gameEnd`/`shot`/valid-
`goal` events only. Raw fields are always preserved alongside.

### General-purpose duplicate detection (`is_duplicate_event`)
A single rule, applied uniformly to every event type: an event is flagged
as a likely duplicate only when it matches the **immediately preceding**
event of the same `event_type` in the raw stream (any other event type in
between resets the check — strict adjacency, not "same clock somewhere in
the game") on ALL of: identical `team_id`, identical top-level
`description` text, identical `period`, clock (`seconds_passed`) within 1
second. This single description-based rule was checked against all 51
games across every event type (including `shot`/`goal`/`shotclockexpired`/
`pregame`/`gameEnd`, never checked individually before) and reproduces
exactly what four separate field-specific rules had found by hand: 22
turnover pairs, 10 groundball pairs, 3 penalty pairs, 1 faceoff pair — zero
new occurrences anywhere else. Two distinct events that merely share a
clock (legitimate — multiple things can happen in the same second) are
never flagged; only exact content matches are. `is_duplicate_groundball`/
`_turnover`/`_faceoff`/`_penalty` are the same flag, filtered per type, kept
for backward compatibility. Rows are never dropped.

### Shot-type derived flags (`is_two_point_attempt`, `is_man_up_shot`)
Deterministic from `shot_type`, verified against every value seen all
season (`1_PT`, `2_PT`, `MU`, `MU_2_PT` — no others):

| shot_type | is_two_point_attempt | is_man_up_shot |
|---|---|---|
| 1_PT | False | False |
| 2_PT | True | False |
| MU | False | True |
| MU_2_PT | True | True |

## Game classification

PLL's own `seasonSegment` field (from the schedule endpoint) is the
authoritative source — not slugname pattern-matching:

| seasonSegment | game_type | is_playoff | is_all_star | include_in_league_analytics |
|---|---|---|---|---|
| `regular` | regular_season | False | False | **True** |
| `post` | playoffs | True | False | **True** |
| `allstar` | all_star | False | True | **False** |

`teams.csv` additionally carries `is_all_star_team` (a team_id that only
ever appears in an all-star-classified game) so team-level baselines can
exclude the 2 all-star squads (ASE, ASW) without touching game-level logic.
All-star games/teams are never deleted — only flagged for exclusion from
league-analytics aggregates.

`games.csv` includes **every** scheduled game (54, not just the 51
completed) — `is_completed` distinguishes them, and no play-by-play/box-
score data is ever fetched for a not-yet-played game.

## Validation status definitions

For each (game, metric) pair, `data/processed/2026/validation_report.csv`
carries `raw_value` (computed with no cleaning applied), `cleaned_value`
(after applying the flags above), and `official_value` (from `teams_stats`,
filtered to the two teams that actually played that game — see the phantom-
team-row issue in `FULL_SEASON_ANOMALIES.md`).

- **`raw_status`/`cleaned_status`**: `PASS` if that value matches official
  exactly, else `MISMATCH`.
- **`final_status`**:
  - **`PASS`** — cleaned value matches official exactly.
  - **`KNOWN_DATA_ISSUE`** — cleaned still mismatches, but for THIS
    specific game+metric, cleaning actually found and excluded something
    (`cleaned_value != raw_value` — i.e. a duplicate or invalid event was
    genuinely detected here) and the residual is within a magnitude cap
    drawn from what was actually observed and investigated (ground_balls/
    turnovers ≤3, faceoff_wins ≤2, penalties ≤5; `caused_turnovers` is an
    unconditional structural issue since `causedTurnoverId` is always null
    by construction, not evidence-dependent).
  - **`UNRESOLVED`** — cleaned still mismatches and there is no supporting
    evidence for THIS specific game: either no duplicate/invalid event was
    found and excluded here at all, or the residual exceeds the
    investigated magnitude cap. **Critically, this status is never
    downgraded to KNOWN_DATA_ISSUE merely because the metric name matches
    a game elsewhere that does have a documented cause** — each game+metric
    is judged on its own evidence, not by association. This is a
    deliberate correction from an earlier, looser Phase 3 draft that had
    classified several evidence-free residuals as "known" simply because
    other games with the same metric had a real explanation.

`goals_with_pre_shot_pass` is a **diagnostic-only** row (not built or
reported as an analytics product) that cross-checks how often a valid
goal's `shotAssistId` is populated against the official `assists`
box-score stat, purely to sanity-check the field's behavior — it is never
to be read as "assists" and no assist statistics are calculated from it.

## Known unresolved discrepancies (as of this hardening pass)

42 (game, metric) pairs are genuinely `UNRESOLVED` — see
`FULL_SEASON_ANOMALIES.md` for the full list and further detail. In
summary: small (±1, occasionally ±2) residuals in `turnovers` (14 games)
and `ground_balls` (15 games) where no specific duplicate event was found
in that game; `shot_clock_expirations` (5 games, always +1, no duplicate
mechanism ever found for this event type); `saves` (1 game, 2026-ev-8, no
mechanism found); and `penalties` in 2026-ev-45 (+1, no duplicate found —
distinct from the well-explained 2026-ev-38/2026-ev-42 penalty cases).

## Reproducing this pipeline

```
python3 scripts/pll_ingest_season.py       # fetch/refresh raw JSON (resumable)
python3 scripts/pll_build_tables.py        # build games/teams/players/events/*_game_stats.csv
python3 scripts/pll_validate_season.py     # build validation_report.csv
python3 scripts/pll_integrity_checks.py    # print season-wide integrity summary
```
