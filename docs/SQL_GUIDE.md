# Final SQL guide

The final definitions live in `sql/publication.sql`. `scripts/pll_build_publication.py` loads the frozen canonical inputs with explicit string player IDs and season keys, then executes that SQL. Python performs no metric arithmetic in the builder.

```sh
python3 -B scripts/pll_build_publication.py --database /tmp/pll-publication.duckdb
python3 -B scripts/pll_query_publication.py
```

`sql/publication_examples.sql` contains 16 independently runnable statements against the resulting database. With a DuckDB CLI installed, run `duckdb /tmp/pll-publication.duckdb < sql/publication_examples.sql`.

Primary views: `team_advanced_stats`, `player_offensive_advanced`, `player_shooting_advanced`, `player_two_point_stats`, `faceoff_advanced`, `goalie_advanced`, `defensive_production`, `player_season_summary`, `possession_length_analysis`.

Supporting exports: `season_baselines`, `team_game_publication`, `publication_coverage`, `possession_sensitivity`.

Team key: `(season,team_id)`. Player key: `(season,player_id,aggregation_level,team_id)`. `SEASON` has team_id `ALL`; `STINT` retains actual team. Never join on a name or sum both aggregation levels. Player IDs remain strings with leading zeros. Display names may change without changing the identity key; positions record observed position codes.

Team-game outputs enable known scoring-gap exclusions and explicit game selection. For alternative game populations, recompute numerators and baselines from the filtered canonical views; do not subtract games from a season percentage.

Each CSV is ordered by all columns. Example rankings use stable IDs as tie-breakers and exclude undefined metric values. No arbitrary reliability qualification is implied by positive-exposure filters. CSV empty cells represent SQL NULL, not zero.

Historical SQL remains preserved outside this final layer. Do not combine archived player-value tables with publication views.
