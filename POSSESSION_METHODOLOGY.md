# PLL 2026 Possession Reconstruction Methodology (Phase 4)

Turns the cleaned, validated event-level play-by-play (`events.csv`, Phases
1–3.5) into a canonical possession-level dataset
(`data/processed/2026/possessions.csv`) via an explicit, deterministic state
machine (`scripts/pll_build_possessions.py`). This document is the
reproducible specification of that machine: another analyst should be able
to read this and reimplement the same possession boundaries from the raw
events.

## Formal definition of a PLL possession

A possession is a maximal, continuous span of one team's offensive control
of the ball, bounded by events that either (a) end that control with strong
evidence (a goal, a turnover, a shot-clock violation, or the opponent
recovering a loose ball) or (b) run into a period/game boundary. A
possession never spans two teams and never spans two periods.

## Why possession reconstruction is necessary

PLL's play-by-play feed is an *event* log, not a *possession* log — it never
states "possession changed here." Advanced metrics planned for later phases
(offensive/defensive efficiency, pace, time of possession, EGA, PTI) are all
possession-denominated, so a trustworthy possession layer has to exist
before any of them can be built. This phase produces exactly and only that
layer.

## Scope

Possessions are built only for games where `games.include_in_league_analytics
== True` (regular season + playoffs; the all-star game is excluded — see
"All-Star exclusion" below), and only from `events.csv` rows where
`is_analysis_eligible_event == True` (excludes exact-duplicate events and
the confirmed-invalid penalty/goal-with-no-salvageable-data flagged in
Phase 3.5/4.25 — see `DATASET_2026.md` "Metric-specific eligibility"). This
reuses the existing eligibility definition rather than inventing a new,
conflicting one, per the Phase 4 brief. As of Phase 4.25, the one
confirmed invalid-goal event (2026-ev-1) that is actually a real saved
shot is included here (its `is_valid_goal == False` still prevents it from
being treated as a scoring goal by `add_shot_or_goal`/the goal-closing
branch — it only ever contributes `shot_attempts`/`shots_on_goal`).

## Evidence base

Every rule below was derived by inspecting real 2026 event sequences before
being encoded, not assumed. Key findings that shaped the design:

- **`seconds_passed` is cumulative game-elapsed time**, monotonically
  non-decreasing across an entire game (verified: 0 games violate this).
  This makes it safe to use directly for duration math.
- **Periods routinely end mid-play**, not just on a goal. Checking what
  precedes every faceoff in the raw stream: faceoffs preceded by something
  other than a goal/`pregame` occur 179 times, but 145 of those are simply
  the first faceoff of a new period following a period that ended on a live
  play (not a goal) — expected and handled by period-boundary truncation,
  not an anomaly.
- **~2.5% of faceoffs (33 of 1,326) occur mid-period without a goal closing
  the prior possession.** Manually inspected: causes include faceoff
  re-draws (two faceoff events back to back, e.g. `2026-ev-42`
  `faceoff-100`→`faceoff-400`), penalty-triggered faceoff restarts (e.g.
  `2026-ev-1` `penalty-2016700`→`faceoff-2017600`), and cases with no
  discernible cause at all. Treated uniformly (see "Faceoff handling").
- **~3% of valid goals (34 of 1,138) are not followed by a faceoff before
  real time passes and another event occurs**, even though real lacrosse
  always re-faceoffs after a goal. This is a genuine missing-event gap in
  the raw feed, not a rule exception — handled explicitly (see "Goal
  handling").
- **A small number of events (5, found by checking every valid goal's
  immediate successor) share the exact same `seconds_passed` as the goal
  that just closed a possession** — these are "companion" log entries (e.g.
  PLL logging a `turnover` for the scored-on team at the same instant as
  the goal) describing the same real-world moment from the other side, not
  a new subsequent event. Suppressed as informational (see "Turnover /
  shot-clock handling").
- **The turnover+shotclockexpired redundancy the brief predicted is real
  and exact**: e.g. `2026-ev-1` `shotclockexpired-2100` and `turnover-2110`
  share `team_id=RED` and the identical `seconds_passed=57`. Generalizing
  the same-instant-companion rule collapses this automatically — no
  special-cased pair-matching was needed.

## State-machine architecture

Implemented as a `Possession` accumulator object plus a per-period event
loop (`build_possessions_for_game` in `scripts/pll_build_possessions.py`).
State is reset at the start of every period (a new period always begins
possession-context-free — the first event is a faceoff, which never
consults prior context). Within a period, the machine tracks:

- `current`: the in-progress `Possession` (or `None` if no possession is
  currently open — a real, valid state, not an error condition)
- `pending`: `{reason, team, seconds_passed}` of the most recently closed
  possession in this period, used to infer why the *next* possession
  starts (or `None` at the very start of a period)
- `possession_number`: a strictly increasing counter, continuous across
  periods within a game

Each event is dispatched by `event_type` to one of the rule blocks below.
Every possession boundary produced has a recorded `start_reason`/
`end_reason` — there is no silent state transition anywhere in the machine.

## Faceoff handling

A completed faceoff always starts a new possession for the winning team
(`start_reason = faceoff_win`, `is_ambiguous = False` unconditionally — a
faceoff's `team_id` is 100% reliable evidence, verified in Phase 3.5: 0
unresolved team IDs, 1,326/1,326 `faceoffWinnerId`/`faceoffLoserId`
resolved).

If a faceoff event arrives while a possession is **still open** (not
independently closed by a goal/turnover/shot-clock/defensive recovery —
the ~2.5% case above), the open possession is force-closed with
`end_reason = ambiguous_control_change`, flagged `is_ambiguous = True` with
an explanatory note, **before** the new faceoff-based possession opens
cleanly. The old possession's ending is genuinely uncertain (something
happened that the feed didn't log); the new one's start is not.

A faceoff-embedded immediate recovery (`gbPlayerId` on the faceoff event
itself, or a separate `groundball` event by the same team right after) does
not change possession — it's the winning team continuing to hold what they
just won.

### Faceoff redraw handling (Phase 4.25)

**Rule**: if the possession about to be force-closed by an incoming
faceoff is itself nothing but its own opening faceoff event
(`start_reason == faceoff_win` and it has exactly 1 event total — no shot,
turnover, or groundball was ever added to it) AND this new faceoff arrives
with **zero other events of any kind in between**, it is closed with
`end_reason = faceoff_violation_redraw`, `is_ambiguous = False` — instead
of the general `ambiguous_control_change` path.

**Evidence**: two faceoff events immediately adjacent in the raw stream,
same period, with literally nothing between them, occur exactly **2 times**
in the full 2026 season (checked directly, not sampled):
`2026-ev-28` `faceoff-3018500`→`faceoff-3019000` (period 4, 31s apart) and
`2026-ev-42` `faceoff-100`→`faceoff-400` (period 1, 14s apart — the very
first faceoff of that game, already called out in the evidence base above).
In both cases the first faceoff's own possession has zero recorded plays —
there is no possession *content* that went unlogged, only an
administrative redo (an offsides call, a violation, a too-many-men
infraction — none of which the feed encodes as its own event type) between
two live-ball draws. Since nothing happened, closing it as
`ambiguous_control_change` overstates the uncertainty: there is no lost
evidence about what the team *did* with the ball (they never got to do
anything), only about *why* a second faceoff was needed, which was never
knowable from this feed regardless of how the possession is labeled.

**Assumptions / why this is narrow**: this does NOT extend to a
groundball-started possession immediately followed by a faceoff (5 such
cases exist this season: `2026-ev-5`, `-23`, `-31`, `-38`, `-40`) — there,
a team demonstrably recovered the ball first (real evidence a possession
existed and who had it), so forcing it closed as an unremarkable "redraw"
would discard genuine information. Those 5 remain `ambiguous_control_change`
as before, correctly, since something real did happen and its resolution
is still unconfirmed.

**Before/after** (`2026-ev-42`, period 1):

| | before | after |
|---|---|---|
| `faceoff-100` possession | `end_reason=ambiguous_control_change`, `is_ambiguous=True` | `end_reason=faceoff_violation_redraw`, `is_ambiguous=False` |
| `faceoff-400` possession | `start_reason=faceoff_win`, `is_ambiguous=False` (unchanged) | `start_reason=faceoff_win`, `is_ambiguous=False` (unchanged) |

**Regression test**: `tests/test_build_possessions.py::TestFaceoffRedraw` —
covers this exact motivating pattern plus two plausible false positives:
(1) a groundball-started possession immediately followed by a faceoff
(must stay `ambiguous_control_change`, not be swept into this rule), and
(2) a faceoff-started possession that saw a real shot before the next
faceoff (must not be treated as an empty redraw).

**Season-wide impact**: possession count unchanged (4,388); ambiguous
count drops by exactly 2, from 1,591 to 1,589 (36.3% → 36.2%) — this is a
narrow, evidence-bounded fix, not a general loosening of the ambiguity
criteria.

## Shot handling

**A shot never itself ends a possession**, per the Phase 4 brief. Every
`shot`/`goal` event where the team matches the currently tracked offense is
simply added to the possession's totals (`shot_attempts`, `shots_on_goal`
via `shot_outcome`). If a shot/goal arrives for a team that does **not**
match the tracked offense (or no possession is open at all), that is
treated as unresolved sequence evidence: the mismatched open possession (if
any) is force-closed as `ambiguous_control_change`, and a new possession
opens for the shooting team using the same context-inference logic as any
other gap-opening (see "Ambiguity policy" below) — always flagged
`is_ambiguous = True` in this path, since a shot with no clean preceding
evidence chain is the weakest form of possession-opening evidence the
model accepts.

## Rebound / offensive ground-ball handling

A `groundball` event where the recovering team already matches the current
possession's offense team is a pure continuation — no boundary, just
accumulates into `ground_balls`. This is what keeps a
shoot→miss→own-rebound→shoot sequence as one possession.

## Defensive ground-ball handling

A `groundball` event where the recovering team differs from the current
open possession's offense team closes the old possession
(`end_reason = defensive_ground_ball`) and immediately opens a new one for
the recovering team (`start_reason = defensive_ground_ball`,
`is_ambiguous = False` — a groundball event's team attribution is as solid
as a faceoff's).

## Turnover / shot-clock-expiration handling

If a possession is open for the team named on the `turnover`/
`shotclockexpired` event, it closes cleanly
(`end_reason = turnover` / `shot_clock_expiration`).

If **no** possession is open for that team, two sub-cases:

1. **Same-instant companion** (this event's `seconds_passed` exactly equals
   the most recently closed possession's closing `seconds_passed`): treated
   as purely informational, no state change. This is what collapses the
   turnover+shotclockexpired redundancy, and also the rarer
   goal-companion-turnover pattern found in the evidence base.
2. **Genuine gap** (real elapsed time since the last close): a **transient
   possession** is opened for this team and immediately closed by this same
   event. This models real, evidenced-but-briefly-held control (a team can
   legitimately gain and lose the ball with no separately logged faceoff or
   groundball in between) rather than discarding the turnover as orphaned.

## Turnover + shot-clock-expiration redundancy

Not special-cased — it falls directly out of the same-instant-companion
rule above, since the two events describing one real transition always
share the identical team and timestamp. Verified season-wide (validation
check #14): zero redundant pairs produced two boundaries.

## Goal handling

A **valid** goal (`is_valid_goal == True`) always closes the scoring team's
possession (`end_reason = goal`) and records `goals`/`points_scored`
(1 or 2, from `shot_type` — see "Two-point scoring" below). **No new
possession is opened for the opponent at this point** — the brief is
explicit that this must wait for real subsequent evidence, normally the
next faceoff.

An **invalid** goal (the one confirmed-mislabeled event, `2026-ev-1`
`shot-3004600`) is a real saved shot, not a scoring play — as of Phase
4.25 it is included in possession construction (it passes
`is_analysis_eligible_event`; see "Scope" above) and contributes normally
to `shot_attempts`/`shots_on_goal` via `add_shot_or_goal`, but
`is_valid_goal == False` means the goal-closing branch (`if et == "goal"
and row["is_valid_goal"] == True: close(...)`) never fires for it — it
neither closes a possession nor contributes `goals`/`points_scored`.
Before Phase 4.25 it was excluded entirely from possession construction
(it failed the then-stricter `is_analysis_eligible_event` filter), which
silently dropped a real shot/save from that possession's totals — see
`DATASET_2026.md` and `FULL_SEASON_ANOMALIES.md` §5.

## Two-point scoring

`points_scored` is computed per goal from `shot_type` via
`{"1_PT": 1, "MU": 1, "2_PT": 2, "MU_2_PT": 2}`, exactly preserving PLL's
scoring (never collapsed to NCAA-style 1-point-only). Verified season-wide:
summing `points_scored` by offense team per game reproduces the official
final score in **all 50** eligible games, with **zero** mismatches — the
strongest single trust signal for this phase.

## Penalty handling

No state effect. A `penalty` event is skipped entirely by the state
machine (`NO_EFFECT_TYPES`) — it neither opens nor closes a possession. It
remains fully present and traceable in `events.csv`; any possession whose
`[start_event_number, end_event_number]` window contains a penalty simply
has it there positionally (see the manual audit example G).

## Man-up context

Not tracked via penalty correlation — instead read directly off
`has_man_up_shot` (any contained shot/goal with `is_man_up_shot == True`,
i.e. `shot_type` in `{MU, MU_2_PT}`), which PLL's feed already asserts
directly and reliably rather than requiring possession-side inference from
penalty timing.

## Period boundaries

Possessions never cross periods — the event loop is grouped by `period`
before processing, and `pending`/`current` state resets at every period
start. If a possession is still open when a period's events are exhausted,
it is closed with `end_reason = period_end`, `is_truncated = True`, using
the last event of that period as the closing reference (duration is
therefore a minimum/lower bound for a truncated possession — the actual
buzzer may have sounded slightly later than the last logged event).

## Overtime handling

No special-casing — periods are processed generically by whatever `period`
value appears (4 regulation quarters, then `period == 5` for sudden-death
OT in the 3 games that reached it: `2026-ev-24`, `2026-ev-35`,
`2026-ev-42`). OT possessions are built with exactly the same rules;
example L in the manual audit shows a real OT possession.

## Game-end handling

If the very last event of the game's final period is `gameEnd` and a
possession is still open (rare — normally the game-winning goal already
closed the last possession cleanly), it closes with `end_reason = game_end`,
`is_truncated = True`. In the normal case (goal → `gameEnd`, no possession
open), nothing is force-closed — confirmed: only 36 of 50 games have a
`game_end`-ending possession, exactly the games where something besides a
clean final goal was live when the clock expired.

## Ambiguity policy

When the machine cannot cleanly explain a boundary from direct evidence
(no faceoff, no direct groundball steal, only weak/absent context), it
never guesses a "most likely" explanation. It falls back to
`start_reason = other_confirmed_control` (team attribution is still solid —
it comes straight from the triggering event's own `team_id` — only the
*mechanism* of how they got the ball is unconfirmed) and sets
`is_ambiguous = True` with a specific, machine-generated note explaining
what evidence was missing. `ambiguous_reason` is never a generic label —
every instance names the actual prior state that failed to resolve
cleanly, so it's directly auditable (see manual audit example N).

**Cascading is expected and correct, not a bug**: if a possession closes
ambiguously, the *next* possession's start-reason inference also cannot
find clean context (since `pending.reason == 'ambiguous_control_change'`
isn't a recognized clean case), so it is also flagged ambiguous. One
underlying data gap can therefore surface as two flagged possessions. This
is intentional — both boundaries genuinely lack independent confirming
evidence.

`start_reason = 'unknown'` is defined in the taxonomy but never actually
used in the 2026 season (validation check #17: 0 occurrences) — every event
type that can open a possession always carries a resolved `team_id`.

## Full start/end reason taxonomy (as actually produced, not the brief's illustrative list)

**Start reasons** (season counts, Phase 4.25 refresh): `faceoff_win`
(1,301), `opponent_turnover` (1,264), `other_confirmed_control` (922,
always `is_ambiguous=True`), `defensive_ground_ball` (561),
`opponent_shot_clock_expiration` (340). `unknown` is defined but unused (0
occurrences).

**End reasons** (season counts, Phase 4.25 refresh): `turnover` (1,352),
`goal` (1,118), `ambiguous_control_change` (838, always
`is_ambiguous=True` on that possession), `defensive_ground_ball` (561),
`shot_clock_expiration` (358), `period_end` (123, `is_truncated=True`),
`game_end` (36, `is_truncated=True`), `faceoff_violation_redraw` (2, always
`is_ambiguous=False` — see "Faceoff redraw handling" above).

## Source-data limitations affecting possession reconstruction

- The ~34 missing-post-goal-faceoff cases and ~33 mid-period unexplained
  faceoff cases (evidence base above) are the primary drivers of flagged
  ambiguity, along with the shot/turnover "conflicting team" cases that
  arise from the same underlying missing-event gaps.
- The 42 `UNRESOLVED` event-count discrepancies documented in
  `FULL_SEASON_ANOMALIES.md` (small turnover/groundball/shot-clock/save
  count residuals vs. the official box score) are not separately re-litigated
  here — they affect a small number of individual events, not the
  possession *structure*, and are inherited as-is.

## Validation methodology

`scripts/pll_validate_possessions.py` runs the 18 checks specified for
Phase 4 against every possession. 17 are hard PASS/FAIL checks; #12
(consecutive possessions alternating teams) is diagnostic-only by design,
since the brief explicitly allows same-team-consecutive possessions when
"event semantics provide a defensible explanation" — which the transient-
possession and ambiguous-reopen mechanisms both are. See the Phase 4 final
report for full results.

## Known unresolved cases

- **Phase 4.25 refresh**: 1,589 of 4,388 possessions (36.2%) are flagged
  `is_ambiguous=True` (was 1,591/4,388 before the faceoff-redraw rule; the
  +2 possessions vs. the original Phase 4 figure of 4,386 come from
  2026-ev-1's mislabeled-goal-as-real-saved-shot event being restored to
  `is_analysis_eligible_event` in Phase 4.25 — see `DATASET_2026.md` — which
  shifted that possession's boundary). See `FULL_SEASON_ANOMALIES.md` §7
  and `PHASE_4_25_REPORT.md` for the full before/after breakdown by reason,
  game, and team, and for what was investigated and NOT changed (evidence
  found insufficient) alongside what was.
  Traced to source: this is dominated by real, evidenced data gaps (missing
  post-goal faceoffs, missing intermediate turnover/groundball events)
  rather than logic errors — every hard structural validation check (1–11,
  13–18) passes with zero failures, and points reconciliation is exact in
  all 50 games. The rate is honestly reported, not suppressed.
- 159 possessions (3.6%) are truncated by a period/game boundary while
  still open; their `duration_seconds` is a lower bound, not exact.
