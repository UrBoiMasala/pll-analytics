> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# PLL Advanced Player Value — Model V1 (Phase 13)

This is the production implementation of the role-specific player value
system Phase 12 recommended (Architecture C: role-specific models only). It
introduces **no new value formula** — every component reuses an
already-validated Phase 6-10 computation. What is new is the productionized
layer around it: frozen specification, decomposition, bootstrap uncertainty,
qualification, team accounting, historical backtest, sensitivity, and a SQL
exposure layer.

**No Statistical Tewaaraton, MVP score, WAR, replacement-level composite, or
cross-position leaderboard exists anywhere in this system.**

---

## 1. The question this system answers, precisely

> "Given the opportunities observable for this player's role, how much
> measurable value did the player produce relative to an appropriate PLL
> baseline?"

This is a **retrospective, single-season, single-role** question. It is not
an ability estimate (see `PLAYER_VALUE_UNCERTAINTY.md` and
`docs/PLAYER_VALUE_DEFINITION.md` §1 for why those are different questions),
and it is never asked across roles at once.

## 2. The frozen specification

`data/processed/history/player_value_model_spec_v1.csv`, 12 rows, written
and run **before** any leaderboard existed. Every row states: model_name,
role, component, target_concept, unit, formula, numerator, denominator,
baseline, baseline_scope, opportunity_measure, shrinkage_used,
career_information_used, minimum_sample_rule, uncertainty_method, additive,
publication_status, known_limitations, phase12_evidence_reference.

Four changes were made to *scripts* after seeing output, all recorded in
`data/processed/history/player_value_model_change_log.csv` — **none changed
a value, a formula, a baseline, or a ranking**:

1. A mislabeled diagnostic column in the offense components table (cosmetic).
2. The team-accounting script's own check was too narrow (it filtered
   components by role before summing, missing cross-role incidental
   production); corrected to an unconditional identity check plus a
   separate, honestly-labeled coverage-gap statistic.
3. A counterfactual test's pair-matching tolerance was too loose relative to
   how tightly offensive rates cluster near zero; corrected to a tolerance-
   free nearest-pair search.
4. The team-accounting LEAGUE_TOTAL row summed already-rounded per-team
   subtotals, accumulating a rounding residual just over its own 1e-6
   tolerance in 3 of 5 seasons; corrected to sum full-precision player-level
   columns directly.

## 3. The four role models, one line each

| Model | Role | Unit | Status |
|---|---|---|---|
| `offensive_value_v1` | attack, midfield | PLL points above position baseline | VIABLE |
| `faceoff_value_v1` | faceoff | PLL points above league win-rate baseline | VIABLE_WITH_CAVEAT |
| `goalie_value_v1` | goalie | PLL points above league expected-points-allowed baseline | VIABLE_WITH_CAVEAT |
| `defensive_production_v1` | defensive_field | box-score counts, unranked | ROLE_ONLY (production, not value) |

Full detail: `docs/OFFENSIVE_PLAYER_VALUE.md`, `docs/FACEOFF_PLAYER_VALUE.md`,
`docs/GOALIE_PLAYER_VALUE.md`, `docs/DEFENSIVE_PRODUCTION_LIMITATIONS.md`.

**They are never combined.** No file, query, or document in this project
sums, averages, or ranks across these four. `docs/CROSS_POSITION_VALUE_PHASE12.md`
is the reason.

## 4. Team accounting

`data/processed/2026/player_value_team_accounting.csv`. Two distinct claims,
kept separate (a prior version of this script conflated them and reported a
spurious failure — see the change log):

1. **The unconditional accounting identity is exact.** For every player,
   `shooting_value_raw + turnover_value_raw + faceoff_value_raw +
   goalie_value_raw + defensive_value_partial_raw = EPA_points_raw`
   (verified to 1e-15 in Phase 12; re-verified at team and league level
   here). **40/40 team-seasons PASS**, tolerance 1e-6.
2. **The four published role leaderboards do not partition 100% of team
   EPA.** `defensive_field` publishes no value (by design — see
   `DEFENSIVE_PRODUCTION_LIMITATIONS.md`), and any player's off-role
   incidental production (a backup faceoff taker who is primarily a
   defenseman, or any player's own caused-turnover credit against their own
   position group's rate) is real EPA that no leaderboard captures. This
   gap is measured and reported, never hidden: e.g. in 2026, team EPA sums
   to ~0 league-wide while the four leaderboards' values sum to +58.76 —
   the difference is the `defensive_field` group's own EPA (which is
   substantially negative that season) plus smaller incidental leakage.

## 5. Uncertainty

Parametric binomial bootstrap, 1,000 draws, fixed seed, per role. Full
methodology: `docs/PLAYER_VALUE_UNCERTAINTY.md`.

## 6. Qualification

Reuses already-published reliability/eligibility columns
(`role_rate_reliability`, `offensive_rate_ranking_eligible`,
`future_award_input_eligible`) — no new threshold is invented.
`QUALIFIED` / `SMALL_SAMPLE` / `DESCRIPTIVE_ONLY` / `INSUFFICIENT_EVIDENCE`.
No player is deleted from a leaderboard for being small-sample; the flag
travels with the row.

## 7. Historical backtest

The SAME functions run across 2022-2026 — Section N is not a separate model,
it is this code applied to five slices of the one canonical table.
`docs/PLAYER_VALUE_HISTORICAL_BACKTEST.md`.

## 8. Sensitivity

Six alternative-assumption comparisons, none adopted, all measured:
`data/processed/history/player_value_sensitivity.csv`.

## 9. SQL layer

`sql/phase13_*.sql`. Python owns every statistical estimate; SQL only
exposes and joins the already-published CSVs via DuckDB views. Verified to
agree exactly (`data/processed/history/phase13_sql_python_agreement.csv`,
5/5 PASS).

## 10. Reproducing this phase

```
python3 scripts/pll_phase13_model_spec.py
python3 scripts/pll_phase13_player_value_v1.py
python3 scripts/pll_phase13_team_accounting.py
python3 scripts/pll_phase13_historical_stability.py
python3 scripts/pll_phase13_counterfactuals.py
python3 scripts/pll_phase13_sensitivity.py
python3 scripts/pll_phase13_dominance.py
python3 scripts/pll_phase13_change_log.py
python3 scripts/pll_phase13_sql_layer.py
python3 scripts/pll_validate_phase13.py
python3 -m pytest tests/ -q
```

No step contains an unseeded random component (RNG seed 20261013, +1, +2
per role, fixed).
