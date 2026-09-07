# PLL 2026 Season Dataset

Built by ingesting, cleaning, and validating every completed game of the
2026 Premier Lacrosse League season from PLL's public stats API, and
reconstructing a possession-level layer on top of the cleaned events. No
advanced/possession-denominated metrics (EGA, player-value ratings, PTI,
MVP models, dashboards) have been built on top of it yet — see "Phase 5
recommendation" in `PHASE_4_25_REPORT.md` for what's ready vs. what still
needs uncertainty analysis. See `VALIDATION_METHODOLOGY.md` for the full
event-level cleaning/validation rulebook, `POSSESSION_METHODOLOGY.md` for
the possession-reconstruction rules and evidence base, and
`FULL_SEASON_ANOMALIES.md` for every known data-quality issue.

## Source endpoints

All under `https://stats.premierlacrosseleague.com/api/v4/` (public,
unauthenticated — a standard browser `User-Agent` + `Referer` header is
sufficient; no login, cookies, or token required):

- `GET /games?year=2026` — season schedule (authoritative game list;
  always re-fetched fresh on every ingestion run, unlike per-game data, so
  reruns detect newly-completed games automatically)
- `GET /games/{slug}` — game metadata (teams, final score, venue, date)
- `GET /games/{slug}/play-by-plays` — full play-by-play
- `GET /games/{slug}/players/stats` — player box score for that game
- `GET /games/{slug}/teams/stats` — team box score for that game

The latter 3 endpoints are **never** queried for a game that hasn't been
played yet (`eventStatus==0`) — that data doesn't exist.

## Extraction date

2026-09-02 (Phase 3 full ingestion), hardened 2026-09-02 (Phase 3.5).

## Scope

- 54 games in the 2026 schedule as of extraction; **51 completed**
  (`eventStatus==3`), 3 not yet played (semifinal-1, semifinal-2,
  championship-game; `eventStatus==0`). This count is never hard-coded
  anywhere in the pipeline — every script re-derives it from the live
  schedule response.
- **All 51 completed games ingested successfully** — 0 failures.
- Ingestion (`scripts/pll_ingest_season.py`) is fully resumable and safe to
  rerun after more games complete: the schedule is always refreshed, a
  completed game's raw files are only downloaded once (cached
  indefinitely — raw data for a finished game does not change), and a
  rerun with 0 new completions does 0 new game-data network calls.
- Includes regular season, the all-star game, and 2 quarterfinal playoff
  games. Semifinals/championship not yet played as of extraction date —
  present in `games.csv` with `is_completed=False`, no fabricated stats.

## Tables (`data/processed/2026/`)

### `games.csv` (54 rows — every scheduled game, completed or not)
`game_id, game_slug, event_id, year, week, season_segment, game_type, is_playoff, is_all_star, include_in_league_analytics, is_completed, event_status, start_time_unix, start_date_utc, venue, location, home_team_id, away_team_id, home_score, away_score, home_period_scores, away_period_scores`

`game_type` (`regular_season` / `playoffs` / `all_star` / `other`) is
derived directly from PLL's own `seasonSegment` field. Score/venue/period-
score fields are populated only for completed games (`game_meta` doesn't
exist otherwise) — left null rather than guessed for the 3 upcoming games.

### `teams.csv` (10 rows: 8 franchises + 2 all-star squads)
`team_id, full_name, location, location_code, conference, team_color, background_color, is_all_star_team`

`is_all_star_team` is True only for ASE/ASW — a team_id that only ever
appears in a `game_type=='all_star'` game. Filter on it (or on
`games.include_in_league_analytics`) to exclude all-star participation
from team-level baselines/ratings without deleting anything.

### `players.csv` (228 rows, deduplicated by `player_id`)
`player_id, name, first_name, last_name, team_id, position, position_name, jersey_num, slug, profile_url`

### `events.csv` (11,254 rows — the canonical play-by-play)
`game_id, game_slug, event_id, event_number, period, clock, seconds_passed, team_id, team, player_id, player, secondary_player_id, secondary_player, event_type, shot_type, description, home_score_raw, away_score_raw, gb_player_id, goalie_id, goalie, shot_on_goal, shot_saved, save_type, penalty_length_sec, penalty_description, away_win_prob, home_win_prob, is_valid_goal, goal_invalid_reason, home_score_corrected, away_score_corrected, shot_outcome, is_duplicate_event, is_duplicate_groundball, is_duplicate_turnover, is_duplicate_faceoff, is_duplicate_penalty, is_valid_penalty, is_two_point_attempt, is_man_up_shot, game_type, include_in_league_analytics, pre_shot_pass_player_id, is_analysis_eligible_event`

No rows are ever deleted — anomalies are flagged, not removed.
`is_analysis_eligible_event` = the game counts toward league analytics
(`include_in_league_analytics`) AND the event isn't a confirmed exact
duplicate (`is_duplicate_event`) AND it isn't a confirmed-invalid penalty
AND it isn't a confirmed-invalid goal **that also carries no other usable
information**. It deliberately does **not** exclude anything merely
ambiguous — an unpopulated `shotAssistId`, or the unresolved count residuals
in `FULL_SEASON_ANOMALIES.md`, are left in and flagged elsewhere, not
silently dropped from this eligibility flag.

**Metric-specific eligibility (Phase 4.25):** the one known invalid-goal
case (2026-ev-1, marker `shot-3004600`) is a real saved shot mislabeled
`eventType=='goal'` (see `FULL_SEASON_ANOMALIES.md` §5) — its
`shot_outcome` is correctly derived as `"saved"`. Prior to Phase 4.25 it
was excluded from `is_analysis_eligible_event` entirely, which made this
legitimate shot/save invisible to any shot- or save-denominated metric
built on that flag (including possession-level `shot_attempts`/
`shots_on_goal`). It is now kept **eligible** (its `shot_outcome` is
counted normally) while `is_valid_goal=False` still, correctly, keeps it
out of every goal/points aggregation — those aggregations filter on
`is_valid_goal` directly and always have. A future invalid goal with truly
no salvageable shot data (`shot_outcome` null) would still be excluded from
`is_analysis_eligible_event`, since there would be nothing left to salvage.

`event_type` is never reinterpreted — there is deliberately no
"event_type_cleaned" column, since validity concerns live entirely in the
`is_valid_*`/`is_duplicate_*` flags, not in the event type itself.

**`secondary_player_id`/`pre_shot_pass_player_id` on shot/goal rows is the
raw `shotAssistId`, NOT a confirmed official assist.** Per the Phase 2/3
investigation, it identifies the player who passed to the shooter on that
attempt, whether or not it scored (44.1% of shot/goal events have it
populated, including on non-scoring shots). **A missing `shotAssistId`
does not prove no pass occurred** — it is simply unpopulated, not a
negative assertion. No assist statistics are calculated anywhere in this
dataset from this field; `goals_with_pre_shot_pass` in
`validation_report.csv` is a diagnostic cross-check only (see
`VALIDATION_METHODOLOGY.md`), not an analytics product.

### `player_game_stats.csv` / `team_game_stats.csv`
Per-game box-score rows from `players/stats`/`teams/stats`, unmodified
except for an added `game_id`/`game_slug`. PLL's own column names
(`officialId`, `teamId`, camelCase stats) are preserved, not renamed.

**`team_game_stats.csv` is participant-filtered (Phase 4.25).** The raw
`teams_stats` endpoint has, in 2 known games (2026-ev-46, 2026-ev-47 — see
`FULL_SEASON_ANOMALIES.md` §4), returned an extra row for a team that did
not play in that game (a PLL backend bug). `pll_build_tables.py` now keeps
only rows whose `officialId` matches that game's own `game_meta`
home/away team — the authoritative source for who actually played — for
every game, not just the 2 known-affected ones. Every rejected row (a
non-participant, an exact duplicate participant row, or a participant with
no row at all) is preserved, with a reason, in the sibling
`team_game_stats_exceptions.csv` rather than silently dropped. A hard
structural check (run at build time, and re-verifiable any time) requires
every completed game to have exactly 2 distinct participant `officialId`
values in `team_game_stats.csv` and a unique `(game_id, officialId)` key.

### `team_game_stats_exceptions.csv`
One row per rejected/missing `teams_stats` record, each with a
`rejection_reason` (e.g. "not a participant in 2026-ev-47 per game_meta",
"expected participant WHP has NO teams_stats row at all in ..."). Preserves
the full original raw row (including whatever real-looking-but-wrong stat
values it carried) for audit — see `FULL_SEASON_ANOMALIES.md` §4 for what's
been found there so far.

### `unresolved_player_ids.csv` / `unresolved_team_ids.csv`
Both empty (0 rows). Every player ID referenced anywhere in `events.csv`
(via any of `player_id`, `secondary_player_id`, `goalie_id`,
`gb_player_id`) resolves to a roster entry in some game's `players/stats`,
and every `team_id` referenced in `events.csv` or `games.csv` resolves to
`teams.csv`. See "Player-ID / team-ID behavior" below for the full raw-
field-level breakdown.

### `validation_report.csv` (767 rows)
`game_slug, metric, raw_value, cleaned_value, official_value, raw_difference, cleaned_difference, raw_status, cleaned_status, final_status, notes`

17 metrics × 51 games (a few games contribute an extra diagnostic row, e.g.
`team_stats_row_count`). See `VALIDATION_METHODOLOGY.md` for exact status
definitions — summary: **653 PASS (85.1%), 72 KNOWN_DATA_ISSUE (9.4%), 42
UNRESOLVED (5.5%)**.

## Cleaning rules

Full detail and rationale in `VALIDATION_METHODOLOGY.md`. Summary:
`is_valid_goal`, `is_valid_penalty` (validity checks), `home_score_corrected`/
`away_score_corrected` (score reconstruction), `shot_outcome`
(goal/saved/on_goal_no_save/missed classification), `is_duplicate_event`
(general-purpose exact-duplicate flag, all event types), `is_two_point_attempt`/
`is_man_up_shot` (deterministic from `shot_type`). All flag-only — raw JSON
under `data/raw/2026/` is never modified, and no row is ever deleted from
`events.csv`.

## Known limitations / PLL data-quality issues

Full detail and every affected game in `FULL_SEASON_ANOMALIES.md`.
Headline numbers after the Phase 3.5 hardening pass: of 767 validation
checks, **42 are genuinely unresolved** — mostly small (±1, rarely ±2)
`turnovers`/`ground_balls`/`shot_clock_expirations` residuals with no
duplicate or malformed event found in that specific game, plus one
isolated `saves` case and one `penalties` case. These are honestly
reported as unexplained, not folded into a "known issue" bucket just
because a same-named metric has a real explanation elsewhere. The
`commitedTurnoverId`/`causedTurnoverId`/`offenseGoalieId`/
`assistOpportunityPlayerId`/`closestDefenderId` fields are confirmed
**always null** — every event, every game, all season.

## Player-ID / team-ID behavior

Checked directly against the raw JSON fields (not just the normalized
`events.csv` columns) for every populated occurrence, across all 51 games:

| Raw field | Populated | Resolved | Unresolved |
|---|---|---|---|
| `shooterId` | 4,211 | 4,211 | 0 |
| `goalieId` | 4,211 | 4,211 | 0 |
| `shotAssistId` | 1,855 | 1,855 | 0 |
| `faceoffWinnerId` | 1,326 | 1,326 | 0 |
| `faceoffLoserId` | 1,326 | 1,326 | 0 |
| `gbPlayerId` | 4,285 | 4,285 | 0 |
| `commitedPenaltyId` | 285 | 285 | 0 |
| `offenseGoalieId`, `assistOpportunityPlayerId`, `closestDefenderId`, `commitedTurnoverId`, `causedTurnoverId` | 0 | — | — |

**0 unresolved player IDs, 0 unresolved team IDs**, across the entire
season. IDs are stable and used as join keys throughout — names are never
used as primary keys.

## Event types (9, unchanged from Phase 2/3 across the full season)

`pregame` (51), `gameEnd` (51), `faceoff` (1,326), `groundball` (3,176),
`shot` (3,072, non-scoring only), `goal` (1,139 raw / 1,138 valid),
`shotclockexpired` (367), `turnover` (1,787), `penalty` (285 raw / 284
valid).

## Shot types

`1_PT` (3,582), `2_PT` (539), `MU` (77, man-up 1pt), `MU_2_PT` (13, man-up
2pt). Preserved exactly as supplied — never collapsed. `is_two_point_attempt`/
`is_man_up_shot` are unambiguous derived booleans (see table in
`VALIDATION_METHODOLOGY.md`), not a reinterpretation of `shot_type` itself.

## Win-probability semantics

`homeTeamWinProbability`/`awayTeamWinProbability` preserved exactly as
supplied by PLL — **never interpolated, no WPA calculated**. Confirmed
facts (unchanged since Phase 2, re-verified at full-season scale): scale is
0–1; `home + away` sums to exactly 1.0 whenever both are populated; values
move live throughout the game (not a static pregame number); coverage is
**64.8%** of all 11,254 events (7,292) — populated on `pregame`, `faceoff`,
`goal`, `shot`, `gameEnd` (~100%), `shotclockexpired` (~92%), **never** on
`groundball`/`penalty`, and only ~78% of the time on `turnover` (no pattern
found explaining which turnovers lack it). How to handle the missing
44.9%/coverage gaps for any future analysis is an open decision, deferred.

## shotAssistId coverage

44.1% of shot/goal events (1,855 of 4,211) have `shotAssistId` populated.
See "Tables → events.csv" above for the full semantics caveat.

## Fields confirmed unusable

`commitedTurnoverId`, `causedTurnoverId`, `offenseGoalieId`,
`assistOpportunityPlayerId`, `closestDefenderId` — always null, every
event, every game, all season. Retained in the raw JSON (untouched) but not
surfaced as meaningful columns in `events.csv`.
