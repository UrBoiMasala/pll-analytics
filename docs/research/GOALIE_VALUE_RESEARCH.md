> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Goalie Value Research (Phase 12 §H)

Goalie value carries the largest career-pooling reliability gain in the
project and, simultaneously, the single strongest counterfactual argument
against any cross-position total-value model. This document tests every
assumption named in the Phase 12 brief before adopting the
`shots_faced × (expected − observed)` framework, rather than assuming it.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

---

## 1. Testing each assumption

**Are shots faced accurately attributable?** Yes — `shots_on_goal_faced` is
a box-score total per goalie, reconciling with the team's shots-allowed
figures. This is the correct opportunity denominator (not raw `shots`, which
includes misses the goalie never had to face).

**Must one-point and two-point shots be separated?** Yes, and this project
already does: `goalie_value_raw` is built from **separate one- and two-point
expected-points-allowed baselines** (`PLAYER_VALUE_ACCOUNTING.md` §4C: a
one-point shot on goal has expectation 0.461, a two-point shot 0.482 —
different point weights on a different baseline rate). A single pooled
save-percentage baseline would misprice a goalie's shot mix.

**Is shot quality observable?** **No.** No shot location, distance, or
defender-pressure field exists anywhere in the raw feed. `goalie_value_raw`
prices every shot on goal at the league-average rate for its point value,
which means a goalie behind a defense that concedes close-range shots is
charged for the resulting lower save rate exactly as if he faced
league-average shot quality.

**Do save% differences mostly represent goalie skill or defensive shot
quality?** **Cannot be separated with this feed** — this is precisely the
consequence of the previous finding. The between-goalie spread that IS
measurable (`career_ability_reliability.csv`: implied true sd 0.022, about
2.2 save-percentage points) is real (excess variance exceeds binomial noise,
kappa is finite at 495.2, not capped), but it does not distinguish "goalie
is skilled" from "goalie's defense allows easier shots" — no data exists to
attribute between the two.

**Reliability of career save%?** κ = 495.2 shots on goal — close to a full
season's workload for a starter (median 354). 8 of 27 career goalies (29.6%)
clear reliability 0.5, the largest single career-pooling gain of any rate in
the project (from 1 of 16 at single-season scope). Split-half reliability
(odd vs even seasons) is only **0.102** on 17 goalies — the smallest
sample-constrained population of any rate, which is why career save% is
classified `READY_WITH_CAVEAT` rather than `READY`.

**Is a league-average baseline defensible?** Yes for pricing (the same
principle applies to every other role), but the workload confound below
means the *total* it produces is not a fair cross-goalie comparison even
among goalies themselves at different workloads.

**Uncertainty from missing shot location/distance/defender data?**
Unquantifiable directly (no ground truth exists to check against), but its
existence is not speculative: it is the mechanism behind the previous two
findings, and it means `goalie_value_raw`'s point estimate carries
unmodeled variance beyond its own posterior interval.

## 2. The decisive counterfactual

`player_value_counterfactual_tests.csv`, `T5_same_save_pct_different_shots_faced`
— reproducing Phase 10's probe P4 on the canonical dataset: two goalies at
**identical** per-shot skill above league expectation, at 10th- vs
90th-percentile shots-on-goal faced, differ in total `goalie_value_raw` by
construction — confirmed. The original Phase 10 measurement on 2026 alone
found a **30x** total-value difference from workload at identical skill,
driven entirely by how many shots the team conceded — the goalie's own
defense's action, not his. **This is the single strongest argument in the
entire project against a cross-position total-value model built on this
feed.**

## 3. Can goalie value share a common points scale with offense?

**Only under stated assumptions, and they are demanding.** Mathematically,
`goalie_value_raw` and `offensive_EPA_points_raw` are both PLL-point
residuals against a league baseline (verified additive, disjoint
opportunity sets). Practically:

- `cross_position_value_audit.csv`: goalie value's pooled SD is **7.98**
  against attack's 4.00 — a goalie's season carries roughly twice the spread
  of an attackman's, mechanically, because a busy goalie faces 150-330 shots
  on goal against an attackman's ~60-130 offensive opportunities.
- The workload confound (§2) means a within-goalie-role total ranking is
  itself team-context-contaminated before any cross-role question is even
  asked.

A cross-position model that includes goalie value must, at minimum: (1)
state whether it is answering "who has the best per-shot skill" (MF3's
per-opportunity variant) or "who produced the most total value" (raw MF3),
because they rank goalies very differently at different workloads; and (2)
disclose that the goalie's total is substantially a function of his
defense's performance, which is exactly the P4 finding.

## 4. Verdict

**MF3_goalie_above_baseline is VIABLE_WITH_CAVEAT** for a within-role,
single-season ranking, with the P4 workload confound disclosed as a
first-class caveat, not a footnote. **MF6_statistical_goalie_of_the_year is
VIABLE_WITH_CAVEAT** for the same reason. Any cross-role use of
`goalie_value_raw`'s total is **REJECTED** on the same grounds Section J
below states generally.
