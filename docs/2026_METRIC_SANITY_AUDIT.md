# 2026 Metric Sanity Audit

**Successful code execution is not completion.** This document is the record of
looking at the actual 2026 numbers — the leaders, the laggards, the small-sample
extremes, the degenerate distributions — tracing every suspicious result back to
the underlying data, and classifying it.

The machine-readable companion is `data/processed/2026/metric_sanity_flags_2026.csv`
(401 rows) and `metric_distribution_audit_2026.csv` (201 rows).

## The classification, and the rule

| Class | Meaning | Count | Action |
|---|---|---|---|
| **A** | Real performance | 11 | Publish. Do not "correct" a surprising result. |
| **B** | Sample-size artifact | 325 | Publish with the denominator; never gate on it silently. |
| **C** | Role/opportunity artifact | 43 | Publish with the position; supply the within-role reading. |
| **D** | Known feed limitation | 22 | Publish the limitation alongside. Never work around it. |
| **E** | **Implementation/data bug** | **0 remaining** | **Fix.** |

**Only class E was ever fixed.** Five class-E defects were found; all five are
below with the fix. Everything else is reported and left alone.

---

## 1. Reconciliation first

Before any judgement about whether a number is surprising, the numbers have to
be right. Independently recomputed in pandas from the original sources:

| Quantity | Phase 8 | Independent recomputation | Source |
|---|---|---|---|
| League points | 1,190 | 1,190 | sum of every final score in `games.csv` |
| Player `scoring_points` sum | 1,190 | 1,190 | official player box score |
| Team `points_scored` sum | 1,190 | 1,190 | official team box score |
| Shots | 4,106 | 4,106 | box score **and** event log agree |
| One-point / two-point attempts | 3,570 / 536 | 3,570 / 536 | event log |
| One-point / two-point goals | 1,046 / 72 | 1,046 / 72 | event log |
| Possessions | 4,388 | 4,388 | `possessions.csv`, partitioned by offence |
| Goalie save trials | 2,412 | 2,412 | saves + goals allowed, matches Phase 7's prior fit |

All 15 official player totals and 19 official team totals reconcile **exactly**
(validation checks 2, 4, 5, 8). Not approximately — exactly.

Spot-checked by hand against the raw box score:

| Player | Games | Shots | Goals | 1PG | 2PG | Assists | `scoring_points` |
|---|---|---|---|---|---|---|---|
| Marcus Holman | 13 | 83 | 28 | 22 | 6 | 8 | 34 |
| CJ Kirst | 10 | 84 | 34 | 34 | 0 | 5 | 34 |
| Logan Wisnauskas | 13 | 43 | 25 | 25 | 0 | 9 | 25 |
| Sean Byrne | 7 | 0 | 0 | 0 | 0 | 0 | 0 (86 sv, 52 ga) |

---

## 2. The five class-E bugs found and fixed

### E-1. Save rates denominated on the wrong base

`save_rate_shrunk` and its qualification gate were denominated on
`shots_on_goal_faced` (2,567 league-wide), while `save_pct` and Phase 7's prior
are defined on `saves + goals_allowed` (2,412). The event log records shots on
goal the box score resolves as neither a save nor a goal, so the two counts
differ by 155 — up to 23 for a single keeper.

**Fix.** Every save-*rate* row now carries `saves+goals_allowed`; only the
genuinely per-shot goalie value metrics use `shots_on_goal_faced`. The
qualification rule text, which said "301 shots on goal faced", now says what it
means. Validation check 7 and a test enforce the split.

### E-2. Ranking on floating-point residue

Phase 7 computes a per-game value as `(rate × games) / games`. Two players who
both caused zero turnovers get values that are equal in every meaningful sense
and differ in the last unit in the last place. Ranking the raw doubles split
**40 identical `defensive_EPA_partial_per_game` values into a group of 8 at rank
128 and a group of 32 at rank 136** — asserting that eight players were strictly
better than thirty-two others on a difference of 1e-17.

**Fix.** Both leaderboards now rank on the value rounded to 12 decimals, far
below the resolution of any real difference in this system. `metric_value` is
still published at full precision. A synthetic unit test covers it.

### E-3. `EPA_points_raw` published with no sample size

The leaderboard emitted `denominator_name = 'role-specific opportunity base'`
and `denominator_value = NULL` — precisely the metric that most needs a
denominator, shipped without one.

**Fix.** Each player now carries his own role's opportunity count, named:
`shots_on_goal_faced (goalie role base)`, `faceoffs (faceoff role base)` or
`recorded_offensive_opportunities (field role base)`. A `position_rank` and
`position_n_ranked` were added to every leaderboard row at the same time, so the
defensible within-role reading sits beside the class-C overall rank.

### E-4. A missing argument in the catalog source

`turnovers_per_possession` was constructed without its `unit`, shifting every
subsequent positional argument by one — the catalog modules would not import at
all. This is the partially-written state the interruption left behind.

**Fix.** Unit restored. `pll_metric_catalog.py` now validates the whole catalog
at import and raises on a missing column, a duplicate key, a status outside the
closed vocabulary, an UNSUPPORTED metric with no stated reason, or a redundancy
cross-reference that points at nothing.

### E-5. Bounds checked by column name instead of by definition

The first audit implementation inferred "this is a percentage" from the column
name. It reported **680 false out-of-bounds failures** — the `*_percentile`
columns are on a 0–100 scale, not 0–1 — while missing
`possession_span_coverage_ratio`, which is bounded and does not end in `_pct`.
It also flagged `turnover_rate` (turnovers *per possession*, not a proportion).

**Fix.** Bounds now come from the catalog's declared `unit`. The audit checks
the data against the published contract rather than against a naming convention.

Two further defects in the audit's own reporting were corrected the same way:
`n_iqr_outliers` now reports NULL rather than `0` when the interquartile range
is zero (more than 79% of players never face a shot or take a draw, so `q1 = q3
= 0` and the Tukey rule degenerates — reporting "0 outliers" for a column whose
maximum is 332 is worse than reporting nothing), and `SHRINKAGE_FULLY_COLLAPSED`
now tests relative spread rather than bit-equality, which is why the two-point
collapse is now flagged.

---

## 3. Suspicious results traced individually

### 3.1 Whipsnakes led net efficiency and went 5–8 — **A**

+0.0346 points per possession on 1,144 possessions, a +14 point differential,
and a losing record. Traced to `games.csv`: both figures reconcile exactly. A
positive differential distributed as narrow losses and comfortable wins produces
exactly this. **Real.** It is why efficiency is published as efficiency and not
sold as a power rating.

### 3.2 Logan Wisnauskas shot 58.1% — **A, with B**

25 goals on 43 shots, verified against the official box score game by game. The
highest conversion rate in the league on any meaningful volume, and it drives
his league-leading `offensive_EPA_points_raw` (+12.96) and `EPA_points_null_z`
(+3.99σ) on only 57 recorded offensive opportunities.

**Real performance.** Also 43 shots against a reliability-0.5 threshold of 70.8,
so `shooting_reliability = 0.378` and he does **not** qualify for the shooting
leaderboard. Both facts are on the row. His shrunk shooting rate is 0.389
against a raw 0.581 — the shrinkage is doing exactly what it is for.

### 3.3 A goalie leads `EPA_points_raw` — **C**

Sean Byrne, +13.64 on 152 shots on goal faced in 7 games, ahead of Marcus Holman
(+13.03 on 98 offensive opportunities). The opportunity bases are not
commensurate:

| Role | n | sd of `EPA_points_raw` |
|---|---|---|
| goalie | 17 | **9.59** |
| offensive field | 100 | 3.93 |
| faceoff | 13 | 4.39 |
| defensive field | 96 | 1.46 |

A 6.6× spread ratio. A goalie faces 150–330 valued events; a defensive
midfielder's only valued defensive event is a caused turnover. **This is not a
ranking of players and is not published as one** — it is the retrospective
record, class C, with `canonical_position` and `position_rank` on every row.
Byrne is 1st of 17 goalies; Holman is 1st of 37 attackmen.

The same effect appears at the bottom: the three lowest `EPA_points_raw` in the
league are all goalies (Liam Entenmann −23.82 on 315 shots faced).

### 3.4 `EPA_points_per_game`'s top five are all goalies — **C**

Games played is the weakest denominator in the framework: the feed has no
minutes, shifts or lineups, so a keeper who played every second and a
midfielder who took four shifts are both "1 game". Nick Washuta ranks 2nd on
**3 games**. Class C, compounded by B.

### 3.5 The qualified `turnovers_per_touch` leader is a goalie — **C and D**

Blaze Riorden, 2 turnovers on 185 touches (0.011). Goalies handle the ball on
every clear and are rarely charged with a recorded turnover. Compounded by the
19% unattributed-turnover gap (§4.1), which is unlikely to be uniform across
roles. Descriptive; not a possession-security ranking.

### 3.6 The `faceoff_value_raw` laggards are not faceoff specialists — **C**

The four worst faceoff values belong to a short-stick defensive midfielder (Ray
Dearth, −4.98 on 37 draws), a midfielder (Ty English, −4.64 on 29) and two more
SSDMs. These are emergency draw-takers measured against a league baseline set by
specialists. The metric is behaving correctly; the *population* is the artifact.
`canonical_position` and `position_rank` are on the row.

### 3.7 Perfect rates at the top of unqualified leaderboards — **B**

251 `DEGENERATE_RATE_EXTREME` flags. The headline cases:

| Metric | "Leader" | Value | Denominator |
|---|---|---|---|
| shooting_pct | Dylan Hess (SSDM) | 1.000 | **1 shot** |
| shooting_pct | Casey Wilson | 1.000 | **2 shots** |
| faceoff_win_pct | Chris Merle (SSDM) | 1.000 | **1 draw** |
| one_point_conversion_pct | Matthew Dunn | 1.000 | **1 attempt** |
| points_per_shot | Henry Bard (D) | 2.000 | **1 shot** (a two-pointer) |
| turnovers_per_touch | Mark Glicini | 0.000 | **2 touches** |

These rows are **not removed**. The `ALL` scope is the descriptive record and
censoring it would be a different kind of lie. They are flagged, they carry
their denominator, and the `QUALIFIED` scope exists for the other question.

Three `RAW_SHRUNK_ORDER_FLIP` flags make the same point at the top of the table:
the raw shooting leader is Dylan Hess (1.000 on 1 shot); the shrunk leader is
Logan Wisnauskas (0.389 on 43).

### 3.8 Nine of the eleven `EXTREME_Z` flags are faceoff values — **A**

`faceoff_value_null_z` ranges from +3.72 (Andrew McMeekin) to −4.98 (Ty
English). Faceoff is by far the most strongly identified rate in the framework —
implied true between-player sd 0.122, κ of only 15.9 draws — so a genuine
faceoff specialist really is many standard deviations from chance. These are
**real**, and they are the one place in the system where individual skill is
cleanly separable from noise.

### 3.9 `expected_EPA_given_usage` is a constant — **A (a finding, not a fault)**

The distribution audit flags it degenerate: one value, 0.086932, for all 187
field players in the fitted population. Traced to `player_usage_model.csv`:
Phase 7's 5-fold cross-validation selected the **constant** model over linear and
quadratic (CV MSE 8.767 vs 8.803 vs 8.847). Usage does not predict the mean of
measured value in 2026 (Pearson r = +0.072, Spearman −0.027).

Consequently `EPA_vs_usage_expectation` correlates with
`offensive_EPA_points_raw` at Pearson *and* Spearman exactly 1.000 — it is a
constant offset. The catalog's `redundancy_class` now records this measured
result, and the metric stays EXPERIMENTAL / REVISE_BEFORE_HISTORICAL.

**The finding survives:** usage moves the *variance* of measured value, not its
mean — the sd of offensive EPA rises from 0.50 in the lowest usage quintile to
4.73 in the highest.

---

## 4. Feed limitations, re-confirmed on the 2026 outputs

### 4.1 19.4% of turnovers belong to nobody — **D**

Player turnover sums: **1,369**. Official team total: **1,699**. The gap is
330 turnovers (19.4%) whose feed description names only a team.

Everything built on player turnovers is understated by an unknown, non-uniform
amount: `turnover_value_raw`, `turnovers_per_touch`, `offensive_play_share` and
`recorded_offensive_opportunities` (which is `shots + turnovers`). No threshold
fixes this and none was applied.

### 4.2 18 faceoffs credited to neither team — **D**

The official box score records 18 more faceoffs league-wide (0.7%) than wins plus
losses, symmetrically for both teams, in 8 of the 50 games. Confirmed identical
at team level and player level. Every faceoff percentage divides by draws
*taken* and is therefore very slightly conservative. Reported as 17 class-D
flags; **not corrected** — the official figure is the published figure.

### 4.3 One goalie clears the save-percentage gate — **D**

κ for save percentage is 300.3 trials. The busiest keeper in the league faced
309. Emmet Carroll is the only qualifier, and a one-row "leaderboard" ranks
nobody. **This is the correct output of the rule.** 2026 alone cannot separate
goalies on save percentage; use the `ALL` scope with the trial count to describe
the season.

### 4.4 Two-point ability: the QUALIFIED scope is deliberately empty — **D**

The observed between-player two-point variance (0.0234) is *smaller* than
binomial noise alone predicts (0.0276). The estimated prior strength is capped
at 1e6; all 127 shrunk rates lie within 5e-6 of the league mean 0.134328 (a
relative spread of 3.7e-05) and every reliability is below 0.001.

No player-level two-point ability estimate is published at any sample size.
**The absence of a QUALIFIED scope is the finding, not an omission.**

Production is still described: Bryan Costabile's 7 two-point goals on 29
attempts is on the counting leaderboard, and `two_point_audit_2026.csv` carries
Wilson intervals so a thin cell looks thin. The Wald standard error collapses to
exactly 0.000 for a 0-for-14 player, which is why the Wilson interval is
published beside it — 0-for-14 is [0.000, 0.215], not a certainty.

### 4.5 Six leaderboards whose top 10 is a single position group — **C**

`save_pct`, `save_rate_shrunk`, `goalie_value_raw`, `goalie_EPA_per_SOG`,
`goalie_value_null_z` (all goalie) and `caused_turnovers` (all defensive field).
Expected for role-specific metrics, and flagged so nobody mistakes one for a
general ranking.

### 4.6 Value earned on an opportunity base the row does not name — **C**

37 rows carry a non-zero value total while their named denominator is zero. All
are `offensive_EPA_points_raw`, `EPA_points_raw` or `EPA_points_null_z` for
players with no shots and no turnovers: turnover value is denominated on
**touches**, while `recorded_offensive_opportunities` is `shots + turnovers`.
Tate Gallagher earned +0.28 on 7 touches in a single game. Phase 6 is working
correctly; a single named denominator cannot express a total that sums
components with different bases. Reported rather than hidden.

---

## 5. Distribution findings

- **Two degenerate distributions.** `expected_EPA_given_usage` (§3.9) and
  `ties` (zero for all eight teams — PLL plays overtime; kept so the identity
  `wins + losses + ties = games_played` is checkable rather than assumed).
- **Fifteen player metrics are more than 50% zero**, all role-determined: 79.4%
  of players never take a draw, 93.0% never face a shot, 83.3% never score a
  two-pointer. Skewness runs to +5.37 (`faceoff_wins`). These distributions are
  not pathological — they are what a roster of specialists looks like — but any
  league-wide mean over them is meaningless. Use within-position summaries.
- **No metric is outside its declared bounds** (validation checks 11 and 22).
- **No infinities anywhere**, no NULL in a CORE team metric, no NULL ranked on
  any leaderboard.
- **The only deliberate NULLs** are the three usage-expectation columns, NULL
  for the 41 players outside the fitted population. NULL, not 0, because 0 would
  be a claim.

---

## 6. What was deliberately *not* done

- No leader was removed for having a small sample.
- No surprising-but-real result was smoothed, capped or winsorised.
- No threshold was chosen to make a leaderboard look sensible; every gate is
  reliability ≥ 0.5 with the trial count set by the rate's own estimated prior.
- No missing statistic was manufactured to fill a category.
- No composite, award score, MVP model or Statistical Tewaaraton was created.
