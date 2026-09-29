> Historical research/reference document. Final publication scope and corrected interpretations are defined in [PROJECT_REFOCUS](../PROJECT_REFOCUS.md) and [METRIC_LIMITATIONS](../METRIC_LIMITATIONS.md). Old production/qualification labels do not apply to the final product.

# Phase 10 Validation

24 checks, all PASS. Written to
`data/processed/history/phase10_validation_report.csv` in the same
`check_id / check_name / status / n_failures / detail` shape as every earlier
phase.

**Independence.** Every numeric check recomputes its target from the canonical
tables or the raw JSON corpus rather than reading the artifact it is validating.
Where a Phase 10 module used an imported estimator, the check **reimplements the
arithmetic inline** so the two cannot fail together.

---

## The checks

| # | Check | Result | What it actually recomputes |
|---|---|---|---|
| 1 | `identity_integrity_2022_2026` | PASS | 419 `officialId`s re-derived from `player_stats_2022_2026`; 264 span more than one season; no player carries two rows for one season |
| 2 | `no_duplicate_or_split_player_careers` | PASS | one career per id, covering exactly the observed player set; **0** ids share a normalised name with another id |
| 3 | `season_totals_reconcile_to_career_totals` | PASS | 16 counting columns re-summed from the 1,023 pooled player-season rows for all 419 players |
| 4 | `frozen_2026_and_published_possession_layers_unchanged` | PASS | 24 frozen artifacts present; every headline 2026 total still equals Phase 8's figure; possession counts unchanged in all five seasons |
| 5 | `repair_evidence_classification_recomputes` | PASS | the DIRECT class re-derived independently from the raw `markerId` sequence and the faceoff/ground-ball companion relation, in all five seasons |
| 6 | `every_repaired_transition_carries_evidence` | PASS | **256** applied repairs in 2023, each with an evidence class, an action, a source event id and its original timestamp; **199** transpositions all supported by a `markerId` contradiction |
| 7 | `repaired_possessions_reconcile_to_official_scoring` | PASS | PLL points re-derived from the repaired layer for every eligible team-game; 2 residuals, both the documented `archers-cannons-2022-6-18` exception |
| 8 | `repair_creates_and_deletes_no_events` | PASS | every boundary in both layers points at an event that exists; no duplicate event, no negative duration, no offence == defence |
| 9 | `career_opportunities_equal_component_season_opportunities` | PASS | 6 rates; every career successes and trials total re-summed from the season rows |
| 10 | `raw_career_rates_recompute_exactly` | PASS | **2,613** (player, rate) estimates: raw rate equals successes/trials to 1e-12; every rate, shrunk rate and reliability in [0,1] |
| 11 | `no_impossible_rates` | PASS | successes never exceed trials, in the estimates or in any of the 1,023 pooled rows |
| 12 | `no_nan_or_inf_in_publishable_phase10_metrics` | PASS | 6 publishable tables; nulls permitted **only** where they encode a meaning |
| 13 | `shrinkage_and_reliability_recompute_independently` | PASS | 5 rates; the beta prior re-derived by an **inline** method-of-moments implementation sharing no code with the estimator under test, then every player's shrunk rate and reliability re-derived from it |
| 14 | `uncertainty_bounds_valid` | PASS | **2,342** posterior intervals: ordered, inside [0,1], containing their own point estimate, and **narrowing monotonically with trials** in every rate |
| 15 | `positional_baselines_recompute` | PASS | 5 position baselines re-derived directly from `player_stats_2022_2026` |
| 16 | `cross_position_transformations_recompute` | PASS | M01 and M04 — the two whose whole purpose is scale comparison — re-derived on 1,012 player-seasons |
| 17 | `two_point_ability_remains_unsupported` | PASS | identification re-tested in every season and both pooled scopes: `identifiable = [False × 7]`; the published shrunk rate is fully collapsed; the readiness table says UNSUPPORTED |
| 18 | `every_readiness_classification_is_sourced` | PASS | 14 classified inputs, each with a supporting statistic, a justification, a caveat and at least one evidence file that **exists on disk** |
| 19 | `phase10_rebuild_is_deterministic` | PASS | **29** outputs recomputed by re-running all four modules and compared by SHA-256 |
| 20 | `all_prior_validators_still_pass` | PASS | 6 earlier validation reports re-read; every check still PASS |
| 21 | `season_and_career_samples_separately_recoverable` | PASS | every career names its component seasons, teams, positions and roles in season order; **9** multi-role careers keep every role |
| 22 | `no_mvp_tewaaraton_award_or_composite_artifact_exists` | PASS | **1,241** column names scanned across **55** surfaces for 8 forbidden patterns; no cross-position file keyed by player; the readiness table carries **no numeric column** |
| 23 | `repair_leaves_frozen_seasons_and_all_scoring_untouched` | PASS | 2022, 2025, 2026 bit-identical; total points unchanged in all five seasons; **0 of 40** team ranks move |
| 24 | `all_phase10_outputs_present` | PASS | 29 expected artifacts |

---

## Checks required specifically for the possession repair

The Phase 10 brief names six invariants for any repaired transition. Each maps
to a check and, where a rule is involved, to a unit test on synthetic events:

| Requirement | Check | Test |
|---|---|---|
| every repaired transition must carry evidence | **6** | `TestRepairOverTheCorpus::test_every_applied_repair_carries_direct_evidence` |
| original values must remain recoverable | **6**, **4** | `test_the_original_2023_layer_is_still_on_disk_and_unchanged` |
| repaired goals must reconcile exactly to official scoring | **7** | `test_scoring_reconciles_exactly_in_the_repaired_layer` |
| no duplicate event may create a boundary | **8** | — |
| no existing valid event may be silently deleted | **8** | `test_repair_transposes_and_retimes_and_changes_nothing_else` |
| all changes must be reproducible | **19** | `TestPhase10ChangedNothingFrozen` |

---

## Tests

`tests/test_phase10.py` — **55 tests**, in the repository's established three
kinds.

**1. Unit tests on the RULES, against synthetic events (9).** Each repair rule is
verified in isolation rather than merely observed to hold in the data, and the
plausible false positives are covered as carefully as the motivating case:

- the real `championship-2023-9-22` shape fires DIRECT;
- a repair transposes and retimes and changes **nothing else** — every other
  field is asserted unchanged;
- **a genuine faceoff-then-goal 30 seconds later does NOT fire** (`markerId`
  agrees with the array order);
- **the real multi-event scramble in `playoffs-quarterfinal-2-2023-9-1` p2 is
  UNRESOLVED**, not repaired — this is the case that produced a negative
  duration before the single-displacement precondition was added;
- **the real duplicated faceoff in `2024_game_10` is reported, not repaired**;
- DIRECT_TIMING retimes and never reorders;
- STRONGLY_INFERRED is not applied by the primary variant but *is* applied when
  selected;
- no repaired possession anywhere has a backwards step in time.

**2. Integration over the real corpus (25).** Scoring reconciliation, the
repair's confinement to 2023 and 2024, career total reconciliation, independent
recomputation of shrinkage from the imported estimator, posterior-interval
validity, the role-scale gap, baseline recomputation, defensive attribution
counts, and the readiness table's structure.

**3. Regression (21).** Phase 8's 2026 totals, published possession counts in
every season, Phase 9's report still all-PASS, and five tests that fail if a
forbidden composite artifact is introduced under any name.

---

## Full suite

```
Phase 10 checks                     24 / 24 PASS
Phase 9 checks                      22 / 22 PASS   (unchanged)
Phase 8 / 7 / 6 / 5 validators      24 / 27 / 24 / 20  all PASS  (unchanged)
Possession validator (2026)         all PASS       (unchanged)
Tests, Phases 1-10                 337 / 337 PASS  (282 prior + 55 new)
2026 statistical outputs changed    none
```

---

## Reproducing the whole phase

```
python3 scripts/pll_phase10_possession_repair.py    # B: detection, repair, statistics
python3 scripts/pll_phase10_career.py               # C, D, E: identity, ability, two-point
python3 scripts/pll_phase10_cross_position.py       # F, G, H, I, J
python3 scripts/pll_phase10_readiness.py            # K
python3 scripts/pll_validate_phase10.py             # 24 checks
python3 -m unittest tests.test_phase10 -v           # 55 tests
python3 -m unittest discover -s tests               # 337 tests, Phases 1-10
```

No step contains a random component. Check 19 re-runs all four modules inside
the validator and compares all 29 outputs by SHA-256.

---

## What the validation does NOT prove

Stated because a validation report that only lists passes is misleading:

- **It does not prove the 2023 repair is right.** It proves the repair is
  evidence-bounded, reproducible, reconciling and confined. The argument that
  the transposition reflects what happened on the field is made in
  [`2023_POSSESSION_REPAIR.md`](../2023_POSSESSION_REPAIR.md) §2 and rests on the
  `markerId` sequence and the faceoff/ground-ball atomicity — both strong, and
  both inference from a feed rather than observation of a game.
- **It does not prove 2022's low possession count is fine.** Phase 9 flagged
  2022 at 82.5 possessions per game, 7.4% below the median. Phase 10 found no
  defect that explains it and did not repair it. That flag stands, unexplained.
- **It does not validate the career ability estimates as estimates of current
  ability.** Check 13 proves they recompute; nothing proves ageing and role
  change do not matter, because neither is modelled.
- **It does not establish that any cross-position transformation is usable.**
  Check 16 proves two of them recompute. The research finding is that none is
  usable.
