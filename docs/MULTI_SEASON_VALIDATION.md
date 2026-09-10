# Multi-Season Validation (2022–2026)

What was checked, what it found, and which residuals are the feed rather than
the pipeline.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

Sources: `phase9_validation_report.csv`, `historical_reconciliation_report.csv`,
`historical_reconciliation_season.csv`, `historical_duplicate_audit.csv`,
`multi_season_sanity_flags.csv`, `historical_schema_compatibility.csv`.

---

## 1. Headline

| | |
|---|---|
| Phase 9 validation checks | **22 / 22 PASS** |
| Tests, Phases 1–9 | **282 / 282 PASS** (221 pre-existing + 61 new) |
| Earlier-phase validators re-run | Phase 5 **20/20**, Phase 6 **24/24**, Phase 7 **27/27**, Phase 8 **24/24** |
| Class-E (implementation bug) sanity flags | **0** |
| 2026 statistical outputs changed by Phase 9 | **none** |

**Independence.** Every numeric check recomputes its target from the raw JSON
corpus or the canonical tables in pandas. The production SQL is never
re-executed to check itself, and no check reads the artifact it validates as its
own source of truth.

---

## 2. Sample admitted

| Season | Scheduled | Completed | Competitive | **Admitted** | Regular | Playoff | Events | Possessions | Player-seasons | Points |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 52 | 52 | 46 | **46** | 40 | 6 | 9,561 | 3,795 | 200 | 1,077 |
| 2023 | 48 | 48 | 46 | **46** | 40 | 6 | 10,463 | 4,460 | 200 | 1,124 |
| 2024 | 47 | 47 | 45 | **45** | 40 | 5 | 10,094 | 4,047 | 199 | 1,060 |
| 2025 | 47 | 47 | 45 | **45** | 40 | 5 | 10,006 | 4,009 | 196 | 1,094 |
| 2026 | 54 | 51 | 53 | **50** | 48 | 2 | 10,959 | 4,388 | 228 | 1,190 |
| **Total** | **248** | **245** | **235** | **232** | **208** | **24** | **51,083** | **20,699** | **1,023** | **5,545** |

40 team-seasons · 1,023 player-seasons · **419** distinct players with a
statistical row · 423 distinct `officialId`s observed.

**2026 grew the sample by 4.6×.** Phase 8's conclusions were drawn from 50 games;
they are now testable against 232.

---

## 3. Score reconciliation — **OBSERVED**

PLL points reconstructed from valid goal events (`1_PT`/`MU` = 1,
`2_PT`/`MU_2_PT` = 2) and compared with the official final score, per team-game.

| Season | Team-games | Exact | League points official | Reconstructed |
|---|---|---|---|---|
| 2022 | 92 | **97.8%** | 1,077 | 1,070 |
| 2023 | 92 | **100%** | 1,124 | 1,124 |
| 2024 | 90 | **100%** | 1,060 | 1,060 |
| 2025 | 90 | **100%** | 1,094 | 1,094 |
| 2026 | 100 | **100%** | 1,190 | 1,190 |

**One game in five seasons fails**, and it is a source defect, not a pipeline
defect: `archers-cannons-2022-6-18`, where the feed's score columns move on
missed-shot events and decrease. See
[`HISTORICAL_INGESTION_METHODOLOGY.md`](HISTORICAL_INGESTION_METHODOLOGY.md) §5.
It is documented in `historical_analytics_exclusions.csv` and flagged class D.
Validation check 7 fails on any *undocumented* residual.

---

## 4. Official box score vs play-by-play — **OBSERVED**

Percentage of team-games where the event log exactly reproduces the official
column. **These residuals are measured, not corrected.**

| Season | goals | shots | saves | faceoffs | turnovers | ground balls | penalties |
|---|---|---|---|---|---|---|---|
| 2022 | 97.8 | 96.7 | 97.8 | 89.1 | 94.6 | **100.0** | 98.9 |
| 2023 | **100** | **100** | 93.5 | 80.4 | 88.0 | 95.7 | 95.7 |
| 2024 | **100** | **100** | **100** | 71.1 | **47.8** | 95.6 | 72.2 |
| 2025 | **100** | **100** | 97.8 | 80.0 | 70.0 | 73.3 | 98.9 |
| 2026 | **100** | **100** | 99.0 | 82.0 | 67.0 | 79.0 | 97.0 |

**INFERRED.** Goals and shots reconcile perfectly from 2023 onward — the
quantities every efficiency metric depends on are sound. Turnovers and ground
balls disagree materially in every season including 2026, which is the same
Phase 4.25 finding extended backwards: the play-by-play and the box score count
these differently, and **the official figure is the published figure** in every
season. 2024's 47.8% turnover agreement is the worst cell in the table and is
recorded as a limitation of 2024, not smoothed.

`assists` is deliberately **not** compared: `shotAssistId` is a pre-shot pass
indicator, not a confirmed assist, and reporting a residual against it would
invent a disagreement. Official assists are carried through unchanged.

### A correction made during this phase

The first implementation compared official `faceoffs` **per team** against
faceoff *events*, producing a spurious "0–2% exact" in every season **including
2026**. PLL's `faceoffs` is the number of draws a team *contested* — the same
number for both teams — while a faceoff event carries one winning team. The
comparison was a category error; scoped per game it is 71–89%. This was a defect
in the new Phase 9 check, found and fixed, and it changed no published metric.

---

## 5. Duplicate and integrity audit — **OBSERVED**

Three kinds, never conflated:

| Class | 2022 | 2023 | 2024 | 2025 | 2026 | Defect? |
|---|---|---|---|---|---|---|
| `SOURCE_DUPLICATE_EVENT` | 8 | 18 | 35 | 50 | 36 | **No** — the feed repeats events |
| `LOCAL_DUPLICATE_FILE` | 0 | 0 | 0 | 0 | 0 | — |
| `PIPELINE_DUPLICATION` | **0** | **0** | **0** | **0** | **0** | would be |
| `SOURCE_VERSION_CONFLICT` | 0 | 0 | 0 | 0 | 0 | — |

**Zero pipeline duplication in any season**, across events, games, player-game
rows and possessions. Source duplicates run 0.08%–0.48% of events and are
handled by Phase 2's **existing, unchanged** duplicate rules — flagged, never
deleted. Legitimate repeated game actions are untouched.

**INFERRED.** The source duplicate rate rises steadily (0.08% in 2022 to 0.48% in
2025). This is a property of the feed's evolution, is small in absolute terms,
and required no rule change to handle in any season — which is itself evidence
the Phase 2 logic generalises.

---

## 6. Possession reconstruction — **OBSERVED**

The possession rules were **not tuned** for any historical season. That is the
point: a difference below is evidence about the season.

| Season | Possessions | Per game | Ambiguous | Truncated | Faceoff start | Turnover end | Goal end |
|---|---|---|---|---|---|---|---|
| 2022 | 3,795 | **82.5** | 31.9% | 3.1% | 31.4% | 34.4% | 26.7% |
| 2023 | 4,460 | **97.0** | **43.2%** | 2.9% | 27.1% | 29.6% | 23.5% |
| 2024 | 4,047 | 89.9 | 34.1% | 3.2% | 29.5% | 32.2% | 24.2% |
| 2025 | 4,009 | 89.1 | 35.9% | 3.4% | 29.5% | 30.5% | 25.4% |
| 2026 | 4,388 | 87.8 | 36.2% | 3.6% | 29.6% | 30.8% | 25.5% |

Goal-to-possession mapping is **exact in all five seasons**: every valid goal and
every PLL point lands in exactly one possession (check 10).

### 2023 is a feed artifact, not a faster league — **OBSERVED, INFERRED**

2023 shows 97.0 possessions per game (+10.5% on the five-season median) and
43.2% ambiguity. The cause is identifiable in the ambiguity reasons:

- **202** possessions follow a goal with **no faceoff logged at all**;
- **159** faceoffs occur while a previous possession was still open.

Those two categories — 361 possessions, 8.1% of the season — are the top two
reasons in 2023 and **do not appear in 2026's top reasons at all**. They are
missing faceoff *events*, which manufacture extra possession boundaries.

**The consequence must travel with every 2023 possession-denominated number.**
2023 has the *highest* points per game of the five seasons (12.12) and the
*lowest* offensive efficiency (0.2503). Those are not both true of the offence;
the denominator is inflated. 2023 per-possession rates are **not comparable**
with other seasons without this caveat, and the sanity audit raises it as a
class-D flag.

---

## 7. Are the seasons poolable? — **DERIVED**

Share of variance in each team metric that sits *between* seasons rather than
between teams (one-way η², 5 seasons × 8 teams — descriptive, not a p-value).

| Metric | 2022 | 2023 | 2024 | 2025 | 2026 | η² | Verdict |
|---|---|---|---|---|---|---|---|
| team_possessions_per_game | 41.28 | **48.47** | 44.86 | 44.47 | 43.84 | **0.561** | **material** |
| shot_clock_expiration_rate | .052 | .072 | .082 | .092 | .081 | **0.414** | **material** |
| shots_per_possession | .936 | **.860** | .934 | .936 | .936 | **0.296** | **material** |
| two_point_attempt_rate | .104 | .136 | .141 | .136 | .131 | 0.210 | modest |
| shots_on_goal_pct | .637 | .625 | .613 | .632 | .625 | 0.153 | modest |
| offensive_efficiency | .281 | **.250** | .261 | .272 | .271 | 0.147 | modest |
| shooting_pct | .285 | .270 | .259 | .271 | .272 | 0.144 | modest |
| defensive_efficiency | .282 | .255 | .263 | .273 | .271 | 0.114 | modest |
| turnover_rate | .401 | .375 | .395 | .394 | .388 | 0.092 | negligible |
| save_pct_official | .519 | .539 | .543 | .540 | .538 | 0.049 | negligible |
| points_per_game | 11.62 | 12.12 | 11.75 | 12.10 | 11.88 | 0.021 | negligible |
| two_point_conversion_pct | .144 | .142 | .147 | .146 | .129 | 0.020 | negligible |
| faceoff_win_pct | .503 | .503 | .488 | .489 | .496 | 0.003 | negligible |
| net_efficiency | −.001 | −.005 | −.002 | −.001 | .000 | 0.002 | negligible |

**INFERRED guidance, and it is deliberately conservative:**

- **Do not pool the three `material` metrics without centring within season.**
  All three are possession-denominated or shot-clock-related, and 2022 and 2023
  are the outliers — consistent with §6's finding that 2023's denominator is
  inflated and with a genuine rise in shot-clock expirations after 2022.
- **The `modest` group is poolable if the season mean travels with it.**
- **The `negligible` group is poolable as-is.** Notably `faceoff_win_pct`
  (η² = 0.003), `net_efficiency` and `points_per_game` are essentially identical
  across five seasons — the scoring environment has been remarkably stable even
  as pace moved.
- **No season effect was modelled or corrected.** Season is reported as a
  column; no metric anywhere in this repository is season-adjusted.

---

## 8. Multi-season sanity flags — **OBSERVED**

49 flags, Phase 8's classification, same rule: **only class E is fixed.**

| Class | Meaning | Count |
|---|---|---|
| A | real performance | 1 |
| B | sample-size artifact | 24 |
| C | role/opportunity artifact | 0 |
| D | known feed limitation | 24 |
| **E** | **implementation/data bug** | **0** |

The class-D group is the substance of this phase: 3 cross-season
discontinuities, 2 possession-count anomalies, 2 feed logging gaps, 2 score
irreconciliations, 8 season-specific vocabulary differences and 7
two-point non-identification results.

Two defects **were** found and fixed during the phase, both in Phase 9's own new
code and neither affecting a published metric: the faceoff comparison scoping
(§4) and two validation checks that were too strict about ids appearing only in
excluded games. Both are described where they occurred.

---

## 9. What Phase 9 did not disturb

**Check 12 and 6 regression tests assert this directly.** Every 2026 figure
Phase 8 published is unchanged: 8 teams, 228 players, 1,190 league points, 4,106
shots, 536 two-point attempts, 72 two-point goals, 4,388 possessions, 50
eligible games. All 57 canonical 2026 outputs are byte-identical **except two
governance files** — `metric_catalog_2026.csv` and `metric_redundancy_2026.csv`
— which changed only in the four freeze classifications Phase 9 was chartered to
reassess and the declared-redundancy text for one of them. No measured value and
no publication status moved; the redundancy file's 191 rows and correlation sums
are identical.
