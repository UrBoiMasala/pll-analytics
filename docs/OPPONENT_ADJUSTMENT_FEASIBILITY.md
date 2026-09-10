> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Opponent Adjustment Feasibility (2022–2026)

Phase 8 deferred opponent adjustment with the reason "50 games and 8 teams is
too small". Phase 9 has 232 games across five seasons and can replace that
assumption with a measurement.

**The answer is not the one the deferral anticipated.** Identifiability was
never the problem. The problem is that PLL's schedule is so balanced there is
almost nothing to adjust for.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**. Source: `multi_season_opponent_adjustment.csv`.

---

## 1. The two questions, separated

An opponent adjustment is worth building only if **both** hold:

1. **Is it identifiable?** The schedule graph must be connected enough that
   every team's strength can be separated from its opponents'.
2. **Is it worth anything?** Teams must actually face *different* slates. A
   perfectly balanced schedule leaves nothing to correct.

These are usually conflated. In PLL they have opposite answers.

---

## 2. Question 1 — identifiability: **YES, perfectly** — OBSERVED

| Season | Team-games | Distinct pairings | Possible pairings | **Connectivity** | Games/team |
|---|---|---|---|---|---|
| 2022 | 92 | 28 | 28 | **1.00** | 11.5 |
| 2023 | 92 | 28 | 28 | **1.00** | 11.5 |
| 2024 | 90 | 28 | 28 | **1.00** | 11.3 |
| 2025 | 90 | 28 | 28 | **1.00** | 11.3 |
| 2026 | 100 | 28 | 28 | **1.00** | 12.5 |

PLL plays an 8-team near-round-robin: **all 28 possible pairings occur in every
season**. This is the best case a two-way model can have — no disconnected
components, no team estimable only through a long chain. Phase 8's stated
reason for deferring ("poorly identified at this sample") is **not supported**.

---

## 3. Question 2 — is it worth anything: **BARELY** — OBSERVED

**DERIVED.** A ridge-regularised two-way model (λ = 1.0) of team-game offensive
efficiency on offence and defence indicators, ratings centred to sum to zero,
bootstrapped over **games** (400 resamples, seeded) so the movement carries its
own uncertainty.

| Season | SoS spread | Team spread | **SoS as share of team spread** | Adjustment sd | Bootstrap SE | **Signal-to-noise** | Max rank change | Spearman raw vs adj |
|---|---|---|---|---|---|---|---|---|
| 2022 | 0.0053 | 0.0180 | 29.2% | 0.0162 | 0.0156 | **1.04** | 2 | 0.929 |
| 2023 | 0.0078 | 0.0403 | 19.3% | 0.0356 | 0.0176 | **2.02** | 1 | 0.976 |
| 2024 | 0.0039 | 0.0272 | 14.5% | 0.0266 | 0.0192 | **1.38** | 0 | 1.000 |
| 2025 | 0.0045 | 0.0221 | 20.3% | 0.0217 | 0.0162 | **1.34** | 1 | 0.976 |
| 2026 | 0.0024 | 0.0134 | 17.7% | 0.0133 | 0.0183 | **0.73** | 0 | 1.000 |

Three things follow.

**The schedule is nearly balanced.** The spread in strength of opposition
actually faced is only **14–29%** of the spread between the teams themselves.
Everybody plays everybody, roughly the same number of times.

**The adjustment barely moves anything.** Maximum rank change across five
seasons is **2 places** (2022); it is **0 or 1** in four of five seasons, with
rank correlation against unadjusted of **0.93–1.00**.

**In 2026 the adjustment is smaller than its own error.** Signal-to-noise 0.73 —
the bootstrap standard error of a team's adjustment *exceeds* the spread of the
adjustments themselves. Publishing that number would mean publishing something
**less reliable than the unadjusted figure it replaces**.

---

## 4. Why pooling seasons does not help — **INFERRED**

The obvious move — fit one model on all 232 games — is wrong, and not for a
statistical reason.

A 2022 Whipsnakes roster and a 2026 Whipsnakes roster are **not the same unit**.
The franchise name persists; the players, coaches and in two cases the franchise
itself do not (Chrome exits after 2023, Outlaws enter in 2024). Treating them as
one team would estimate a five-year average of five different teams and label it
an opponent effect.

Pooling therefore gives **replication of the feasibility question across five
independent seasons**, which is what §3 reports, rather than added connectivity
to a single graph. That replication is itself valuable: the finding is not a
2026 accident.

---

## 5. Verdict: still DEFERRED, now for a measured reason

**INFERRED, and stated plainly.** Opponent adjustment for PLL is *feasible* and
*nearly inert*. The cost of adding it is a new model, a new set of assumptions
and a second set of numbers to explain; the benefit is a rank change of 0–2
places in an 8-team table whose Phase 5 null model already showed that chance
alone moves 8–12 total rank places.

**Adding it would not make the ratings better. It would make them harder to
explain and, in 2026, less reliable.**

The catalog entry `opponent_adjusted_value` therefore stays **DEFERRED**, with
its reason rewritten from an assumption to this measurement, and its freeze
classification moved from `REVISE_BEFORE_HISTORICAL` to `DO_NOT_USE` — there is
no longer an open question to revisit before ingesting history, because history
has been ingested and has answered it.

### What would change this verdict

- **A materially unbalanced schedule.** If PLL expands past 8 teams into
  conferences with unequal cross-play, SoS spread would rise and the adjustment
  would start to matter. The measurement in §3 should be re-run, not assumed, at
  that point.
- **A metric with more per-game noise than offensive efficiency.** The signal-to-
  noise figures here are specific to that response variable.
- **A question that is genuinely about schedule.** "Who had the hardest slate?"
  is answered directly by the `strength_of_schedule_sd` column without adjusting
  anything.

### What is published

Nothing is adjusted. Every efficiency and value metric in this repository
remains **unadjusted and labelled as such**, in all five seasons. The
feasibility evidence is published as data
(`multi_season_opponent_adjustment.csv`) so the decision can be re-examined
against numbers rather than re-argued.

**UNSUPPORTED:** any claim in this repository that a team or player figure is
opponent-adjusted, strength-of-schedule adjusted, or otherwise corrected for
who they played.
