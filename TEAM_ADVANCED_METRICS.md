# PLL 2026 Team Advanced Metrics (Phase 5)

Team-level, possession-denominated advanced metrics built on the Phase 4.25
possession layer. Nothing in Phases 1–4.25 was modified: Phase 5 reads
`events.csv`, `possessions.csv`, `games.csv`, `teams.csv`,
`team_game_stats.csv` and `validation_report.csv` and writes only new tables.
Player-value, EGA, PTI, Elo, opponent-adjusted ratings, Statistical Tewaaraton
and dashboards are explicitly **not** part of this phase and none were built.

## Metric philosophy

1. **Points, not goals, are the unit of PLL offence.** A two-point goal is one
   goal worth two points. Every efficiency metric is denominated in points;
   every shooting-accuracy metric stays denominated in goals. The two are never
   mixed, and `points == goals + two_point_goals` is asserted on every row.
2. **One number, one source, named.** Where the play-by-play and the official
   box score disagree, both are published under distinct names (`turnovers`
   vs. `turnovers_pbp`) with the per-team residual on the same row. Nothing is
   blended, reconciled, or silently corrected.
3. **A denominator is a claim.** Every rate's denominator is recorded in
   `metric_definitions.csv`, and validation check 10 fails if any emitted
   column lacks one.
4. **Uncertainty travels with the row.** Phase 4.25's unresolved validation
   residuals and possession-ambiguity flags propagate to every team-game row
   rather than living in a document.
5. **A metric the data cannot support is not published.** Three Lacrosse
   Reference concepts and two feed-level metrics were built up to the point of
   evidence, failed, and were labelled `deferred`/`unsupported` instead of
   shipped. See "Deferred and unsupported".

## Outputs

| File | Rows | Grain |
|---|---|---|
| `data/processed/2026/team_game_advanced.csv` | 100 (133 cols) | one team in one eligible game |
| `data/processed/2026/team_season_advanced.csv` | 8 (121 cols) | one team, 2026 season |
| `data/processed/2026/team_rankings.csv` | 184 | one (metric, team) |
| `data/processed/2026/possession_length_splits.csv` | 63 | one (scope, span bucket) |
| `data/processed/2026/team_metric_sensitivity.csv` | 96 | one (subset, metric, team) |
| `data/processed/2026/team_metric_sensitivity_null_model.csv` | 12 | one (subset, metric) |
| `data/processed/2026/metric_definitions.csv` | 119 | one metric |
| `data/processed/2026/team_metrics_validation_report.csv` | 20 | one check |

Scope is the 50 games with `include_in_league_analytics == True` — regular
season plus the 2 completed quarterfinals. **The all-star game is excluded**,
once, in the `eligible_games` view that every downstream query joins through;
validation check 14 asserts that neither the all-star `game_id` nor the ASE/ASW
team ids appear anywhere in the Phase 5 tables.

## Source selection

Before choosing a source for any metric, every candidate was compared against
the official box score across all 100 team-games:

| Quantity | Play-by-play vs official | Source chosen |
|---|---|---|
| shots, shots on goal, goals, points | **100/100 exact** | play-by-play (agrees with official) |
| two-point shots, two-point goals | **100/100 exact** | play-by-play |
| saves | 99/100 (the known 2026-ev-8 residual) | official, `saves_pbp` exposed |
| faceoff wins | 99/100 | **official** |
| turnovers | 67/100 (pbp higher by 22 season-wide) | **official**, `turnovers_pbp` exposed |
| ground balls | 79/100 (pbp higher by 16 season-wide) | **official**, `ground_balls_pbp` exposed |
| man-up shots | 30/100 (official higher in 70) | **official** — see "Man-up" |
| time of possession | no comparable pbp quantity | **official** — see "Time of possession" |

Faceoffs and ground balls follow the brief's instruction not to rebuild a
worse metric from play-by-play when the official table is cleaner. The official
faceoff denominator is also the better one: in 8 games `faceoffsWon +
faceoffsLost` is 1–2 short of `faceoffs`, because PLL counts no-decision draws
(violations/redraws) in the total, and the event log has no representation for
those.

## Core efficiency

```
offensive_efficiency = points_scored  / offensive_possessions
defensive_efficiency = points_allowed / defensive_possessions
net_efficiency       = offensive_efficiency - defensive_efficiency
```

Not multiplied by 100. `*_per_100` columns exist under explicit names for
anyone who wants that scale. `points_per_possession` and
`offensive_efficiency` are the same number; both names are emitted because both
are in common use, and `metric_definitions.csv` records the alias rather than
leaving two identical columns unexplained (validation check 12 asserts the
identity holds).

Season rates are recomputed from **season totals**, never as the mean of
per-game rates — those differ whenever games have different possession counts,
and validation check 18 explicitly fails if the season value ever equals the
mean of the per-game values.

League 2026: **0.271 points per possession**, 43.9 offensive possessions per
team per game.

None of these are opponent-adjusted. Schedule strength is a later phase.

## Pace and possession share

Pace is expressed in **possession counts**, not seconds:
`team_possessions_per_game`, `combined_possessions_per_game`. This is a
deliberate consequence of the time-of-possession finding below — possession
counts are structurally validated, possession durations are not a valid
time-of-possession measure.

`faceoff_start_possession_share` is the share of a team's offensive possessions
that began on a faceoff win. Faceoff-started possessions are never flagged
ambiguous (a faceoff's team attribution was 1,326/1,326 resolved in Phase 3.5),
so this split is trustworthy where the fuller possession-source split is not.

## Shooting

`shooting_pct = goals / shots` — deliberately **not** points per shot. A team
that scores two two-point goals on two shots shot 100%, not 200%; a unit test
asserts exactly this.

`points_per_shot = points / shots` is the metric that credits two-point volume.
`goals_per_possession` is the share of offensive possessions ending in a goal
(a goal always closes its possession, so a possession contains at most one —
verified season-wide), which makes it directly comparable to Lacrosse
Reference's "Efficiency" column.

League 2026: 27.2% shooting, 0.290 points per shot, 0.93 shots per possession.

## Two-point metrics (PLL-specific)

`two_point_attempts`, `two_point_goals`, `two_point_points`,
`two_point_attempt_rate`, `two_point_conversion_pct`, `two_point_points_share`,
`points_per_two_point_attempt`, `two_point_possession_rate`, plus
`one_point_attempts` / `one_point_goals` / `one_point_conversion_pct` as the
comparison baseline.

All derive from the existing `is_two_point_attempt` flag (`shot_type` in
`{2_PT, MU_2_PT}`); no new classifier was written, and the derived counts equal
official `twoPointShots`/`twoPointGoals` in all 100 team-games.

The reason `one_point_conversion_pct` is published alongside
`points_per_two_point_attempt` is that together they answer the question the
NCAA has no version of. League 2026:

| | conversion | expected points per attempt |
|---|---|---|
| one-point shot | 29.3% | **0.293** |
| two-point shot | 13.4% | **0.269** |

Across the league in 2026 the two-point shot returned *slightly less* per
attempt than the shot inside the arc. 13.1% of all shots were two-pointers,
producing 12.1% of all points. This is a league-level average over 536
attempts, not a claim about any individual shot or team, and it is exactly the
kind of finding that requires PLL-native metrics — there is no NCAA analogue to
adapt.

## Turnovers

```
turnovers                          official box score
turnovers_per_possession           turnovers / offensive_possessions
turnover_rate                      alias of the above (both are named in the brief)
possession_ending_turnover_rate    possessions ending in a turnover / offensive possessions
```

The last one is not a duplicate. The possession engine suppresses same-instant
"companion" turnover events (the turnover PLL logs alongside the opponent's
goal), so possession-ending turnovers (1,352 season-wide) are fewer than
turnover events (1,721) and fewer than official turnovers (1,699). The official
count is the right numerator for a turnover rate; the possession-ending count
is the one that can be subset by possession and is therefore what the
sensitivity analysis uses.

`caused_turnovers_official` is official-only and always will be: the
event-level caused-turnover field is structurally null in every event of the
season.

## Man-up

**PLL's man-up tag lands on goals only.** All 90 `MU`/`MU_2_PT` events in the
2026 season are valid goals — there is no such thing in this feed as a tagged
man-up shot that missed. Official `powerPlayShots` exceeds the tagged count in
70 of 100 team-games, confirming the tag is not a shot tag.

Consequences, all of them enforced in the output:

- Man-up **shots** come from official `powerPlayShots`; man-up **goals** from
  official `powerPlayGoals`; `man_up_shooting_pct` is official over official.
- Man-up **points** come from the play-by-play tag, because only it
  distinguishes a one-point from a two-point man-up goal. It matches official
  `powerPlayGoals` in 97 of 100 team-games; the residual is exposed as
  `man_up_goals_pbp_minus_official`.
- The denominator is the **extra-man opportunity** (`timesManUp`), not a
  possession: `man_up_goals_per_opportunity`, `man_up_points_per_opportunity`,
  `man_up_shots_per_opportunity`.
- `man_up_possessions` is **not published**. The possession flag
  `has_man_up_shot` is true for exactly 90 possessions and every one contains a
  man-up goal, so the column would be a renamed copy of the goal count, and any
  rate built on it is degenerate — man-up shooting percentage computed that way
  is 1.000 for all 8 teams. Penalty events carry no possession linkage either,
  so man-up possessions cannot be recovered from penalty timing without
  inventing the state.

A regression test asserts the goals-only property, so if PLL starts tagging
missed man-up shots this decision gets revisited rather than silently
inherited.

## Time of possession — why no reconstructed version is published

The Phase 5 brief asks whether a defensible team time-of-possession metric can
be produced from the possession layer. **It cannot, and none is published.**

The possession engine gives each possession a `duration_seconds` equal to the
span from its first logged event to its last. That span is not time of
possession, because it excludes the interval between the previous possession's
last logged event and this one's first — the transition, the clear, the dead
ball. Measured against PLL's own `timeInPossesion`:

| | value |
|---|---|
| median span coverage of official ToP | **0.751** |
| range across team-games | 0.536 – 0.998 |
| correlation with official ToP | **r = 0.58** |
| mean absolute error in team possession *share* | **4.9 percentage points** |

A 25% shortfall that varied consistently would be rescalable. A 0.54–1.00
range at r = 0.58 is not. So:

- `observed_possession_seconds` and `complete_possession_seconds` are published
  as **diagnostics**, explicitly described as sums of logged event spans and
  lower bounds.
- `time_of_possession_official_seconds` (PLL's own figure) is the
  authoritative time-of-possession column.
- `possession_span_coverage_ratio` is published so the gap is visible per row.
- No column named `time_of_possession_observed_seconds` or
  `time_of_possession_complete_only_seconds` exists; a test asserts their
  absence.

**The event timestamps themselves are sound** — this is a coverage problem, not
a clock problem. Three independent checks confirm the clock:

1. `seconds_passed` is monotonic with zero negative gaps, and 47 of 50 games
   end at exactly 2,880 seconds (4 × 12-minute quarters); the other 3 went to
   overtime.
2. Possessions that started on a **change of possession** and ended in a
   shot-clock violation have a median span of **51.5s** (opponent turnover) and
   **53s** (defensive ground ball) — against PLL's 52-second shot clock.
3. Possessions that started on a **faceoff win** and ended in a shot-clock
   violation have a modal span of **34s** and median 37s — against PLL's
   32-second post-faceoff shot clock, plus the few seconds it takes to secure
   the draw.

Durations are therefore trustworthy *as spans between logged events*, which is
what makes the possession-length splits below defensible even though a
time-of-possession total is not.

## Possession length

`possession_length_splits.csv`, league-wide and per team. Eligibility is
stricter than "all possessions":

```
is_measurable_span = NOT is_ambiguous AND NOT is_truncated AND event_count > 1
```

2,096 of 4,388 possessions (47.8%) qualify. The `event_count > 1` condition
matters: 871 possessions season-wide are opened and closed by the *same single
event*, so their span is 0 by construction. That is the absence of a
measurement, not a fast possession.

Buckets were chosen after inspecting the distribution (deciles at
0/5/12/19/25/30/35/41/52s), not in advance:

**`0s` · `01-09s` · `10-19s` · `20-29s` · `30-44s` · `45-59s` · `60s+`**

Same-second possessions get their own bucket rather than being folded into a
`0-10s` bucket. They behave nothing like the rest of that range — 0.81 points
per possession and a 76% goal rate, against 0.43 and 40% for genuine 1–9 second
possessions — because they are overwhelmingly cases where the feed logged a
possession's start and its goal in the same second. Merging them would have
made the fastest bucket read 0.60 points per possession and manufactured a
"fast offence is hyper-efficient" effect out of a logging artifact.

League 2026:

| bucket | poss | share | PPP | shots/poss | turnover rate | points/shot |
|---|---|---|---|---|---|---|
| 0s | 251 | 12.0% | 0.809 | 0.76 | 0.231 | 1.057 |
| 01-09s | 322 | 15.4% | 0.435 | 0.86 | 0.283 | 0.507 |
| 10-19s | 279 | 13.3% | 0.455 | 0.94 | 0.315 | 0.487 |
| 20-29s | 372 | 17.8% | 0.503 | 1.06 | 0.309 | 0.472 |
| 30-44s | 536 | 25.6% | 0.285 | 1.19 | 0.187 | 0.240 |
| 45-59s | 221 | 10.5% | 0.317 | 1.69 | 0.213 | 0.187 |
| 60s+ | 115 | 5.5% | 0.270 | 2.44 | 0.191 | 0.110 |

Longer possessions generate steadily more shots and steadily fewer points per
shot. Team-level cells run from 10 to 85 possessions; `possessions` is on every
row so a thin cell is visible rather than implied.

**No bucket is labelled "transition" or "settled offence".** Possession length
is measured; playing style is an interpretation, and this phase does not make
it.

## Ground balls

`ground_balls` is official. `ground_balls_per_possession` uses **offensive +
defensive possessions** as its denominator, because ground balls are recovered
on both sides of the ball — dividing by offensive possessions alone would
misattribute the rate. No offensive-ground-ball or contested-ground-ball
percentage is computed: the feed supplies no such denominator.

## Team goalkeeping

`saves` and `goals_allowed` are official; `shots_on_goal_allowed` is
play-by-play (which matches official exactly). Two save percentages are
published because two real denominators exist:

- `save_pct_official` = saves / (saves + goals allowed) — PLL's own definition.
- `save_pct_vs_shots_on_goal` = saves / opponent shots on goal.

They differ because 154 shots season-wide are classified on goal but neither
saved nor a goal (`on_goal_no_save`). Neither silently replaces the other.

## Uncertainty flags

Every team-game row carries two independent kinds of evidence:

**Game-level status**, straight from `validation_report.csv`:
`turnover_validation_status`, `ground_ball_validation_status`,
`shot_clock_validation_status`, `save_validation_status`,
`penalty_validation_status`, plus boolean `has_*_validation_issue` and
`has_unresolved_validation_issue`. Affected team-game rows: 58 turnovers, 40
ground balls, 10 shot clock, 6 penalties, 2 saves; 68 of 100 rows carry at
least one unresolved issue.

**Team-level residuals**, computed in Phase 5 because
`validation_report.csv` is game-level only and cannot say *which* of the two
teams carries a discrepancy: `turnovers_pbp_minus_official`,
`ground_balls_pbp_minus_official`, `faceoff_wins_pbp_minus_official`,
`saves_pbp_minus_official`, `shot_clock_expirations_pbp_minus_official`.
Nothing is corrected — the residual is reported alongside both source values.

Possession-model uncertainty travels separately:
`ambiguous_offensive_possessions`, `ambiguous_defensive_possessions`,
`ambiguous_offensive_possession_share`, `truncated_possessions`,
`complete_possessions`, `measurable_span_possessions`.

## Sensitivity analysis

`team_metric_sensitivity.csv` recomputes six possession-denominated metrics on
three nested possession sets — full (4,388), non-ambiguous (2,799), and
non-ambiguous + non-truncated (2,672) — taking numerator and denominator from
the same subset every time. That constraint forces one substitution: the
turnover metric is `possession_ending_turnover_rate`, because an official
season total cannot be subset by possession ambiguity and pairing an
unsubsettable numerator with a shrinking denominator would manufacture a
difference that is pure arithmetic.

Restricting to high-confidence possessions moves values a lot:

| metric | mean abs. change | max abs. change | teams changing rank |
|---|---|---|---|
| offensive_efficiency | 0.070 | 0.086 | 4 of 8 |
| defensive_efficiency | 0.069 | 0.096 | 5 of 8 |
| net_efficiency | 0.021 | 0.037 | 7 of 8 |
| possession_ending_turnover_rate | 0.082 | 0.112 | 4 of 8 |
| shots_per_possession | 0.035 | 0.073 | 5 of 8 |
| two_point_possession_rate | 0.029 | 0.041 | 4 of 8 |

(non-ambiguous + non-truncated subset; max rank movement 4 places.)

**That table on its own would be misread, in two different directions.** Two
further analyses were run.

### Why the levels shift: a selection effect, not an error

52.7% of ambiguous possessions end in `ambiguous_control_change` — the engine
force-closing a possession because the feed lost the thread. Those possessions
*structurally* cannot have ended in a goal, because a goal would have closed
them cleanly. Excluding them therefore preferentially discards non-scoring
possessions, and league points per possession rises from 0.271 to 0.326.

The high-confidence subset is **not a cleaner estimate of the same quantity**.
It is a biased subsample of a different population. The full possession set
remains the correct basis for published efficiency: those possessions really
happened and the team that had the ball is known with certainty — only the
boundary mechanism is unconfirmed. Dropping them would undercount possessions
and overstate efficiency.

### Whether the rank movement means anything: a null model

`scripts/pll_sensitivity_null_model.py` answers the question the rank-change
column cannot. The high-confidence subset is only ~61% the size of the full
set, and any smaller sample reshuffles a close 8-team ranking on noise alone.
So for each metric it draws 2,000 random subsets of each team's possessions of
*exactly the same size* as that team's high-confidence subset, recomputes the
metric, re-ranks, and compares the observed rank churn against that
distribution.

Result, across all 12 metric × subset combinations:

- **Rank churn: p ranges 0.135 to 0.922. Not one is significant.** The observed
  reshuffling is indistinguishable from — and for most metrics smaller than —
  what randomly dropping the same number of possessions produces.
- **Level shift: p < 0.005 for five of six metrics.** Ambiguity genuinely
  shifts metric levels, well outside sampling noise.
- **`net_efficiency` is invariant in level too**: shift +0.0006, p = 0.94. The
  offensive and defensive selection effects cancel almost exactly, as they must
  when every possession is one team's offence and another's defence.

**Conclusion: possession ambiguity does not materially change any team ranking
in this dataset, and net efficiency is insensitive to it in level as well.**
Absolute per-possession *levels* are subset-dependent and must not be quoted
across subsets. The separate and more important caveat the null model exposes
is that 8-team rankings over 12–13 games are fragile in general: random
subsampling alone moves 8–12 rank places in total, so small rank gaps in
`team_rankings.csv` should not be read as meaningful.

## Rankings

`team_rankings.csv` is long format — one row per (metric, team) — so the
direction convention lives in the data as `higher_is_better` rather than only
in documentation. 23 metrics ranked.

`RANK()` is used rather than `DENSE_RANK()`: with 8 teams, competition ranking
is the right semantics — if two teams tie for 1st there is no 2nd, and
`rank_value` reads directly as "teams ahead of you, plus one". `DENSE_RANK`
would compress the scale so that "3rd of 8" meant different things depending on
how many ties happened above. Lower-is-better metrics
(`defensive_efficiency`, `turnover_rate`, `shots_allowed_per_possession`,
`shot_clock_expiration_rate`) are ranked ascending, so rank 1 is always best.
`z_score` uses `STDDEV_POP` because these 8 teams are the entire league, not a
sample from one.

No composite "best team" rating is produced — deferred by scope.

## SQL architecture

DuckDB 1.4.5, in-memory, driven by `scripts/pll_build_team_metrics.py`. Python
does loading, ordering, export and validation; **the metric definitions live in
SQL**.

```
sql/00_base_views.sql             eligible games, participants, eligible shots,
                                  possession confidence subsets, validation flags
sql/team_game_advanced.sql        100 x 133  (CTEs, FILTER aggregates, NULLIF)
sql/team_season_advanced.sql      8 x 121    (totals-based rates, MEDIAN)
sql/possession_length_splits.sql  63         (CASE bucketing, window share)
sql/team_rankings.sql             184        (LATERAL VALUES unpivot, RANK,
                                              STDDEV_POP window)
sql/team_metric_sensitivity.sql   96         (CROSS JOIN subsets, self-join on
                                              the full set, RANK per subset)
```

Determinism: every query has an explicit `ORDER BY` and no metric depends on
row order. Validation check 20 rebuilds every output into a scratch directory
and compares SHA-256 against the committed files.

## Validation

`scripts/pll_validate_team_metrics.py` → `team_metrics_validation_report.csv`,
**20/20 checks passing**. Every numeric check recomputes its value in pandas
from the canonical tables; none of the SQL is re-run to check itself. Check 17
in particular rebuilds 23 columns with completely separate groupby code.

Check 20 rebuilds into a **temporary directory** rather than over the files
under test — an earlier version overwrote its own inputs mid-run, which made
checks 1–19 describe a different artifact than the one on disk.

## Differences from NCAA / Lacrosse Reference

Lacrosse Reference's public methodology was read before any metric was defined.
Of 119 documented metrics: 40 formula-identical to the LR concept, 47 adapted,
23 PLL-only, 9 examined and not built.

| LR concept | PLL version | Same formula? | Why it changes |
|---|---|---|---|
| offensive efficiency = goals/possessions | points/possessions | **No** | NCAA has no two-point goal; using goals would discard 12.1% of PLL scoring. `goals_per_possession` is also published for direct comparability. |
| "Efficiency" = % of possessions ending in a goal | `goals_per_possession` | Yes | A goal always closes its possession, so the two are identical here. |
| defensive efficiency | points allowed / defensive possessions | No (same reason) | — |
| cumulative efficiency | not built | — | LR adds a team's defensive gap vs. league-average offence. That is a light opponent adjustment, and opponent adjustment is out of scope for Phase 5. `net_efficiency` is published as the unadjusted difference and labelled as such. |
| shooting percentage | `shooting_pct` = goals/shots | Yes | Unchanged. `points_per_shot` added as the PLL-specific companion. |
| shots per possession | `shots_per_possession` | Yes | Unchanged. |
| turnover rate | `turnover_rate` | Yes | Unchanged (official numerator). |
| faceoff win % | `faceoff_win_pct` | Yes | PLL's own denominator includes no-decision draws. |
| efficiency by possession length | `possession_length_splits.csv` | **Adapted** | LR buckets short/medium/long at 30s/60s. PLL's two shot clocks (32s off a faceoff, 52s on a change of possession) make different edges informative, and a same-second bucket was needed to isolate a logging artifact. |
| time of possession | official only | **Not built** from PBP | See "Time of possession". |
| efficiency by possession start type | partially deferred | **Adapted** | Only the faceoff split is published. 922 possessions carry `start_reason = other_confirmed_control` (team known, mechanism unknown), so a defensive-stop vs. ground-ball split would assign ~21% of possessions to a bucket the feed never established. |
| clearing / riding efficiency | not built | **Deferred** | Official clear/ride counts pass through as raw columns only. |
| EMO metrics | opportunity-denominated | **Adapted** | See "Man-up". |

## Deferred and unsupported

| Metric | Status | Reason |
|---|---|---|
| `man_up_possessions` | unsupported | PLL's man-up tag is on goals only; the column would be a renamed goal count and every rate on it is degenerate. |
| `assist_metrics` | unsupported | `shotAssistId` is a pre-shot pass indicator, not a confirmed assist, and unpopulated is not a negative assertion. |
| `time_of_possession_reconstructed` | deferred | r = 0.58 vs. official, 0.54–1.00 coverage range. |
| `clearing_efficiency` | deferred | The feed logs no clear event, so a clear cannot be tied to a possession boundary; and 36.2% of possessions have an unconfirmed start mechanism — exactly the field this metric needs. |
| `possession_source_efficiency_split` | deferred | 922 possessions have a known team but unknown control-gain mechanism. |
| `opponent_adjusted_efficiency` | deferred | Out of scope for Phase 5; every efficiency here is raw. |

## Known limitations

1. **Not opponent-adjusted.** A team's efficiency reflects its schedule.
2. **8 teams, 12–13 games.** The null model shows random resampling alone moves
   8–12 total rank places; small rank gaps are not meaningful.
3. **Per-possession levels are subset-dependent.** 0.271 PPP on the full set vs.
   0.326 on the non-ambiguous set are answers to different questions.
4. **68 of 100 team-game rows carry at least one unresolved Phase 4.25
   validation issue**, almost all ±1 in turnovers or ground balls. Single-game
   turnover/ground-ball/shot-clock/save/penalty values should not be treated as
   exact without checking the flags; season aggregates are affected by well
   under 1%.
5. **`observed_possession_seconds` is a lower bound**, never a time of
   possession.
6. **Possession-length splits cover 47.8% of possessions.** The excluded half
   is not random — it is disproportionately ambiguous and non-scoring — so the
   splits describe cleanly-bounded possessions, not all possessions.
7. **Man-up analysis is opportunity-denominated and partly official-sourced.**
   No penalty-clock state is reconstructed anywhere.
8. **`caused_turnovers` exists only at the official team level** and can never
   be attributed to a possession or player from this feed.
