# Faceoff Player Value — V1

## Definition

`faceoff_value_total = (faceoff_wins - faceoffs*league_win_rate) *
points_per_marginal_win` — the already-published `faceoff_value_raw`.
**Unit**: PLL points above a league-average faceoff man on the same number
of draws. **Baseline**: the empirical league faceoff win probability for
the season (~0.4966). **Interpretation**: how many points this specialist's
wins-above-expectation were worth, at the empirically estimated value of
converting a loss into a win. **Inputs**: `faceoffs`, `faceoff_wins`.
**Exclusions**: ground-ball recovery (61.5% of post-faceoff ground balls go
to the faceoff winner himself — crediting them separately would pay for
the same draw twice, `PLAYER_VALUE_ACCOUNTING.md` §4F).

## Rate/volume decomposition — new in Phase 13

An exact algebraic identity on the published value, not a new estimate:

```
rate_value   = faceoff_value_total * (league_mean_faceoffs / faceoffs)
volume_value = faceoff_value_total - rate_value
```

`rate_value` is "what this player's value would be at his own rate above
baseline, at the league-average draw volume." `volume_value` is the
residual — the extra (or reduced) value purely from taking more (or fewer)
draws than average. **These sum to `faceoff_value_total` exactly, every
row** (`data/processed/2026/faceoff_value_components.csv`, `accounting_check`
column, max value 0.0 across 13 players).

## Why this decomposition exists

Phase 10's counterfactual P4/P5 and Phase 12's reproduction (test T4) showed
a decisive workload confound: two specialists at an *identical* win rate
above baseline can differ 2x+ in total value purely from draw count. This
decomposition makes that split visible on every row, so a reader can see
whether a given player's rank is rate-driven or volume-driven
(`workload_vs_skill` column) without reading code.

## 2026 example

TD Ierlan: total value 10.64 = rate_value 5.47 + volume_value 5.17
(labeled RATE_DRIVEN, since |rate_value| slightly exceeds |volume_value|).
Andrew McMeekin: total 10.17 = rate_value 7.41 + volume_value 2.76 — a
clearer rate-driven case (higher win rate, fewer draws than Ierlan).

## Uncertainty

Parametric binomial bootstrap: `faceoff_wins ~ Binomial(faceoffs, observed
win rate)`, `faceoff_value_total` recomputed per draw. The marginal-win
coefficient is recovered algebraically from the published value (median
ratio across faceoff takers with a denominator large enough to be stable)
and held fixed across draws.

## Qualification (2026)

13 of 13 faceoff-role players; QUALIFIED requires `role_rate_reliability
≥0.5` and `future_award_input_eligible`. Faceoff is the best-identified
skill in the project (career κ=10.4 draws), so a higher share of the
faceoff board qualifies than any other role.

## Known limitations

- `faceoff_volume_value` is mechanically driven by draw count, not skill —
  ranking by `faceoff_value_total` alone rewards being given more draws.
- No possession-value component beyond the win-rate-above-expectation
  framing (ground balls deferred, see above).
