# PLL Play-by-Play Event Schema

Derived from 6 games (2026-ev-1, 2026-ev-9, 2026-ev-24, 2026-ev-34, 2026-ev-41,
2026-quarterfinals-1; 1,369 total events) pulled from
`GET /api/v4/games/{slug}/play-by-plays`. Field population percentages below
are computed across all 6 games combined, per event type.

Every event carries these fields regardless of type: `markerId` (event id),
`eventType`, `period`, `minutes`/`seconds` (clock remaining in period),
`secondsPassed` (elapsed game time), `teamId`, `description`, `homeScore`/
`visitorScore` (see **Score field caveat** below), and a `details` object
(only ever non-empty for `shot`/`goal`).

Nine event types were observed; no new ones appeared beyond what game 1
showed. One new `shotType` value appeared in the 6-game sample:
`MU_2_PT` (man-up 2-point goal), alongside `1_PT`, `2_PT`, `MU` (man-up
1-point goal) from game 1.

---

## `pregame` (6 events, 1/game)

- **Always populated:** clock (12:00), score (0-0), description ("Game Start"), win probabilities.
- **Never populated:** teamId, all player IDs.
- **Interpretation:** synthetic marker opening the event stream.
- **Possession:** N/A.
- **Data-quality issues:** none.

## `faceoff` (167 events)

- **Always populated:** teamId (winner's team), `faceoffWinnerId`, `faceoffLoserId`, description, win probabilities.
- **Sometimes populated:** `gbPlayerId` (80.2%) — the faceoff winner immediately recovering the ball is folded into the *same* event rather than requiring a separate `groundball` event.
- **Interpretation:** faceoff result; team + both participants are 100% attributable.
- **Possession:** **starts** possession for the winning team (unless the ball is contested/out of bounds, which the feed doesn't distinguish beyond the following events).
- **Data-quality issues:** none found.

## `groundball` (390 events)

- **Always populated:** teamId, `gbPlayerId`, description.
- **Interpretation:** loose-ball recovery by a named player.
- **Possession:** **continues or starts** possession for the recovering player's team (offensive rebound if same team just shot, defensive change if opposing team).
- **Data-quality issues:** **duplicate logging.** In 2026-ev-1, two scramble situations produced 2–3 near-identical `groundball` events for the *same player* within the same or adjacent second (Ryan Stines x3, Aidan Danenza x2). Verified real (not a parsing artifact) — box-score `groundBalls` totals confirm the true count is lower. See `is_duplicate_groundball` cleaning rule. Only 2026-ev-1 was affected among the 6 games; a small (+1) residual gap between deduped pbp counts and the box score persisted in 3/6 games even after conservative deduplication — see the Phase 2 validation report.

## `shot` (367 events — non-scoring attempts only; goals are a separate type)

- **Always populated:** teamId, `shotType` (`1_PT`/`2_PT`), `shooterId`, `goalieId`, description, `details.shotOnGoal`, `details.shotSaved`.
- **Sometimes populated:** `shotAssistId` (42.0% — the passer on the attempt, whether or not it scores; not strictly a "scoring assist"), `details.saveType` (`clean`/`messy`, 41.7% — populated exactly when `shotSaved==True`), win probabilities (99.5%, missing on 2 of 367).
- **Interpretation:** every non-scoring shot decomposes into exactly one of 3 outcomes via `details`: `shotSaved=True` → goalie save (100% consistent with description containing "Save by"); `shotOnGoal=True, shotSaved=False` → on frame but not saved/scored (4.1%, 15/367 — plausibly hit iron; feed gives no further detail); `shotOnGoal=False, shotSaved=False` → wide/missed entirely.
- **Possession:** **ends** possession only when followed by an opposing groundball (rebounds can continue the same team's possession — see `groundball`).
- **Data-quality issues:** none beyond the shared score-field caveat.

## `goal` (145 events)

- **Always populated:** teamId, `shotType`, `shooterId`, `goalieId` (goalie who conceded), description (99.3%), win probabilities.
- **Sometimes populated:** `shotAssistId` (48.3% — unassisted goals have none), `details.*` (0.7% — see anomaly below).
- **Interpretation:** a scoring play. Point value from `shotType`: `1_PT`/`MU`→1pt, `2_PT`/`MU_2_PT`→2pt. `MU`/`MU_2_PT` also indicate the goal was scored on a man-up/power-play possession.
- **Possession:** **ends** possession (ball goes back to the other team).
- **Data-quality issues:** **do not trust `eventType=="goal"` alone.** One event in 2026-ev-1 (`shot-3004600`) had `eventType=="goal"` but was actually a saved shot: empty description, zero score change, and `details.shotSaved==True`. Validated with the `is_valid_goal` rule (score-delta match + non-empty description + `shotSaved != True`); reconstructing the running score using only validated goals reproduces the official final score exactly in all 6 games. Occurred in only 1 of 6 games / 1 of 145 raw "goal" events.

## `shotclockexpired` (48 events)

- **Always populated:** teamId, description ("Shot Clock Violation.").
- **Sometimes populated:** win probabilities (91.7%).
- **No player IDs at all** — team-level only.
- **Interpretation:** offensive team failed to shoot in time.
- **Possession:** **ends** possession — always immediately followed by a `turnover` event for the same team/moment (structurally redundant pair; treat as one real-world event when reconstructing possessions).
- **Data-quality issues:** small (+1) unexplained residual vs. official `shotClockExpirations` box-score total in 1 of 6 games (2026-ev-41); root cause not isolated.

## `turnover` (213 events)

- **Always populated:** teamId (team that turned it over), description ("Turnover by XXX").
- **Sometimes populated:** win probabilities (77.9% — notably lower than other types; no pattern found explaining which turnovers lack it).
- **Never populated:** `commitedTurnoverId`, `causedTurnoverId` — always null across all 1,369 events in the sample. The player who committed the turnover and any defender who caused it are **not attributable** from the play-by-play feed, even though the box score (`players/stats`, `teams/stats`) tracks both `turnovers` and `causedTurnovers` per player/team.
- **Interpretation:** team-level possession change, cause/player unknown.
- **Possession:** **ends** possession for the named team.
- **Data-quality issues:** persistent, small (+1) discrepancy vs. official box-score `turnovers` total in 4 of 6 games. One case (2026-ev-41) traced to an exact adjacent same-team/same-clock duplicate event (same pattern as the groundball issue). The other 3 (2026-ev-1, 2026-ev-9, 2026-ev-24) could not be isolated to a single anomalous event despite checking for exact-key duplicates, empty team codes, and period-boundary artifacts — flagged as an unresolved, bounded (~3% of events) known issue rather than force-fit a fix.

## `penalty` (27 events)

- **Always populated:** teamId, `commitedPenaltyId`, description.
- **Sometimes populated:** `penaltyLength` (96.3%), `penaltyDescription` (92.6%, the categorized reason — can legitimately be empty on an otherwise well-formed penalty, e.g. 2026-ev-24's `penalty-2007400`).
- **Interpretation:** man-down/man-up situation begins; `penaltyLength` (seconds) + this event's clock gives the man-up window.
- **Possession:** does not itself change possession, but creates a man-up window — watch for `MU`/`MU_2_PT` goals scored inside it.
- **Data-quality issues:** one malformed event (2026-ev-9, `penalty-3012200`) had `penaltyLength=None` and a near-empty description — validated as invalid via `is_valid_penalty` (penaltyLength not null). Excluding it makes the pbp penalty count match the box score exactly; occurred in only 1 of 27 penalty events across the sample.

## `gameEnd` (6 events, 1/game)

- **Always populated:** score (true final), description ("Game End"), win probabilities (100/0 split for the winner).
- **Interpretation:** closes the event stream.
- **Possession:** N/A.
- **Data-quality issues:** none.

---

## Score field caveat (applies to every event type)

`homeScore`/`visitorScore` are only the true **live** running score on
`pregame`, `shot`, `goal`, and `gameEnd` events. On `faceoff`, `groundball`,
`turnover`, `penalty`, and `shotclockexpired` events, the API returns a
placeholder (observed to equal the game's eventual **final** score)
regardless of when in the game the event occurred — confirmed systemic
across all 6 games (each game's untrustworthy-type events show the final
score on 99–100% of occurrences, from the very first play onward). Use
`home_score_corrected`/`away_score_corrected` (reconstructed by the cleaning
pipeline from `pregame`/`shot`/valid-`goal`/`gameEnd` events only), never
the raw fields, for anything score-dependent.

## Possession-reconstruction usefulness (flagged, not built)

Events ranked by how directly they signal a possession boundary:

- **Strong signal, both team+player known:** `faceoff` (start), `goal` (end)
- **Strong signal, team+player known:** `groundball` (continues offense / starts defense, once deduplicated)
- **Strong signal, team known / player unknown:** `turnover`, `shotclockexpired` (end; the pair is redundant — collapse to one)
- **Ambiguous, needs shot outcome:** `shot` (only ends possession if not followed by a same-team `groundball` rebound)
- **Context modifier, not itself a boundary:** `penalty` (creates a man-up window; combine with goal `shotType` to detect PP scores)
- **No explicit signal at all:** end of period — the feed has no "end of quarter, possession still live" marker; a possession alive when `period` increments must be inferred as truncated, not read directly from an event.
