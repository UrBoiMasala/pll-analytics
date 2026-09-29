# The 2022–2026 PLL Statistical Reference

**Phase 9 — historical ingestion and multi-season validation.**

Phase 8 produced a defensible 2026 statistical layer from 50 games. Phase 9
extends it to **232 games across five seasons** and uses the extra evidence to
put the 2026 conclusions under pressure. Several survived, one was overturned,
and two open questions were closed.

This is the entry point to the multi-season layer.
[`2026_STATISTICAL_REFERENCE.md`](2026_STATISTICAL_REFERENCE.md) remains the
reference for the 2026 season itself and is unchanged.

---

## 1. Scope

| | 2022 | 2023 | 2024 | 2025 | 2026 | **Total** |
|---|---|---|---|---|---|---|
| Games admitted | 46 | 46 | 45 | 45 | 50 | **232** |
| — regular / playoff | 40/6 | 40/6 | 40/5 | 40/5 | 48/2 | 208/24 |
| Events | 9,561 | 10,463 | 10,094 | 10,006 | 10,959 | **51,083** |
| Possessions | 3,795 | 4,460 | 4,047 | 4,009 | 4,388 | **20,699** |
| Player-seasons | 200 | 200 | 199 | 196 | 228 | **1,023** |
| League points | 1,077 | 1,124 | 1,060 | 1,094 | 1,190 | **5,545** |

40 team-seasons · **419** distinct players · 8 teams every season (Chrome exits
after 2023, Outlaws enter in 2024).

**2021 is excluded and was verified, not assumed** — its `2_PT` shot tag does
not exist and 58 goals that moved the score by two are labelled `1_PT`. See
[`docs/HISTORICAL_INGESTION_METHODOLOGY.md`](../research/HISTORICAL_INGESTION_METHODOLOGY.md) §6.

---

## 2. What Phase 9 produced

**Per season** (`data/processed/<year>/`): the full Phase 1–8 stack — `games`,
`teams`, `players`, `events`, `player_game_stats`, `team_game_stats`,
`possessions`, plus `team_stats_YEAR.csv`, `player_stats_YEAR.csv`,
`team_leaderboards_YEAR.csv`, `player_leaderboards_YEAR.csv`,
`two_point_audit_YEAR.csv`, `metric_catalog_YEAR.csv`,
`metric_sanity_flags_YEAR.csv` and both validation reports.

**Pooled and audit** (`data/processed/history/`):

| File | What it is |
|---|---|
| `historical_game_inventory.csv` | 248 scheduled games, every one with an admission decision and a reason |
| `historical_schema_compatibility.csv` | 92 audited aspects × 4 seasons vs 2026 |
| `historical_ingestion_report.csv` | every pipeline stage, status, timestamp |
| `historical_reconciliation_report.csv` / `_season.csv` | per-team-game and per-season reconciliation |
| `historical_analytics_exclusions.csv` | the one measured exclusion |
| `historical_player_identity_audit.csv` | 423 ids, career shape, aggregation safety |
| `historical_duplicate_audit.csv` | source vs local vs pipeline duplication |
| `team_stats_2022_2026.csv`, `player_stats_2022_2026.csv` | pooled, `season` on every row |
| `team_leaderboards_2022_2026.csv`, `player_leaderboards_2022_2026.csv` | pooled |
| `two_point_audit_2022_2026.csv`, `metric_sanity_flags_2022_2026.csv` | pooled |
| `multi_season_metric_distributions.csv` | season effects / poolability |
| `multi_season_reliability.csv` | 2026-only vs pooled-season vs pooled-career |
| `player_year_to_year_stability.csv` | r(t, t+1) with bootstrap CIs |
| `multi_season_usage_model.csv` | constant / linear / quadratic, player-level CV |
| `multi_season_two_point_analysis.csv` + `_identification.csv` | the two-point question |
| `multi_season_opponent_adjustment.csv` | feasibility, measured |
| `multi_season_sanity_flags.csv` | 49 flags, A–E |
| `metric_catalog_freeze_reassessment.csv` | the four decisions Phase 9 closed |
| `phase9_validation_report.csv` | 22 checks, all PASS |

**Documentation:**
[`HISTORICAL_INGESTION_METHODOLOGY.md`](../research/HISTORICAL_INGESTION_METHODOLOGY.md) ·
[`MULTI_SEASON_VALIDATION.md`](../research/MULTI_SEASON_VALIDATION.md) ·
[`PLAYER_IDENTITY_ACROSS_SEASONS.md`](../research/PLAYER_IDENTITY_ACROSS_SEASONS.md) ·
[`MULTI_SEASON_RELIABILITY.md`](../research/MULTI_SEASON_RELIABILITY.md) ·
[`TWO_POINT_HISTORICAL_ANALYSIS.md`](../research/TWO_POINT_HISTORICAL_ANALYSIS.md) ·
[`OPPONENT_ADJUSTMENT_FEASIBILITY.md`](../research/OPPONENT_ADJUSTMENT_FEASIBILITY.md)

---

## 3. The six findings that matter

### 3.1 Pooling seasons the wrong way makes things worse — **NEW**

Stacking player-seasons as extra rows drove shooting κ from 70.8 to 145.5 and
left **zero** of 863 player-seasons above reliability 0.5 — worse than 2026
alone. More units are not more evidence per unit; the median player-season still
carries 11 shot attempts.

**Aggregating a player's career is what works.**

### 3.2 Shooting and goalie skill become identifiable at career level — **NEW**

| | 2026 only | Career-pooled |
|---|---|---|
| Shooters clearing reliability 0.5 | 13 of 192 (6.8%) | **66 of 370 (17.8%)** |
| Goalies clearing it | **1 of 16** | **8 of 27 (29.6%)** |
| Faceoff takers clearing it | 18 of 47 | 56 of 103 (54.4%) |

Phase 8's one-row save-percentage leaderboard was the starkest symptom of
one-season data. Eight goalies now clear the gate on career trials.

### 3.3 Two-point ability is still not identifiable — **CONFIRMED, five times over**

Observed between-player variance is **below** binomial noise in **every season
and both pooled scopes**. Excess variance: −0.0113, −0.0054, −0.0019, −0.0091,
−0.0041, and −0.0060 / −0.0035 pooled. The prior stays capped at 1e6 everywhere.

The binding constraint is attempts per player — a median of **2 a season**,
rising only to **3** across a career. **No qualified two-point leaderboard exists
in any season**, and this is now a five-season replicated result rather than a
one-season caution.

### 3.4 The two-point return is break-even, not negative — **OVERTURNS a 2026 impression**

Phase 8 reported 2026's two-point shot returning 0.024 points *fewer* per
attempt than the one-point shot. Across five seasons:

| 2022 | 2023 | 2024 | 2025 | 2026 | **Pooled** |
|---|---|---|---|---|---|
| +0.0067 | +0.0044 | +0.0206 | −0.0002 | **−0.0243** | **+0.0004** |

**2026 is the outlier.** Over 2,464 attempts the long shot has returned almost
exactly what the short shot returned.

### 3.5 The constant usage model survives five seasons — **CONFIRMED**

Refitted on 844 player-seasons with cross-validation folds cut by **player**:
constant CV MSE **7.4407**, linear 7.5067, quadratic 7.5235. The constant wins
again. More pointedly, the per-season usage/EPA correlation is **negative in
four of five seasons** (−0.057, −0.021, −0.036, −0.027) and +0.072 only in 2026 —
so 2026's weak positive was noise, not a small real effect.

### 3.6 Opponent adjustment is feasible and nearly worthless — **NEW, and not the expected answer**

Phase 8 deferred it for being under-identified. That was wrong: **schedule
connectivity is 1.00 in every season** — all 28 pairings occur. The real reason
to defer is the opposite one: a balanced round-robin leaves nothing to adjust
for. Strength-of-schedule spread is 14–29% of between-team spread, the ridge fit
moves ranks by **0–2 places**, and in 2026 the adjustment is **smaller than its
own bootstrap standard error**.

**Still deferred — now for a measured reason.**

---

## 4. League environment, 2022–2026

Stable where it matters, with two real shifts:

| Shifted | 2022 → 2026 |
|---|---|
| **Pace** | 41.3 → 43.8 team possessions/game, peaking at 48.5 in 2023 (partly a feed artifact, §5) |
| **Shot clock expirations** | 0.052 → 0.081 per possession, rising steadily |
| **Two-point usage** | 10.4% → 13.1% of attempts, plateauing after 2022 |

| Essentially unchanged | η² between seasons |
|---|---|
| Faceoff win % | 0.003 |
| Net efficiency | 0.002 |
| Points per game | 0.021 |
| Two-point conversion % | 0.020 |
| Save % | 0.049 |

**The scoring environment has been remarkably stable.** Points per game moved
from 11.62 to 11.88 across five seasons.

---

## 5. Two caveats that must travel with historical numbers

**2023 possession-denominated metrics are not comparable** — *as published in
`possessions.csv`.* 2023 shows 288 goals with no faceoff logged after them and
1,027 possessions force-closed as `ambiguous_control_change`, inflating the
possession count ~10% and deflating every per-possession rate. 2023 has the
*highest* points per game and the *lowest* offensive efficiency of the five
seasons; both cannot be true of the offence.

> **Phase 10 update (diagnosed and repaired).** The faceoffs were never
> missing — 2023 logs 26.28 per game, the normal number. In 12 games the feed
> emits the post-goal faceoff *before* its own goal and stamps it with the
> goal's clock, contradicting the feed's own `markerId` sequence. An
> evidence-bounded order repair moves 2023 to **91.4 possessions/game**,
> **0.2674 points/possession** and **35.0%** ambiguity — inside the five-season
> range, with **zero** team-ranking changes and 2022/2025/2026 left
> bit-identical. The repaired layer is published as
> `data/processed/<year>/possessions_repaired.csv`; `possessions.csv` is
> unchanged. See [`docs/2023_POSSESSION_REPAIR.md`](../research/2023_POSSESSION_REPAIR.md).
> **Any cross-season possession-denominated comparison must state which layer
> it used.**

**One 2022 game does not reconcile.** `archers-cannons-2022-6-18` — the feed's
score columns move on missed-shot events and decrease, leaving 7 points (0.65%
of 2022) unrecoverable. Admitted, flagged, never corrected.

---

## 6. Validation

| | |
|---|---|
| Phase 9 checks | **22 / 22 PASS** |
| Tests, Phases 1–9 | **282 / 282 PASS** |
| Phase 5 / 6 / 7 / 8 validators | 20/20 · 24/24 · 27/27 · 24/24 |
| Class-E sanity flags | **0** |
| 2026 statistical outputs changed | **none** |

```
python3 scripts/pll_ingest_season.py --year 2022     # raw (idempotent)
python3 scripts/pll_build_history.py                 # tables, possessions, validators
python3 scripts/pll_build_history_stats.py           # Phase 5-8 layers + pooled
python3 scripts/pll_history_schema_audit.py
python3 scripts/pll_history_reconcile.py
python3 scripts/pll_history_identity_audit.py
python3 scripts/pll_multi_season_analysis.py
python3 scripts/pll_history_sanity_audit.py
python3 scripts/pll_validate_phase9.py               # 22 checks
python3 -m unittest tests.test_history               # 61 tests
```

---

## 7. What Phase 9 did not build

No Statistical Tewaaraton. No MVP model. No WAR, replacement level, fantasy
score, cross-position composite, award ranking or dashboard. Validation check 19
scans every column and metric name across all five seasons and every pooled
file; `tests/test_history.py` fails if one appears.

**Phase 10 has since done that asking** without building the model. It repaired
the 2023 possession anomaly from the raw events, published a per-player career
ability layer, tested ten cross-position normalisation methods against measured
properties and counterfactual probes, and classified every candidate award
input. Its answer is that a defensible award model is buildable **within a
role** and not **across** roles, for reasons of measurement coverage rather than
statistical technique. Entry points:
[`docs/MVP_INPUT_READINESS.md`](../research/MVP_INPUT_READINESS.md) ·
[`docs/CROSS_POSITION_VALUE_RESEARCH.md`](../research/CROSS_POSITION_VALUE_RESEARCH.md) ·
[`docs/CAREER_ABILITY_METHODOLOGY.md`](../research/CAREER_ABILITY_METHODOLOGY.md) ·
[`docs/2023_POSSESSION_REPAIR.md`](../research/2023_POSSESSION_REPAIR.md) ·
[`docs/PHASE10_VALIDATION.md`](../history/PHASE10_VALIDATION.md).

Phase 9's job was to build the empirical foundation that lets a **later** phase
ask whether such a model is defensible. The most useful thing it establishes for
that question is negative and specific: **a career-pooled shrunk rate is a
defensible ability estimate for shooting, one-point conversion, faceoff and
turnover tendency — and for nothing else.** Two-point ability, cross-position
comparability, opponent strength and possession participation all remain
unsupported, for reasons now measured across five seasons rather than one.
