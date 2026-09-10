# Career-Level Player Ability, 2022–2026 (Phase 10 §§C–E)

Phase 9 established the finding this layer rests on: pooling player-**seasons**
as extra rows makes identification *worse*, while pooling a player's **career**
makes it better. Phase 10 turns that summary into a published, per-player,
independently recomputable layer, and puts three further questions to it.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

Sources: `player_career_2022_2026.csv`, `career_ability_reliability.csv`,
`career_rate_estimates.csv`, `career_scope_comparison.csv`,
`career_season_composition_sensitivity.csv`, `career_identity_audit.csv`,
`career_two_point_identification.csv`.

---

## 1. Identity, re-audited with the career as the unit — **OBSERVED**

Phase 9's rule stands and is not re-litigated: **identity is `officialId`,
nothing else, and no player is ever merged on a name.** Phase 10 re-audits it
because the failure modes change when a career is the row rather than a season.

| Question | Answer |
|---|---|
| Distinct players, 2022–2026 | **419** |
| Careers produced | **419** — one per id, exactly |
| One human split across two ids (would show as a shared normalised name) | **0** |
| Two humans fused into one id (would show as two name spellings on one id) | **0** |
| A player carrying two rows for one season | **0** |
| Careers not safe to aggregate | **0** |

Career length: 155 players with 1 season, 86 with 2, 71 with 3, 52 with 4,
**55 with all five**.

> **Reconciling with Phase 9's figures.**
> [`PLAYER_IDENTITY_ACROSS_SEASONS.md`](PLAYER_IDENTITY_ACROSS_SEASONS.md)
> reports **423** ids, 100 team-changers and 42 position-changers. It audits
> `players.csv` — every id that appears on a roster. Phase 10 audits
> `player_stats_2022_2026.csv` — every player with a box-score row in an
> analytics-eligible game — which is **419**. The four-id difference is roster
> entries who never recorded a statistic, and it is why the team- and
> position-change counts differ by three and two. Neither number is wrong; they
> count different populations, and the career layer must be built on the second
> because a career of zero opportunities is not a career.

**Team and position changes do not split or fuse a career.** 97 players changed
team, 44 changed listed position, 9 changed *value role* (e.g. midfield →
faceoff), and 26 have a season gap. Every one keeps a single career row.

### The state machine, and why role change is a caveat rather than a block

```
BLOCKED_DUPLICATE_SEASON_ROW    two rows for one season          0 players
REVIEW_POSSIBLE_SPLIT_CAREER    normalised name shared by 2 ids  0 players
REVIEW_MULTIPLE_NAME_SPELLINGS  one id, two spellings            0 players
SAFE_WITH_ROLE_CHANGE_CAVEAT    value role changed               9 players
SAFE                            everything else                410 players
```

**INFERRED caveat.** A career rate for one of the 9 role-changers mixes two
jobs. `canonical_position` is resolved *per season*, so the change is visible;
`career_position_representation` records every position with the count of
seasons played there (`attack:3,midfield:2`), and **no career is forced to a
single position**. `modal_position` exists for convenience and is explicitly
not authoritative. Validation check 21 fails if a multi-role career is ever
collapsed.

---

## 2. Method — **DERIVED**, and unchanged on purpose

`beta_prior_by_moments` and `beta_quantile` are **imported** from the Phase 6/7
modules, never reimplemented, so a career prior is directly comparable with the
per-season priors already published and cannot drift from them.

```
shrunk       = (successes + alpha) / (trials + alpha + beta)
kappa        = alpha + beta            prior strength, in trials
reliability  = n / (n + kappa)         posterior weight on the player's own record
interval     = exact 95% beta-posterior quantiles of Beta(alpha+k, beta+n-k)
```

`kappa` is set so the between-player variance the prior implies matches the
observed variance **net of the binomial noise each player's own sample
contributes**. A small kappa means the league genuinely spreads out; a capped
one (1e6) means it does not.

### The reliability gate is not an arbitrary threshold

`reliability >= 0.5` is exactly `n >= kappa` — the point at which the posterior
stops being mostly prior. Since kappa is estimated from the data, the gate moves
with the evidence rather than being chosen. Every table reports the **full**
reliability distribution so a reader can apply a different line, and
`phase10_historical_stability.csv` reports the qualifying population at 0.3,
0.5 and 0.7:

| Rate | ≥ 0.3 | **≥ 0.5** | ≥ 0.7 | of |
|---|---|---|---|---|
| turnovers_per_touch | 289 | **218** | 122 | 419 |
| faceoff_win_pct | 69 | **56** | 43 | 103 |
| shooting_pct | 115 | **66** | 14 | 370 |
| one_point_pct | 99 | **47** | 6 | 340 |
| save_pct | 17 | **8** | 1 | 27 |
| two_point_pct | **0** | **0** | **0** | 271 |

The ordering of the rates is identical at every gate. The conclusion does not
depend on where the line is drawn — only the headcount does.

### What counts as estimable

Two conditions, both required:

1. observed between-player variance must exceed binomial noise (otherwise every
   shrunk value is the league mean and the "estimate" carries no information
   about the player);
2. at least one real player must reach the gate (otherwise the rate is
   identified for the *league* but for no *individual*).

---

## 3. Career results — **OBSERVED**

`career_ability_reliability.csv`, scope `pooled_player_career`.

| Rate | Players | Trials | Median | Max | Prior mean | **κ** | Implied true sd | Raw sd → shrunk sd | **≥ 0.5** | Estimable |
|---|---|---|---|---|---|---|---|---|---|---|
| **two_point_attempt_share** | 370 | 19,030 | 18 | 391 | 0.1295 | **2.99** | **0.168** | 0.318 → 0.202 | **315 (85.1%)** | yes |
| **faceoff_win_pct** | 103 | 12,174 | 18 | 1,435 | 0.4965 | **10.42** | **0.148** | 0.220 → 0.122 | **56 (54.4%)** | yes |
| **turnovers_per_touch** | 419 | 119,917 | 147 | 2,177 | 0.0543 | 138.0 | 0.019 | 0.058 → 0.014 | **218 (52.0%)** | yes |
| shots_on_goal_pct | 370 | 19,030 | 18 | 391 | 0.6263 | 76.7 | 0.055 | 0.231 → 0.027 | 79 (21.4%) | yes |
| shooting_pct | 370 | 19,030 | 18 | 391 | 0.2725 | 102.8 | 0.044 | 0.173 → 0.022 | 66 (17.8%) | yes |
| one_point_pct | 340 | 16,565 | 15.5 | 380 | 0.2913 | 124.5 | 0.041 | 0.191 → 0.019 | 47 (13.8%) | yes |
| save_pct | 27 | 11,183 | **354** | 1,316 | 0.5363 | **495.2** | 0.022 | 0.059 → 0.013 | 8 (29.6%) | yes |
| goals_per_shot_on_goal | 343 | 11,918 | 12 | 286 | 0.4351 | 136.8 | 0.042 | 0.234 → 0.017 | 18 (5.2%) | marginal |
| **two_point_pct** | 271 | 2,465 | **3** | 110 | 0.1460 | **capped 1e6** | 0.0004 | 0.153 → **0.000** | **0** | **NO** |

Phase 9's headline figures — 66 of 370 shooters, 8 of 27 goalies, 56 of 103
faceoff takers — reproduce **exactly** on an independently written aggregation.
That agreement is a check, not a restatement: Phase 10 rebuilds the career
totals from `player_stats_2022_2026.csv` with its own code path and gets the
same priors.

### 3.1 Two rates Phase 10 added, and one of them is the most identified quantity in the project

**`two_point_attempt_share` — shot SELECTION — κ = 2.99 attempts.**
Whether a player *chooses* the long shot is the most strongly identified
individual property in this feed: 85.1% of shooters clear the gate, the implied
true between-player sd is 0.168, and shrinkage barely moves the raw spread
(0.318 → 0.202) because there is that much real signal.

This sits directly beside the result in §5 and the two are worth stating
together: **who shoots two-pointers is highly individual; who *converts* them is
not measurably individual at all.** A future model may treat two-point usage as
a player property. It may not treat two-point efficiency as one.

**`shots_on_goal_pct` — accuracy — κ = 76.7 shots, 21.4% clear the gate**, more
than shooting percentage itself (17.8%). Splitting shooting into *hitting the
cage* and *beating the goalie once you do* (`goals_per_shot_on_goal`, 5.2%)
shows the identifiable half is accuracy. Finishing conditional on hitting the
cage is barely separable from noise — which is what you would expect if the
goalie owns most of that outcome.

### 3.2 Faceoff remains the cleanly identified skill

κ = 10.4 draws against 77–495 for every other rate, and an implied true
between-player sd of **0.148**, three to seven times any other conversion rate's.
Two-point attempt share is nominally larger (0.168) but it is a *choice*, not a
contest outcome.

### 3.3 Goalies: the largest single improvement, and still only eight

One goalie of sixteen cleared the gate on 2026 alone; **eight of 27 clear it on
career trials**. Note that κ *rises* from 300 to 495 — the true between-goalie
spread is genuinely small (implied sd 0.022, about 2.2 save-percentage points) —
so this is more evidence overcoming a harder problem, not a lowered bar.

---

## 4. Single season vs pooled seasons vs career — **OBSERVED**, with the explanation

`career_scope_comparison.csv`. The percentage of units clearing reliability 0.5:

| Rate | 2026 only | pooled player-**seasons** | **career** | career wins? | pooling seasons wins? |
|---|---|---|---|---|---|
| shooting_pct | 6.8% | **0.0%** | **17.8%** | yes | **no** |
| one_point_pct | 4.8% | **0.0%** | **13.8%** | yes | **no** |
| save_pct | 6.3% | **0.0%** | **29.6%** | yes | **no** |
| faceoff_win_pct | 38.3% | 51.3% | **54.4%** | yes | yes |
| turnovers_per_touch | 35.5% | 30.6% | **52.0%** | yes | no |
| shots_on_goal_pct | 25.0% | 4.6% | 21.4% | **no** | no |
| goals_per_shot_on_goal | 0.0% | 0.0% | **5.2%** | yes | no |
| two_point_pct | 0.0% | 0.0% | **0.0%** | no | no |

### Why additional observations do or do not improve identification

**More units are not more evidence per unit.** Stacking five seasons as
independent rows takes shooting from 192 units to 863 but leaves the median
player-season at 11 shot attempts. What it *does* add is genuine heterogeneity —
a 2022 rookie and a 2026 veteran are different players in a way the model does
not represent — which inflates the observed between-player variance the
estimator must explain, and the estimator correctly attributes more of it to
noise. κ goes 70.8 → 145.5 and **zero** of 863 player-seasons clear the gate.

**Summing a player's trials is more evidence per unit.** The same 19,030 shots
regrouped by *player* raise the median from 9 (2026) to 18, and the median
goalie from 148 trials to **354**. κ falls to 102.8 and 66 shooters clear.

**The binding constraint is always trials per unit, never the number of units.**
`shots_on_goal_pct` is the exception that proves it: it is the one rate where a
single 2026 season beats the career (25.0% vs 21.4%), because its 2026 κ (37.2)
happens to be lower than its career κ (76.7) — the *pooled* population is more
heterogeneous than one season's, and the extra trials do not quite pay for it.

**Two-point stays at zero at every scope** because trials never arrive: the
median career carries 3 attempts. Aggregation cannot manufacture a denominator.

---

## 5. Two-point ability, re-tested on the final career aggregation — **UNSUPPORTED**

`career_two_point_identification.csv`.

| Scope | Shooters | Attempts | Median | Max | Observed variance | Binomial noise | **Excess** | κ | Max reliability | ≥ 0.5 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 102 | 372 | 2 | 17 | 0.024805 | 0.036085 | **−0.011280** | 1e6 | 0.000017 | 0 |
| 2023 | 114 | 520 | 3 | 35 | 0.022264 | 0.027656 | **−0.005392** | 1e6 | 0.000035 | 0 |
| 2024 | 122 | 528 | 2 | 29 | 0.027483 | 0.029399 | **−0.001916** | 1e6 | 0.000029 | 0 |
| 2025 | 120 | 509 | 2 | 28 | 0.020189 | 0.029292 | **−0.009103** | 1e6 | 0.000028 | 0 |
| 2026 | 127 | 536 | 2 | 29 | 0.023445 | 0.027552 | **−0.004107** | 1e6 | 0.000029 | 0 |
| pooled player-seasons | 585 | 2,465 | 2 | 35 | 0.023642 | 0.029598 | **−0.005956** | 1e6 | 0.000035 | 0 |
| **pooled career** | **271** | **2,465** | **3** | **110** | **0.010224** | **0.013711** | **−0.003487** | **1e6** | **0.000110** | **0** |
| *one-point, same players, career* | *340* | *16,565* | *15.5* | *380* | *0.005882* | *0.004237* | ***+0.001645*** | *124.5* | *0.753* | *47* |

The last row is the control that makes this a finding rather than an artefact of
the estimator: **on the same players, with the same code, one-point conversion
comes out identifiable.** Two-point does not.

### Career attempt distribution — **OBSERVED**

271 shooters, 2,465 career attempts. Percentiles: p10 = 1, p25 = 2, **p50 = 3**,
p75 = 10.5, p90 = 22, p95 = 36.5, p99 = 76, max 110. Only 33 players reach 20
career attempts and only 6 reach 50.

### The formal classification

```
INDIVIDUAL_TWO_POINT_ABILITY = UNSUPPORTED / DO_NOT_USE
```

**This is a statement about identification, not about the shot.** It does *not*
remove two-point production. The following stay published as descriptive
statistics and reconcile exactly (Phase 9 check 8): `two_point_goals`,
`two_point_attempts`, the PLL points they generated, `two_point_pct_raw`, and
two-point usage — which §3.1 shows is *strongly* individual.

Validation check 17 and five tests fail if a two-point ability estimate is ever
presented as reliable, if the published shrunk rate stops being collapsed, or if
the readiness table stops classifying it UNSUPPORTED.

---

## 6. Sensitivity to season composition — **MODELED**

`career_season_composition_sensitivity.csv`. Leave-one-season-out, reported at
both levels because they answer different questions.

| Rate | κ change | Mean abs change in shrunk rate | **Spearman vs full career** |
|---|---|---|---|
| two_point_attempt_share | −3.6% to +2.7% | 0.014–0.016 | **0.979–0.986** |
| turnovers_per_touch | −5.8% to +11.0% | 0.002 | **0.950–0.970** |
| shots_on_goal_pct | −17.0% to +32.6% | 0.005–0.007 | 0.918–0.935 |
| shooting_pct | −9.6% to +13.5% | 0.004–0.005 | 0.906–0.943 |
| one_point_pct | −10.7% to +14.7% | 0.003–0.005 | 0.904–0.953 |
| faceoff_win_pct | −12.1% to +45.2% | 0.013–0.037 | 0.901–0.966 |
| goals_per_shot_on_goal | −8.3% to +38.6% | 0.003–0.005 | 0.886–0.945 |
| save_pct | −18.1% to +13.3% | 0.002–0.004 | 0.854–0.965 |
| *two_point_pct* | *0.0%* | *0.000–0.003* | *0.838–0.912 — **meaningless**, the prior is capped so every value is the league mean and the "ranks" are numerical dust* |

**Reading:** the *ordering* of players is robust — no rate's rank correlation
with the full-career estimate falls below 0.85 when a whole season is removed.
The *prior strength* is not: faceoff κ moves by up to 45% and
`goals_per_shot_on_goal` by 39%, because both are estimated on small
populations. A career estimate is a stable statement about who is better and a
less stable statement about how confident to be.

---

## 7. Year-to-year persistence, and its sensitivity to the choices

`phase10_historical_stability.csv`. Pearson r on consecutive seasons, at three
minimum-opportunity thresholds — the sensitivity analysis the single number
usually hides:

| Rate | ≥ 10 trials | ≥ 20 | ≥ 40 |
|---|---|---|---|
| turnovers_per_touch | 0.391 *(n=525)* | 0.368 *(481)* | 0.433 *(418)* |
| shooting_pct | 0.313 *(239)* | 0.350 *(177)* | 0.363 *(94)* |
| one_point_pct | 0.291 *(213)* | 0.293 *(161)* | 0.261 *(76)* |
| faceoff_win_pct | 0.664 *(45)* | 0.289 *(30)* | 0.379 *(24)* |
| save_pct | 0.149 *(38)* | 0.162 *(36)* | 0.182 *(32)* |
| two_point_pct | 0.045 *(30)* | — *(n=4)* | — *(n=0)* |

Shooting and turnover tendency persist at every threshold. Faceoff swings from
0.664 to 0.289 to 0.379 on 45, 30 and 24 pairs — that is **sample size, not
instability**, and it is why the Phase 9 caution against reading a wide interval
as a negative result still holds.

### Split-half reliability (odd vs even seasons of a career) — **DERIVED**

Both halves ≥ 20 trials; Spearman–Brown steps the half-length correlation up to
full career length.

| Rate | n | Observed r | Spearman–Brown |
|---|---|---|---|
| turnovers_per_touch | 230 | 0.582 | **0.736** |
| shooting_pct | 97 | 0.474 | **0.643** |
| one_point_pct | 92 | 0.470 | **0.640** |
| faceoff_win_pct | 16 | 0.398 | 0.570 |
| save_pct | 17 | 0.102 | 0.185 |

This is the strongest evidence in the phase that a career rate measures
something durable: split a player's *own* career in half and the two halves
agree at 0.47–0.58 for the three well-populated rates. **Save percentage does
not** — 0.102 on 17 goalies — which is the same sample-size problem as above and
is why goalie ability is READY_WITH_CAVEAT rather than READY.

### How much depends on raw vs shrunk

Spearman between the raw and shrunk career rate: save_pct 0.869,
turnovers_per_touch 0.861, one_point_pct 0.741, shooting_pct 0.717,
faceoff_win_pct **0.408**. The shrinkage choice is largest exactly where the
prior is weakest relative to the spread — faceoff, where κ is 10 draws and the
raw rate of a 12-draw player is nearly all noise.

---

## 8. What `player_career_2022_2026.csv` contains

One row per player, 419 rows. Every counting column is a plain sum of the
season rows, so the reconciliation is exact and checkable (validation check 3,
16 columns).

| Group | Columns |
|---|---|
| Identity | `player_id`, `player_name`, `n_seasons`, `seasons`, `teams`, `teams_by_season` |
| Role | `positions_by_season`, `value_roles_by_season`, `career_position_representation`, `modal_position`, `career_position_is_single_role` |
| Opportunities | `games_played`, `shots`, `one_point_attempts`, `two_point_attempts`, `shots_on_goal`, `touches`, `faceoffs`, `saves`, `goals_allowed`, `shots_on_goal_faced`, `recorded_offensive_opportunities`, … |
| Raw rates | `shooting_pct_raw`, `one_point_pct_raw`, `two_point_pct_raw`, `faceoff_win_pct_raw`, `save_pct_raw`, `turnovers_per_touch_raw`, `shots_on_goal_pct_raw` |
| Estimates | `<rate>_shrunk`, `<rate>_reliability`, `<rate>_ci_lo`, `<rate>_ci_hi` for six rates |
| State | `career_aggregation_state`, `safe_to_aggregate_career`, `changed_team`, `changed_position`, `has_season_gap`, `rates_reaching_reliability_gate`, `n_rates_reaching_reliability_gate`, `qualification_state` |

**Qualification is per rate, never a single verdict.** 239 of 419 players reach
the gate on at least one rate; 180 are `DESCRIPTIVE_ONLY`. Of the 239: 133 clear
on one rate, 57 on two, 48 on three, **1 on four**.

There is deliberately **no summary value column** — no career total, no rating,
no score. A test fails if one appears.

---

## 9. What this layer may and may not be used for

**May:**
- estimate a player's underlying rate for shooting, one-point conversion, shot
  accuracy, faceoff, turnover tendency, save percentage and two-point *usage*,
  for the players who clear the gate, with the interval stated;
- gate a rate leaderboard on `reliability` rather than on an invented minimum;
- compare two players **within a role** on any of the above.

**May not — UNSUPPORTED:**
- treat a career rate as an estimate of **current** ability. Ageing, role change
  and team context are modelled nowhere;
- publish any two-point *ability* estimate at any scope;
- compare a career rate across roles as if it were a value (see
  [`CROSS_POSITION_VALUE_RESEARCH.md`](CROSS_POSITION_VALUE_RESEARCH.md));
- read `goals_per_shot_on_goal` as a finishing skill for the 95% of players
  below the gate.
