> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Cross-Position Comparability — Phase 12 Synthesis (Phase 12 §J)

This is the central research question the Phase 12 brief poses: does any
empirically grounded bridge exist between offensive, faceoff, goalie and
defensive value? Phases 7 and 10 already answered this in detail
(`CROSS_POSITION_COMPARABILITY.md`, `CROSS_POSITION_VALUE_RESEARCH.md`).
This document is the Phase 12 synthesis — it does not re-argue the finding,
it re-tests the bridges against the specific standard the brief sets
("a mathematical unit alone does not prove comparability") using the
signal-inventory and dependency evidence built in this phase, and states the
verdict for a future phase to build against.

Labels: **OBSERVED** · **DERIVED** · **MODELED** · **INFERRED** ·
**UNSUPPORTED**.

---

## 1. The three candidate bridges, tested against the standard

### Bridge 1: expected points (`EPA_points_raw`)

**Assumptions**: a PLL point above a role's own baseline means the same
amount of "value" regardless of role. **Empirical support**: none — it is
an assumption, not a finding. **Evidence against it**: role SD ratio 4.58x
pooled (2.0-8.6x by season, `cross_position_value_audit.csv`); opportunity
mean ratio 20.9x; counterfactual P1 (Phase 10, re-cited): identical z=+2.0
within-role corresponds to raw magnitudes from 2.91 to 18.61 PLL points
depending on role. **Uncertainty**: the SD ratio is itself estimated with a
bootstrapped 95% CI that excludes 1.0 by a wide margin (new Phase 12
computation, `player_value_validation_results.csv` BOOTSTRAP_UNCERTAINTY row)
— the gap is not sampling noise. **Sensitivity**: unchanged across all five
individual seasons (never below 3.2x). **Distortion from role-opportunity
differences**: this IS the distortion — the whole finding is that opportunity
volume differs by an order of magnitude across roles and the SD ratio tracks
it.

**Verdict: REJECTED as a value bridge.** The unit is shared; the scale is
not, and no transformation of it that keeps magnitude equalizes the scale
(§2).

### Bridge 2: possession value

**Assumptions**: possessions can be attributed to individual players.
**Empirical support**: none is possible — no lineup/on-off/shift data
exists anywhere in the feed (`PLAYER_VALUE_ACCOUNTING.md` §6). **Verdict:
UNSUPPORTED**, not merely rejected — the bridge cannot be tested at all with
this data, and collapses into Bridge 1 for the touches it can see.

### Bridge 3: scoring margin (team-level)

**Assumptions**: a player's role-value share of a team's summed EPA
translates into a share of the team's scoring margin / win contribution.
**Empirical support**: real, and newly measured in Phase 12 — team-summed
EPA correlates with team win_pct at r=0.76 (n=40 team-seasons), and a
4-predictor regression (offense/faceoff/defense/goalie EPA sums) reaches
R²=0.663 in-sample, 0.526 leave-one-season-out. **Uncertainty**: bootstrap
95% CIs on all four coefficients exclude zero, but span up to ~3x their own
point estimate (off_epa: [0.0003, 0.0085] around a point estimate of
0.0044). **Sensitivity**: R² degrades materially out-of-sample (0.663 →
0.526), consistent with overfitting risk at n=40 for 4 predictors.
**Distortion from role-opportunity differences**: severe and unresolved —
`off_epa` aggregates 15-20 players per team-season, `fo_epa`/`g_epa`
aggregate 1-3; the regression's own coefficients are team-level weights, not
validated per-player weights, and no assumption converts one into the other
defensibly with this sample size.

**Verdict: EXPERIMENTAL.** This is the strongest of the three bridges by a
real correlational measure, and it is still not usable as an individual-
level cross-role value bridge, for the reasons stated. It is the single
most literal, most-completed attempt at deriving empirical cross-role
weights this project has made, and it is included specifically so a future
phase does not have to re-run it to learn it fails.

## 2. Why position z-scores/percentiles are not evidence of value equivalence

This is stated as its own item because it is the single most common naive
mistake a cross-position model could make, and the brief explicitly warns
against it. `player_value_model_candidates.csv` rows `XPOS_M03`/`XPOS_M04`
and the `FORBIDDEN_positional_zscore_as_value` row all carry status
`REJECTED`, and the reason is quantitative, not definitional: two players at
*identical* within-role z=+2.0 correspond to raw values from 2.91
(defensive_field) to 18.61 (goalie) PLL points — a **6.4x** spread hidden
entirely behind the claim "these are both 2 standard deviations above
average." Equal standing within a group is a statement about that group's
own distribution; it says nothing about how that group's typical unit of
standing compares to another group's.

## 3. Conclusion — the same one Phases 7 and 10 reached, now tested one more way

**No bridge tested — including the one new one this phase ran to
completion — supports converting a within-role value into a cross-role
ranking.** The binding constraint remains measurement coverage: attack and
midfield value is measured over ~19,000 career shots; defensive value is
measured over caused turnovers with a games-played denominator, from a feed
in which zero events name a defender (`DEFENSIVE_VALUE_FEASIBILITY.md`).
Until the feed records more of what a defender does, or until a
substantially larger multi-team panel makes Model Family 5's regression
trustworthy at the individual level, a cross-role model built on this data
will systematically misstate at least one role's contribution — not because
that role contributes less, but because less of what it contributes is
written down or because the estimator does not have enough independent
observations to trust.

## 4. What this means for the recommended architecture

See `PHASE12_VALIDATION.md` §7 for the formal A/B/C/D determination. The
short version, stated here because it follows directly from §§1-3: option
**A (a defensible universal value model)** is not supported by any evidence
this phase or Phases 7/10 produced. **Option C (role-specific models only)**
is the recommendation, not B — no *pair* of roles (not even the two
best-identified ones, offense and faceoff) was shown comparable on any
tested bridge, so there is no principled subset to carve out as "partially
common." A common *unit* exists (`EPA_points_raw`, PLL points above a role
baseline) and is genuinely additive within a role, and that unit is what
makes five separate, internally rigorous role-specific award models
possible — but a common *scale* across any two roles was not established by
anything tested here or in Phases 7/10, including the one new bridge
(Model Family 5) built specifically to look for one.
