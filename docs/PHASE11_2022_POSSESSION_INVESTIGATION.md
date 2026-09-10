> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Phase 11 — The 2022 Possession-Rate Investigation

## Verdict

**Genuine historical/style difference — not repaired.** No reproducible
implementation bug or feed-completeness gap was found. Per the Phase 11
brief's explicit instruction not to repair 2022 merely because its possession
count is lower, the pipeline is unchanged for 2022 and the anomaly is
documented rather than "fixed."

## 1. The distribution — **OBSERVED**

Per-game, not just season averages (`data/processed/<year>/possessions.csv`,
`games.csv`):

| Season | n games | mean poss/game | median | min | max | std |
|---|---|---|---|---|---|---|
| 2022 | 46 | 82.50 | 83.0 | 68 | 97 | 7.11 |
| 2023 | 46 | 96.96 | 93.0 | 80 | 132 | 12.28 |
| 2024 | 45 | 89.93 | 90.0 | 70 | 127 | 9.74 |
| 2025 | 45 | 89.09 | 90.0 | 74 | 105 | 7.51 |
| 2026 | 50 | 87.76 | 88.0 | 71 | 105 | 6.86 |

2022's maximum (97) sits below every other season's median. This is a
season-wide shift, not a handful of outlier games dragging the average —
2022's own distribution is in fact tighter (std 7.11) than the others.

## 2. Hypotheses tested and ruled out

**(a) Implementation bug in the possession state machine** — ruled out.
`pll_build_possessions.py`'s rules never branch on season. 2022's possession-
ambiguity rate (31.9%) is LOWER than every clean season (2024: 34.1%, 2025:
35.9%, 2026: 36.2%) — a bug or gap in the state machine would show as MORE
ambiguity, not less. Truncated-possession rate (3.11%) and the
goals-followed-by-a-faceoff rate (94.9%) are both in-range with other
seasons. Faceoffs/game (25.93) is normal (in range 25.93-26.51 across all
five seasons) — this alone rules out a faceoff-logging defect as the cause,
which was the most obvious a-priori hypothesis.

**(b) Feed-schema difference** — ruled out. Raw JSON for a 2022 game and a
2026 game, compared field-by-field, show identical structure for every event
type including `shotclockexpired` (same keys, same nesting, including empty
`details:{}` in both). No missing field, no structural difference.

**(c) Source-completeness / official-reconciliation gap** — ruled out, and in
fact reversed. 2022's turnover exact-match rate against official box scores
(94.6%) and groundball exact-match rate (100.0%) BEAT 2024 (47.8%, 95.6%) and
2025 (70.0%, 73.3%) — 2022 reconciles as well as or better than later seasons
on exactly the categories that drive possession counts. The one 2022
reconciliation failure remains the already-documented
`archers-cannons-2022-6-18` (goal-count shortfall, 6 vs 1), which is a
mid-pack game for possession count (90/game) — not a driver of the anomaly
and not evidence of a broader gap.

**(d) Game-selection bias** — not investigated further; 2022's completed/
included game count (46) is in the normal range and no unusual game-type
skew was found in the per-game breakdown.

**(e) Duplicate-handling / ordering defects specific to 2022** — ruled out.
2022 carries zero DIRECT/DIRECT_TIMING/DUPLICATE_FACEOFF_EVENT candidates
under the Phase 10/11 classification (9 STRONGLY_INFERRED only, the smallest
non-zero count of any season) — it is exactly as "clean" by this measure as
2025/2026.

## 3. What actually drives it — **OBSERVED / INFERRED**

Mechanistic signature from per-game event-type rates: 2022 has materially
fewer `shotclockexpired` events/game (4.28 vs 6.96-8.38 in other seasons —
roughly half) and fewer `turnover` events/game (32.93 vs 34.4-36.5), both of
which directly end possessions in the state machine. Consistent with this,
2022 possessions run longer (mean 26.25s / median 22.0s vs 23.5-23.9s /
19-20s elsewhere) and score more efficiently per possession (0.282 pts/poss,
the highest of any season) while shots-per-possession is essentially
identical across every season (0.930-0.938) — i.e. 2022 teams held the ball
longer without taking more shots per possession, then either scored or lost
it to a defensive turnover rather than the shot clock. Goals/game (22.02) and
faceoffs/game (25.93) are both normal. This is a coherent, internally
consistent signature of genuinely longer average possessions and fewer
shot-clock-forced turnovers, not a fragmented or degraded data pattern.

**INFERRED, not verified from data in this repository:** a shorter shot clock
or stricter enforcement in 2023+ versus 2022 (PLL's first season) would
produce exactly this signature. This repository's data cannot confirm PLL's
exact shot-clock rule history — this is general lacrosse-context knowledge,
offered as the most plausible mechanism, not a claim this repo's data proves.

## 4. Classification

**GENUINE_HISTORICAL_DIFFERENCE**, not `SOURCE_DATA_LIMITATION` and not
`IMPLEMENTATION_BUG`. 2022's possession count is lower because 2022
possessions were, on the evidence available, genuinely longer — not because
events are missing, misordered, duplicated, or the state machine treats 2022
differently. Phase 9's `POSSESSION_COUNT_ANOMALY` flag for 2022 stands, now
with a concrete, evidence-backed explanation rather than as an open question.
2022's canonical pipeline output is unchanged by Phase 11.
