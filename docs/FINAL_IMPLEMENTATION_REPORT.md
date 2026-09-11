# Final PLL analytics implementation report

## Result

Local final statistics product implemented: 35 core metrics, nine primary publication views, four supporting views, five seasons and pooled exports. No dashboard. Public GitHub publication is blocked by source-data redistribution terms; the local product is not represented as publicly released.

## Checkpoint and validation

- Local project directory was preserved. Public project identity is `pll-analytics`.
- Initial branch: `main`; clean HEAD: `eebde31a69b300ac36a744aeb2fea0f67b1e9949` (Refocus analytics project and simplify final metric scope).
- Baseline: 424 tests passed, 14/14 refocus checks. An initial sandbox-limited run could not write legacy research outputs; rerunning with authorized directory access established the passing baseline.
- Final full suite: **443 passed**, 11 existing dependency/deprecation warnings. No skipped test substituted for a failure.
- Refocus validator: **14/14 PASS**. This still validates the preserved 29-row historical proposal and canonical checkpoint; the new validator checks the active 35-row catalog.
- Publication validator: **148/148 PASS**, including canonical reconciliation and pooled plus five-season SQL/CSV equality.
- Determinism: **79/79 CSVs** match two independent builds in fresh temporary directories and the stored publication files. Binary database byte identity is not claimed.
- All **16 example SQL statements** execute successfully.
- No raw or canonical processed files changed. Original research outputs also remain unchanged. Refocus checks verify immutable payload hashes and canonical version invariants.

Two development failures were resolved: an empty shot season initially disappeared through an inner baseline join, now corrected using the eligible-season spine; SQL examples initially used naive semicolon splitting, now replaced by DuckDB's statement parser. Negative regressions cover zero exposure and example execution.

## Exact core catalog

### TEAM

`possessions_per_game`, `offensive_efficiency`, `defensive_efficiency`, `net_efficiency`, `shots_per_possession`, `turnovers_per_possession`, `shot_clock_expirations_per_possession`, `offensive_pace_seconds`, `median_possession_span`, `shot_producing_possession_rate`, `multi_shot_possession_rate`, `team_assist_to_goal_ratio`, `time_of_possession_share`, `defensive_pace_seconds`.

### OFFENSE

`shooting_pct`, `shots_on_goal_pct`, `scoring_points_per_shot`, `turnovers_per_touch`, `turnovers_below_expected`, `shooting_value_above_expected`.

### PLL_2PT

`two_point_attempt_rate`, `two_point_conversion_pct`, `two_point_shooting_value`, `team_two_point_attempt_share`.

### FACEOFF

`faceoff_pct`, `draw_share`, `faceoff_wins_above_average`.

### GOALIE

`save_pct`, `one_point_save_pct`, `two_point_save_pct`, `saves_above_average`.

### DEFENSE

`caused_turnovers_per_game`, `ground_balls_per_game`, `penalties_per_game`.

### USAGE

`shot_share`.

## Reuse versus implementation

Reused mathematics/source contracts (13): possessions_per_game; offensive_efficiency; defensive_efficiency; net_efficiency; shots_per_possession; turnovers_per_possession; offensive_pace_seconds (the existing mean span under a clear name); median_possession_span; turnovers_per_touch; faceoff_pct; draw_share; faceoff_wins_above_average; caused_turnovers_per_game. The final layer expresses these in its shared SQL schema rather than depending on archived value pipelines.

Adapted existing metrics (11): shot_clock_expirations_per_possession (events); shooting_pct; shots_on_goal_pct; scoring_points_per_shot; turnovers_below_expected; shooting_value_above_expected; two_point_attempt_rate; two_point_conversion_pct; two_point_shooting_value; save_pct (resolved events instead of the earlier box-score source); shot_share (existing share mathematics with final eligible-event numerator/denominator and actual appearances).

Completed partial definitions (4): team_two_point_attempt_share; one_point_save_pct; two_point_save_pct; saves_above_average. The final goalie residual uses the pooled resolved event baseline consistently across total and split outcomes.

New final calculations (7): ground_balls_per_game; penalties_per_game; shot_producing_possession_rate; multi_shot_possession_rate; team_assist_to_goal_ratio; time_of_possession_share over canonical-v2 measurable spans; defensive_pace_seconds. These are simple derived measures, not claims of statistical invention. Possession-length binary shot frequency is an additional analysis calculation, not another core metric.

## Decisions and specification differences

- Offensive pace replaces mean_possession_span; they are mathematically identical at the same scope. No duplicate numeric column.
- Possession margin is not mechanically symmetric or zero. It remains diagnostic/ANALYSIS_ONLY, excluded from core metrics and rankings because reconstruction/ambiguity changes the differences; no claim it measures additional possessions won.
- Broad offensive_play_share is REJECTED for the final product. Existing event-log counts mix roles; the narrower shots-plus-turnovers proxy is calculable but adds limited information alongside shot share and ball security and must not be presented as a comprehensive offensive-play share. No arbitrary assist/ground-ball weights were added.
- The latest specification's resolved-event goalie contract supersedes the refocus proposal's box-score overall save denominator. This affects historical goalie results and is explicit in the dictionary.
- Goalie two-point mix is CONTEXT, not core.
- Player views contain both explicitly labeled SEASON and STINT rows to preserve transfers. Queries must select one level.
- No arbitrary qualification threshold. Rate examples expose opportunities; an optional example display filter is not a reliability conclusion.

CONTEXT: raw production and exposure counts, coverage, same-season pooled rates, team two-point selection/scoring share/return, goalie shot mix, official score residuals, positions and team stints.

ANALYSIS_ONLY: possession-length splits, ambiguity sensitivity, league environment comparisons and diagnostic possession-count differences. Clock buckets are not labeled tactical types.

REJECTED: broad offensive play share, performance interpretation of possession margin, duplicate offensive mean-span column, fast-break inference from elapsed time, assisted-goal linkage from pre-shot passes, redundant conditional ratios, universal scores and all retired rank/bootstrap machinery.

## Final outputs

Primary SQL views and identically named CSVs:

1. team_advanced_stats
2. player_offensive_advanced
3. player_shooting_advanced
4. player_two_point_stats
5. faceoff_advanced
6. goalie_advanced
7. defensive_production
8. player_season_summary
9. possession_length_analysis

Supporting exports: season_baselines, team_game_publication, publication_coverage, possession_sensitivity. All 13 have pooled and five per-season versions: 78 CSVs plus the metric dictionary, validation and determinism reports. The optional local DuckDB database is ignored and reproducible, not a tracked binary deliverable.

Files added/updated include SQL definitions/examples, builder/catalog/query/validator/determinism scripts, publication tests, all final CSVs, README, final catalog, methodology, SQL guide, safety review, dependency pins and ignore rules. Small retained documentation edits remove stale stage statements and the personal absolute path. No broad directory reorganization occurred.

## Coverage and limitations

| Season | Eligible games | Possessions | Measurable possessions | Unattributed shots | Scoring gap |
|---|---:|---:|---:|---:|---:|
| 2022 | 46 | 3795 | 2196 | 4 | -7 |
| 2023 | 46 | 4204 | 2296 | 0 | 0 |
| 2024 | 45 | 4001 | 2215 | 1 | 0 |
| 2025 | 45 | 4009 | 2100 | 0 | 0 |
| 2026 | 50 | 4388 | 2306 | 0 | 0 |

2026 is partial through the latest included game start, 2026-08-30 00:30 UTC. Postseason games are included where completed. Do not compare raw partial-season volumes as if exposure matched completed seasons.

The known 2022 seven-point source gap remains flagged, not repaired. Unattributed shots remain in team/league denominators. Duration is measured only for unambiguous, nontruncated distinct-event spans; it is not total clock control. Goalie outcomes lack shot quality and defensive-environment controls. Defensive production lacks minutes, lineups, matchups and on/off attribution. No persistent talent or comprehensive defensive value is claimed.

## Example 2026 results

These are descriptive snapshot results, not evidence of persistent skill. Player residuals use SEASON rows only.

| Metric | Leader | Value | Exposure/context |
|---|---|---:|---|
| Offensive efficiency | WAT | 29.9603 | 151 PLL points / 504 possessions × 100 |
| Defensive efficiency | ARC | 23.4927 | 113 points allowed / 481 opponent possessions × 100 |
| Net efficiency | WHP | +3.4642 | PLL points per 100 possessions |
| Shot-producing possession rate | WAT | 71.0317% | 358 / 504 |
| Multi-shot possession rate | WAT | 22.0238% | 111 / 504 |
| Shortest offensive measurable span | OUT | 23.5597 seconds | 51.8584% measurable coverage |
| Longest opponent measurable span | ARC | 29.0465 seconds | 53.6383% measurable coverage; not a skill claim |
| Measurable TOP share | WAT | 55.5647% | 8,088 / 14,556 measured seconds |
| Official assists per goal | OUT | 0.6115 | 85 assists / 139 goals |
| Shooting value above expectation | Logan Wisnauskas | +12.4255 points | 43 shots |
| Shot share | CJ Kirst | 20.1923% | 84 / 416 appearance-matched team shots |
| Faceoff wins above average | TD Ierlan | +30.7135 wins | 353 attempts |
| Saves above average | Sean Byrne | +11.9387 saves | 138 resolved SOG |

Unfiltered PLL points/shot leader: Henry Bard, 2.0 from one shot. This illustrates why denominator display matters. With an explicitly illustrative 20-shot display filter, Logan Wisnauskas leads at 25/43 = 0.5814. The 20-shot filter is not a scientific qualification and is not imposed on stored outputs.

## Publication safety and GitHub status

No MVP/WAR/cross-position composite, retired bootstrap, rank probabilities, pairwise comparisons, faceoff point conversion or new talent model enters final outputs. No dashboard was built.

Intended repository name: **pll-analytics**. No remote existed and GitHub CLI was unavailable. No GitHub repository was created, no branch was pushed, and no public URL/visibility is claimed. The stronger blocker is the official PLL statistics/data redistribution terms. See [safety audit and gated manual commands](PUBLICATION_SAFETY.md). Raw data remains local and preserved; no raw data was publicly uploaded.

Initial repository footprint: about 196 MiB, raw data 62 MiB, processed data 99 MiB, Git objects 28 MiB. Publication outputs add about 3.6 MiB. Largest existing tracked file: 28,421,936 bytes (27.1 MiB), below GitHub's [100 MiB file limit](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). Final repository remains comfortably below that individual-file limit; size is not the blocking issue.

The pre-implementation history scan covered 1,855 blobs with no matches to the checked credential/private-key patterns. Current README/docs contain no unnecessary local absolute paths. History was preserved; no cosmetic history rewrite. Environment files, caches, OS metadata and local DuckDB binaries are ignored; intentional analytical CSVs remain tracked. No raw data was deleted or automatically moved to LFS.

## Commit identification

This report is included in the commit titled **Implement final PLL advanced statistics layer** on `main`. Obtain the exact self-containing commit hash with `git log -1 --format=%H --grep='^Implement final PLL advanced statistics layer$'`. The conversation completion report records the actual hash after successful commit and clean-tree verification; no circular self-hash is embedded here.
