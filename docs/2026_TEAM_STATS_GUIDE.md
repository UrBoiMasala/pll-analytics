> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# 2026 Team Statistics — Guide

How to read `data/processed/2026/team_stats_2026.csv` (8 rows, 106 columns) and
`team_leaderboards_2026.csv` (280 rows). Definitions of record live in
`metric_catalog_2026.csv`, one row per metric; this guide is the narrative that
tells you which columns to reach for and which to leave alone.

Upstream methodology: [`../TEAM_ADVANCED_METRICS.md`](reference/TEAM_ADVANCED_METRICS.md)
(Phase 5) and [`../POSSESSION_METHODOLOGY.md`](reference/POSSESSION_METHODOLOGY.md)
(Phase 4). Phase 8 re-derives none of it.

---

## 0. The two things to internalise before reading anything

**An eight-team league over 12–13 games is a small sample, and rank gaps are
mostly noise.** The Phase 5 null model resampled possessions and found that
chance alone moves 8–12 total rank places across the table. A one-place gap in
an eight-team standing means very little. Every leaderboard row therefore
carries `gap_to_next_rank`, `league_sd`, `league_median` and `is_tie` so the gap
is visible rather than implied.

**Per-possession LEVELS are subset-dependent; per-possession RANKINGS are not.**
League offensive efficiency is 0.271 points per possession on the full
possession set and 0.326 on the high-confidence subset. These are answers to
different questions, not a better and a worse estimate of one. Rankings survive
the subset (Phase 5 null model, p 0.135–0.922), which is why `rank_stability`
columns travel on every possession-denominated leaderboard row.

---

## 1. The 2026 team table at a glance

| Team | G | W–L | Pts | Opp | Off eff | Def eff | Net eff | Poss/g | FO% | Sv% |
|---|---|---|---|---|---|---|---|---|---|---|
| Whipsnakes | 13 | 5–8 | 158 | 144 | .282 | .247 | **+.0346** | 43.2 | .422 | .563 |
| Archers | 12 | 7–5 | 142 | 113 | .269 | **.235** | +.0345 | 43.9 | .563 | **.595** |
| Waterdogs | 12 | **9–3** | 151 | 137 | **.300** | .283 | +.0165 | 42.0 | .531 | .576 |
| Cannons | 13 | 8–5 | 163 | 151 | .269 | .267 | +.0017 | **46.6** | **.580** | .513 |
| Outlaws | 13 | 7–6 | 153 | 158 | .271 | .277 | −.0064 | 43.5 | .490 | .515 |
| Chaos | 12 | 5–7 | 129 | 149 | .253 | .263 | −.0098 | 42.4 | .350 | .542 |
| Redwoods | 13 | 6–7 | **164** | 166 | .274 | .284 | −.0100 | 46.0 | .573 | .526 |
| Atlas | 12 | 3–9 | 130 | 172 | .251 | .310 | −.0589 | 43.2 | .457 | .471 |

Efficiency is points per possession. `Sv%` is `save_pct_official`.

**Read the top two rows carefully.** Whipsnakes led net efficiency and went
5–8; Waterdogs went 9–3 and ranked third. This is not a bug — it was traced in
the sanity audit and both figures reconcile exactly to the official box score
and the final scores. A +14 point differential across 13 games distributed as
narrow losses and comfortable wins produces exactly this. It is a good
illustration of why efficiency is published as efficiency and not sold as a
power rating.

---

## 2. How the columns are organised

`team_stats_2026.csv` is grouped in blocks, in this order:

| Block | Columns | What it answers |
|---|---|---|
| identity | `team_id`, `team_name` | — |
| record / scoring | 13 | Wins, points, differentials, per-game context |
| possession | 8 | How many possessions, how they started, pace |
| efficiency | 12 | Points, goals, shots and turnovers per possession |
| shooting | 8 | Volume and conversion |
| two-point | 16 | The PLL-specific block — see §4 |
| faceoff | 4 | Draws |
| turnovers / ground balls | 7 | Security and loose-ball recovery |
| goalkeeping / defence | 11 | What the defence conceded |
| discipline / shot clock | 4 | Penalties, expirations |
| extra man | 11 | Opportunity-denominated only — see §5 |
| clearing / riding | 3 | **Raw counts only** — see §6 |
| time of possession | 3 | **Official only** — see §7 |
| uncertainty | 6 | Per-team exposure to ambiguity and residuals |

The last block is the one most systems omit. It is on every row on purpose:
`ambiguous_offensive_possessions`, `truncated_possessions`,
`measurable_span_possessions` and `games_with_unresolved_validation_issue` tell
you how much of a team's row rests on a judgement call.

---

## 3. Which efficiency metric to use

- **`offensive_efficiency` / `defensive_efficiency`** — points per possession.
  These are the CORE pair. Use them.
- **`net_efficiency`** — the difference. Also CORE, but note its denominator is
  offensive *plus* defensive possessions, so its scale is not the same as either
  component's.
- **`*_per_100`** — the same numbers ×100, published because a per-100 figure is
  the convention in most basketball-derived work. Catalogued as
  `IDENTICAL(...)`; never quote both as if they were two findings.
- **`goals_per_possession`** — the NCAA-comparable version, because it ignores
  the two-point arc. Use it *only* for NCAA comparison; for PLL offence use
  `offensive_efficiency`.
- **`turnover_rate` and `turnovers_per_possession` are the same number** under
  two names (both are in the brief). `possession_ending_turnover_rate` is
  **not** a third alias: the possession engine suppresses the companion turnover
  PLL logs alongside an opponent's goal, so possession-ending turnovers (1,352)
  are fewer than turnover events (1,721) and fewer than official turnovers
  (1,699). Do not quote them interchangeably.

**None of this is opponent-adjusted.** No strength-of-schedule adjustment exists
anywhere in this project.

---

## 4. The two-point block

This is what makes a PLL statistical system different from an NCAA one, so it
gets sixteen columns and its own audit table (`two_point_audit_2026.csv`).

**League 2026:** 536 two-point attempts (13.1% of all shots), 72 goals, a 13.4%
conversion rate. The economics:

| | Return per attempt |
|---|---|
| One-point attempt | 0.293 points |
| Two-point attempt | 0.269 points |
| **Difference** | **−0.024 points** |

At 2026 conversion rates the long shot returned slightly *less* per attempt than
the short one, league-wide. Four teams were above water and four below, spanning
+0.107 (Atlas) to −0.230 (Redwoods).

**Three cautions, all of which are on the metric rows themselves:**

1. **The samples are thin.** A team's two-point conversion rests on 38–83
   attempts. The Wilson intervals in the audit table are wide and mostly
   overlap: Redwoods [0.015, 0.120] against Outlaws [0.113, 0.286] is the widest
   separation in the league and it barely clears.
2. **This is a realised return, not a shot-selection finding.** Shot events in
   this feed carry no location, no distance and no defender. Whether a team's
   negative return means bad shot selection, good shots that missed, or defences
   that concede long looks is unobservable here.
3. **`two_point_conversion_pct` is CONTEXTUAL, never a headline.** Publish it
   with `two_point_attempts` beside it.

Also in the audit table, and worth knowing: the two-point return was **positive
only when leading by 4 or more** (+0.148 on 64 attempts) and among the highest-
volume shooters (+0.101 on 204 attempts by players with 11+ attempts). Both cells
are small; neither supports a causal claim.

---

## 5. Extra man — opportunities, never possessions

**PLL's man-up tag lands on GOALS ONLY.** All 90 tagged events in 2026 are valid
goals. There is therefore no man-up *possession* anywhere in this system, and
`man_up_possessions` is catalogued UNSUPPORTED. Man-up shot volume comes from
the official box score, and every extra-man rate is denominated on the
**opportunity** (`timesManUp` / `timesShortHanded`), never on a possession. No
penalty-clock state is reconstructed.

Denominators are small — 22 to 41 man-up opportunities per team — so treat the
whole block as CONTEXTUAL even where the catalog says CORE for the rate itself.

---

## 6. Clearing and riding — counts only

`clears`, `clear_attempts` and `ride_attempts` are official box-score counts and
are published as counts. **No clearing or riding efficiency exists**, and one
was not manufactured: the event log has no clear or ride events to build a
defensible denominator from. `clearing_efficiency` is catalogued DEFERRED and
`riding_efficiency` UNSUPPORTED, each naming the missing input. A test asserts
that no column matching `clear*`/`ride*` ever acquires `pct`, `rate` or
`efficiency` in its name.

---

## 7. Time of possession — the official figure only

Use `time_of_possession_official_seconds` and its per-game companion.

A possession **span** — the interval from a possession's first logged event to
its last — is *not* time of possession. It recovers a median 75% of PLL's
official figure, with a 0.54–1.00 range and r = 0.58, because it excludes
transition, clearing and dead-ball time. Worse, 871 possessions league-wide are
opened and closed by the same single event, so their span is 0 by construction:
an absence of measurement, not a fast possession.

The span columns therefore stay in `team_season_advanced.csv` (Phase 5) and are
**not** carried into the published table. `possession_span_coverage_ratio` *is*
carried, so the size of the gap stays visible.
`time_of_possession_reconstructed` is catalogued DEFERRED / DO_NOT_USE.

---

## 8. Faceoffs: the denominator has a wrinkle

`faceoff_win_pct` divides by `faceoffs`, which is the count of draws **taken**.
The official box score records 18 more faceoffs league-wide (0.7%) than it
records wins plus losses — symmetrically for both teams, in 8 of the 50 games.
Those draws are credited to neither side.

This is a property of the source, reported as 17 class-D
`OFFICIAL_SOURCE_DISAGREEMENT` sanity flags and **never corrected**. The
practical consequence is that every faceoff percentage in this system is very
slightly conservative. It is not a defect and it does not move any ranking.

---

## 9. Reading the team leaderboards

`team_leaderboards_2026.csv` is long: one row per (category, metric, team),
across eight categories — `offense`, `defense`, `shooting`, `possession`,
`faceoff`, `goalie_defense`, `two_point`, `extra_man`.

| Column | Why it is there |
|---|---|
| `denominator_name`, `denominator_value` | Non-negotiable. A rate without its denominator is not a statistic. |
| `higher_is_better` | The direction is data, not a convention the reader must remember. `turnover_rate` rank 1 is the *lowest* rate. |
| `league_mean` **and** `league_median` | Eight-team distributions are small enough for one team to move the mean visibly. |
| `gap_to_next_rank`, `is_tie` | So a meaningless gap looks meaningless. |
| `teams_changing_rank_high_confidence`, `rank_stability_note` | Joined from Phase 5's possession-sensitivity analysis: did restricting to high-confidence possessions move anyone? |
| `z_score` | Standardised within the metric, across 8 teams. Interpret loosely. |

Ranking uses competition ranking (`RANK()`), on the metric value **rounded to 12
decimals**. The rounding is not cosmetic — see the player guide §9 for the defect
it fixes.

Phase 5's `team_rankings.csv` is **not** replaced. It remains the Phase 5
artifact; the Phase 8 leaderboard is the publication view with denominators and
stability attached.

---

## 10. Team leaders, 2026

Rank 1 in each category, with the denominator:

| Category | Metric | Leader | Value | Denominator |
|---|---|---|---|---|
| offense | offensive_efficiency | Waterdogs | 0.300 | 504 off. poss. |
| offense | net_efficiency | Whipsnakes | +0.0346 | 1,144 poss. |
| offense | points_per_game | Redwoods | 12.62 | 13 games |
| defense | defensive_efficiency | Archers | 0.235 | 481 def. poss. |
| defense | opponent_shooting_pct | Archers | 0.232 | 461 shots faced |
| defense | turnovers_forced_per_def_poss | Chaos | 0.408 | 566 def. poss. |
| shooting | shooting_pct | Whipsnakes | 0.286 | 538 shots |
| shooting | points_per_shot | Waterdogs | 0.302 | 500 shots |
| possession | team_possessions_per_game | Cannons | 46.6 | 13 games |
| possession | turnover_rate (low) | Cannons | 0.348 | 606 off. poss. |
| faceoff | faceoff_win_pct | Cannons | 0.580 | 343 draws |
| goalie_defense | save_pct_official | Archers | 0.595 | 264 trials |
| two_point | two_point_conversion_pct | Outlaws | 0.184 | 76 attempts |
| two_point | two_point_attempt_rate | Atlas | 0.162 | 474 shots |
| extra_man | man_up_points_per_opportunity | Waterdogs | 0.474 | 38 opportunities |

Archers lead every defensive category and the save percentage; the two are not
independent, and `save_pct_official` and `opponent_shooting_pct_on_goal`
correlate at ρ = −1.000 across eight teams (they are near-complements). Treat
them as one finding.

---

## 11. Redundancy: metrics that are not two findings

`metric_redundancy_2026.csv` measures what the catalog declares. Fifteen
team-level pairs are **empirically interchangeable** (|r| ≥ 0.99 *and*
|ρ| ≥ 0.99). The ones worth knowing:

| Pair | Why |
|---|---|
| `turnovers_per_possession` / `turnover_rate` | Same formula, two names. |
| `offensive_efficiency` / `offensive_efficiency_per_100` | Factor of 100. |
| `one_point_conversion_pct` / `points_per_one_point_attempt` | A one-point goal is worth one point. |
| `two_point_conversion_pct` / `points_per_two_point_attempt` | Factor of 2. |
| `one_point_goals` / `one_point_points`, `two_point_goals` / `two_point_points` | Factors of 1 and 2. |
| `save_pct_official` / `opponent_shooting_pct_on_goal` | Near-complements. |

And one that is a **coincidence of n = 8, not a relationship**:
`games_played` and `playoff_games` correlate at exactly 1.000, because the only
teams that played 13 games are the two that played a quarterfinal. It is in the
file as a standing reminder that a correlation over eight teams is fragile.
