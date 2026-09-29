# Querying the statistics

## Create a local database

After installing the analytics dependencies:

```sh
python -B scripts/pll_build_publication.py --database /tmp/pll-publication.duckdb --output /tmp/pll-publication-check
```

The database stores its inputs and SQL views. Rebuild it if canonical inputs change.
The separate output directory avoids replacing the included CSV checkpoint.

## Team efficiency

```sql
SELECT team_id, games_played, possessions, offensive_efficiency
FROM team_advanced_stats
WHERE season = 2026
ORDER BY offensive_efficiency DESC NULLS LAST, team_id;
```

Efficiency is PLL points per 100 reconstructed possessions. The 2026 population is
partial; display that label with results.

## Player shooting

```sql
SELECT player_name, player_id, shots, scoring_points_per_shot
FROM player_season_summary
WHERE season = 2026
  AND aggregation_level = 'SEASON'
  AND shots > 0
ORDER BY scoring_points_per_shot DESC NULLS LAST, player_id;
```

The positive-shot filter prevents undefined rates. It is not a qualification rule:
a one-shot player can lead this table. Always display exposure.

## Tables and keys

| Table group | Outputs |
| --- | --- |
| Team | `team_advanced_stats`, `team_game_publication` |
| Player | `player_season_summary`, `player_offensive_advanced`, `player_shooting_advanced`, `player_two_point_stats` |
| Roles | `faceoff_advanced`, `goalie_advanced`, `defensive_production` |
| Context | `season_baselines`, `publication_coverage`, `possession_sensitivity`, `possession_length_analysis` |

- Team key: `(season, team_id)`.
- Player key: `(season, player_id, aggregation_level, team_id)`.
- `SEASON` rows have `team_id = 'ALL'`; `STINT` rows preserve actual teams.
- Never add both aggregation levels or join players by display name.
- Empty CSV cells are SQL `NULL`, not zero. Preserve string IDs.

The [example queries](../sql/publication_examples.sql) contain 16 analyses. With the
DuckDB CLI installed, run `duckdb /tmp/pll-publication.duckdb < sql/publication_examples.sql`.
The repository also includes `python -B scripts/pll_query_publication.py`.

For alternative game populations, recompute numerators and baselines from filtered
canonical inputs. Do not subtract excluded games from an already-computed percentage.
See the [metric catalog](FINAL_METRIC_CATALOG.md) for exact source contracts.
