> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Future Statistical Award System — Specification (Phase 12 §O)

**This document calculates no player scores.** It specifies how a future
phase could build an award system that the evidence in `PLAYER_VALUE_DEFINITION.md`,
`PLAYER_VALUE_MODEL_RESEARCH.md`, and `CROSS_POSITION_VALUE_PHASE12.md`
actually supports. Because those documents find no defensible cross-role
bridge (recommended architecture: **C — role-specific models only**, see
`PHASE12_VALIDATION.md` §7), this specification is **not** for a single
cross-position "Statistical Tewaaraton." It is for the strongest alternative
the evidence licenses: **a family of separate, single-role statistical
awards**, each fully specified, plus a shared discipline for all of them.

---

## 0. Why not one cross-role award

Restated once, briefly, because it is the reason every choice below is
role-scoped: no transformation tested (ten cross-position bridges in Phase
10, plus a new team-outcome regression in Phase 12) converts `EPA_points_raw`
into a cross-role-comparable value without either discarding magnitude
(percentile/z-score), assuming the answer (quantile-mapping), or resting on
n=40 team-seasons for a handful of coefficients that are not even per-player
weights. **Any future system claiming a single cross-role number is
asserting an unvalidated equivalence** and must not cite this project's
research as its support.

---

## 1. Award architecture

Five separate award tracks, one per role, sharing a common methodology
where the underlying data supports it and diverging where it does not:

| Track | Positions eligible | Status |
|---|---|---|
| Statistical Offensive Player of the Year | attack, midfield | **VIABLE** |
| Statistical FOGO of the Year | faceoff | **VIABLE_WITH_CAVEAT** |
| Statistical Goalie of the Year | goalie | **VIABLE_WITH_CAVEAT** |
| Measurable Defensive Production Leaderboard | defensive_field | **VIABLE_WITH_CAVEAT**, and NOT a "value" or "best defender" claim |
| (No cross-role award of any kind) | — | **UNSUPPORTED** |

## 2. Target concept

**Most valuable SEASON** (retrospective), not best ability, per
`PLAYER_VALUE_DEFINITION.md` §8 and `SHRINKAGE_POLICY.md` §4. This determines
raw vs. shrunk immediately (§6).

## 3. Inputs, by track

- **Offense**: `shooting_value_raw`, `turnover_value_raw` (sum =
  `offensive_EPA_points_raw`), plus disclosed `shooting_reliability`,
  `one_point_reliability`, `turnover-rate reliability`.
- **FOGO**: `faceoff_value_raw`, plus disclosed `faceoff_reliability` and
  the workload-confound statement (draw volume, `faceoffs`).
- **Goalie**: `goalie_value_raw`, plus disclosed `save_reliability` and the
  workload-confound statement (`shots_on_goal_faced`).
- **Defensive production leaderboard**: `caused_turnovers`, `ground_balls`,
  `games_played`, shown as three separate columns, **never combined**.

## 4. Formulas

Exactly the existing, already-validated Phase 6 residual-baseline formulas —
this specification does not propose any new formula:

```
component = (observed points/outcome on the player's own opportunities)
          − (league-average expectation on the SAME opportunities)
```

No new coefficient, weight, or combination rule is introduced anywhere.

## 5. Units

PLL points above the role's own baseline, exactly as `EPA_points_raw`
already defines it. **Never rescaled, standardized, or quantile-mapped
across roles** — doing so is exactly the `XPOS_M03`/`M04`/`M09` family this
project has rejected.

## 6. Baselines

`position` scope, pooled across seasons — the recommended scope for
`EPA_points_raw` on all five roles per `positional_baselines.csv` (53 of 58
role/component combinations recommend `position` scope; between-season
movement of the baseline is inside within-season sampling error for every
role). **Raw value, never shrunk, as the ranking input** — per
`SHRINKAGE_POLICY.md` §4, shrinking a rate and multiplying by the player's
own opportunity count is a materially different and unjustified claim from
shrinking the rate itself.

## 7. Shrinkage

Not applied to the value component (§6). Applied only to the **disclosed
reliability figure** that must accompany every ranked entry — e.g. "ranked
3rd; shooting-rate reliability 0.34" — using the existing, unmodified
Phase 6/10 empirical-Bayes estimator (`beta_prior_by_moments`,
`empirical_bayes_rates`). No new shrinkage method is specified.

## 8. Minimum sample rules

Adopt the existing `future_award_input_eligible` flag (1% of team play
shares, Phase 7's faithful reproduction of Lacrosse Reference's own
published threshold) as the ELIGIBILITY gate for appearing on any track's
leaderboard at all. Separately, disclose (never gate on) the component-level
`*_reliability` value for every listed player — a player may be eligible by
volume and still carry a wide posterior interval on his rate; the interval
must be visible, not used to exclude him from a season-total ranking (season
totals answer a different question than rate ability, per
`PLAYER_VALUE_DEFINITION.md` §1).

## 9. Uncertainty treatment

Every ranked entry must carry, at minimum: (a) the raw value; (b) the
component-level empirical-Bayes reliability; (c) for FOGO and Goalie tracks
specifically, the player's own opportunity count displayed alongside the
value, so a reader can see the workload confound directly rather than infer
it. No bootstrap interval is specified for the value itself, because the
value is an accounting quantity (what happened), not an estimate with
sampling variance in the usual sense — the reliability figure is the
correct uncertainty statement for the underlying RATE, not for the total.

## 10. Role handling

Never combined. Each track is scored, ranked, and published independently.
A player who changed role mid-season (9 of 419 players across 2022-2026,
per `CAREER_ABILITY_METHODOLOGY.md` §1) is scored within whichever role his
`canonical_position` resolves to **for that season** — the existing,
already-validated per-season resolution, not a career-level average.

## 11. Treatment of availability

`games_played` is disclosed alongside every entry (its own column, never
folded into the value) as a transparency measure, exactly per
`mvp_input_readiness.csv`'s classification of `availability_games_played` as
`READY as a denominator/disclosure, NOT as a value input`. It must never be
added to or multiplied into the ranking value — every season-total measure
already rewards it implicitly, and adding it again double-counts durability.

## 12. Treatment of team context

Not applied. `OPPONENT_ADJUSTMENT_FEASIBILITY.md`'s verdict stands:
identifiable but nearly inert (adjustment moves ranks by 0-2 places; in 2026
its own bootstrap SE exceeds its signal). A future phase should re-run that
measurement, not assume its conclusion, if the league's schedule ever
becomes materially unbalanced (e.g. expansion into conferences).

## 13. Treatment of playoffs

Not separated in this specification. All five seasons' analytics-eligible
games (regular season and playoffs alike) are pooled for the baseline
computation, consistent with every published Phase 6-11 baseline. A future
phase MAY test whether playoff and regular-season baselines differ
materially before deciding whether to separate them — that test has not
been run and this specification does not assume an answer.

## 14. Whether career information enters

**No**, not into the value itself (§6-7). It MAY be displayed as a
secondary, clearly-labeled data point — "career shooting rate (shrunk):
0.31, reliability 0.62" — alongside the season ranking, to give context on
how much of the season's performance looks like the player's established
level. It must never be blended into the season ranking number, per
`SHRINKAGE_POLICY.md` §5.

## 15. Known limitations, stated once, applying to every track

1. Year-to-year rank correlation for every tested value transformation is
   0.159-0.253 — a season ranking describes that season, not a persistent
   talent measure.
2. No track is comparable to any other track's ranking. Presenting all five
   tracks on one page is not a composite as long as no combined score,
   ordinal merge, or "overall MVP" pick is derived from them.
3. FOGO and Goalie tracks carry an explicit, quantified workload confound
   (2.1x and 30x respectively at identical per-opportunity skill) that must
   be disclosed with every ranking, not buried in a methodology footnote.
4. The Defensive track is production, not value — it must never be
   presented with a single combined score, and the "partial" qualifier
   stays in every column name.
5. Two-point shooting ability must never appear in any track's ranking
   input, in any form, at any scope.
6. This specification proposes no new statistical machinery. Every formula,
   baseline, shrinkage method, and eligibility rule already exists,
   published and validated, in Phases 6-10.

## 16. Explicit non-goals

This specification does not, and a future phase implementing it must not,
produce: a single number combining two or more tracks; a rank that spans
roles; a "Most Valuable Player" label applied across tracks; or any
artifact matching the forbidden patterns in `pll_metric_catalog.FORBIDDEN_IN_PUBLISHED`.
