> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Offensive Value Decomposition (Phase 12 §F)

Offense is the strongest-supported part of this dataset — the widest event
coverage (19,030 career shots, 2022-2026), the only rate with two
identifiable dimensions of shooting skill, and the only role where every
counterfactual test in `player_value_counterfactual_tests.csv` behaves
exactly as expected. This document decomposes offensive value into its
candidate components and states which are identifiable without double
counting.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

---

## 1. The candidate decomposition

| Component | Identifiable? | Evidence |
|---|---|---|
| **SHOT VOLUME** | Opportunity, not value | `shots`/`recorded_offensive_opportunities` — a denominator |
| **SHOT SELECTION** (two-point attempt share) | **YES — the most identifiable individual property in the project** | κ=2.99 attempts, 85.1% of career shooters clear reliability 0.5 |
| **SHOT CONVERSION** (shooting_pct) | **PARTIALLY**, career scope only | 17.8% of career shooters clear reliability 0.5 (season scope: 6.8%) |
| **SHOT CONVERSION, split further**: accuracy (`shots_on_goal_pct`) vs finishing-once-on-goal (`goals_per_shot_on_goal`) | Accuracy is MORE identifiable (21.4%) than finishing (5.2%) | Splitting shows the identifiable half of "shooting" is hitting the cage, not beating the goalie — consistent with the goalie owning most of the residual |
| **TWO-POINT CONVERSION** | **UNSUPPORTED at every scope** | Career observed variance 0.0102 < binomial noise 0.0137 (excess -0.0035); control (one-point, same players) is identifiable at reliability 0.753 |
| **TURNOVER COST** | **PARTIALLY** | κ=138.0 touches, 52.0% of career players clear reliability 0.5 — the highest-clearing rate in the project |
| **AVAILABILITY / TOTAL OPPORTUNITY** | Denominator, not value | `games_played` — READY as a denominator, UNSUPPORTED as an independent value input |

## 2. No double counting, verified

`player_value_metric_dependency.csv`. Shooting value and turnover value are
**DISJOINT_BY_CONSTRUCTION** (different opportunity sets — shots vs
touches), and `offensive_EPA_points_raw = shooting_value_raw +
turnover_value_raw` exactly (max abs diff 1.8e-15 over 446 attack/midfield
player-seasons). Counterfactual `T3_same_scoring_different_turnovers`
confirms this from a different angle: at identical (median) shooting value,
the 75th-percentile-turnover player's offensive total strictly exceeds the
25th-percentile-turnover player's — ball security is never "free" at any
scoring level, and the two components add rather than compete.

The VIF diagnostic (`PLAYER_VALUE_MODEL_RESEARCH.md` §C.4) is the adversarial
check: `goals` and `shots` carry VIF 58.3 and 43.8 against a pool that
includes `shooting_value_raw` — evidence that a naive composite using raw
counts AND the EPA-style residual as separately-weighted inputs would be
massively collinear. This project's published components avoid that by
construction: `shooting_value_raw` already IS the repriced form of
`goals`/`shots`, and nothing sums them a second time.

## 3. "What happened" vs "what ability does this demonstrate" — kept separate

Two-point production (`two_point_goals`, `two_point_attempts`, the PLL points
they generated) **stays published as a descriptive statistic** and reconciles
exactly to the official box score (Phase 9 check 8). It is **fully countable
production**, unaffected by the two-point-conversion-ability finding above.
What is not published anywhere is a two-point *ability* estimate: every
`two_point_pct_shrunk` value at every scope tested (season, pooled seasons,
pooled career) collapses to the league mean, and `player_value_signal_inventory.csv`
classifies `two_point_conversion_pct` `season_award_suitability =
"UNSUPPORTED"` explicitly to keep this from being silently resurrected.

**The distinction that matters**: a player who took and made a two-point
shot this season legitimately produced 2 points, countable in
`scoring_points` and `EPA_points_raw`. Nothing in the identification finding
above removes that production. What is removed is any claim that the rate at
which he did so measures a persistent, individual skill — the league-wide
data give no evidence any player differs from any other on that specific
rate.

## 4. Counterfactual verification

`player_value_counterfactual_tests.csv`, T1-T3 (offense-scoped):

- **T1** (same efficiency, different volume): a total-value metric correctly
  assigns more value to the higher-volume player at equal per-opportunity
  rate — PASS, and this is the *expected* behavior for a production metric,
  not a defect.
- **T2** (same volume, different efficiency): a total-value metric correctly
  assigns strictly more value to the more efficient player at equal volume —
  PASS (basic monotonicity).
- **T3** (same scoring, different turnovers): confirmed additive and
  independently signed — PASS.

## 5. Verdict

**MF3_offense_above_baseline is VIABLE** — the strongest-supported model
family in this dataset. Within-role ranking on `EPA_points_raw` or
`offensive_EPA_points_raw`, with reliability disclosed per component, is
defensible for a single-season, single-role award. It remains
**season-specific** (year-to-year rank correlation 0.159-0.253 across all
ten cross-position transforms, which apply to the offensive components too)
and must never be presented as a persistent talent measure without
substituting the career-shrunk rate, which answers a different question
(MF4).
