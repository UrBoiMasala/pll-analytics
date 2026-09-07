# Full-Season (2026) Anomaly Log

Compiled after ingesting and validating all 51 completed 2026 games, then
hardened in Phase 3.5 with stricter, per-game evidence-based validation
status. All cleaning is flag-only in the processed layer; raw JSON under
`data/raw/2026/` is never modified. See `VALIDATION_METHODOLOGY.md` for the
full status-classification rules.

## Phase 3.5 reclassification summary

Phase 3 classified a mismatch as `KNOWN_DATA_ISSUE` whenever the *metric*
(e.g. "turnovers") had a documented duplicate-logging mechanism anywhere in
the season, even in games where no duplicate was actually found. Phase 3.5
tightened this: a game+metric is only `KNOWN_DATA_ISSUE` if cleaning
**actually found and excluded something in that specific game**. Applying
this stricter standard:

- **72** (game, metric) pairs remain genuinely `KNOWN_DATA_ISSUE` (down
  from a looser 165 in the original Phase 3 pass).
- **42** (game, metric) pairs are now honestly `UNRESOLVED` — most of these
  were previously mislabeled as "known" simply because another game shared
  the same metric name with a real explanation.
- **653** pairs are exact `PASS`.

Of the original 5 Phase 3 `FAIL` rows specifically: 3 (2026-ev-38 penalties,
2026-ev-42 penalties, 2026-ev-42 faceoff_wins) have concrete, verified
duplicate/malformed events behind them and are `KNOWN_DATA_ISSUE`; 2
(2026-ev-8 saves, 2026-ev-45 penalties) have **no** supporting evidence at
all — cleaning found nothing to flag in either game — and are honestly
`UNRESOLVED`.

## 1. Genuinely unresolved discrepancies (42 total, by metric)

| Metric | # games | Pattern |
|---|---|---|
| `turnovers` | 19 | ±1 (one game ±2), no duplicate found in that specific game |
| `ground_balls` | 16 | ±1 (two games ±2), no duplicate found in that specific game |
| `shot_clock_expirations` | 5 | always +1; no duplicate-logging mechanism has ever been found for this event type, in any game, all season |
| `saves` | 1 (2026-ev-8) | +1; checked for duplicate/adjacent saved-shot events, found none |
| `penalties` | 1 (2026-ev-45) | +1; all 9 raw penalty events in this game are genuinely distinct (different players/times) — no duplicate-logging explanation applies here, unlike the well-understood 2026-ev-38/2026-ev-42 cases |

No root cause was isolated for any of these despite checking exact-key
duplicates, near-miss timing (±2–3s), empty team codes, and period-boundary
artifacts. Most plausibly a mix of (a) near-duplicate scramble events just
outside the 1-second/strict-adjacency matching window, or (b) minor
post-game scorekeeper corrections applied to the official box score that
were never back-propagated to the live play-by-play log. Given the small,
bounded per-game magnitude (never more than 2, out of games with 60–90+
turnovers/ground balls), this does not compromise `events.csv`'s overall
reliability, but it is reported as genuinely unresolved rather than papered
over — per instruction, no aggressive correction is applied without
stronger evidence.

## 2. Exact-duplicate event logging (CONFIRMED mechanism, generalized rule)

The raw feed occasionally logs the identical real-world event twice in a
row under a different `markerId`. A single general rule
(`is_duplicate_event` — see `VALIDATION_METHODOLOGY.md`) now covers every
event type uniformly and was checked against all 9 event types across all
51 games (previously only 4 types had been checked individually):

| Event type | Flagged True | Games affected |
|---|---|---|
| `turnover` | 22 | several, incl. 2026-ev-41 |
| `groundball` | 10 | mostly 2026-ev-1 |
| `penalty` | 3 | 2026-ev-42, partial in 2026-ev-38 (see #3) |
| `faceoff` | 1 | 2026-ev-42 |
| `shot`/`goal`/`shotclockexpired`/`pregame`/`gameEnd` | 0 | none — checked directly, no occurrences found |

## 3. Chaotic multi-penalty incident, only partially resolvable

**2026-ev-38** (period 3, clock 2:35) contains an 11-event penalty burst —
a real bench-clearing incident — with several exact-duplicate sub-clusters
inside it (e.g. "Brett Dobson, 120s, Cross Checking" logged 3 times),
interleaved with genuinely distinct penalties on other players at the
*same* clock stamp. The strict-adjacency dedup rule only catches duplicate
pairs that are immediately consecutive; several duplicate copies here are
separated by a different player's real penalty, breaking the chain. Raw
penalty count 25 vs. official 20; after cleaning, `cleaned_value` = 23
(residual of 3, `KNOWN_DATA_ISSUE` — cleaning did find and exclude 2 exact
duplicates here, so there is real evidence, just not a complete fix). A
looser "match anywhere within the same clock stamp" rule could likely close
this gap further but was deliberately **not implemented** — it risks false
positives on legitimate multi-player incidents league-wide and is
unvalidated.

2026-ev-42 shows a smaller (1-event) version of the same class of issue,
also `KNOWN_DATA_ISSUE`. 2026-ev-45's penalty residual is a **different,
unexplained** situation — see #1.

## 4. Phantom third team in `teams_stats`

**2026-ev-46** (WAT vs. WHP) and **2026-ev-47** (WAT vs. ATL) — both
involving the Waterdogs, played the same week — have `teams_stats`
endpoints that return **3 team rows instead of 2**, including a team that
did not play in that game. In ev-47, the two real teams' own stat values
are additionally corrupted (WAT shows 16 goals vs. 18 true per
`game_meta`). This is a PLL backend bug — `game_meta` and the play-by-play
itself remain internally consistent for both games. The validation
pipeline filters `teams_stats` rows to only the two teams listed in
`game_meta` before summing official totals (`team_stats_row_count` rows,
`KNOWN_DATA_ISSUE`).

## 5. Confirmed-generalized issues from Phase 2 (no new behavior)

- **Mislabeled `goal`** (`is_valid_goal`): 1 case across the full season
  (1,139 raw "goal" events → 1,138 valid), same rate as Phase 2's single
  case (2026-ev-1).
- **Placeholder raw scores**: confirmed systemic across all 51 games;
  `home_score_corrected`/`away_score_corrected` reconstructs correctly in
  every game (zero non-monotonic or final-score-mismatched corrections).
- **Malformed `penalty`** (null `penaltyLength`): 1 case across the season
  (285 raw → 284 valid), consistent with Phase 2.
- **Structurally always-null fields** (`commitedTurnoverId`,
  `causedTurnoverId`, `offenseGoalieId`, `assistOpportunityPlayerId`,
  `closestDefenderId`): confirmed null across all 11,254 events, all 51
  games. `causedTurnovers` therefore remains unattributable at the event
  level league-wide.

## 6. Non-issues ruled out during integrity checking

- **Overtime periods (period 5)**: 2026-ev-24, 2026-ev-35, 2026-ev-42 went
  to OT — not a data problem, an early integrity check's assumption was
  corrected.
- No duplicate `game_id`, no duplicate `event_id` within any game, no
  empty play-by-play feeds, no games missing player or team stats, **0
  unresolved player IDs and 0 unresolved team IDs** anywhere in the season
  (verified directly against raw JSON fields, not just normalized columns
  — see `DATASET_2026.md`).
