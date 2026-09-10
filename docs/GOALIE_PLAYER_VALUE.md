> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Goalie Player Value — V1

## Definition

`goalie_value_total = expected_points_allowed - observed_points_allowed`,
where `expected_points_allowed = one_point_SOG_faced * E[points | 1PT SOG] +
two_point_SOG_faced * E[points | 2PT SOG]` — the already-published
`goalie_value_raw`. **Unit**: PLL points prevented above a league-average
goalie on the same shots faced. **Baseline**: league-average points-allowed
rate, separately for one- and two-point shots on goal. **Interpretation**:
how many fewer points this goalie conceded than an average goalie would
have, on the same shots. **Inputs**: `shots_on_goal_faced`,
`one_point_shots_on_goal_faced`, `two_point_shots_on_goal_faced`,
`goals_allowed`, `two_point_goals_allowed`.

## What this is NOT

**Not shot-quality adjusted.** No shot location, distance, or defender data
exists in this feed. A goalie behind a defense that concedes point-blank
shots is charged for it exactly as if he faced league-average shot quality.
This is stated on every leaderboard row's `publication_caveat`, not a
footnote.

## Rate/workload decomposition — new in Phase 13

The same exact-identity trick as faceoff:

```
rate_value     = goalie_value_total * (league_mean_shots_faced / shots_on_goal_faced)
workload_value = goalie_value_total - rate_value
```

Sums to `goalie_value_total` exactly, every row
(`data/processed/2026/goalie_value_components.csv`, `accounting_check`
column, max value ~2.9e-15 across 17 goalies). Reproduces Phase 10's
decisive counterfactual P4 (two goalies of identical per-shot skill can
differ 30x in total value from team-conceded shot volume alone) as a
visible, per-row split rather than a documented caveat alone.

## Uncertainty

Parametric binomial bootstrap: one/two-point goals allowed each
`~Binomial(shots on goal faced of that class, observed allow rate)`;
`expected_points_allowed` is reconstructed exactly from the published value
(`actual_points_allowed + goalie_value_raw`) and held fixed. **No external
coefficient recovery is needed for this bootstrap** — unlike faceoff, every
quantity is directly reconstructable from published columns.

Example: Sean Byrne (152 SOG faced, save% 0.623): point estimate +13.55,
95% bootstrap interval **[-0.45, +27.55]** — a very wide interval reflecting
his small sample. This width is reported deliberately rather than
suppressed; a point estimate alone would overstate how precisely this value
is known.

## Qualification (2026)

`role_rate_reliability≥0.5` and `future_award_input_eligible` jointly
determine QUALIFIED. Only 1 of 17 goalies is QUALIFIED at single-season
scope in 2026's data (career pooling raises this to 8 of 27 league-wide,
per Phase 10 — see `docs/PLAYER_VALUE_DEFINITION.md` §3 for why the season
and career questions differ).

## Known limitations

- Substantially confounded with team defensive shot-volume (§ above).
- Single-season save-percentage reliability is the lowest of any rate in
  the project; most of the goalie board is SMALL_SAMPLE.
- 1PT/2PT baseline split barely matters in practice (sensitivity check
  `S4_separate_1pt_2pt_baseline_vs_pooled`, rank correlation 1.000) — kept
  because the accounting doc's stated rationale (expected points per SOG
  0.461 vs 0.482) is confirmed, not because it changes rankings.
