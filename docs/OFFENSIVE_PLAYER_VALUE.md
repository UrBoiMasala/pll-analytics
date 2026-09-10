# Offensive Player Value — V1

## Definition

`offensive_value = shooting_value_raw + turnover_value_raw`

**Unit**: PLL points above a league-average attack/midfield player on the
same recorded opportunities. **Baseline**: position-scope, pooled
2022-2026 (per-shot-class expected conversion rate for shooting;
position-group per-touch turnover rate for turnovers). **Interpretation**:
what this player's shots and touches actually produced, minus what an
average player at his position would have produced on the identical
opportunities, this season. **Inputs**: `one_point_attempts`,
`two_point_attempts`, `one_point_goals`, `two_point_goals` (shooting);
`touches`, `turnovers` (turnover cost). **Exclusions**: assists (already
priced inside the shooter's own goal, crediting them separately would
double the value of one goal — `PLAYER_VALUE_ACCOUNTING.md` §4H); shot
creation (not separable from finishing in this feed); possession itself (no
lineup data exists to attribute it).

## Accounting

`shooting_value_raw + turnover_value_raw = offensive_value` exactly, every
row (`data/processed/2026/offensive_value_components.csv`,
`accounting_check` column, max value 0.0 across 100 players).

## Two-point treatment

Three separate concepts, never conflated:

1. **Two-point PRODUCTION** (`two_point_goals`, `two_point_attempts`) —
   real, countable, already inside `shooting_value_raw`'s numerator.
2. **Two-point SELECTION** (`two_point_attempt_share_raw =
   two_point_attempts/shots`) — an identifiable individual tendency
   (career κ=2.99 attempts, 85.1% of career shooters clear reliability 0.5)
   — shown as a descriptive column, never priced independently (pricing it
   again would double-count the same shots `shooting_value_raw` already
   prices).
3. **Two-point CONVERSION ABILITY** — **UNSUPPORTED**, at every scope
   tested. Never estimated, never shown as a shrunk rate, never used as a
   ranking input.

## Uncertainty

Parametric binomial bootstrap (1,000 draws): `one_point_goals ~
Binomial(one_point_attempts, observed rate)`, `two_point_goals ~
Binomial(two_point_attempts, observed rate)`, `shooting_value` recomputed
per draw holding the published expected-points baseline fixed.
`turnover_value_raw` is held fixed at its observed value in every draw —
**a stated limitation**, not an omission: `~19%` of league turnovers are
attributed to a team only, not a player, so resampling turnover COUNT would
require assumptions about that unattributed 19% this model does not make.

## Qualification (2026)

| State | n | % |
|---|---|---|
| QUALIFIED | 13 | 13.0% |
| SMALL_SAMPLE (via reliability<0.5 but eligible) | — | folded into DESCRIPTIVE_ONLY below in v1 (see note) |
| DESCRIPTIVE_ONLY | 86 | 86.0% |
| INSUFFICIENT_EVIDENCE | 1 | 1.0% |

Note: `offensive_rate_ranking_eligible` (the 1% team-play-share minimum) and
`role_rate_reliability≥0.5` jointly determine QUALIFIED; nearly every
attack/midfield player clears the eligibility bar but not the reliability
one, so this v1's state distribution is dominated by DESCRIPTIVE_ONLY
exactly as Phase 8's finding predicts (13/192 shooters cleared reliability
in the full 2026 population; 13/100 in this attack/midfield-only subset).

## Known limitations

- Season value is not stable year to year: `player_value_historical_stability.csv`
  shows Spearman rho 0.09-0.28 across consecutive seasons — describes one
  season, not a talent measure.
- Turnover attribution is incomplete league-wide (~19% team-only).
- No creation/finishing split; no possession attribution.
