> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# 2026 Player Statistics — Guide

How to read `data/processed/2026/player_stats_2026.csv` (228 rows, 123 columns)
and `player_leaderboards_2026.csv` (12,788 rows). Definitions of record live in
`metric_catalog_2026.csv`; this guide is the narrative.

Upstream methodology: [`../PLAYER_VALUE_METHODOLOGY.md`](reference/PLAYER_VALUE_METHODOLOGY.md)
(Phase 6), [`../PLAYER_ADJUSTED_VALUE_METHODOLOGY.md`](reference/PLAYER_ADJUSTED_VALUE_METHODOLOGY.md)
(Phase 7), [`PLAYER_VALUE_ACCOUNTING.md`](PLAYER_VALUE_ACCOUNTING.md),
[`SHRINKAGE_POLICY.md`](SHRINKAGE_POLICY.md),
[`CROSS_POSITION_COMPARABILITY.md`](CROSS_POSITION_COMPARABILITY.md).
Phase 8 re-derives none of it; validation check 16 compares 34 carried columns
bit-for-bit against their Phase 6/7 sources.

---

## 0. Five rules, before any number

1. **A rate without its denominator is not a statistic.** Three players led
   shooting percentage at 1.000, on 1, 2 and 1 shots.
2. **Raw ≠ shrunk, and neither is "better".** Raw answers *what happened*.
   Shrunk answers *what is this player's ability*. Both are published; they are
   never substituted for one another.
3. **A value total is not comparable across positions.** The observed spread of
   `EPA_points_raw` is 9.59 for goalies and 1.46 for defensive field players —
   6.6×. Partition by `canonical_position` before reading, or use the
   `position_rank` that sits on every leaderboard row.
4. **Defensive value is PARTIAL.** 0.0 means "caused turnovers at the position
   group's per-game rate", not "an average defender".
5. **Individual two-point shooting ability is not identifiable from 2026.**
   Production may be described; ability may not be ranked.

---

## 1. The two blocks

`player_stats_2026.csv` is deliberately split, and the blocks never mix.

**BLOCK A — descriptive production.** Counting stats and simple rates from the
official box score, plus the event-derived goalie shot split Phase 6 reconciled.
Everything here answers *what is on the stat sheet*. **Appearing in Block A
confers no value**: assists, ground balls and penalties are carried because you
need them to interpret Block B, and are explicitly unvalued in the accounting.

**BLOCK B — advanced value.** Phase 6 components and Phase 7 usage, reliability
and positional normalization, selected unchanged.

---

## 2. `scoring_points` is not what PLL calls "points"

This is the single easiest way to publish a wrong leaderboard, so it is stated
first.

```
scoring_points = one_point_goals + 2 × two_point_goals
```

It is PLL **points from goals**, and it sums to the official final score
exactly: 1,190 league-wide, matching the sum of every final score in `games.csv`.
Validation check 4 asserts this.

PLL's own `points` column in `player_game_stats.csv` is
`onePointGoals + 2×twoPointGoals + assists` — the NCAA points convention —
verified on all 1,824 rows. **It is not a scoring quantity and is never used as
one here.** The consequence is visible and deliberate:

| Player | `scoring_points` (here) | PLL's `points` |
|---|---|---|
| Marcus Holman | 34 | 42 |
| CJ Kirst | 34 | 39 |
| Logan Wisnauskas | 25 | 34 |

If you want the PLL-site figure, add `official_assists` yourself and say that
you did. `official_assists` is published separately, is CONTEXTUAL, and is
reliable — exact in 100 of 100 team-games.

---

## 3. Positions and roles — three different columns

| Column | What it is |
|---|---|
| `roster_position_code` | The raw box-score label. |
| `canonical_position` | The modal non-null label over the player's games. One of attack / midfield / short_stick_defensive_midfield / long_stick_midfield / defense / faceoff / goalie / unknown. Resolved once per **player**, not per game. |
| `position_group` | The coarse grouping used for positional baselines. |
| `value_role` | The role the **value accounting** uses: `offensive_field`, `defensive_field`, `faceoff`, `goalie`, `unclassified_field`. |

`canonical_position` and `value_role` disagree on purpose. A midfielder who took
29 draws is `midfield` on the roster and can still be outside the `faceoff`
value role. Two of 228 players carry no label in any game and are mapped
`unknown` rather than guessed.

Phase 7 **tested and rejected** Lacrosse Reference's 30%-opportunity-share rule
for splitting offence from defence: applying it put 24 of 96 rostered defenders
(21 of 42 SSDMs) in the offensive class, because the feed attributes 741 caused
turnovers against 4,106 shots. The roster label wins, and `mapping_reason`
records why on every row.

---

## 4. The value accounting

```
EPA_points_raw = shooting_value_raw
               + turnover_value_raw
               + faceoff_value_raw
               + goalie_value_raw
               + defensive_value_partial_raw
```

Validation check 9 and a test re-add this for all 228 players. The unit is
**PLL points above the league-average expected outcome of the same opportunity**.

Two components are deliberately **absent**:

- **Ground balls.** 1,095 of 3,091 ground balls immediately follow a faceoff,
  99.7% go to the faceoff-winning team and 61.5% to the winner himself. A
  per-ground-ball credit would pay the same player twice for one change of
  possession 673 times. There is also no ground-ball *opportunity* denominator
  in the feed. The empirical event value survives as the
  `ground_ball_event_value_descriptive` column of `player_value_components.csv`,
  outside every total.
- **Assists.** The points from an assisted goal are already fully priced in the
  shooter's shooting value; an independent assist credit would create two
  players' worth of value from one goal.

Both carry a `*_value_status` column saying so, and a test fails if a valued
column for either ever appears.

### Reading the components

| Component | Opportunity base | Defined for |
|---|---|---|
| `shooting_value_raw` | shot attempts | 192 shooters |
| `turnover_value_raw` | touches | everyone with a touch |
| `faceoff_value_raw` | faceoffs | 47 draw-takers |
| `goalie_value_raw` | shots on goal faced | 16 goalies |
| `defensive_value_partial_raw` | **games played** | everyone |

The mixed bases are why `EPA_points_raw` is class C. They are also why a player
can carry a non-zero `offensive_EPA_points_raw` on zero recorded offensive
opportunities: turnover value is denominated on *touches*, and a player who
handled the ball without losing it earns credit while `shots + turnovers` stays
at zero. Thirty-seven such rows exist and each is reported as a class-C
`VALUE_ON_EMPTY_NAMED_BASE` sanity flag rather than hidden.

---

## 5. Raw vs shrunk — the policy

Every rate is published twice, in separately named columns, on separate
leaderboard rows that each carry the other as `companion_metric_name` /
`companion_metric_value`.

| Question | Use |
|---|---|
| "Who converted the most this season?" | `*_pct` / `*_rate_raw` |
| "Who is the best finisher?" / "What should we expect next season?" | `*_rate_shrunk` |
| "Who has enough evidence to be ranked at all?" | `*_reliability` and the eligibility flags |

**The choice matters a great deal**, which is why both are shown:

| Rate | Players | Spearman (raw vs shrunk rank) | Max move | Moved |
|---|---|---|---|---|
| shooting_pct | 192 | 0.675 | 91 places | 189 |
| faceoff_win_pct | 47 | 0.629 | 20 places | 43 |
| save_pct | 16 | 0.847 | 6 places | 13 |

Presenting one ordering without the other presents a methodological choice as a
finding. Never write a shrunk value into a `*_raw` column; a test asserts the
four pairs are not numerically identical.

---

## 6. Reliability and the qualification gates

`reliability = n / (n + κ)`, where κ is the empirical-Bayes prior strength
estimated by method of moments from the 2026 league. Validation check 14
recomputes all five reliability columns from Phase 7's published κ.

**No gate is a round number.** Reliability ≥ 0.5 — the point at which the
posterior weights the player's own record above the league prior — implies a
different trial count for every rate:

| Rate | κ | Trials for 0.5 | Clearing |
|---|---|---|---|
| faceoff_win_pct | 15.9 | 15.9 draws | 18 / 47 |
| shooting_pct | 70.8 | 70.8 shots | 13 / 192 |
| one_point_pct | 75.3 | 75.3 attempts | 8 / 168 |
| turnovers_per_touch | 108.8 | 108.8 touches | 81 / 228 |
| save_pct | 300.3 | 300.3 trials | **1 / 16** |
| two_point_pct | capped 1e6 | unreachable | **0 / 127** |

The turnovers-per-touch κ is the one number Phase 8 estimated, using Phase 6's
own `beta_prior_by_moments` — imported, not reimplemented.

**Only 13 of 192 shooters clear the shooting gate.** That is the finding, not an
inconvenience: one PLL season barely identifies individual shooting ability.

---

## 7. The goalie trial base — two different counts

`save_pct = saves / (saves + goals_allowed)` — the official definition, and the
base Phase 7 estimated the prior on (2,412 league trials, max 309).

`shots_on_goal_faced` is a **different and larger** count: 2,567 league-wide.
The event log records shots on goal that the official box score resolves as
neither a save nor a goal.

Both are correct; they answer different questions. Every save-*rate* row is
denominated on `saves+goals_allowed`; only the genuinely per-shot goalie value
metrics (`goalie_value_raw`, `goalie_EPA_per_SOG`, `points_allowed_per_sog_faced`)
use `shots_on_goal_faced`. Validation check 7 and a test enforce the split, and
this was a real defect found and fixed during the audit.

**No shot-quality adjustment is possible.** Shot events carry no location, no
distance and no defender — verified across all 51 raw games. A keeper behind a
defence that concedes point-blank looks worse.

---

## 8. Usage — an opportunity share, not possession participation

```
offensive_play_share = (shots + turnovers) / the same, summed over the team
                       in the games the player appeared in
```

**This is not the share of team possessions the player was on the field for.**
The PLL feed carries no lineup, substitution, shift or minutes data of any kind.
Numerator and denominator are both counted individual actions, and roughly 19%
of league turnovers are attributed to no player at all — so the numerator is
understated by an unknown, non-uniform amount.

It is also class C: attack averages 0.114 and defensive field 0.013. **The
ordering is the role, not the player.**

### The usage-expectation family is nearly inert in 2026

Phase 7 fitted `E[offensive EPA | usage]` by 5-fold cross-validated model
selection over constant / linear / quadratic. **The constant won.** So
`expected_EPA_given_usage` is a single number — 0.086932 — for all 187 field
players in the fitted population, and the distribution audit flags it as
degenerate. `EPA_vs_usage_expectation` is therefore offensive EPA minus a
constant, correlating with it at Pearson *and* Spearman exactly 1.000.

That is not a bug and it is not useless — it is the finding. Usage does not move
the **mean** of measured value in 2026 (r = +0.07). What usage moves is the
**spread**: the sd of offensive EPA rises from 0.50 in the lowest usage quintile
to 4.73 in the highest. `EPA_vs_usage_expectation_z`, which divides by the
chance sd at the player's own volume, is the column that does the real work.

All three are **EXPERIMENTAL / REVISE_BEFORE_HISTORICAL**: fitted on one season
of 187 players, and a multi-season pool is the first thing that could select a
non-constant model.

`expected_EPA_given_usage` is **NULL** for goalies and faceoff specialists —
outside the fitted population. NULL, never 0, because 0 would be a claim.

---

## 9. Reading the player leaderboards

One row per (category, metric, scope, player), across eleven categories.

**Two scopes per metric:**

- `ALL` — every player for whom the metric is defined. This is the **descriptive
  record** and it is not censored. A player who went 3-for-3 appears at rank 1
  with `denominator_value = 3` on the same row.
- `QUALIFIED` — only players clearing the evidence gate, re-ranked among
  themselves. **Absent entirely for two-point conversion**, and that absence is
  the finding.

**Columns that must not be dropped when you build anything on this file:**

| Column | Why |
|---|---|
| `denominator_name` / `denominator_value` | See rule 1. |
| `reliability_name` / `reliability_value` | How much evidence is behind the rate. |
| `raw_or_shrunk` | `raw`, `shrunk`, `chance_standardized` or `within_position`. |
| `companion_metric_*` | The other half of the raw/shrunk pair. |
| `qualification_rule` / `qualification_reason` | Why this player is (or is not) eligible, in prose, on the row. |
| `canonical_position`, `position_rank`, `position_n_ranked` | The defensible reading of a class-C metric. |

**Ranking is done on the metric value rounded to 12 decimals.** This is not
cosmetic. Phase 7 computes per-game values as `(rate × games) / games`, so two
players who both caused zero turnovers get values equal in every meaningful
sense that differ in the last unit in the last place. Ranking the raw doubles
split 40 identical `defensive_EPA_partial_per_game` values into a group of 8 at
rank 128 and a group of 32 at rank 136 — asserting that eight players were
strictly better than thirty-two others on a difference of 1e-17. `metric_value`
is still published at full precision; only the sort key is rounded.

---

## 10. 2026 player leaders, with sample sizes

**Scoring (counting stats — no evidence gate applies):**

| Metric | Leader | Value | Denominator |
|---|---|---|---|
| scoring_points | Marcus Holman / CJ Kirst (tie) | 34 | 13 / 10 games |
| scoring_points_per_game | CJ Kirst | 3.40 | 10 games |
| goals | CJ Kirst | 34 | 84 shots |
| official_assists | Michael Sowers | 22 | 12 games |
| shots | Dylan Molloy | 98 | 13 games |
| two_point_goals | Bryan Costabile | 7 | 29 attempts |

**Rates — QUALIFIED scope only:**

| Metric | Leader | Value | Denominator | Reliability | Field |
|---|---|---|---|---|---|
| shooting_pct | CJ Kirst | .405 | 84 shots | 0.543 | 13 of 192 |
| faceoff_win_pct | Andrew McMeekin | .614 | 249 draws | 0.940 | 18 of 47 |
| save_pct | Emmet Carroll | .563 | 309 trials | 0.507 | **1 of 16** |
| EPA_per_recorded_opportunity | Marcus Holman | .129 | 98 opportunities | 0.540 | 13 of 228 |
| turnovers_per_touch (low) | Blaze Riorden | .011 | 185 touches | 0.630 | 81 of 228 |

**Value totals — read the position, not the rank:**

| Metric | Leader | Value | Role base |
|---|---|---|---|
| EPA_points_raw | Sean Byrne (G) | +13.64 | 152 shots on goal faced |
| offensive_EPA_points_raw | Logan Wisnauskas (A) | +12.96 | 57 opportunities |
| faceoff_value_raw | TD Ierlan | +10.64 | 353 draws |
| goalie_value_raw | Sean Byrne | +13.55 | 152 SOG faced |
| defensive_value_partial_raw | Brett Makar (D) | +3.10 | 12 games |
| caused_turnovers | Brett Makar | 24 | 12 games |
| EPA_points_null_z | Logan Wisnauskas | +3.99 σ | 57 opportunities |

Every one of these was traced to the underlying box score during the sanity
audit and reconciles exactly. Several are real but heavily sample-dependent —
Wisnauskas shot 25-for-43 (58.1%), the highest in the league on any meaningful
volume, and his reliability is 0.378, below the ranking gate. See
[`2026_METRIC_SANITY_AUDIT.md`](2026_METRIC_SANITY_AUDIT.md) §3 for each case.

**A leader that is a role artifact, not a player finding:**
`EPA_points_per_game`'s top five are all goalies. Games played is the weakest
denominator in the framework — the feed has no minutes — and goalies play whole
games. `turnovers_per_touch`'s qualified leader is also a goalie. Neither is a
defect; both are class-C flags.

---

## 11. Redundancy

`metric_redundancy_2026.csv` measures 133 overlapping player-level pairs, 28 of
them empirically interchangeable. The ones that matter:

| Pair | Why | Action |
|---|---|---|
| `shooting_pct` / `shooting_rate_raw` | Same number. | Quote one. |
| `save_pct` / `save_rate_raw` | Same number. | Quote one. |
| `faceoff_win_pct` / `faceoff_rate_raw` / `faceoff_EPA_per_faceoff` | The EPA version is linear in the win percentage. | Quote one. |
| `two_point_conversion_pct` / `two_point_rate_raw` | Same number. | Quote one. |
| `offensive_EPA_points_raw` / `EPA_vs_usage_expectation` | Constant offset (§8). | Quote one, until a season selects a non-constant usage model. |
| `two_point_attempts` / `two_point_reliability` | Reliability is monotone in trials and the prior is capped, so the "reliability" is just the attempt count rescaled. | Do not present the reliability as evidence — there is none. |
| `goals` / `scoring_points` (ρ = 0.998) | 2026 had only 72 two-point goals. | Distinct by definition; nearly identical in this season. Keep both. |

Among the 16 goalies, most goalie columns correlate above 0.99 with each other
simply because n = 16. Treat the whole goalie block as roughly one finding.
