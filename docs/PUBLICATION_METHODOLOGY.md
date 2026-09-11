# Publication methodology and reproduction

Source statistics: [Premier Lacrosse League](https://premierlacrosseleague.com/). This is an independent research project, not an official PLL product.

## Data flow

Frozen raw payloads → existing ingestion/cleaning → canonical v2 → possession reconstruction → `sql/publication.sql` → final CSVs and DuckDB views. The new builder reads the canonical checkpoint and does not invoke archived value models or change raw/canonical data.

Install dependencies from `requirements.txt`. Build with `python3 -B scripts/pll_build_publication.py`. For a queryable local database use `--database /tmp/pll-publication.duckdb`. The database materializes canonical input tables so it has no personal absolute path dependency; views calculate metrics in SQL. Rebuild the database after changes to canonical input.

Default CSV location: `data/publication/`. Each table has pooled and five season-specific exports. `player_season_summary` includes all final player fields; role tables are narrower projections. `aggregation_level=SEASON` combines actual stints; `STINT` preserves actual teams. Use exactly one level in a query. No primary-team denominator is used.

Run `python3 -B scripts/pll_validate_publication.py` for read-only checks, or add `--write-report` to update the stored report. Run `python3 -B -m pytest -q -p no:cacheprovider` for the complete suite. Existing historical tests regenerate their own research artifacts; those are not final product dependencies.

Run `python3 -B scripts/pll_check_publication_determinism.py` to build into two distinct temporary output directories and compare every exported CSV byte against each other and the publication checkpoint. Do not compare binary DuckDB files for determinism.

## Publication contract

Read the metric dictionary and final catalog for exact numerator, denominator and source rules. Ratios are not averages of player or team percentages. League comparisons pool original counts. Same-season league baselines are retrospective, include the focal player, and do not estimate persistent skill.

Duration values measure spans in the observed, measurable subset. Coverage must accompany pace and TOP. The two new shot-producing frequencies use all reconstructed possessions; `possession_sensitivity` provides ambiguous/unambiguous comparisons rather than hiding low-confidence records.

The possession-length table uses the seven existing duration buckets, not inferred tactics. Its share denominator is measurable possessions. Turnovers here mean possessions ending with `end_reason=turnover`, unlike official team turnovers in the core team rate. Do not equate these sources.

## Coverage and display

2022–2026 include completed competitive regular-season and playoff games in each frozen extract. The latest included 2026 game starts 2026-08-30 00:30 UTC; this is not a completed season or an asserted final-whistle time. See `publication_coverage` for game counts and snapshot labels.

The known 2022 Archers–Cannons seven-point feed gap remains unrepaired. Four 2022 shots and one 2024 shot lack a player ID; they remain in team totals and league baselines. Historical faceoff/feed anomalies remain documented in the canonical research. Never force official and event sources to agree by imputing missing events.

NULL means undefined or unavailable; zero is an observed count/result. Missing official measures make their aggregate NULL. No fake goalie value at zero opportunities. Unresolved goalie SOG does not count as a save or goal; resolved coverage is displayed. No minimum exposure is a scientific qualification: example filters are transparently illustrative, and default outputs preserve all rows with exposure.

Rate leaders should always show denominator and games. Do not compare partial-2026 raw totals to completed seasons without labeling. Lower offensive pace means shorter observed spans; defensive pace is contextual, not defensive skill. Defensive production lacks minutes, shifts, lineups, matchups and on/off attribution.

No dashboard is included. No universal player score, bootstrap rankings, pairwise probabilities, shrinkage or faceoff point conversion enters publication tables.
