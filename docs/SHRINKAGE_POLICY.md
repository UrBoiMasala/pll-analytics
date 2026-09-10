# Raw vs Shrunk — Project Policy (Phase 7 §§12–15)

Phase 6 found that shrinkage moves 219 of 228 shooting ranks and left the choice
open. Phase 7 has to close it, because every later phase needs to know which
number answers which question.

This document states the policy, the statistical reason for it, and the evidence
it rests on. **It is not chosen on the basis of which version produces a more
plausible-looking leaderboard**, and the evidence below was computed before any
player name was inspected.

---

## The policy, in three sentences

1. **Raw values describe 2026 and are never overwritten.** `EPA_points_raw` and
   every `*_value_raw` column stay exactly as Phase 6 computed them. They answer
   *what happened*.
2. **Shrunk rates estimate underlying ability and are published separately.**
   `*_rate_shrunk` answers *how good is this player, probably*. It is never
   substituted into a value column.
3. **Which one a later phase should use depends on the question that phase is
   asking**, and the two questions are set out in §4 below. Neither is the
   default.

Three concepts are kept apart and never collapsed into one number:

| Concept | Column family | Question |
|---|---|---|
| `observed_value` | `*_value_raw`, `EPA_points_raw` | What did this player's recorded actions actually produce in 2026? |
| `estimated_skill` | `*_rate_shrunk` | What is this player's underlying rate, with sampling noise reduced? |
| `reliability_adjusted_value` | `*_reliability`, `*_null_z`, posterior intervals | How much evidence is behind the observation, and how unusual is it given the volume? |

---

## 1. Why raw values are never overwritten

**A player who converted an unusually high share of his shots did create those
points.** Marcus Holman's +13.0 EPA_points is not an estimate that might be
wrong; it is an accounting of what his shots produced against what league-average
shots produce. Shrinking it away would answer a question nobody asked: not "what
happened" and not "how good is he", but "what would have happened if he had been
more average", which is neither.

There is also a technical reason shrinkage must not touch the value columns, and
Phase 6 stated it: shrinking a **rate** and then multiplying it by the player's
own **opportunity count** drags every player's total toward zero *in proportion
to his sample size*. That is a far stronger claim than shrinking the rate. It
says a 20-shot player produced less than he did, rather than that we know less
about him than we would like.

The league-sum-to-zero identity is a third reason: every raw component sums to
exactly 0 across the league by construction, and a shrunk-value version does
not. Losing that identity would break the accounting Phase 6 validates to ten
decimal places.

---

## 2. Why shrunk rates exist anyway

A raw rate from 9 shots is mostly noise. The median 2026 shooter took **9 shot
attempts**; the median two-point shooter took **2**. Ranking on raw rates at
those samples ranks on luck.

Empirical-Bayes shrinkage — the Phase 6 estimator, imported by Phase 7 rather
than re-derived, so the two can never diverge — pulls each player's rate toward
the league mean by an amount the data itself determines:

```
shrunk = (successes + alpha) / (trials + alpha + beta)
kappa  = alpha + beta   (the prior strength, in trials)
```

`kappa` is estimated by matching the observed between-player variance net of the
binomial noise each player's own sample contributes. A small `kappa` means the
league really does spread out beyond chance; a huge one means it does not.

---

## 3. The evidence: what is actually identified in 2026

### 3.1 By rate

| Rate | Players with trials | Median / max trials | Prior strength `kappa` | Implied true between-player sd | Raw sd → shrunk sd | Players at reliability ≥ 0.5 |
|---|---|---|---|---|---|---|
| **Faceoff win %** | 47 | 8 / 353 | **15.9 draws** | 0.122 | 0.272 → 0.092 | **18 / 47 (38%)** |
| Shooting % | 192 | 9 / 98 | 70.8 shots | 0.053 | 0.192 → 0.024 | 13 / 192 (7%) |
| One-point % | 168 | 9 / 94 | 75.3 shots | 0.052 | 0.205 → 0.023 | 8 / 168 (5%) |
| Save % | 16 | 148 / 309 | 300.3 SOG | 0.029 | 0.153 → 0.017 | **1 / 16 (6%)** |
| **Two-point %** | 127 | 2 / 29 | **1,000,000 (capped)** | 0.0003 | 0.200 → **0.000** | **0 / 127** |

### 3.2 By value component — an independent check

The rate table above uses only the empirical-Bayes prior. Phase 7 adds a second,
independent diagnostic that does not use shrinkage at all: divide each player's
component by the **closed-form standard deviation that component would have
under chance alone** at his own opportunity counts, then look at the spread of
the result. Under the null that nobody differs in ability, that spread is 1.0.

| Component | Players | sd of null-standardized value | Implied skill share of variance |
|---|---|---|---|
| **Faceoff value** | 47 | **1.830** | **0.70** |
| Caused-turnover value | 228 | 1.291 | 0.40 |
| Turnover value | 228 | 1.268 | 0.38 |
| Goalie value | 16 | 1.320 | 0.43 |
| **Shooting value** | 192 | **1.067** | **0.12** |

The two methods agree without being told to. Faceoff skill is by far the most
identified quantity in the framework; shooting is the least. **This is a genuine
verification, not a restatement**: the null-variance diagnostic is derived from
the league conversion baselines and each player's attempt mix, and shares no
arithmetic with the beta-binomial prior.

### 3.3 Where Phase 7 disagrees with Phase 6's wording

Phase 6 described save percentage as "partially identified". Phase 7 verifies
that **real between-goalie spread exists** (the estimated true sd is about 2.9
percentage points, and the prior strength is finite, not capped) but that
**almost no individual goalie can be separated from the prior**: the busiest
goalie in the league faced 309 shots on goal against a prior strength of 300, so
exactly one of sixteen reaches reliability 0.5. Both statements are true and
they answer different questions. `player_rate_identification.csv` therefore
reports a compound label rather than a single adjective, because collapsing the
two is how "partially identified" comes to mean whatever the reader wants.

Phase 6's other three characterisations are confirmed as written.

---

## 4. When to use which — the policy for later phases

### Use RAW value when the question is retrospective

> "Who produced the most measurable value in the 2026 season?"

Season awards are, in most sports, awarded for what a player did, not for what
his true talent is estimated to be. A most-valuable-player argument that
shrinks away an exceptional finishing season is answering a different question
from the one the award asks. **Raw `EPA_points_raw` is the correct input to a
retrospective, single-season award model.**

### Use SHRUNK rates when the question is about ability or the future

> "Who is the best finisher?" · "Who should we expect to convert next season?"

These are inferential questions about a latent quantity, and the raw rate is a
biased answer to them at 2026 sample sizes — biased toward whoever got lucky in
a small sample. **`*_rate_shrunk` is the correct input to any ability claim,
projection or multi-season comparison.**

### Use RELIABILITY to decide who may be ranked at all

Neither raw nor shrunk fixes the problem that a 6-shot player's efficiency is
uninformative. The reliability columns and the `rate_ranking_eligible` /
`offensive_rate_ranking_eligible` flags decide **who appears on a rate
leaderboard**, independently of which value version is being ranked.

### The recommendation for Phase 8, stated plainly

Phase 8 should build its award model on **raw `EPA_points_raw`**, gated by
**reliability-based eligibility**, and should **report the shrunk-rate
alternative alongside** rather than choosing between them silently. The
justification is that the Statistical Tewaaraton question is retrospective
("who had the best season"), and the honesty requirement is that the sensitivity
of the answer to that choice is large and must be visible.

**How large:** replacing the shooting component with its shrunk-rate equivalent
moves 219 of 228 total-value ranks, with a maximum single move of 161 places and
a rank correlation of **0.758**. The players most affected are exactly the ones
you would expect — mid-volume shooters with extreme conversion rates: Matt
Collison (29 shots, 153 places), Graham Bundy (43 shots, 153 places), Jackson
Eicher (64 shots, 128 places).

A Phase 8 that presents one of these orderings without the other is presenting a
methodological choice as a finding.

---

## 5. What must never be done

- **Never substitute a shrunk rate into a `*_raw` value column.** Validation
  check 12 and a test enforce that raw and shrunk are separately named; the
  sensitivity analysis exists so the shrunk version is available without
  overwriting anything.
- **Never publish a two-point shooting leaderboard from 2026 data.** The
  observed between-player spread (0.0234) is *smaller* than binomial noise alone
  predicts (0.0276). Every player's shrunk two-point rate is the league mean and
  every player's two-point reliability is below 0.001. Validation check 13 and
  three tests fail if a two-point estimate is ever presented as reliable.
- **Never treat shrinkage as a correction for bias in the value accounting.** It
  is not. The raw components are unbiased estimates of what happened; shrinkage
  trades bias for variance in estimating what will happen again.
- **Never choose between raw and shrunk by looking at which produces a more
  familiar name at the top.** The evidence in §3 was computed and written down
  before any leaderboard in this phase was printed.
