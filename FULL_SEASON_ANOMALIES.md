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
  from a looser 165 in the original Phase 3 pass) — **70** as of the Phase
  4.25 refresh, purely because the 2 `team_stats_row_count` diagnostic
  rows for 2026-ev-46/2026-ev-47 no longer exist once `team_game_stats.csv`
  is participant-filtered at build time (§4); no game/metric actually
  changed status.
- **42** (game, metric) pairs are now honestly `UNRESOLVED` — most of these
  were previously mislabeled as "known" simply because another game shared
  the same metric name with a real explanation. Still 42 after the Phase
  4.25 refresh (§7) — the underlying raw event data is unchanged, and the
  deeper investigation in §7 found real, extra evidence for why several of
  these remain unresolved rather than closing any of them.
- **653** pairs are exact `PASS`, unchanged.

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
did not play in that game:

- **2026-ev-46**: real participants are WAT (home, 11 goals) and WHP (away,
  9 goals), matching `game_meta` (`homeScore=11`, `visitorScore=9`) exactly.
  The phantom row is **ATL** (2 goals, 7 shots) — a team that did not play
  in this game at all, and whose stat line is not all-zero (it looks like a
  stray row from a different ATL game bleeding into this response, not a
  blank placeholder).
- **2026-ev-47**: real participants are WAT (home, 16 goals) and ATL (away,
  9 goals), matching `game_meta` (`homeScore=18`, `visitorScore=10` — see
  below on the goals/points distinction) exactly. The phantom row is
  **WHP** with an all-zero stat line (0 goals, 0 shots, 0 everything) — a
  team that did not play in this game.

**Correction (Phase 4.25): WAT's "16 goals" in ev-47 is not a corrupted
value and is not inconsistent with the true final score of 18.** A prior
version of this document read WAT's 16 raw `goals` against `game_meta`'s
`homeScore` of 18 and called the stat line corrupted. That comparison was
wrong on its own terms: PLL awards 2-point goals (see `shot_type` in
`{2_PT, MU_2_PT}`), so **goals** (a count of scoring plays) and **points**
(the score, weighting each goal by 1 or 2) are two different quantities by
design, not two measurements of the same thing. WAT's own `teams_stats` row
for ev-47 carries `onePointGoals=14`, `twoPointGoals=2` — 14+2 = **16
goals** (matches the `goals` field exactly) and 14×1 + 2×2 = **18 points**
(matches `homeScore` exactly). ATL's row (`onePointGoals=8`,
`twoPointGoals=1`) reproduces `visitorScore=10` the same way (8+1=9 goals,
8+2=10 points). Both teams' `teams_stats` rows in ev-47 are fully internally
consistent with `game_meta` once one-point vs. two-point goals are
accounted for — there is no corruption in WAT's or ATL's own stat lines in
either game, only the unrelated phantom third row.

This is a PLL backend bug (an extra, wrong team folded into the
`teams_stats` response) — `game_meta` and the play-by-play itself remain
internally consistent for both games, and so does each real participant's
own `teams_stats` row. As of Phase 4.25, this is handled one layer earlier
than before: `pll_build_tables.build_team_game_stats` filters
`team_game_stats.csv` itself to the two `game_meta` participants for every
game (not just at validation time), routing every rejected/phantom row into
`data/processed/2026/team_game_stats_exceptions.csv` with an explicit
reason, and a hard structural check enforces exactly 2 distinct participant
teams and a unique `(game_id, officialId)` key for every completed game
(see `DATASET_2026.md`). `pll_validate_season.py`'s own `teams_stats`
filtering (`team_stats_row_count`, `KNOWN_DATA_ISSUE`) is now a second,
redundant check against an already-clean table rather than the only place
the phantom rows are excluded.

## 5. Confirmed-generalized issues from Phase 2 (no new behavior)

- **Mislabeled `goal`** (`is_valid_goal`): 1 case across the full season
  (1,139 raw "goal" events → 1,138 valid), same rate as Phase 2's single
  case (2026-ev-1, marker `shot-3004600`). This event is a real saved shot
  (`shot_saved=True`, `shot_on_goal=True`, empty description, zero score
  change), not a goal — `is_valid_goal=False` and it is correctly excluded
  from every goal/scoring aggregation. **Phase 4.25 correction:** prior to
  Phase 4.25, it was also excluded from `is_analysis_eligible_event`
  entirely (the general "safe to build metrics from" flag), which silently
  dropped this legitimate shot/save from any shot- or save-denominated
  metric built on that flag (including possession `shot_attempts`/
  `shots_on_goal`). It is now kept eligible — its `shot_outcome` ("saved")
  is preserved and counted normally — while `is_valid_goal=False` still
  keeps it out of goal/points counts. See `DATASET_2026.md` and
  `pll_build_tables.build_events_table`.
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

## 7. Phase 4.25 deeper investigation of the 42 unresolved discrepancies

Recomputed from the Phase 4.25 live-refresh data (raw content identical to
the prior extraction for all 51 games — see `PHASE_4_25_REPORT.md` — so the
counts below are unchanged: still 42 `UNRESOLVED`, now 70 not 72
`KNOWN_DATA_ISSUE` purely because the 2 `team_stats_row_count` rows for
2026-ev-46/2026-ev-47 no longer exist — `team_game_stats.csv` is now
participant-filtered at build time, see §4).

**Team-level check (no cancellation found).** Every unresolved/known-issue
`turnovers`/`ground_balls`/`shot_clock_expirations` game-level residual was
re-derived by summing the two participant teams' own pbp-vs-official
differences separately, per the Phase 4.25 brief's "opposite errors can
cancel when summed" instruction. Result: **zero cases** where a whole-game
`PASS` (diff 0) hides a nonzero per-team split (e.g. +1/-1). Every nonzero
team-level diff found is a strict subset of an already-flagged whole-game
residual, and where a residual involves both teams (2026-ev-6/-28/-35/-42/
-43, 5 cases) both teams' diffs point the **same** direction (adding up to,
not cancelling into, the game-level total) — so no additional hidden error
exists beyond what game-level totals already show.

**Turnovers/shot-clock-expirations: description carries no real signal —
confirmed, not just asserted.** Inspected raw events directly:
`turnover`/`shotclockexpired` descriptions are always the fixed strings
`"Turnover by <TEAM_CODE>"` / `"Shot Clock Violation."` — identical for
every event of that type by the same team, all game, all season (there is
no player field at all — `commitedTurnoverId` is confirmed always null).
This means the general dedup rule's "identical description" condition adds
*zero* discriminating power for these two types beyond team_id — the only
real evidence is strict full-stream adjacency + the ≤1s clock window. This
is why these residuals cannot be closed further without risking false
positives, and it's a materially stronger statement than "no duplicate
found" — there is no reliable additional signal to look for.

**Ground balls: a wider timing window was tested and REJECTED with
evidence.** `groundball` descriptions DO carry the recovering player's name
(e.g. `"Groundball picked up by C. Mackesy."`), which is real
disambiguating information the other two metrics lack. Widening the
duplicate-detection window from 1s to 5s (same-player, same-team, strict
full-stream adjacency, same period — otherwise identical to the existing
rule) surfaces 17 additional candidate pairs across the season, and one
of them (2026-ev-42, `groundball-2002500`→`groundball-2002600`, gap 4s,
same player "C. Mackesy", zero other events between them) looks like
exactly the kind of duplicate the existing rule already catches at 1s.
**However, checking all 17 candidates against each game's own official
`groundBalls` total shows 5 of them (2026-ev-4, -8, -12, -21, -22) are
currently exact `PASS` (cleaned already equals official) — treating any of
these as a duplicate would remove a ground ball the official box score
does count, turning a passing game into a new, previously-nonexistent
mismatch.** This is decisive: the same-player/short-gap/no-intervening-
event pattern is not a reliable duplicate signal for ground balls in
general, even though it looks compelling in isolation for ev-42. **No
change was made** to the dedup window — this is a tested-and-rejected fix,
not an untried one; see `tests/test_pbp_clean.py::test_groundball_wider_window_would_introduce_false_positives`
for the regression test asserting this stays untouched.

**Saves (2026-ev-8, +1): isolated to one team, no duplicate found even
after exhaustive checking.** Splitting by defending team: WAT's saves
match official exactly (10=10); the entire +1 residual is on CAN's side
(17 pbp vs. 16 official). All 17 of CAN's saved-shot pbp events were
inspected directly — 17 distinct shooters/timestamps/periods, no two
adjacent, no two within 5 seconds of each other, no repeated
shooter+goalie+timestamp combination. There is no duplicate-logging
artifact here; this looks like a genuine PLL scorekeeping/box-score
compilation gap that cannot be reconstructed from the play-by-play feed.
Remains `UNRESOLVED`, now with a fully documented negative search rather
than an unverified claim.

**Penalties (2026-ev-45, +1): isolated to one team, plus a newly-found
internal inconsistency that doesn't resolve it.** RED's penalty count
matches official exactly (3=3); the +1 residual is entirely CAN's (6 pbp
vs. 5 official). Of CAN's 6 raw penalty events, one
(`penalty-3008900`, period 4, Zach Goodrich) has an internal
**length/description mismatch**: `penaltyLength=120` but the event's own
`description` text reads "30 sec penalty for Cross Checking" — the
duration field and the description's stated duration disagree with each
other. This is a genuine, newly-documented data-quality defect in that one
raw event, but it is NOT the same signature as the confirmed null-length
malformed-penalty rule (`is_valid_penalty`), and there isn't enough
evidence to say PLL's official count of 5 specifically excludes *this*
event rather than one of CAN's other 5 (all of which look completely
well-formed). Recorded here as a documented anomaly; the game's status
stays honestly `UNRESOLVED` rather than guessing which event to drop.
