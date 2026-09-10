> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Phase 13 Validation

18 checks. Written to `data/processed/history/phase13_validation_report.csv`
in the same `check_id / check_name / status / n_failures / detail` shape as
every earlier phase.

**Independence.** Checks 1-4 re-hash/re-read Phase 8-12's own frozen
artifacts rather than trusting that nothing touched them; checks 10-13
recompute accounting identities from the published CSVs directly; check 14
re-runs the entire leaderboard-generation module and diffs by SHA-256;
check 17 re-runs the SQL layer and diffs against the CSVs it is supposed to
expose, with a floating-point tolerance appropriate to DuckDB/pandas float
rendering differences; check 18 re-runs `pytest --collect-only` rather than
trusting a remembered test count.

---

## The checks

| # | Check | Result | What it verifies |
|---|---|---|---|
| 1 | `raw_data_unchanged` | PASS | raw_manifest_hash recomputed per season from `_meta.json` content hashes |
| 2 | `canonical_manifest_artifacts_unchanged` | PASS | every hash in `CANONICAL_MANIFEST_V1.json` re-computed from disk |
| 3 | `phase11_canonical_dataset_unchanged` | PASS | `phase11_validation_report.csv` re-read, still all PASS |
| 4 | `phase12_research_outputs_unchanged` | PASS | `phase12_validation_report.csv` re-read (still all PASS); 5 Phase 12 CSVs confirmed present |
| 5 | `no_universal_mvp_tewaaraton_war_composite_leaderboard` | PASS | 24 Phase 13 CSV schemas scanned for forbidden column names and cross-role columns; 8 docs scanned for forbidden prose (negation-aware) |
| 6 | `no_arbitrary_weight_composite_exists` | PASS | 7 Phase 13 scripts scanned for a literal weighted-sum pattern |
| 7 | `no_positional_zscore_percentile_mislabeled_as_value` | PASS | every Phase 13 schema scanned for a z-score/percentile column named as a value |
| 8 | `no_individual_defensive_value_fabricated` | PASS | `defensive_production_2026.csv` carries `ROLE_ONLY` status and a coverage disclosure on every row; no fabricated exposure column |
| 9 | `no_two_point_conversion_ability_estimate_created` | PASS | offensive leaderboard schema and `career_ability_reliability.csv` re-checked; `two_point_pct` still non-estimable |
| 10 | `offensive_decomposition_sums_exactly` | PASS | 100 rows: `shooting_value_raw + turnover_value_raw == offensive_value`, max residual 0.0 |
| 11 | `faceoff_decomposition_sums_exactly` | PASS | 13 rows: `rate_value + volume_value == faceoff_value_total`, max residual 0.0 |
| 12 | `goalie_decomposition_sums_exactly` | PASS | 17 rows: `rate_value + workload_value == goalie_value_total`, max residual ~2.9e-15 |
| 13 | `team_accounting_reconciles_within_tolerance` | PASS | 45 team-season/league rows, unconditional 5-component identity, tolerance 1e-6 |
| 14 | `ranking_is_deterministic` | PASS | 7 leaderboard/component files regenerated and compared byte-for-byte |
| 15 | `minimum_sample_flags_reproducible` | PASS | qualification-state value counts identical before/after the deterministic rebuild |
| 16 | `historical_rebuild_uses_identical_model_definitions` | PASS | 460 historical offensive rows (2022-2026): `offensive_value == offensive_EPA_points_raw` for every season, confirming one model definition |
| 17 | `sql_outputs_agree_with_python_outputs` | PASS | 5 SQL views diffed against their source CSVs, numeric tolerance 1e-9 |
| 18 | `no_prior_test_was_weakened` | PASS | `pytest --collect-only` re-run; every pre-Phase-13 test file still collects at least its known minimum test count |

---

## Two findings the validator surfaced and both were fixed at the SCRIPT level, never the model

**Check 13, first run: FAIL on 3 of 5 league-total rows.** Residuals of
1.0e-6 to 2.0e-6 — just over the declared tolerance. Root cause: the
LEAGUE_TOTAL row summed 8 already-rounded (6-decimal) per-team subtotals,
and up to 8 independent roundings of 5e-7 each can accumulate past 1e-6.
The underlying identity was never wrong (the 40 individual team-season rows
all passed throughout). Fixed by computing the league total directly from
full-precision player-level columns. See
`player_value_model_change_log.csv` entry 4.

**Check 5, first run: FAIL on one doc.** `PLAYER_VALUE_MODEL_V1.md` states
"No Statistical Tewaaraton, MVP score, WAR, replacement-level composite, or
cross-position leaderboard exists anywhere in this system" — a disclaimer
in this project's own established style. The check's negation-detection
window (60 characters back from the forbidden phrase) was too short to see
the "No" at the start of that sentence. Fixed by widening the window to 150
characters — the correct fix is to the CHECK's own sensitivity, and no doc
text needed to change (the sentence was already correct English).

Neither finding is a "leaderboard looked wrong" correction — both were the
validator's own logic being too strict/too narrow, discovered and fixed
before this report was finalized, and both are recorded honestly rather
than by quietly loosening a threshold to make the checks pass.

---

## Non-negotiable rules, checked directly against the published files

| Rule (Phase 13 brief) | Where verified |
|---|---|
| No universal MVP/Tewaaraton/WAR/cross-position composite | check 5 |
| Ranking is deterministic | check 14 |
| Offensive/faceoff/goalie decompositions are exact | checks 10-12 |
| Team accounting reconciles within tolerance | check 13 |
| No individual defensive value fabricated | check 8 |
| No two-point conversion ability | check 9 |
| Historical rebuild uses one model definition | check 16 |
| SQL agrees with Python | check 17 |
| No prior test weakened | check 18 |

---

## Full suite

```
Phase 13 checks                     18 / 18 PASS
Phase 8-12 validators                unchanged, still all PASS (re-verified by checks 1-4)
Tests, Phases 1-13                  see PHASE13 final report for the exact count
2022-2026 canonical outputs changed  none
Phase 12 research outputs changed    none
```

## Reproducing this phase

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
python3 -m unittest tests.test_phase13 -v
python3 -m pytest tests/ -q
```

## What this validation does NOT prove

- It does not prove the offense/faceoff/goalie value formulas are correct —
  it proves they are the SAME formulas Phase 6-10 already validated,
  applied consistently, and that Phase 13's own additions (decomposition,
  bootstrap, qualification) do not silently change them.
- It does not prove 2026's slightly elevated offensive-value mean (z=2.74
  vs 2022-2025) has a specific cause — it proves the pattern was
  investigated and no defect was found, per Section Q's discipline
  (`PLAYER_VALUE_HISTORICAL_BACKTEST.md` §3).
- It does not prove the bootstrap uncertainty intervals are exact in a
  strict frequentist sense — it proves they are computed from a stated,
  reproducible binomial model rather than asserted.
