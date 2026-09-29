> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Player Value Uncertainty Methodology (V1)

## Method chosen, and why

**Parametric binomial bootstrap**, 1,000 draws per role, fixed seed
(20261013, +1 for faceoff, +2 for goalie). Chosen over the alternatives
named in the Phase 13 brief because every value component here is, at
root, a function of a small number of binomial outcomes (shot makes,
faceoff wins, goals allowed) at an observed rate and a known trial count —
exactly the case a parametric binomial bootstrap is built for, and it
requires no additional model (unlike a posterior/shrinkage interval, which
would need a prior Phase 12 already found weak at single-season scope for
most rates, or an empirical resampling across seasons, which would conflate
season-to-season instability with within-season sampling noise).

## What is resampled, per role

- **Offense**: `one_point_goals ~ Binomial(one_point_attempts, observed
  rate)`, `two_point_goals ~ Binomial(two_point_attempts, observed rate)`.
  `shooting_value` recomputed per draw holding the baseline fixed.
  `turnover_value_raw` is held fixed (stated limitation — see
  `OFFENSIVE_PLAYER_VALUE.md`).
- **Faceoff**: `faceoff_wins ~ Binomial(faceoffs, observed win rate)`.
- **Goalie**: one/two-point goals allowed each `~Binomial(shots on goal
  faced of that class, observed allow rate)`.

In every case, the **expectation/baseline term is reconstructed exactly**
from already-published columns (e.g. goalie: `expected_points_allowed =
actual_points_allowed + goalie_value_raw`) and held fixed across draws —
only the OBSERVED outcome is resampled, which is the correct target for
"how much would this player's measured value bounce around if the season
replayed with the same underlying rate."

## What this interval means, precisely

It answers: *given this player's own observed rate and trial count, how
much would his measured value vary due to outcome randomness alone if the
season were replayed?* It does **not** answer *how good is this player,
probably* (that is the career-ability question, `career_ability_reliability.csv`,
deliberately a different quantity) and it does **not** incorporate model
uncertainty in the baseline itself (the baseline is treated as known,
because it is estimated from hundreds to thousands of league-wide
observations, several orders of magnitude larger than any individual
player's own sample).

## Rank-stability diagnostics

For every qualifying player, per draw: recompute the FULL role ranking,
then report:

- **`rank_ci_lo`/`rank_ci_hi`**: 2.5th/97.5th percentile rank across 1,000
  draws.
- **`top10_inclusion_frequency`**: fraction of draws in which the player
  places in the role's top 10.
- **Pairwise uncertainty** (`data/processed/history/offensive_value_pairwise_uncertainty_2022_2026.csv`):
  for adjacent-ranked pairs, `P(A > B)` across the same 1,000 paired draws.

## What this reveals, honestly

Goalie value intervals are the widest in the system relative to their point
estimates — e.g. 2026's #1 goalie (Sean Byrne, 152 shots on goal faced)
carries a 95% interval of **[-0.45, +27.55]** around a point estimate of
+13.55. This is not a defect; it is the correct, disclosed consequence of a
small single-season sample, and it is exactly why the qualification column
(`SMALL_SAMPLE`) exists alongside it.

Offensive value's top-ranked player in 2026 (Logan Wisnauskas, 43 shots)
has a `top10_inclusion_frequency` of 0.976 — high, but not 1.0: in about
2.4% of resampled seasons at his own observed rate and volume, he would
have fallen out of the top 10 by chance alone.

## What this does NOT do

- It does not bootstrap the position-scope baseline itself (treated as
  fixed, per above).
- It does not produce an interval for `defensive_production_2026.csv` —
  a box-score count is not a rate estimate, so no interval is attached; the
  availability confound is disclosed as text instead
  (`DEFENSIVE_PRODUCTION_LIMITATIONS.md`).
- It does not claim any interval is exact in a frequentist sense beyond the
  binomial model's own assumptions (independent trials at a stationary
  rate) — a documented, standard limitation of any such interval.
