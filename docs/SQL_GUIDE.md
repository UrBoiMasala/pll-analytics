# SQL guide and proposed final schema

The retained team SQL layer is implemented in `sql/00_base_views.sql` and the team queries. The final publication views below are a design contract for the next phase; they do not yet exist. No query should silently read archived Phase 13 value leaderboards.

## Keys and grain

| Proposed view | Unique key | Content |
|---|---|---|
| team_advanced_stats | season, team_id, season_scope | 9 team metrics plus box-score context and coverage |
| player_offensive_advanced | season, player_id, season_scope | ball security and offensive context |
| player_shooting_advanced | season, player_id, season_scope | shooting rates and class-average residual |
| player_two_point_stats | season, player_id, season_scope | 4 two-point metrics and denominators |
| faceoff_advanced | season, player_id, season_scope | draws, workload, wins above average |
| goalie_advanced | season, player_id, season_scope | resolved shots, saves, class coverage and stopping |
| defensive_production | season, player_id, season_scope | attributable counts and per-game rates |
| player_season_summary | season, player_id, season_scope | roster context and one-to-one joined role statistics |

Supporting relations: games keyed `(season, game_id)`; player_game keyed `(season, game_id, player_id)` with actual team; player_team_stints keyed `(season, player_id, team_id)`; league_baselines keyed `(season, season_scope, baseline_name, shot_class)`; final_metric_definitions keyed metric_name. `season_scope` is an explicit enum such as ALL_COMPETITIVE, REGULAR_SEASON or PLAYOFFS; recompute baselines in the same scope.

Use VARCHAR for every identifier. Validate uniqueness before joins; never join on names. Derive season rates from summed counts, not averages of game rates. Divide by NULLIF(denominator,0). No-exposure values and ranks stay NULL. Use ORDER BY metric DESC NULLS LAST, player_id ASC (or team_id ASC) for deterministic display; any rank column uses that explicit order. Seasonal rows may have multiple team stints; do not join unaggregated stints to a season table and then sum duplicated values.

## Example target queries (for the next phase)

```sql
SELECT player_id, shooting_value_above_expected, attempts
FROM player_shooting_advanced
WHERE season=2026 AND season_scope='ALL_COMPETITIVE' AND attempts>=20
ORDER BY shooting_value_above_expected DESC NULLS LAST, player_id LIMIT 10;

SELECT player_id, two_point_attempt_rate, two_point_attempts
FROM player_two_point_stats
WHERE season=2026 AND season_scope='ALL_COMPETITIVE' AND attempts>=20
ORDER BY two_point_attempt_rate DESC NULLS LAST, player_id;

SELECT team_id, offensive_efficiency, possessions_per_game
FROM team_advanced_stats WHERE season=2026 AND season_scope='ALL_COMPETITIVE'
ORDER BY offensive_efficiency DESC NULLS LAST, team_id;

SELECT player_id, faceoff_wins_above_average, faceoffs
FROM faceoff_advanced WHERE season=2026 AND season_scope='ALL_COMPETITIVE'
ORDER BY faceoff_wins_above_average DESC NULLS LAST, player_id;

SELECT player_id, saves_above_average, resolved_shots_faced
FROM goalie_advanced WHERE season=2026 AND season_scope='ALL_COMPETITIVE'
ORDER BY saves_above_average DESC NULLS LAST, player_id;

SELECT season, SUM(two_point_attempts)*1.0/NULLIF(SUM(attempts),0) AS league_2pt_rate
FROM player_two_point_stats WHERE season_scope='ALL_COMPETITIVE'
GROUP BY season ORDER BY season;

SELECT team_id, possessions_per_game FROM team_advanced_stats
WHERE season=2026 AND season_scope='ALL_COMPETITIVE'
ORDER BY possessions_per_game DESC NULLS LAST, team_id;

SELECT player_id, turnovers_per_touch, touches
FROM player_offensive_advanced
WHERE season=2026 AND season_scope='ALL_COMPETITIVE' AND touches>=100
ORDER BY turnovers_per_touch ASC NULLS LAST, player_id;
```

The 20-attempt and 100-touch filters illustrate transparent usage choices, not established reliability thresholds. League two-point trends must also reconcile unattributed player events to league event totals; if coverage is incomplete, query the canonical league shot relation instead of summing player rows.
