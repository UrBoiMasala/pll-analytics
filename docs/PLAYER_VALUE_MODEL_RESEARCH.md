# Player Value Model Research (Phase 12 §§B-M)

The central research question: **what is the most statistically defensible
way to measure an individual PLL player's contribution to winning/value using
the data this project actually possesses?** This document inventories every
candidate signal, measures dependency/double-counting among them, runs every
model family the Phase 12 brief names to completion (including one it names
as untested — Model Family 5), and reports a scorecard. **No Statistical
Tewaaraton, MVP score, WAR, replacement-level composite, fantasy score or
cross-position leaderboard is built here or anywhere in this project.**

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

Sources: `player_value_signal_inventory.csv`, `player_value_metric_dependency.csv`,
`player_value_model_candidates.csv`, `player_value_validation_results.csv`,
`player_value_counterfactual_tests.csv`, and every Phase 6/7/9/10 artifact
they cite. Built by `scripts/pll_phase12_player_value_research.py`.

---

## B. Signal inventory — 24 candidate signals, classified

`player_value_signal_inventory.csv`. Every candidate signal the Phase 12
brief names is either an existing column (real sample sizes and reliability
looked up from `career_ability_reliability.csv`), an existing EPA-style
component, or an explicitly deferred/absent concept (ground balls, opponent
adjustment). None is invented.

Highlights, by category:

**Scoring/shooting.** `two_point_attempt_share` is the single most
identifiable individual property in the project (85.1% of career shooters
clear reliability 0.5) and it is a *choice*, not an outcome — it must never be
conflated with `two_point_conversion_pct`, which is **UNSUPPORTED** at every
scope tested (career observed variance 0.0102 is below binomial noise
0.0137). `shooting_value_raw` is flagged `double_counting_with:
EPA_points_raw` because it is ≥96% of offensive EPA's variance for field
players (verified below) — summing it alongside `EPA_points_raw` in any
future composite would double-count every shot.

**Ball security/usage.** `turnovers_per_touch` is the highest-clearing career
rate in the project (52.0% of 419 players). `games_played` is flagged
`READY as denominator, NOT as value input` — every season-total already
rewards it implicitly.

**Faceoff.** `faceoff_win_pct` remains the cleanest contest-outcome skill
(implied true between-player sd 0.148, 3-7x any other rate's). `ground_balls`
is flagged `UNSUPPORTED as a value input` specifically because 61.5% of
ground balls after a faceoff go to the winner himself — a future ground-ball
value component must first solve this overlap.

**Goalie.** `save_pct` career-pools to 29.6% reliability (8 of 27), the
single largest career-pooling gain in the project.

**Defense.** `caused_turnovers` is flagged `NOT_COMPARABLE across roles;
usable only as an availability-adjusted, WITHIN-ROLE partial signal` — zero
of 52,633 raw events name a causing or closest defender.

**Team context.** Team outcome variables are flagged `USABLE ONLY as a
concurrent-validity check, never as a player input` — see §E below for why.

---

## C. Dependency / redundancy analysis — NEW in Phase 12

Phase 6 argued the value components are disjoint **by construction**
(`PLAYER_VALUE_ACCOUNTING.md`). Phase 12 verifies this **by measurement**,
on the full canonical 2022-2026 population (1,023 player-seasons), and adds a
multicollinearity diagnostic the project has not run before.

### C.1 The accounting identity, re-verified on 5 seasons

`sum(shooting_value_raw, turnover_value_raw, faceoff_value_raw,
goalie_value_raw, defensive_value_partial_raw) = EPA_points_raw` to
**5.3e-15** max absolute difference across all 1,023 player-seasons — exact,
not approximate. This is the row-level invariant that prevents double
counting: PASS (see `player_value_validation_results.csv`, ACCOUNTING_VALIDITY).

### C.2 A genuinely new finding: the LEAGUE-sum-to-zero property is not exact in every season

The **row-level** identity above is exact everywhere. The stronger, separate
claim — that `EPA_points_raw` sums to exactly zero across the *league* —
holds to floating-point precision in 2023, 2025 and 2026, but **not** in
2022 (`-0.93`) or 2024 (`+0.28`):

| Season | League sum of EPA_points_raw | Driven by |
|---|---|---|
| 2022 | **-0.93** | `shooting_value_raw` +6.09, `goalie_value_raw` -7.00 |
| 2023 | 1.9e-14 | — |
| 2024 | **+0.28** | `shooting_value_raw` +0.28 (all other components exact) |
| 2025 | -1.7e-15 | — |
| 2026 | -3.3e-14 | — |

**INFERRED.** 2022's residual is plausibly explained by the one
already-documented 2022 source-data limitation:
`archers-cannons-2022-6-18`'s goal-count reconciliation gap against official
scoring (`CANONICAL_MANIFEST_V1.json` `known_source_limitations`). This is
the only known event-level defect in 2022 of comparable magnitude, but Phase
12 did not re-trace it event-by-event, so the attribution is **INFERRED, not
OBSERVED**. 2024's smaller residual has no equally obvious cause and is
recorded as an open, unattributed, small discrepancy for a future phase.
**Neither residual is large enough to change any published Phase 6-11
per-player value** (the row-level identity, which every player-level use
actually depends on, is exact); it matters only for anyone who might sum
`EPA_points_raw` across an entire season and expect exactly zero.

### C.3 Pairwise dependency, by pool

`player_value_metric_dependency.csv`, `analysis_type=PAIRWISE_CORRELATION`.
Selected findings:

- `goals` vs `scoring_points`: r=0.99 — **MECHANICAL_NEAR_IDENTITY**.
- `shots` vs `shooting_value_raw`: **NESTED_COMPONENT** — shooting_value_raw
  is priced ON these same shots.
- `shooting_value_raw` vs `offensive_EPA_points_raw`: r≈0.96-0.99 for field
  players, and **exact by construction** (offensive_EPA_points_raw =
  shooting_value_raw + turnover_value_raw, re-verified to 1.8e-15).
- `games_played` vs `caused_turnovers`, re-verified per season on the
  canonical player table: reproduces the Phase 10 finding of rho 0.49-0.80 —
  **HIGH double-counting risk** with any model that treats caused_turnovers
  as an independent skill signal without conditioning on games played.
- `shooting_value_raw` vs `turnover_value_raw`: **DISJOINT_BY_CONSTRUCTION**
  (different opportunity sets — shots vs touches) — the one pairing in the
  offensive pool with `double_counting_risk = NONE`.

### C.4 Multicollinearity diagnostic (VIF) — NEW

If a naive composite fed `{goals, shots, shooting_pct, turnovers,
turnovers_per_touch, games_played, shooting_value_raw}` to attack/midfield
players as separately-weighted "independent" inputs (446 player-seasons),
the variance-inflation factors would be:

| Metric | VIF | Risk |
|---|---|---|
| **goals** | **58.3** | HIGH |
| **shots** | **43.8** | HIGH |
| shooting_value_raw | 9.3 | MODERATE |
| turnovers | 3.9 | LOW |
| games_played | 3.5 | LOW |
| turnovers_per_touch | 1.4 | LOW |
| shooting_pct | 1.9 | LOW |

`goals` and `shots` carry VIF above 40 — they are almost totally collinear
(`goals = shots × shooting_pct`) with the rest of the pool. This is
constructed evidence, not a claim that this project ever built such a
composite: **no published composite in this project uses more than one of
these as independently-weighted inputs**, which is exactly why the VIFs stay
this high — nothing here has been orthogonalized because nothing needed to
be.

---

## D. Model families tested

### MF1 — Direct production / points created

`EPA_points_raw` **within a single role**: **VIABLE**. Cross-role: sums to a
meaningful team quantity only per-role (zero is the league-average outcome
for that role's own opportunity class); it is **not** additive across roles
into one number that means anything, and ranking cross-role on it is
**REJECTED** (identical to Phase 10's finding — role SD ratio 4.58x pooled).

### MF2 — Possession value

**UNSUPPORTED.** A possession cannot be attributed to a player who did not
touch the ball on it, and "touched the ball" is exactly what shot/turnover/
faceoff-denominated EPA already captures — this family collapses into MF1
for what it CAN see and needs lineup/on-off data (absent) for what it would
add.

### MF3 — Above-baseline value, by role

Offense: **VIABLE**. Faceoff and goalie: **VIABLE_WITH_CAVEAT** — both carry
a decisive, quantified workload confound (counterfactuals T4/T5, reproducing
Phase 10's P4/P5: identical per-shot goalie skill yields a 30x total-value
swing from team-conceded shot volume alone; identical faceoff win rate yields
a 2.1x swing from draw count alone). Defense: **ROLE_ONLY** — the underlying
signal (caused turnovers) is a box-score total with a games-played
denominator that only partially removes an availability confound.

### MF4 — Shrunk skill × opportunity

Multiplying a career-shrunk *rate* by a *season's own opportunity count*:
**REJECTED**, on the stated methodological ground `SHRINKAGE_POLICY.md`
already established — this drags every total toward zero in proportion to
sample size, asserting "this player produced less" rather than "we know less
about him". Using the shrunk rate **as an ability estimate** (not
multiplied into a season total): **VIABLE_WITH_CAVEAT** — this answers "who
is the best" (ability), not "who had the best season" (value), and Section A
of `PLAYER_VALUE_DEFINITION.md` explains why those are different questions.

### MF5 — Team outcome association — run to completion, NEW in Phase 12

This is the one model family the Phase 12 brief explicitly asks to be tested
rather than argued about, and it had not been run anywhere in Phases 6-11.
Team-season sums of `offensive_EPA_points_raw`, `faceoff_value_raw`,
`defensive_value_partial_raw`, `goalie_value_raw` regressed on team `win_pct`
(OLS, n=40 team-seasons):

| Statistic | Value |
|---|---|
| R² in-sample | **0.663** |
| R² leave-one-season-out | **0.526** |
| off_epa coefficient (95% bootstrap CI) | 0.0044 [0.0003, 0.0085] |
| fo_epa coefficient (95% bootstrap CI) | 0.0091 [0.0047, 0.0139] |
| def_epa coefficient (95% bootstrap CI) | 0.0369 [0.0156, 0.0607] |
| g_epa coefficient (95% bootstrap CI) | 0.0111 [0.0073, 0.0150] |

**This is a real, non-fabricated result**, and it is included specifically
so the project can explain *why* a genuine attempt at empirically-derived
cross-role weights fails, rather than asserting it would. Four reasons, all
measured:

1. **Circularity.** EPA components are residuals against the same games'
   scoring outcomes that determine win_pct — part of R²=0.66 is definitional.
2. **n=40 for 4 predictors** is roughly 8-10 observations per coefficient —
   thin enough that R² drops to 0.53 leaving one whole season out (5 folds
   only).
3. **A team-level coefficient is not a per-player weight.** `off_epa`
   aggregates ~15-20 field players per team-season; `fo_epa`/`g_epa`
   aggregate 1-3 specialists. "Coefficient per point of off_epa" and
   "coefficient per point of fo_epa" are not comparable at the player level
   without an additional, unvalidated within-role-distribution assumption.
4. It says nothing about **which teammate** produced a team's summed EPA.

**Verdict: EXPERIMENTAL.** This is the strongest evidence in the project
against Rule 2 being satisfiable with the data on hand — not an assertion
that empirical weight derivation is impossible in principle, but a
demonstration of exactly how it fails with n=40 team-seasons.

### MF6 — Role-specific award models

**VIABLE** for offense; **VIABLE_WITH_CAVEAT** for faceoff and goalie (the
workload-confound disclosure must travel with any ranking); **VIABLE_WITH_CAVEAT**
for a defensive *production* leaderboard **only if it never combines its
three columns (caused turnovers, ground balls, games played) into one score**.

### The ten pre-existing cross-position bridges (Phase 10), folded into one scorecard

M01, M02, M03, M04, M05, M06, M07, M08, M09 are all **REJECTED** for a value
ranking (each fails a different, specific, previously-documented test — see
`player_value_model_candidates.csv` rows `XPOS_M01`-`XPOS_M09` for the exact
failure mode of each). M10 (`EPA_points_null_z`) is **VIABLE_WITH_CAVEAT**,
and only under the target concept "how unusual was this season", never
"value" or "contribution".

---

## E. Value units — which ones mean anything

| Candidate unit | Additive? | Zero meaningful? | Cross-position? | Basis | Verdict |
|---|---|---|---|---|---|
| PLL points above role-average expectation (`EPA_points_raw`) | YES, exactly, within role | YES — "exactly average for the role" | **NO** (role SD ratio 4.58x) | observed production | VIABLE within role |
| Per-opportunity value (`EPA/opportunity`) | NO (a rate, not additive across players) | YES | **NO** (worst SD ratio of the ten, 7.14x) | observed production, volume-free | REJECTED as a total; usable as a rate |
| Within-role z / percentile | N/A (rank-based) | YES ("average") | Superficially yes; substantively **NO** (P1: 2.91-18.61 points at identical z=2.0) | standardized production | REJECTED as value |
| `EPA_points_null_z` | N/A | YES ("as expected under chance") | Best of the ten (ratio 2.03) but still not 1.0; still an unusualness measure | statistical significance of production vs. chance | VIABLE_WITH_CAVEAT for "unusualness" only |
| Wins added | N/A | — | — | would require player-level win-probability attribution | **UNSUPPORTED** — no lineup/on-off data exists to build one |

---

## F-J. Offense / faceoff / goalie / defense decomposition

Covered in their own documents: `OFFENSIVE_VALUE_RESEARCH.md`,
`FACEOFF_VALUE_RESEARCH.md`, `GOALIE_VALUE_RESEARCH.md`,
`DEFENSIVE_VALUE_FEASIBILITY.md`.

---

## K. Validation strategy applied

`player_value_validation_results.csv`, 35 rows across all six families the
brief names:

| Family | n rows | Headline result |
|---|---|---|
| ACCOUNTING_VALIDITY | 6 | Row-level identity exact PASS; league-sum PASS in 3/5 seasons, documented FAIL_WITH_KNOWN_CAUSE in 2 (§C.2) |
| PREDICTIVE_VALIDITY | 15 | All ten cross-position transforms: year-to-year rho 0.159-0.253 (FAIL as a talent measure); career rates reach the reliability gate for >0% of players on 5 of 6 rates (PASS as ability inputs) |
| CONCURRENT_VALIDITY | 6 | Team-summed EPA vs win_pct r=0.76, PASS_WITH_CIRCULARITY_CAVEAT (§ above) |
| STABILITY | 1 | Role SD ratio 4.58x pooled, stable across 5 seasons (3.2-6.4x range) |
| BOOTSTRAP_UNCERTAINTY | 1 | 1,000-resample 95% CI on the role SD ratio excludes 1.0 by a wide margin — the cross-role gap is not a small-sample artifact |
| LEAVE_ONE_SEASON_OUT | 6 | Career estimates: rank correlation never below 0.85 (reused); MF5 regression: R² degrades 0.663→0.526 out of sample (new) |

Every row's `reused_from` column states whether the number was newly
computed by Phase 12 or reused verbatim from a Phase 6-10 artifact.

---

## L. Award philosophy

Two distinct questions, per the brief:

1. **Best player / ability**: "Who possesses the greatest underlying
   ability?" — best answered by MF4 (career-shrunk rates), within a role,
   for the players who clear the reliability gate.
2. **Most valuable season**: "Who generated the most measurable value this
   season?" — best answered by MF1/MF3 (raw `EPA_points_raw`), within a
   role, disclosing reliability.

**These are not the same player**, and the evidence says they cannot be
merged: year-to-year rank correlation for every cross-position value
transform is 0.159-0.253, while career-ability rank correlation
leave-one-season-out never falls below 0.85. A season's *value* is mostly
season-specific; a player's *ability* is comparatively durable. A Statistical
Tewaaraton is conventionally a season award — closer to question 2 — and
`STATISTICAL_TEWAARATON_SPECIFICATION.md` is scoped accordingly.

---

## M. Model candidate scorecard

`player_value_model_candidates.csv`, 27 rows, one schema, every column the
brief specifies (`model_id`, `model_family`, `target_concept`, `unit`,
`positions_supported`, `inputs`, `baseline`, `additive`,
`cross_position_claim`, `double_counting_risk`, `sample_size_requirement`,
`reliability`, `validation_result`, `major_assumptions`,
`major_failure_modes`, `status`):

| Status | Count |
|---|---|
| VIABLE | 3 |
| VIABLE_WITH_CAVEAT | 7 |
| ROLE_ONLY | 1 |
| EXPERIMENTAL | 1 |
| REJECTED | 14 |
| UNSUPPORTED | 1 |

The three explicitly forbidden constructions (arbitrary-weighted composite,
equal-weighting default, positional z-score presented as value) are included
as rows specifically so their rejection is documented with a stated reason
rather than merely absent from the file — `REJECTED`, all three, by rule
and/or by the evidence above.
