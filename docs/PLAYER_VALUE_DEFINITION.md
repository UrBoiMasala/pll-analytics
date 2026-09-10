# Player Value: Definitions and What This Dataset Can Estimate (Phase 12 §A)

Before testing a single model, Phase 12 first separates eight concepts the
Phase 12 brief names, which the rest of this project's documentation and code
have used correctly but never laid out side by side. **No ranking, score or
composite is built in this document.**

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

---

## 1. The eight concepts, and why they are not interchangeable

### 1. Production

*What did this player's recorded actions actually generate?* A pure count or
a residual against a league-average opportunity baseline — `goals`,
`scoring_points`, `shooting_value_raw`, `EPA_points_raw`. Mathematically, a
sum over the player's own recorded events. It answers a **retrospective**
question and requires no model of ability at all.

### 2. Efficiency

*Rate of success per opportunity* — `shooting_pct`, `points_per_shot`,
`goalie_EPA_per_SOG`. Mathematically, production divided by opportunity
count. Two players can have identical efficiency and wildly different
production if their opportunity counts differ — this is not a subtlety, it
is the definition. A 3-shot season at 100% shooting and a 100-shot season at
50% are not comparable on efficiency alone, and Model Family 3's diagnostics
(counterfactual T1/T2, reused from Phase 10's P2/P3) exist specifically to
keep this distinction visible.

### 3. Opportunity / usage

*How often was this player put in a position to act?* — `shots`, `touches`,
`faceoffs`, `shots_on_goal_faced`, `recorded_offensive_opportunities`. This is
a **denominator**, not a value. `multi_season_usage_model.csv` established
that the constant model beats every fitted usage→value model in
cross-validation on 844 player-seasons: usage predicts the *variance* of
value, not its *mean*, and its correlation with offensive EPA is negative in
four of five seasons. Treating usage itself as value would reward being
given opportunities, not converting them.

### 4. Underlying skill / ability

*What is this player's true, persistent rate, net of sampling noise?* —
`<rate>_shrunk` at `pooled_player_career` scope. Mathematically, an
empirical-Bayes posterior mean, `(successes + alpha)/(trials + alpha + beta)`.
This is an **inferential** quantity about a latent parameter, not a
description of what happened. `CAREER_ABILITY_METHODOLOGY.md` establishes
that this is estimable for a *minority* of players on 6 of 9 candidate rates,
and for exactly 0% on two-point conversion.

### 5. Marginal contribution

*How much of the team's outcome is attributable to this player, net of what a
substitute would have done?* This concept requires a counterfactual
substitution — what would have happened with someone else in this player's
exact role and exposure. **This dataset cannot estimate it for any role.**
There is no lineup, shift, or on/off data of any kind (`PLAYER_VALUE_ACCOUNTING.md`
§6), so no substitution counterfactual is computable. `EPA_points_raw` is
routinely *described* as marginal value in casual sports-analytics language,
but it is not: it compares a player to a *league-average* player on the
*same recorded opportunities the player himself generated*, never to a
teammate who might have taken those same opportunities differently or not at
all.

### 6. Team-context contribution

*How does this player's production relate to his team's success?* A
correlational, not causal, quantity — see the new Model Family 5 regression
in `PLAYER_VALUE_MODEL_RESEARCH.md` §5. Team win_pct correlates with
team-summed `EPA_points_raw` at r=0.76 across 40 team-seasons, but the EPA
components are residuals against the *same games'* scoring outcomes that
determine win_pct, so part of this relationship is definitional rather than
independent validation. It is a legitimate **concurrent-validity check**, not
a causal attribution of winning to a player.

### 7. Replacement-level value

*How much better is this player than the player who would otherwise occupy
his role?* Phase 10 tested whether a "marginal-opportunity player" baseline
(the bottom third of a role-season by opportunity, chosen non-circularly by
playing time rather than performance) is empirically definable —
`cross_position_replacement_level.csv`. It is definable for four of five
roles, and it **buys nothing**: it sits only 7–20% of a role SD below the
role mean, so subtracting it is subtracting a near-constant (Method M07
reduces to M01 plus an offset — see the model candidate scorecard). This
project's naming guard specifically reserves the string `replacement_level`
for the forbidden composite family; the estimable quantity is published as
`marginal_roster_player_level` precisely so it is never mistaken for a
validated WAR-style baseline.

### 8. Award value / MVP value

*Who had the best measurable SEASON, for the purpose of a retrospective
honor?* This is the target concept a Statistical Tewaaraton actually asks
about. It is explicitly **not** the same question as ability (5) — an award
asks about what happened in one season, an ability estimate asks about a
persistent property — and Section 2 below shows the data supports the two
questions to very different degrees.

---

## 2. Why these are not interchangeable — worked mathematically

Let `v` be a player's raw production (e.g. `EPA_points_raw`), `o` his
opportunity count, and `r = v/o` an efficiency rate at typical scale (not
exact for a baselined residual, but illustrative).

- **Production is opportunity-weighted efficiency**: `v ≈ r · o`. Two players
  with the same `r` differ in `v` purely by `o`; two players with the same
  `v` can have very different `r` and `o` (counterfactual T6 in
  `player_value_counterfactual_tests.csv` constructs exactly this case and
  finds no single correct ranking — the method choice, not the data,
  decides).
- **Ability is `r`'s posterior mean, not its sample value**: shrinkage moves
  `r` toward a league prior by an amount that shrinks as `o` grows. At
  `o` below the rate's own `kappa` (prior strength in trials), the shrunk
  estimate is dominated by the prior and is a statement about the *league*,
  not the *player* (`CAREER_ABILITY_METHODOLOGY.md` §2). This is why
  `shooting_pct_shrunk` at 9 shots (median 2026 season) is nearly the league
  mean regardless of what the player actually shot.
- **Marginal contribution requires a counterfactual `v'`** (what a
  substitute would have produced with this player's role and exposure) that
  this feed cannot construct, because exposure itself (minutes, shifts,
  lineups) is unobserved. `v` is *not* `v - v'`; it never had a `v'` term to
  subtract.
- **Team-context contribution is `Corr(Σv_team, team_outcome)`**, a
  population-level statistic over 40 team-seasons, not a per-player quantity
  at all. Reading it as "this player's share of the win" requires an
  additional, unvalidated within-team allocation Phase 12 does not attempt
  (see Model Family 5's own stated limitation: a team-level coefficient is
  not a per-player weight).
- **Replacement-level value is `v - baseline_marginal`**, and Phase 10 showed
  `baseline_marginal ≈ role_mean - 0.07..0.20·role_sd`, i.e. numerically close
  to the role-mean baseline `MF3` already uses. It is a real but
  low-information correction.
- **Award value, this project's finding, is best approximated by
  within-role `v` (raw `EPA_points_raw`) with a reliability disclosure**, per
  `SHRINKAGE_POLICY.md` §4: "Statistical Tewaaraton question is
  retrospective ('who had the best season'), and raw value is the correct
  input to a retrospective, single-season award model" — provided the model
  never claims to be cross-role (see `CROSS_POSITION_VALUE_PHASE12.md`).

---

## 3. What this dataset can and cannot estimate, concept by concept

| Concept | Estimable? | Scope | Evidence |
|---|---|---|---|
| Production | **YES** | any role, single season or career | Exact accounting identity, verified on all 5 canonical seasons (`player_value_metric_dependency.csv`, ACCOUNTING_IDENTITY rows) |
| Efficiency | **YES, with a reliability gate** | rate-specific; 6 of 9 candidate rates estimable at some scope | `career_ability_reliability.csv` |
| Opportunity / usage | **YES as a denominator; NO as a value** | any role | `multi_season_usage_model.csv`: constant model wins CV |
| Underlying ability | **PARTIALLY**, for a minority of players, at career scope | 6 rates; 0-85.1% of players clear reliability depending on rate | `CAREER_ABILITY_METHODOLOGY.md` |
| Marginal contribution | **NO** | no role | No lineup/shift/on-field data exists anywhere in the feed |
| Team-context contribution | **YES, as a population correlation; NO, as a per-player attribution** | team-season (n=40) | New Phase 12 regression, `PLAYER_VALUE_MODEL_RESEARCH.md` §5 |
| Replacement-level value | **YES, for 4 of 5 roles; adds little** | role-season | `cross_position_replacement_level.csv` |
| Award value (single-season, within-role) | **YES, with a stability caveat** | single role only | `cross_position_method_comparison.csv`: year-to-year rho 0.159-0.253 for every transformation |
| Award value (cross-role) | **NO transformation tested supports it** | — | `CROSS_POSITION_VALUE_RESEARCH.md`, re-affirmed in `CROSS_POSITION_VALUE_PHASE12.md` |

---

## 4. What Phase 12 does with this

Every subsequent Phase 12 document is scoped to exactly one of the rows
above, and none of them upgrades a "NO" or "PARTIALLY" to a "YES" without new
evidence. `docs/PLAYER_VALUE_MODEL_RESEARCH.md` tests the model families the
brief names against this table; `docs/STATISTICAL_TEWAARATON_SPECIFICATION.md`
(if the evidence supports writing one at all) is scoped to the concept the
evidence actually supports — **award value, within role** — not to the
concept a Statistical Tewaaraton is colloquially assumed to answer
(cross-role best player).
