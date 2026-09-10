# Audit remediation

The prior independent audit recommended B — fix specific issues, then proceed. The refocus changes what is worth retaining, without treating preferences as bugs. Archived code and outputs remain available but are excluded from the final product.

| Issue | Severity / type | Decision | Correction and downstream consequence |
|---|---|---|---|
| I1 offensive pairwise labels index the wrong draw columns | HIGH / IMPLEMENTATION_BUG | RETIRED_WITH_FEATURE | No pairwise probabilities or simulated ranks in the final catalog. Existing Phase 13 probabilities remain archived and known incorrect; do not present them. No new uncertainty model. |
| I2 faceoff bootstrap recovers the wrong population baseline/coefficient | HIGH / IMPLEMENTATION_BUG | RETIRED_WITH_FEATURE | Retire point-converted faceoff value and bootstrap. Proposed wins above average uses all season takers directly. Existing point totals and erroneous intervals are not the final product. |
| I3 historical shot diagnostics read 2026 game metadata | HIGH / IMPLEMENTATION_BUG | FIXED | Explicit data_dir passes from the builder to fit_shot_models and _shot_feature_frame. Reject mismatched game IDs. Rebuild all five diagnostics; SQL's actual shot-class selection is explicit. Historical model-quality claims are superseded. Shooting residual baseline itself is unchanged. |
| I4 opening shots counted twice; closing events omitted; span selection wrong | MEDIUM / IMPLEMENTATION_BUG | FIXED | Deduplicate event membership, include closing boundary, use distinct boundary IDs for duration eligibility. Rebuilt all possessions and retained team SQL outputs under v2. No possession boundary or score changes. |
| I5 transfer season totals assigned to modal team | HIGH / IMPLEMENTATION_BUG | FIXED for retained foundation; RETIRED_WITH_FEATURE for legacy value accounting | New player_team_stints_2022_2026 preserves actual player-game team, checks unique keys and excludes incomplete/exhibition games. Final schema requires this grain for team aggregates/shares. Old Phase 12 team regression and Phase 13 value accounting remain archived and wrong for transfers. Do not describe those tables as corrected. |
| I6 zero-shot goalies receive simulated rank probabilities | MEDIUM / IMPLEMENTATION_BUG | RETIRED_WITH_FEATURE | No goalie simulation. Final contract: zero resolved shots gives NULL rate, surplus/rank as appropriate to unavailable exposure, and no leaderboard entry; retain roster context. |
| I7 shrinkage sensitivity label and units disagree | MEDIUM / IMPLEMENTATION_BUG | RETIRED_WITH_FEATURE | No shrinkage sensitivity or career-ability output in the final publication layer. Archived mixed-unit results are not evidence for model robustness. |
| I8 transposed goal rows missing repair flag | MEDIUM / IMPLEMENTATION_BUG | FIXED | Flag both swapped rows. Adds 199 flags in 2023 and one in 2024; order/times unchanged. Rebuilt affected event files; v1 manifest preserved. |
| I9 opening ground balls omitted | MEDIUM / IMPLEMENTATION_BUG | FIXED | Initialize the recovering possession with one ground ball when opened by that event. Rebuilt all five seasons. Possession totals now equal eligible ground-ball events. Official player/team ground-ball counts were already correct. |

## Evidence and verification

Code: `pll_build_possessions.Possession`, `pll_chronology_repair.repair_game_chronology`, `pll_player_value_models._shot_feature_frame` / `fit_shot_models`, `pll_build_player_value.main`, `sql/00_base_views.sql`, and `pll_refocus_foundation.player_team_stints`.

New regression fixtures test opening goals, closing turnovers and duplicate companions, recoveries switching teams, exact transfer production, duplicate-key rejection, all five seasons' pre-shot home-goal margins and wrong-season rejection. Historical chronology tests now expect all changed rows: 455 flags in 2023, not 256 sequences. Candidate evidence counts and chronology decisions are unchanged.

Real transfer example: Michael Boehm's 2026 production remains RED 5 games/13 traditional points and WHP 2 games/2 points. Jake Taylor remains OUT 3 games/6 points and WAT 2 games/4 points. No allocation proportional to games or modal-team shortcut is used.

`refocus_foundation_impact.csv` gives before/after event counts, ground balls, duration eligibility/means and provenance by season. `refocus_statistic_impact.csv` records changes in retained team tables; legacy player-value artifacts are not regenerated as final statistics. The final validation report and deterministic hash comparison support reproducibility.

## Other audit findings

- **Retired:** pooled career ability, reliability qualification, parametric rank intervals, counterfactual research tests, cross-position scale diagnostics, causal interpretations of event windows and team-value regression. These were unnecessary for the new product; their defects are not quietly declared fixed.
- **Corrected for presentation:** unequal variance/workload is not proof of incompatible units; arithmetic is not proof of no double counting; reliability is not calibrated certainty; random-fold retrospective diagnostics are not forward tests; residuals are not pure skill; squared rank correlation is not causal attribution. See METRIC_LIMITATIONS.
- **DEFERRED_WITH_REASON — HIGH / DATA_LIMITATION:** individual defensive attribution, shot quality, lineup exposure and off-ball contributions cannot be recovered from these source files. Final scope excludes unsupported impact claims.
- **DEFERRED_WITH_REASON — MEDIUM / DATA_LIMITATION:** missing 2023 faceoffs and the exact 2022 scoring anomaly remain flagged. Do not manufacture source events. Unresolved goalie shot outcomes remain coverage exclusions rather than inferred saves.
- **DEFERRED_WITH_REASON — LOW / ENGINEERING_IMPROVEMENT:** broad removal of legacy global state, packaging, dependency management modernization, archive directory moves and performance optimization can wait. Active season metadata and UTC handling are explicit where repaired.
- **DEFERRED_WITH_REASON — planned implementation:** the 29-metric publication layer, source reconciliation for each proposed metric, optional goalie class coverage gating, final SQL views and dashboard are subsequent work. The current catalog is a specification; no claim of completed publication metrics.

## Validation changes are version changes, not weakened tolerances

The first full suite found four old freeze checks failing because they compared v2 files to v1 hashes. Version-aware validators now verify all v1 files at `b79076f` and every v2 artifact on disk. The v1 manifest itself and every raw byte remain checked. No hash is replaced in v1 and no mismatch is waived. Collection timing was removed from the legacy report; collection counts are not proof of scientific validity.
