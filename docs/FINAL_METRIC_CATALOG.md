# Final core metric catalog

35 core metrics. Definitions are implemented in [publication SQL](../sql/publication.sql).
The [machine-readable dictionary](../data/publication/metric_dictionary.csv) records formulas, units, source populations, coverage and NULL policies.
The earlier 29-row file under `data/processed/history/` is the preserved refocus proposal, not the active catalog.

All ratios are proportions; multiply by 100 only for percentage displays. Efficiency is already per 100 possessions.
Player outputs contain `aggregation_level=SEASON` (team_id=ALL) and `STINT` (actual team). Never sum both levels together.
The season key is always part of the identity. Counts and denominators are provided, not inferred reliability qualifications.

| Category | Metric | Formula | Unit |
|---|---|---|---|
| TEAM | `possessions_per_game` | `(possessions) / (games_played)` | possessions/game |
| TEAM | `offensive_efficiency` | `(100 * points) / (possessions)` | PLL points/100 possessions |
| TEAM | `defensive_efficiency` | `(100 * points_allowed) / (defensive_possessions)` | PLL points/100 possessions |
| TEAM | `net_efficiency` | `offensive_efficiency - defensive_efficiency` | PLL points/100 possessions |
| TEAM | `shots_per_possession` | `(shots) / (possessions)` | attempts/possession |
| TEAM | `turnovers_per_possession` | `(official_turnovers) / (possessions)` | turnovers/possession |
| TEAM | `shot_clock_expirations_per_possession` | `(shot_clock_events) / (possessions)` | expirations/possession |
| TEAM | `offensive_pace_seconds` | `(measurable_possession_seconds) / (measurable_possessions)` | seconds |
| TEAM | `median_possession_span` | `median duration_seconds over measurable possessions` | seconds |
| OFFENSE | `shooting_pct` | `(g1 + g2) / (shots)` | proportion |
| OFFENSE | `shots_on_goal_pct` | `(sog) / (shots)` | proportion |
| OFFENSE | `scoring_points_per_shot` | `(g1 + 2*g2) / (shots)` | PLL scoring points/attempt |
| OFFENSE | `turnovers_per_touch` | `(turnovers) / (touches)` | turnovers/touch proxy |
| OFFENSE | `turnovers_below_expected` | `touches * league_turnover_per_touch - turnovers` | turnover events |
| OFFENSE | `shooting_value_above_expected` | `g1 + 2*g2 - a1*p1 - 2*a2*p2` | PLL scoring points |
| PLL_2PT | `two_point_attempt_rate` | `(a2) / (shots)` | proportion |
| PLL_2PT | `two_point_conversion_pct` | `(g2) / (a2)` | proportion |
| PLL_2PT | `two_point_shooting_value` | `2 * (g2 - a2*p2)` | PLL scoring points |
| PLL_2PT | `team_two_point_attempt_share` | `(a2) / (team_a2_in_appearances)` | proportion |
| FACEOFF | `faceoff_pct` | `(faceoff_wins) / (faceoffs)` | proportion |
| FACEOFF | `draw_share` | `(faceoffs) / (team_faceoffs_in_appearances)` | proportion |
| FACEOFF | `faceoff_wins_above_average` | `faceoff_wins - faceoffs*league_faceoff_rate` | faceoff wins |
| GOALIE | `save_pct` | `(resolved_saves) / (resolved_shots_faced)` | proportion |
| GOALIE | `one_point_save_pct` | `(sv1) / (sv1 + ga1)` | proportion |
| GOALIE | `two_point_save_pct` | `(sv2) / (sv2 + ga2)` | proportion |
| GOALIE | `saves_above_average` | `resolved_saves - resolved_shots_faced*league_save_rate` | saves |
| DEFENSE | `caused_turnovers_per_game` | `(caused_turnovers) / (games_played)` | events/game |
| DEFENSE | `ground_balls_per_game` | `(ground_balls) / (games_played)` | events/game |
| DEFENSE | `penalties_per_game` | `(penalties) / (games_played)` | penalties/game |
| TEAM | `shot_producing_possession_rate` | `(shot_producing_possessions) / (possessions)` | proportion |
| TEAM | `multi_shot_possession_rate` | `(multi_shot_possessions) / (possessions)` | proportion |
| TEAM | `team_assist_to_goal_ratio` | `(official_assists) / (official_goals)` | proportion |
| TEAM | `time_of_possession_share` | `(measurable_possession_seconds) / (team plus opponent measurable seconds in eligible team games)` | proportion |
| TEAM | `defensive_pace_seconds` | `(defensive_measurable_seconds) / (defensive_measurable_possessions)` | seconds |
| USAGE | `shot_share` | `(shots) / (team_shots_in_appearances)` | proportion |

## Source contracts

- Completed competitive games, including playoffs, are the default. 2026 is a frozen partial snapshot; latest included game starts 2026-08-30 00:30 UTC.
- Team efficiency uses reconstructed PLL scoring, not silently substituted official scores. `score_residual`, `score_gap_games`, and the game table expose disagreement.
- Team turnovers use official team totals, including team-only turnovers. Shot-clock expirations use eligible events.
- Shooting uses eligible events. SOG includes `goal`, `saved`, and `on_goal_no_save`. Five historical shots have no player ID and remain in team and league denominators; see coverage output.
- Player touches and turnovers use official box counts. The league touch rate pools rows with positive touches and nonmissing turnovers; excluded records/counts are exposed. Surplus is turnover events, not points.
- Shooting baselines pool all same-season eligible attempts by class, including unattributed attempts. No future seasons. No position adjustment. Two-point value is part of total shooting value, never an additional component to add again.
- Faceoff rates pool all eligible takers with positive attempts and observed wins. Draw shares use official team attempts in actual appearances.
- All goalie rates and saves above average use resolved event saves/goals. This replaces the proposal's mixed box-score/event goalie sources. Unresolved on-goal events remain visible but excluded from resolved denominators. The optional two-point mix uses all event SOG, including unresolved outcomes.
- Official assist-to-goal ratio does not use pre-shot pass IDs. A two-point goal counts once.
- Duration uses unambiguous, nontruncated possessions with distinct boundary event IDs. Zero observed spans can qualify; single-event pseudo-spans cannot. Mean and median use the same population. TOP uses only measured seconds on both sides in actual eligible games.
- Official missing counts propagate NULL, never zero. Zero event counts mean no qualifying event in the eligible feed, not assurance of source completeness. Zero denominator and zero-exposure surplus return NULL.

## Context and analysis-only fields

CONTEXT: raw counts and exposures, coverage, same-season baselines, scoring reconciliation, team two-point attempt rate/scoring share/return, goalie two-point mix faced, positions and actual-team stints.

ANALYSIS_ONLY: possession-length splits, ambiguity sensitivity, league historical comparisons, diagnostic possession-count margins. Split columns are not additional core metrics.

## Decisions

- `mean_possession_span` and offensive pace are identical: publish only `offensive_pace_seconds`. The old name is a documentation alias, not a duplicate output column.
- `possession_margin_per_game` is not mechanically zero. Absolute game count differences range 0–17; season mean absolute differences range 3.98–6.74. Removing ambiguous possessions changes margins by 1.28–1.76 possessions/game on average. These differences mix reconstruction boundaries and control allocation; do not market them as extra possessions won. Retain count differences only as diagnostic analysis, not a core metric or performance ranking.
- Reject broad `offensive_play_share`: earlier log appearances include goalie/ground-ball/secondary roles and can count multiple roles from one event. Shots-plus-turnovers is a narrower existing opportunity proxy, not all offensive plays; adding assists conflates passer and shooter participation. Publish shot share and touches/turnovers instead.
- Reject fast-break labels inferred from clock time, individual assisted-goal percentages without linkage, redundant conditional efficiency ratios, and all MVP/WAR/value composites.

See [publication methodology](PUBLICATION_METHODOLOGY.md) for reproducibility and display rules.
