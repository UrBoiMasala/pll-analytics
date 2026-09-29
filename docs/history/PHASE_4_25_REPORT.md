# Phase 4.25 Report — Data Accuracy, Ingestion Repair, Possession Hardening

Audit and repair pass over the existing pipeline, performed against live
data where the API was reachable. No advanced metrics (EGA, player-value
ratings, PTI, MVP models, dashboards) were built in this phase.

## 1. Live/snapshot coverage and retrieval date

- **Live API was reachable this run** (`stats.premierlacrosseleague.com`,
  200 responses with a standard browser `User-Agent`+`Referer`).
- Schedule refreshed **2026-09-07**: 54 scheduled games, unchanged from the
  2026-09-02 extraction — **51 completed**, 3 upcoming
  (`semifinal-1`/`semifinal-2` play later today per their own `startTime`,
  `championship-game` on 2026-09-20). No newly-completed games to ingest
  this run; the schedule's own JSON changed only in a `teamLossesPost`
  field our pipeline never reads (confirmed via full-payload diff), so this
  is noted but not a correctness issue.
- **All 51 completed games' 4 raw endpoints were force-refreshed and
  compared by content hash and event ID (`markerId`) against the prior
  2026-09-02 cache.** Result: **0 changes** in any per-game endpoint for
  any of the 51 games — no added, removed, or changed play-by-play events,
  no official score corrections. The underlying event data this dataset is
  built on is unchanged since the last extraction.
- Extraction date recorded in `DATASET_2026.md`: 2026-09-02 (Phase 3),
  hardened 2026-09-02 (Phase 3.5), live-refreshed 2026-09-07 (Phase 4.25).

## 2. Files changed or archived

**Ingestion repair**: `scripts/pll_ingest_season.py` — `--force` now
actually re-downloads and replaces cached responses (previously silently
ignored); structural payload validation replaces "truthy JSON" cache-hit
checks; atomic writes; versioned snapshots (`<slug>/_snapshots/`) +
per-endpoint retrieval metadata (`<slug>/_meta.json`) captured before any
replacement; explicit outcome classification (`ok` / `unchanged` /
`changed` / `incomplete_download` / `empty_feed` / `unavailable_pbp` /
`malformed`).

**Canonical table hardening**: `scripts/pll_build_tables.py` —
`team_game_stats.csv` now filtered to actual game participants (via
`game_meta` home/away), with a new `team_game_stats_exceptions.csv` and a
hard structural check; `is_analysis_eligible_event` no longer blanket-
excludes an invalid goal that carries salvageable shot data (the
2026-ev-1 mislabeled real saved shot).

**Possession rule**: `scripts/pll_build_possessions.py` — new narrow
faceoff-violation/redraw rule (2 occurrences season-wide).

**Docs corrected/updated**: `FULL_SEASON_ANOMALIES.md` (WAT ev-47
goals-vs-points correction, phantom-row detail for both games, Phase 4.25
investigation write-up), `DATASET_2026.md` (possession model now
described, refreshed extraction date, metric-specific eligibility,
participant-filtered team_game_stats, refreshed counts),
`POSSESSION_METHODOLOGY.md` (faceoff-redraw rule, refreshed counts,
corrected goal-handling/scope text).

**Archived** to `archive/legacy_phase1_2/` (see its `README.md`; git
history preserved via `git mv`, nothing deleted): the 6 legacy per-game
CSVs (`2026-ev-1/-9/-24/-34/-41_play_by_play.csv`,
`2026-quarterfinals-1_play_by_play.csv`), the root
`data/processed/validation_report.csv`, and `scripts/pll_validate.py` (the
only consumer/producer of those files, fully superseded by
`pll_validate_season.py`). `scripts/pll_pbp_extractor.py` was **kept in
place** — it is still imported directly by `pll_build_tables.py`
(`normalize_play_by_play`) and is load-bearing, not legacy.

**Repo hygiene**: `.gitignore` added (`.DS_Store`, `__MACOSX/`); 5 stray
`.DS_Store` files deleted from the working tree (none were ever
git-tracked). The repo itself was not under version control before this
phase — initialized `git` and committed a baseline snapshot first, so
every change below is reviewable as a diff.

**Tests added** (new `tests/` directory, stdlib `unittest`, no new
dependency): `test_ingest.py` (14), `test_build_tables.py` (9),
`test_pbp_clean.py` (5), `test_build_possessions.py` (3),
`test_coverage.py` (4) — 35 total, all passing (§6).

## 3. Raw response changes after refresh

**None.** See §1 — all 51 completed games' `play_by_play` / `game_meta` /
`players_stats` / `teams_stats` responses are byte-for-byte (post-JSON-
normalization) identical to the 2026-09-02 cache. `data/raw/2026/_schedule/`
carries no `refresh_diff.json` or `ingest_failures.json` because none were
generated — the "no changes found" result is the diff report.

## 4. Validation before and after

| | rows | PASS | KNOWN_DATA_ISSUE | UNRESOLVED |
|---|---|---|---|---|
| Before (Phase 3.5) | 767 | 653 (85.1%) | 72 (9.4%) | 42 (5.5%) |
| After (Phase 4.25) | 765 | 653 (85.4%) | 70 (9.2%) | 42 (5.5%) |

The row/KNOWN_DATA_ISSUE drop of 2 is **not** an improvement to any
game's data — it's the 2 `team_stats_row_count` diagnostic rows for
2026-ev-46/2026-ev-47 disappearing because `team_game_stats.csv` is now
participant-filtered at build time (§5), so there's nothing left for that
check to flag. 42 UNRESOLVED is unchanged: raw data is identical, and the
Phase 4.25 deeper investigation (`FULL_SEASON_ANOMALIES.md` §7) added
substantial new evidence without closing any of them:

- **Team-level cancellation check** (per instruction: "opposite errors can
  cancel when summed"): recomputed every unresolved/known-issue
  `turnovers`/`ground_balls`/`shot_clock_expirations` residual per
  participant team. **Zero hidden-cancellation cases** — no whole-game
  `PASS` conceals a nonzero per-team split.
- **turnovers/shot_clock_expirations**: confirmed their raw descriptions
  carry zero player-level information (always `"Turnover by <TEAM>"` /
  `"Shot Clock Violation."`), so there is no reliable additional
  dedup signal beyond the existing strict-adjacency+1s rule.
- **ground_balls**: tested widening the dedup window to 5s (justified
  since descriptions DO carry player names) — **rejected with evidence**:
  5 of 17 candidates are in games that already exactly match the official
  count, so treating them as duplicates would create new mismatches in
  currently-passing games. Regression test locks in the unwidened window.
- **saves** (2026-ev-8, +1): isolated to one team (CAN, 17 pbp vs. 16
  official); all 17 events individually inspected, no duplicate found.
- **penalties** (2026-ev-45, +1): isolated to one team (CAN, 6 pbp vs. 5
  official); found a genuine new anomaly (one event's `penaltyLength=120`
  contradicts its own description text "30 sec") but not enough evidence
  to say it's the excluded event.

### 5-6. Hardened canonical tables

- **`team_game_stats.csv`**: 102 rows (51 games × 2 participants exactly),
  down from 104. **`team_game_stats_exceptions.csv`**: 2 rows — the
  phantom ATL row in 2026-ev-46 (real-looking stats, 2 goals/7 shots,
  bled in from elsewhere) and the phantom all-zero WHP row in
  2026-ev-47. Hard check enforces exactly 2 distinct participants and a
  unique `(game_id, officialId)` key for every completed game — passes.
- **FULL_SEASON_ANOMALIES.md correction**: WAT's "16 goals, 18 points" in
  2026-ev-47 is **not** a contradiction — verified via
  `onePointGoals`/`twoPointGoals` (14×1 + 2×2 = 18, matching `homeScore`
  exactly; 14+2 = 16, matching `goals` exactly). The prior doc compared
  goals to points as if they were the same quantity; corrected.
- **ev-1 mislabeled goal** (`shot-3004600`): confirmed a real saved shot
  (`shot_saved=True`, `shot_on_goal=True`, zero score delta, empty
  description). It stays `is_valid_goal=False` (never counted as a goal)
  but is now kept `is_analysis_eligible_event=True` since its
  `shot_outcome` ("saved") is real, usable data — previously it was
  invisible to every shot/save/possession metric built on that flag.

## 5. Ambiguity before and after, by reason

| | possessions | ambiguous | truncated |
|---|---|---|---|
| Before Phase 4.25 | 4,386 | 1,588 (36.2%) | 159 (3.6%) |
| After ev-1 eligibility fix (§4) | 4,388 | 1,591 (36.3%) | 159 |
| After faceoff-redraw rule | **4,388** | **1,589 (36.2%)** | 159 |

The possession count changed (+2) because the ev-1 saved-shot event is now
included as an eligible event (§4), shifting that game's possession
boundaries slightly — not a possession-logic change.

**By the 4 requested ambiguity-source categories** (a possession can carry
more than one reason — see "cascading" in `POSSESSION_METHODOLOGY.md` —
so category counts don't sum to 1,589):

| Category | Occurrences | What it means here |
|---|---|---|
| Uncertain possession existence/boundaries | 838 (= `end_reason=ambiguous_control_change`) | A faceoff or a conflicting-team shot/turnover arrived while a possession was tracked open with no independent close — something happened that the feed didn't log a clean boundary for. |
| Uncertain offensive team | **0** | Every possession-opening event type (faceoff, groundball, turnover, shot-clock, shot/goal) carries a directly-resolved `team_id` (0 unresolved team IDs all season). Validation check #17 confirms `start_reason='unknown'` never occurs. |
| Uncertain timing/duration | 159 (`is_truncated=True`) | Possession still open at a period/game boundary; `duration_seconds` is a lower bound, not exact. Distinct dimension from `is_ambiguous`. |
| Uncertain start/end mechanism despite otherwise-reliable possession | 922 (= `start_reason=other_confirmed_control`) | Team attribution is solid (from the triggering event's own field); only *how* they got the ball (missing post-goal faceoff: 36; other no-clean-evidence-chain gaps: 886) is unconfirmed. |

**Largest categories investigated**: "uncertain mechanism" (922) and
"uncertain boundary" (838) together account for essentially all ambiguity.
Both were traced to the same root cause already documented in
`POSSESSION_METHODOLOGY.md`'s evidence base — missing post-goal faceoffs
(~3% of goals) and missing intermediate turnover/groundball events — which
are gaps in what PLL's feed logs, not reconstructable from adjacent
evidence without inventing plays. **One narrow, fully-evidenced rule was
found and applied**: two faceoff events back-to-back with zero intervening
events (a faceoff violation/redraw) now resolve cleanly instead of being
flagged ambiguous — exactly 2 occurrences all season (2026-ev-28,
2026-ev-42), reducing ambiguous count by 2. A superficially similar
5-occurrence pattern (groundball recovery immediately followed by a
faceoff) was deliberately **not** touched — the ball was demonstrably
recovered there, so treating it the same way would discard real evidence.
Full before/after with event IDs, evidence, and a regression test
(including a false-positive guard) in `POSSESSION_METHODOLOGY.md` and
`tests/test_build_possessions.py`.

Every possession integrity check still passes (17/17 hard checks, 0
failures each); goal-derived points reconcile exactly with final scores in
all 50 eligible games; every valid goal is assigned to exactly one
possession.

## 6. Tests run and results

`python3 -m unittest discover -s tests` — **35/35 passing**:

| File | Tests | Covers |
|---|---|---|
| `test_ingest.py` | 14 | payload validation, forced refresh replacing cache, invalid/empty-response rejection, failed-download preservation, snapshot creation, PBP event diffing |
| `test_build_tables.py` | 9 | team participant filtering + exceptions, structural uniqueness check, the ev-1 metric-specific eligibility (+ 2 false-positive guards) |
| `test_pbp_clean.py` | 5 | ev-1 mislabeled-goal reclassification, a real-goal sanity check, the rejected groundball-window-widening decision (+ false-positive guard) |
| `test_build_possessions.py` | 3 | faceoff-redraw rule + 2 false-positive guards |
| `test_coverage.py` | 4 | newly-completed-game discovery, schedule-never-cached invariant, raw-to-processed event count and marker-ID coverage (integration, against real repo data) |

## 7. Remaining issues and their impact on specific metrics

- **42 UNRESOLVED validation rows** (19 turnovers, 16 ground_balls, 5
  shot_clock_expirations, 1 saves, 1 penalties — always ±1, twice ±2).
  Impact: any *exact* team-game total for these 5 metrics in the affected
  20 unique games may be off by 1-2 in the direction the table shows;
  season-wide aggregates are affected by well under 1%. Do not treat any
  single affected game's turnover/ground-ball/shot-clock/save/penalty
  count as exact without checking `validation_report.csv` first.
- **`caused_turnovers` is entirely unattributable** at the event level
  (field always null) — any metric needing this must come from
  `player_game_stats.csv`/`team_game_stats.csv` directly, never from
  `events.csv`.
- **36.2% of possessions are ambiguous**, concentrated in
  `other_confirmed_control` (mechanism unknown, team known) and
  `ambiguous_control_change` (boundary unknown). Impact: possession
  **existence, team, and scoring** are trustworthy even for ambiguous
  possessions (all structural checks pass, points reconcile exactly); what's
  NOT trustworthy for the ~36% is the *specific mechanism* by which control
  changed and, for `ambiguous_control_change`-bounded possessions, the
  *exact instant* of the boundary. Any metric sensitive to exact possession
  boundaries or "how did they get the ball" (clearing/riding stats,
  transition-specific efficiency) inherits this uncertainty directly.
- **3.6% of possessions are truncated** (period/game boundary) —
  `duration_seconds` is a lower bound for these; any pace/tempo metric
  needs to either exclude truncated possessions or treat their duration as
  censored, not exact.
- **shotAssistId / `pre_shot_pass_player_id` is not a confirmed assist** —
  unpopulated does not mean no pass occurred (unchanged from Phase 3).

## 8. Phase 5 recommendation

**Ready now** (possession-level, structurally sound, points/teams/
existence verified):
- Total/average possessions per team/game, possession-level shot volume
  and shots-on-goal, man-up/two-point possession rates, points-per-
  possession (offensive efficiency) at the team-game level — all backed
  by exact points reconciliation and 0 structural-check failures.
- Faceoff-win-rate-derived possession share (`faceoff_win` starts are
  never ambiguous).

**Needs uncertainty analysis before use** (the metric is computable but a
consumer must decide how to treat the ambiguous ~36%/truncated ~4%):
- Any *pace*/time-of-possession metric — truncated possessions'
  `duration_seconds` is a lower bound only.
- Any metric segmenting possessions by *how* control changed
  (transition offense/defense, "how many possessions started off a clean
  clear" vs. a scramble) — the largest ambiguity bucket is exactly "team
  known, mechanism unknown."
- Defensive/riding metrics keyed to the exact instant of a turnover/
  shot-clock-caused possession change, where `ambiguous_control_change`
  boundaries make the precise transition moment uncertain.

**Not supported by current data** (do not attempt without new source
data):
- Anything requiring `caused_turnovers` at the player or event level
  (field is structurally always null in the feed).
- Any metric requiring a confirmed assist (`shotAssistId` is a pass
  indicator, not an assist confirmation).
- EGA, player-value ratings, PTI, MVP models, dashboards — explicitly out
  of scope for this phase and not attempted.

No claim of zero uncertainty is made anywhere above — the 5.5% UNRESOLVED
validation rate and the 36.2% possession-ambiguity rate are both real and
reported as such, with the specific evidence behind why each remaining
case wasn't (and, for several, couldn't responsibly be) resolved further.
