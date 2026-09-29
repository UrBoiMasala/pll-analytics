# PLL 2026 Usage, Reliability and Positional Normalization (Phase 7)

The layer between measuring player value and comparing players. Phase 6 built
`EPA_points` — what each player's recorded actions produced against
league-average expectation on the same opportunities. Phase 7 answers the
questions you have to answer before those numbers can be put next to each other:

> How much opportunity did the player get? How efficient was he with it? How
> unusual is that? How much evidence is behind it? And which of these numbers
> mean the same thing for a goalie and an attackman?

**Phase 7 builds no Statistical Tewaaraton, no MVP score, no award ranking and
no cross-position composite of any kind.** A validation check and four tests
fail if one appears.

Written to be readable by someone who knows sports analytics but has never seen
this repository.

---

## 1. Why this phase exists

Phase 6 ended with an explicit recommendation *not* to proceed to an award
model, and named the missing work: usage adjustment, positional normalization, a
shrinkage decision, and cross-role comparability. Two Phase 6 findings made that
unavoidable.

**Raw totals rank by opportunity volume.** A goalie faces 150–330 shots on goal;
an attackman takes about 80 shots. The observed standard deviation of
`EPA_points` is 9.59 for goalies and 1.46 for defensive field players — a 6.6×
spread that is a property of what the feed counts, not of how much those players
contributed.

**Shooting rankings are mostly noise.** 219 of 228 shooting ranks moved under
shrinkage. Something had to decide whether that instability disqualifies raw
shooting value, and on what grounds.

---

## 2. Usage: the exact definition

```
recorded_offensive_opportunities  = shots + turnovers          (official box score)

offensive_play_share = recorded_offensive_opportunities
                     ÷ the same quantity summed over the player's TEAM
                       in the games he actually played
```

### Why shots + turnovers, and nothing else

The quantity being proxied is "how much of the team's offensive workload did
this player personally take on". The feed attributes exactly two kinds of
individually-credited action that **consume** an offensive opportunity: a shot
attempt (he used a possession trying to score) and a turnover (he ended one
without a shot). They are disjoint events, so nothing is counted twice, and
together they cover the ways a named player finishes an offensive sequence.

**Assists are excluded.** An assist attaches to a goal that is *already* counted
as the shooter's shot attempt. Including it would count one offensive sequence
twice at team level and inflate feeders relative to shooters as a pure
accounting artefact. An assist-inclusive alternative is run in the sensitivity
analysis (it moves 191 of 228 usage ranks but only by a rank correlation of
0.997 — it changes almost nothing, which is not a reason to adopt a
double-counting definition).

**Ground balls are excluded**, for the reason Phase 6 gave: 1,095 of 3,091
immediately follow a faceoff and 99.7% go to the winning team, so they measure
faceoff outcome, not offensive workload.

**Faceoffs are excluded.** A faceoff win is already paid in `faceoff_value`.
Counting it as an offensive opportunity as well would credit the same draw twice
— once as workload, once as production. A test enforces that a specialist's
offensive usage is strictly smaller than his faceoff count.

### Why the denominator is games played

A player who missed five games is not a low-usage player; he is a player who was
absent. The primary share therefore divides by the team's opportunities **in the
games he appeared in**. Because the denominator differs per player, these do not
sum to 1 within a team — so a second measure, `offensive_play_share_season`,
uses the full-season team denominator and **does** sum to exactly 1.000 per
team, which is what validation check 7 asserts. A mid-season mover contributes a
separate component to each of his teams.

### What usage explicitly is NOT

**It is not the share of team possessions the player was on the field for.** The
PLL feed carries no lineup, substitution, shift or minutes data of any kind,
verified across all 51 raw games in Phases 1–6. Every share in this phase has a
countable numerator and denominator and neither is a possession or a second of
time. Validation checks 21 and 22 scan every Phase 7 output and every Phase 7
query for a possession- or duration-denominated column; two tests do the same.

### Known limitation, carried on every row

Shots reconcile exactly to team totals (4,106 in 100/100 team-games).
Player-attributed turnovers do not: 1,369 against an official team total of
1,699, because roughly **19% of the league's turnovers name only a team**. Both
sides of the share are built from player-attributed sums, so the ratio is
internally consistent, but the absolute opportunity count is understated for
everyone. A shots-only alternative (exact attribution, no turnovers) is run in
the sensitivity analysis: rank correlation 0.959.

---

## 3. The audit of Phase 6's `play_shares`

Phase 6 published `play_shares` — appearances anywhere in the eligible event log
— as the Lacrosse Reference usage proxy. Phase 7 audited it **before** defining
anything, and did not modify it: `event_log_play_shares` reproduces it exactly,
player by player, asserted by validation check 5.

What its 17,063 appearances consist of:

| Source | Appearances | What it is |
|---|---|---|
| Primary actor | 8,779 | shooter, faceoff winner, ground-ball recoverer, penalty committer |
| Goalie of record | 4,106 | **one per shot or goal event** |
| Secondary actor | 3,092 | faceoff loser (1,301) + `shotAssistId` pre-shot passer (1,791) |
| Faceoff `gbPlayerId` | 1,086 | the scrum recovery folded into the faceoff event |

Three findings, and they are why it is reproduced rather than adopted:

1. **Not comparable across positions.** Per game: faceoff 38.0, goalie 27.4,
   attack 8.8, midfield 6.0, SSDM 3.5, LSM 3.2, defense 2.5.
2. **One faceoff generates up to three appearances** — winner, loser, and the
   scrum recovery, 61.5% of which is the winner himself.
3. **It contains `shotAssistId`**, the unreliable pre-shot-pass indicator that
   every Phase 6 value component deliberately excludes.

And what is missing: **turnovers contribute zero appearances**, because the
feed's turnover events name only a team.

Swapping this project's usage measure for the Lacrosse Reference one moves 226
of 228 usage ranks at a rank correlation of **0.556**. Full detail in
[`docs/USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md`](../research/USAGE_ADJUSTMENT_REFERENCE_RESEARCH.md).

---

## 4. Relationship to Lacrosse Reference

Lacrosse Reference publishes exactly one usage adjustment — *"you just divide
total EGA by play shares"* — and one eligibility rule — *1% of a team's play
shares*. Both are reproduced verbatim:

| Their concept | Reproduced as | Status |
|---|---|---|
| Play shares | `event_log_play_shares` | identical to Phase 6's column |
| uaEGA = EGA ÷ play shares | `uaEPA_per_event_log_play_share` | identical to Phase 6's `total_player_value_per_play_share` |
| 1% team play-share minimum | `future_award_input_eligible` | adopted verbatim (204 of 228 players clear it) |
| FOGO at 50% of value | `value_role = 'faceoff'` at 50% of **team faceoffs** | denominator changed; see §7 |
| 30% defensive threshold | **tested and rejected** | see §7 |
| Positional baselines, reliability, goalie treatment, award weights | not documented by them | independently derived, or not built |

The uaEGA reproduction is published under a name that cannot be mistaken for
their metric, because their EGA and this project's `EPA_points` are different
estimands (Phase 6, §"Why EPA_points and not EGA").

---

## 5. Usage is not value

Four dimensions, named apart, never blended:

| Dimension | Columns | Question |
|---|---|---|
| **Volume** | `recorded_offensive_opportunities`, `shots`, `faceoffs`, `shots_on_goal_faced` | How many chances? |
| **Usage** | `offensive_play_share` and alternatives | What share of the team's chances? |
| **Total value** | `EPA_points_raw` and its components | How much did he produce? |
| **Efficiency** | `EPA_per_recorded_opportunity`, `shooting_EPA_per_shot`, … | How much per chance? |

**There is no `EPA × play_share` column anywhere.** Multiplying value by usage
would pay a player twice for the same shots — once for the value he generated on
them and once for having taken them — and would make usage a reward in itself. A
test asserts that no published numeric column equals `EPA_points_raw ×
offensive_play_share`.

---

## 6. Usage-adjusted value, and the finding that shaped it

### 6.1 What the data actually says about usage and value

Fitting `E[offensive EPA | offensive_play_share]` over field players with at
least one recorded offensive opportunity (n = 187), by 5-fold cross-validated
MSE over {constant, linear, quadratic}:

| Model | CV MSE | Improvement vs constant |
|---|---|---|
| **Constant (selected)** | **8.767** | — |
| Linear | 8.803 | −0.40% |
| Quadratic | 8.847 | −0.91% |

Both curves are **worse out of sample than a flat line**. Pearson r between
usage and offensive EPA is **+0.072**.

But the spread moves enormously:

| Usage quintile | Mean play share | Mean opportunities | Mean offensive EPA | **sd of offensive EPA** | Mean chance sd |
|---|---|---|---|---|---|
| 1 | 0.007 | 3.2 | −0.12 | **0.50** | 0.63 |
| 2 | 0.017 | 7.1 | −0.21 | 1.01 | 1.02 |
| 3 | 0.046 | 17.0 | +0.11 | 2.07 | 1.81 |
| 4 | 0.088 | 36.5 | +0.39 | 4.02 | 2.44 |
| 5 | 0.136 | 75.4 | +0.26 | **4.73** | 3.65 |

**In 2026, usage moves the variance of measured value, not its mean.** The
observed spread tracks the chance spread closely, which is exactly what you
would see if higher-usage players were not systematically better or worse per
opportunity — just given more chances to land far from zero.

That finding determines the design. A mean-based usage adjustment subtracts
almost nothing; a *scale* adjustment adjusts the thing that actually changes.

### 6.2 The three published quantities

**Efficiency** — "what did he produce per opportunity?"

```
EPA_per_recorded_opportunity = offensive_EPA_points_raw
                             ÷ recorded_offensive_opportunities
```

**Value relative to the usage expectation** — "how much more than a typical
player at his usage level?"

```
EPA_vs_usage_expectation = offensive_EPA_points_raw − expected_EPA_given_usage
```

`expected_EPA_given_usage` is NULL for goalies and faceoff specialists: they are
outside the fitted population and no offensive-usage expectation is defined for
them. It is NULL, never 0, because 0 would be a claim.

**How unusual, given volume** — the column that does the real work:

```
EPA_vs_usage_expectation_z = EPA_vs_usage_expectation ÷ offensive_EPA_null_sd
```

### 6.3 The null standard deviation

`offensive_EPA_null_sd` is the standard deviation the component would have
**under chance alone at the player's own opportunity counts**. Every Phase 6
component is `observed − expected` where `expected` is a constant given the
opportunity counts, and `observed` is a sum of independent opportunity outcomes,
so the sampling variance is available in closed form from the same league
baselines the component was built with:

| Component | Null variance |
|---|---|
| Shooting | `n₁·p₁(1−p₁) + n₂·4p₂(1−p₂)` |
| Turnover | `c_to² · touches · r(1−r)` |
| Faceoff | `c_fo² · faceoffs · p(1−p)` |
| Goalie | `m₁·q₁(1−q₁) + m₂·4q₂(1−q₂)` |
| Caused turnover | `c_to² · games · rate` (Poisson) |

The factor of **4** on two-point terms is where PLL scoring enters: a two-point
attempt pays 2 points, so its variance is `4p(1−p)`, not `p(1−p)`. A long-range
shooter is not just rarer to convert, he is a higher-variance bet, and dropping
that factor would make him look more distinguishable from chance than he is. A
test pins it down.

No resampling is used, because none is needed: a bootstrap over the same 80 shot
outcomes estimates the same binomial variance with Monte Carlo noise added.

`offensive_EPA_null_sd` is NULL, not 0, where the player had no opportunities of
that class — reporting 0 would say the value is known exactly.

---

## 7. Position mapping and value roles

Two different things, produced in `data/processed/2026/player_position_map.csv`
and never conflated.

### 7.1 `canonical_position` — what he is rostered as

PLL publishes seven role-specific labels that map one-to-one; no NCAA convention
is assumed and no label is invented. Resolution is the Phase 6 rule — modal
non-null box-score label, ties broken alphabetically — recomputed independently
by validation check 3.

| PLL label | canonical_position | position_group |
|---|---|---|
| A | attack | attack (37) |
| M | midfield | midfield (63) |
| SSDM | short_stick_defensive_midfield | defensive_field (96) |
| LSM | long_stick_midfield | defensive_field |
| D | defense | defensive_field |
| FO | faceoff | faceoff (13) |
| G | goalie | goalie (17) |
| *(none)* | unknown | unknown (2) |

`position_group` splits attack from midfield, which Phase 6's `baseline_group`
does not. The reason is that the two phases need different things from a
partition: Phase 6 needed groups large enough to estimate a turnover *rate*,
Phase 7 needs groups whose EPA *distribution* is meaningful, and attackmen and
midfielders have visibly different opportunity volumes (mean play share 0.114
against 0.087). Phase 6's `baseline_group` is carried through unchanged
alongside it and nothing in the Phase 6 value layer is recomputed against the
new partition.

Two of 228 players carry no label in any game. They are mapped `unknown` rather
than guessed; both played 1–2 games with fewer than 8 recorded touches.

### 7.2 `value_role` — what he measurably did

Lacrosse Reference documents a classifier of exactly this shape (FOGO at ≥50% of
value from faceoffs, defensive at ≥30% from defensive plays). It cannot be
applied literally: their value is a cumulative event sum while `EPA_points` is a
**signed residual**, and "50% of a possibly-negative sum" is undefined. The
thresholds are therefore applied to **opportunity shares**, which are
non-negative and well defined.

The rule, in order, first match wins:

1. **goalie** — faced at least one shot on goal as goalie of record. Perfectly
   separating in 2026: all 16 players with a shot on goal faced are rostered G,
   and the one rostered G who faced none is mapped goalie by roster and flagged.
2. **faceoff** — took ≥50% of his team's faceoffs in the games he played. A
   *team-share* threshold, not a raw count, so a wing player who took three
   draws in one game cannot meet it. In 2026 it lands in a wide empirical gap:
   the 13 players above it sit between **0.812 and 0.977**, the next-highest
   player in the league is at **0.158**, and nobody falls between. The threshold
   is Lacrosse Reference's published 50%, not fitted to the gap — but the gap is
   why no player's classification depends on it. A test fails if a future season
   puts someone in that band.
3. **offensive_field / defensive_field** — **by roster position**.

### 7.3 Step 3 is a deliberate refusal, and it is the most important design decision here

A measured offence/defence split was built and rejected on evidence. The feed
attributes exactly **one** defensive act — caused turnovers, 741 league-wide —
against 4,106 shots and 1,369 turnovers. Applying the documented 30% defensive
threshold to opportunity shares put **24 of 96 rostered defenders in the
offensive class, including 21 of 42 SSDMs**: a close defender who took four
shots came out "offensive".

That is a measurement artefact of a one-act-wide defensive record, not a finding
about those players. The roster label is used instead, and the reason is written
onto every row in `mapping_reason`:

> `roster_position: measurable opportunities cannot separate offensive from
> defensive field roles (the feed attributes one defensive act, caused
> turnovers, 741 league-wide)`

Faceoff participation outside the specialist role is not discarded: every player
carries `faceoff_team_share` and `takes_faceoffs`, so the three midfielders and
SSDMs who take real draws (Ty English 29, Ray Dearth 37, Mark Glicini 3) are
visible without being relabelled.

**In 2026 no player's `value_role` differs from what his roster position
implies** — all 228 map exactly as attack/midfield → offensive_field,
D/SSDM/LSM → defensive_field, FO → faceoff, G → goalie. That is partly a
property of this season and partly a consequence of step 3 deferring to the
roster; the two rules that *are* measured (goalie, faceoff) happen to agree with
the labels perfectly. Both columns are published so any future divergence is
visible rather than silently absorbed.

---

## 8. Positional baselines

`data/processed/2026/player_positional_baselines.csv` — 218 rows, one per
(scope, group, metric), for 23 metrics across three scopes: `league` (all 228),
`position` (by `position_group`), `role` (by `value_role`).

Each row carries `n_players`, `n_opportunities`, mean, median, sd, MAD, robust
sd, standard error of the mean, p25, p75, min, max.

For `EPA_points_raw`:

| Scope | Group | n | mean | median | sd | robust sd | se(mean) |
|---|---|---|---|---|---|---|---|
| league | ALL | 228 | −0.000 | −0.268 | 3.918 | 1.603 | 0.259 |
| position | attack | 37 | +1.076 | +0.139 | 4.735 | 2.984 | 0.778 |
| position | midfield | 63 | −0.309 | −0.462 | 3.303 | 1.934 | 0.416 |
| position | defensive_field | 96 | −0.369 | −0.319 | 1.461 | 0.982 | 0.149 |
| position | faceoff | 13 | +1.550 | +0.343 | 4.389 | 2.909 | 1.217 |
| position | goalie | 17 | −0.300 | −0.039 | **9.591** | 9.191 | 2.326 |
| position | unknown | 2 | 0.000 | 0.000 | *suppressed* | *suppressed* | — |

### The suppression rule, and why it is 9

A positional sd is published only when the group has **at least 9 players with
the metric defined**. The relative standard error of an estimated standard
deviation is `1/√(2(n−1))`; at n = 9 that is 25%, and below it the denominator
of a z-score is more uncertain than the numerator it is meant to scale. Every
row carries `sd_is_publishable`, `relative_se_of_sd` and, where suppressed, a
stated reason.

For `EPA_points_raw` exactly one group is suppressed: `unknown`, 2 players.
Standardization for those players falls back to the league scope and their
`EPA_position_z` is NULL. Across all 23 metrics, 36 of 218 rows are suppressed
— mostly a positional group having almost no players with a role-specific rate,
e.g. attack for save percentage.

The faceoff group (13) and the goalie group (17) clear the rule, which is why
Phase 7 can standardize them within role at all.

---

## 9. Standardization method

Three forms, published together, none presented as the answer.

The distributions do not straightforwardly support an ordinary z-score:
offensive-field `EPA_points_raw` has skew +0.75 and excess kurtosis +1.7;
defensive-field shooting value has excess kurtosis +3.4; the faceoff and goalie
groups have 13 and 17 members.

| Form | Definition | When it is right |
|---|---|---|
| `*_position_percentile` | mid-rank empirical CDF within the group, 0–100 | **Recommended first.** Assumes nothing about the distribution. Deliberately coarse in a small group — 7.7 percentile points between adjacent faceoff specialists — and that coarseness is information |
| `*_position_robust_z` | `(x − median) / (1.4826 × MAD)` | Second. Same scale as an ordinary z under normality; a single +8 outlier cannot set the denominator |
| `*_position_z` | `(x − mean) / sd` | Last. Familiar, and correct when the group is large and symmetric. NULL where the group has fewer than 9 players |

A **fourth, different** standardization also travels on the table:
`EPA_points_null_z` divides value by the chance spread at the player's own
opportunity volume rather than by his peer group's spread. It answers "is this
distinguishable from chance?" instead of "is this unusual among peers?", and it
is the only one of the four that does not depend on a group's size or
composition.

Sensitivity: ordinary z against robust z moves 209 of 226 ranks at a rank
correlation of 0.987; positional against league-wide standardization moves 224
of 226 at 0.945.

---

## 10. Cross-position comparability

Audited in full in
[`docs/CROSS_POSITION_COMPARABILITY.md`](../research/CROSS_POSITION_COMPARABILITY.md).
The headline conclusions:

- **`EPA_points_raw` is class C — not cross-position comparable.** A shared unit
  is not a shared scale; the opportunity bases differ by 6.6× in observed spread.
- **Efficiency metrics (`shooting_EPA_per_shot`, `EPA_per_recorded_opportunity`)
  are class B** — comparable after conditioning on volume and gating on
  reliability.
- **`EPA_points_null_z` is the one class-A value-adjacent measure**, and even it
  measures unusualness, not contribution.
- **Positional standardization removes the group effect but does not create
  comparability of value.** A 95th-percentile goalie and a 95th-percentile
  attackman are equally unusual within role and are *not* thereby equally
  valuable.
- **The binding constraint is measurement coverage, not statistics.** Offensive
  value rests on 4,106 shots; defensive value rests on 741 caused turnovers with
  no denominator.

---

## 11. Shrinkage and reliability

Policy in [`docs/SHRINKAGE_POLICY.md`](../research/SHRINKAGE_POLICY.md); the summary:

**Raw values describe 2026 and are never overwritten. Shrunk rates estimate
ability and are published separately. Three concepts stay apart:**
`observed_value` (`*_raw`), `estimated_skill` (`*_rate_shrunk`), and
`reliability_adjusted_value` (`*_reliability`, `*_null_z`, posterior intervals).

Reliability is the empirical-Bayes posterior weight

```
reliability = n / (n + kappa)
```

— the weight the posterior puts on the player's own record rather than the
league prior. `kappa` is Phase 6's own estimated prior strength, **imported not
re-derived**, so Phase 6 shrinkage and Phase 7 reliability cannot silently
diverge. Exact 95% beta-posterior intervals accompany every estimate, computed
from a regularized incomplete beta function written out in
`scripts/pll_adjusted_value_models.py` (this repo runs without scipy by choice)
and tested against closed forms.

| Rate | Players | Median / max trials | `kappa` | Implied true between-player sd | Reliability ≥ 0.5 |
|---|---|---|---|---|---|
| **Faceoff win %** | 47 | 8 / 353 | **15.9 draws** | 0.122 | **18 / 47 (38%)** |
| Shooting % | 192 | 9 / 98 | 70.8 shots | 0.053 | 13 / 192 (7%) |
| One-point % | 168 | 9 / 94 | 75.3 shots | 0.052 | 8 / 168 (5%) |
| Save % | 16 | 148 / 309 | 300.3 SOG | 0.029 | **1 / 16 (6%)** |
| **Two-point %** | 127 | 2 / 29 | **capped at 10⁶** | 0.0003 | **0 / 127** |

An **independent** check, sharing no arithmetic with the beta prior: divide each
player's component by its closed-form chance standard deviation and look at the
spread, which is 1.0 under the null that nobody differs.

| Component | Players | sd of null-standardized value | Implied skill share of variance |
|---|---|---|---|
| **Faceoff value** | 47 | **1.830** | **0.70** |
| Caused-turnover value | 228 | 1.291 | 0.40 |
| Turnover value | 228 | 1.268 | 0.38 |
| Goalie value | 16 | 1.320 | 0.43 |
| **Shooting value** | 192 | **1.067** | **0.12** |

The two methods agree. Phase 6's hierarchy is **verified, not repeated** — with
one refinement: save percentage has genuine between-goalie spread (true sd ≈ 2.9
points) but almost no goalie can be separated from the prior, because the busiest
goalie in the league faced 309 shots on goal against a prior strength of 300.
`player_rate_identification.csv` therefore reports a compound label rather than a
single adjective.

---

## 12. Minimum samples: flags, never deletion

**All 228 players stay in every table.** Nobody is dropped for a small sample;
they are flagged out of the leaderboards their sample cannot support, and they
keep their observed production.

| Flag | Rule | 2026 count |
|---|---|---|
| `descriptive_eligible` | played ≥1 eligible game | 228 |
| `rate_ranking_eligible` | reliability ≥ 0.5 on the rate that defines his role | 27 |
| `offensive_rate_ranking_eligible` | shooting reliability ≥ 0.5 (71 attempts) | 13 |
| `reliability_adjusted_eligible` | ≥1 trial of the relevant rate, so a shrunk estimate exists | 200 |
| `future_award_input_eligible` | ≥1% of team event-log play shares (Lacrosse Reference's rule) | 204 |
| `small_sample` | reliability < 0.5 on the role rate | 201 |
| `chance_variation_exceeds_peer_spread` | own chance sd ≥ the positional group's sd | 50 |

**No threshold here is a round number chosen for convenience.** 0.5 reliability
is the point at which a player's own record outweighs the league prior in the
posterior — a property of the estimator — and the trial count it implies is set
by the data separately for each rate: **16 draws, 71 shots, 300 shots on goal**.
A test asserts that no two rates share a threshold and that none lands on a
round multiple of 10. The one adopted threshold that is not derived, the 1%
play-share rule, is adopted because Lacrosse Reference publishes it, and it is
labelled as a reference reproduction.

Two separate smallness flags exist because they mean different things.
`small_sample` is about evidence. `chance_variation_exceeds_peer_spread` catches
high-volume players too — a 96-attempt midfielder has a chance sd of ~4.5
`EPA_points` against a midfield group sd of 3.3, so luck alone could put him
anywhere in his group.

`rate_ranking_eligible` is role-specific by design, and that is why the separate
offensive gate exists: a faceoff specialist with 353 draws is superbly
identified on the rate that defines his role while having taken six offensive
opportunities, and his faceoff reliability must not license him onto an
efficiency-per-shot leaderboard.

---

## 13. Goalie treatment

Goalies have a fundamentally different opportunity structure — 2,567 shots on
goal faced across 16 keepers, against 4,106 shot attempts across 192 shooters —
and their `EPA_points` spread is 9.59 against 3.93 for offensive field players.

They are therefore **never normalized against field players**. Published per
goalie:

- `goalie_value_raw` (Phase 6, unchanged) and `goalie_EPA_per_SOG`
- `save_rate_raw`, `save_rate_shrunk`, `save_reliability`,
  `save_posterior_ci_width`
- `goalie_value_null_sd` and `goalie_value_null_z`
- `EPA_position_percentile` and `EPA_position_z` computed **within the 17-goalie
  group only**

Validation check 17 recomputes the goalie percentile within the goalie group
alone, matches it, and separately asserts it does **not** coincide with a
league-wide percentile. A test additionally fails if the goalie and
offensive-field EPA spreads ever converge to within 2×, which would mean the
separation needs revisiting.

**Can goalie value enter a cross-position award model directly? Not on this
evidence.** The audit classes `goalie_value_raw` as role-specific (class D —
NULL for 212 players). A later phase may include goalies, but it must argue for
the weighting explicitly rather than inheriting a scale from the opportunity
structure. Phase 7 does not decide it.

---

## 14. Faceoff treatment

13 specialists, identified by taking ≥50% of their team's draws (§7.2), on 2,618
league faceoffs.

Published per specialist: `faceoff_value_raw`, `faceoff_EPA_per_faceoff`,
`faceoff_rate_raw`, `faceoff_rate_shrunk`, `faceoff_reliability`,
`faceoff_posterior_ci_width`, `faceoff_value_null_sd`, `faceoff_value_null_z`,
`faceoff_team_share`, and percentiles within the 13-player group.

**Where a specialist's value comes from.** The `faceoff_share_of_absolute_value`
and `offensive_share_of_absolute_value` columns decompose each player's measured
value into its phases. Denominated in **absolute magnitudes** because the
components are signed residuals: a share of a signed sum can be negative or
unbounded and is not interpretable.

Across the 13 specialists the faceoff share averages **0.53** and spans
**0.12–0.88** — so "a FOGO's value is his faceoffs" is true on average and
emphatically not true player by player. It is the top of the group where it
holds: TD Ierlan 0.72, Mike Sisselberger 0.78, Andrew McMeekin 0.68, Alec
Stathakis 0.70. At the other end, Petey LaSalla's measured value is 87% offensive
(shooting value +3.36 against faceoff value −0.58) and Zac Tucci's is 78%.

The offensive contribution is usually *negative*: specialists shoot rarely and
badly, group mean shooting value **−0.91** against a league mean of 0. Partial
defensive value is minor throughout (mean share 0.05). The practical consequence
for Phase 8 is that a specialist's total is not a faceoff measure, and
`faceoff_value_raw` should be read directly rather than inferred from the total.

**No double-counting.** A faceoff appears in exactly one place in this phase's
usage accounting: it is *excluded* from `recorded_offensive_opportunities`, so a
draw is never credited both as workload and as production. A test asserts a
specialist's offensive usage is strictly smaller than his faceoff count.
(`event_log_play_shares` does count a draw up to three times — that is the
Lacrosse Reference definition, it is reproduced faithfully, and the audit in §3
is why it is not this project's usage measure.)

**One finding worth stating.** The mean null-standardized faceoff value across
all 47 players who took a draw is **−1.01**: non-specialists who take occasional
draws lose them at a clearly below-average rate. Faceoff value sums to zero
league-wide, so the specialists' surplus is largely funded by wing players
taking draws when the specialist is off the field.

---

## 15. Defensive treatment — partial, and kept that way

Phase 6's defensive component is caused turnovers above a positional per-game
average, and nothing else. Phase 7 **does not let normalization make it look
comprehensive.**

- The column is `defensive_value_partial_raw` — the word survives in the name.
- `defense_partial = TRUE` on all 228 rows.
- `defensive_value_scope` carries Phase 6's scope statement verbatim.
- `role_interpretation_caveat` on every defender's row states that a value near
  zero does **not** mean an average defender.
- Official caused turnovers are reported directly (741 season-wide, reconciling
  exactly with team totals in 100/100 team-games), alongside
  `caused_turnover_team_share`.
- Percentiles and z-scores are computed **within the 96-player defensive-field
  group**.

**Not captured, and stated rather than hidden:** off-ball defence, help
positioning, matchup difficulty, forcing a bad shot instead of a turnover, shot
suppression, sliding, recovery, communication, and playing time — the
denominator is games played, because the feed has no minutes, shifts or
lineups, so a defender who plays every defensive possession and one who rotates
are treated as having equal exposure.

Validation check 19 and three tests fail if the word "partial" is dropped from
any defensive column name.

---

## 16. Multi-season feasibility

Investigated read-only, not ingested; full detail in
[`docs/MULTI_SEASON_FEASIBILITY.md`](../research/MULTI_SEASON_FEASIBILITY.md).

**2022–2025 are structurally identical to 2026** — same nine event types, same
shot-type tags including `2_PT` and `MU_2_PT`, same seven position labels,
identical JSON key sets, 190 additional completed games. **`officialId` is
stable across seasons** (79.6% of sampled 2025 players appear on the 2026
roster). **2021 is not usable without bespoke work**: every goal is logged
twice, five extra event types appear, and two-point goals are untagged.

Adding 2022–2025 would be the single highest-value next step for this project —
it is what would move shooting and save percentage from "weakly identified" to
genuinely rankable, and make the two-point question testable rather than
foreclosed. It is *not* done here, because Phase 7's scope is 2026 and nothing
in Phase 7 is blocked by the single-season sample.

One operational finding: the API now returns `403 {"error":"Origin not
allowed"}` without an `Origin` header, so the current ingestion script would
fail if re-run today. Recorded, not fixed — out of scope, and the cached 2026
raw data is intact.

---

## 17. SQL architecture

Phase 5/6's SQL-first pattern continues. Python does what is not a clean
aggregate query — closed-form variance derivation, empirical-Bayes reliability,
an incomplete beta function, cross-validated model selection — and SQL does the
joins, window functions, positional partitions, percentiles and assembly.

```
sql/30_player_adjusted_base_views.sql  Phase 6 outputs loaded from disk; the
                                       offensive-opportunity definition
sql/player_position_mapping.sql        canonical position + value role
sql/player_play_shares.sql             every usage measure + the play-share audit
sql/player_adjusted_core.sql           the analytic core, one row per player
sql/player_positional_baselines.sql    218 baselines via UNPIVOT + partitions
sql/player_usage_adjusted_value.sql    the usage adjustment, in its own table
sql/player_adjusted_value.sql          standardization, eligibility, flags
```

The build runs in three passes, because the usage model needs a usage number
that only SQL produces: SQL → Python → SQL. Python's outputs go to a scratch CSV
and are read back by the SQL layer, so there is one documented source for every
number the SQL multiplies by.

**Determinism.** The DuckDB connection runs single-threaded and the positional
baselines are rounded to 12 decimal places. Both are reproducibility measures,
not precision claims: parallel floating-point aggregation is not associative,
and validation check 25's SHA-256 rebuild caught the baselines moving in the
16th significant figure between two runs of the identical query.

---

## 18. Validation and tests

`scripts/pll_validate_adjusted_player_value.py` →
`player_adjusted_value_validation_report.csv`, **27/27 checks passing**. Every
numeric check recomputes its quantity in pandas from the canonical tables or
from Phase 6's published outputs; the Phase 7 SQL is never re-run to check
itself. Check 15 rebuilds all three standardizations from scratch, check 24
rebuilds the null variances and cross-checks the two output tables against each
other, and check 25 rebuilds every output into a scratch directory and compares
SHA-256.

**151 tests pass** across the repository (95 from Phases 1–6, 56 new). The Phase
6 validator still passes 24/24 and Phase 6's outputs are byte-identical.

---

## 19. Known limitations

1. **~19% of league turnovers are attributed to no player**, so every usage
   count is understated (§2).
2. **The offensive/defensive value-role split is not measured** — it falls back
   to the roster label, because the feed records one defensive act (§7.3).
3. **Defensive value is one act wide**, on a games-played denominator (§15).
4. **The usage model is fitted on a single season of 187 players** and is not
   validated out of season. The constant that won may not win in another year.
5. **Goalie value is not shot-quality adjusted** — inherited from Phase 6.
6. **Two-point shooting ability is not measurable in 2026** and no two-point
   estimate is published as reliable.
7. **Shooting and save percentage are weakly identified individually**: 13 of
   192 and 1 of 16 players reach reliability 0.5.
8. **Nothing is opponent-adjusted.** A faceoff specialist who faced weaker
   opposing specialists is not discounted.
9. **The null-variance model assumes opportunity outcomes are independent**,
   which shots within a game are not exactly.
10. **Percentiles in the 13- and 17-player groups are coarse** — 7.7 and 5.9
    points between adjacent players.
11. **Positional standardization does not make roles comparable in value**, only
    in unusualness (§10).
12. **`event_log_play_shares` contains the unreliable `shotAssistId`.** It is
    reproduced faithfully for reference and is not used as this project's usage
    measure.

---

## 20. What Phase 8 is allowed to consume

**May use:**

- `EPA_points_raw` and its components — as the retrospective record of 2026,
  **within a role**.
- `offensive_play_share` — as usage, never as value.
- `EPA_per_recorded_opportunity`, `shooting_EPA_per_shot` — as efficiency, gated
  by `offensive_rate_ranking_eligible`.
- `EPA_vs_usage_expectation` and its z — as "unusual given workload", for field
  players only.
- `EPA_points_null_z` — as "unusual given volume", in any role.
- `*_position_percentile` — for within-role ranking.
- `*_rate_shrunk` — for any claim about ability rather than about 2026.
- Every `*_reliability` and eligibility flag — to decide who may be ranked.

**Must not:**

- Rank `EPA_points_raw` across positions (§10).
- Treat equal positional percentiles as equal value (§10).
- Treat a defensive value near zero as an average defender (§15).
- Multiply value by usage, or otherwise reward usage for being usage (§5).
- Use `event_log_play_shares` or `uaEPA_per_event_log_play_share` in any
  cross-position comparison (§3).
- Publish a two-point shooting ranking (§11).
- Choose between raw and shrunk silently — the choice moves 219 of 228 ranks and
  must be shown (`docs/SHRINKAGE_POLICY.md`).
- Assume the offensive/defensive role split is measured. It is not (§7.3).

**Must decide explicitly, and argue for:** the cross-position weighting. Phase 7
establishes that no metric here supplies one, and that the opportunity bases
differ by a factor of 6.6 in observed spread. That is a judgement Phase 8 has to
make in the open, not inherit.
