# Proposed final metric catalog

29 core metrics; box-score context is additional and is not marketed as advanced analytics. Metrics are proposed here, not a claim that the final SQL layer is implemented.

All ratios are stored as proportions; display percentages multiply by 100. All zero denominators return NULL. Opportunity-based surplus metrics also return NULL at zero exposure and are excluded from corresponding leaderboards. No universal score and no offensive composite are proposed. ORIGINAL_PLL_METRIC means a PLL-specific adaptation in this project, not a claim of first invention.

## Shared definitions

Scope: completed regular-season and playoff games in each frozen season; all-star/exhibition games excluded. 2026 is a partial snapshot through the last included completed game, not a full season. League rates use the same season and eligibility scope; they include the focal player. These are retrospective descriptive baselines, never forward prediction. Default historical comparisons must disclose postseason inclusion.

GP = appearances (players) or eligible games (teams); P/P_def = reconstructed offensive/defensive possessions; Q = possession PLL scoring points; A1/A2 = eligible one-/two-point attempts; G1/G2 = valid goals in those classes; A=A1+A2; SOG includes goal, saved and on_goal_no_save. C = eligible shotclockexpired event count. M = unambiguous, nontruncated possession with distinct start/end event IDs.

T/U = recorded player touches/turnovers; u_s = sum(U)/sum(T) across all eligible player-game records with positive T in season s. Report excluded zero/missing-T turnover records separately; never silently assign them an exposure. No position-specific baseline. W/F = recorded wins/attempts; f_s = sum(W)/sum(F) over all league takers with F>0. Actual baseline is preferred over 50% because feed attempts and assigned wins can differ; expose the league baseline as context, not a second near-identical leaderboard.

SV/GA = box-score saves/goals allowed, with each goal counted once regardless of PLL point value. s_s = sum(SV)/sum(SV+GA) over goalies with resolved shots. Event class SV1/GA1 and SV2/GA2 require an attributed goalie and a resolved saved/goal outcome; unresolved on-goal events are excluded and counted explicitly. Class coverage versus box totals must accompany these optional class-rate columns.

p1_s=sum(G1)/sum(A1); p2_s=sum(G2)/sum(A2), using all eligible league shot events in season s. Publish baseline attempts and goals. Rates are weighted by attempts, never averages of player percentages. CT/GB/PEN = official caused turnovers/ground balls/penalty counts.

Transferred players: sum numerator and denominator by actual (season, game, team, player). Season totals combine stints; team displays retain stints. Team workload shares use only player appearances and the actual team in each appearance; they are not season availability shares.

Historical exception: the known 2022 Archers–Cannons scoring gap is flagged, not imputed. Team Q uses reconstructed scoring; official scoreboard totals are separate context. Show reconciliation status and offer exclusion of the affected game for comparisons.

## TEAM

| Metric | Formula | Units | Classification |
|---|---|---|---|
| possessions_per_game | `P / GP` | possessions/game | DERIVED_ADVANCED |
| offensive_efficiency | `100 * Q / P` | PLL points/100 possessions | DERIVED_ADVANCED |
| defensive_efficiency | `100 * Q_allowed / P_def` | PLL points/100 possessions | DERIVED_ADVANCED |
| net_efficiency | `offensive_efficiency - defensive_efficiency` | PLL points/100 possessions | DERIVED_ADVANCED |
| shots_per_possession | `A / P` | attempts/possession | DERIVED_ADVANCED |
| turnovers_per_possession | `U_team / P` | turnovers/possession | DERIVED_ADVANCED |
| shot_clock_expirations_per_possession | `C / P` | expirations/possession | DERIVED_ADVANCED |
| mean_possession_span | `mean(duration_seconds where M)` | seconds | DERIVED_ADVANCED |
| median_possession_span | `median(duration_seconds where M)` | seconds | DERIVED_ADVANCED |

- **possessions_per_game**: Reconstructed team pace; regulation and overtime combined. Source: possessions + games.
- **offensive_efficiency**: Points produced on reconstructed offensive possessions. Source: possessions.
- **defensive_efficiency**: Points allowed on reconstructed defensive possessions. Source: possessions.
- **net_efficiency**: Difference between team scoring and conceding rates. Source: possessions.
- **shots_per_possession**: Shot generation per reconstructed possession. Source: eligible events + possessions.
- **turnovers_per_possession**: Official team turnovers per reconstructed possession, including team-only turnovers. Source: team_game_stats + possessions.
- **shot_clock_expirations_per_possession**: Frequency of logged shot-clock expiration events. Source: eligible events + possessions.
- **mean_possession_span**: Average observed span, restricted to measurable boundaries; not full possession duration. Source: possessions.
- **median_possession_span**: Median observed span over the same subset; less sensitive to long spans. Source: possessions.

## OFFENSE

| Metric | Formula | Units | Classification |
|---|---|---|---|
| shooting_pct | `(G1 + G2) / (A1 + A2)` | proportion | STANDARD |
| shots_on_goal_pct | `SOG / A` | proportion | DERIVED_ADVANCED |
| scoring_points_per_shot | `(G1 + 2*G2) / (A1 + A2)` | PLL scoring points/attempt | DERIVED_ADVANCED |
| turnovers_per_touch | `U / T` | turnovers/touch proxy | DERIVED_ADVANCED |
| turnovers_below_expected | `T * u_s - U` | turnover events | DERIVED_ADVANCED |
| shooting_value_above_expected | `G1 + 2*G2 - A1*p1_s - 2*A2*p2_s` | PLL scoring points | ORIGINAL_PLL_METRIC |

- **shooting_pct**: Conversion of all logged attempts into goals, independent of point value. Source: eligible shot events.
- **shots_on_goal_pct**: Share of logged attempts classified as on goal; retain unresolved on-goal class count. Source: eligible shot events.
- **scoring_points_per_shot**: Scoring return on shots. Assists excluded; traditional player points are a separate context field. Source: eligible shot events.
- **turnovers_per_touch**: Recorded ball security per feed touch count; not passing value. Source: player_game_stats.
- **turnovers_below_expected**: Recorded turnovers avoided relative to a season league touch baseline; positive means fewer turnovers. Source: player_game_stats.
- **shooting_value_above_expected**: Scoring above season-average conversion on the same 1PT/2PT shot mix; no total-offense claim. Source: eligible shot events.

## PLL_2PT

| Metric | Formula | Units | Classification |
|---|---|---|---|
| two_point_attempt_rate | `A2 / (A1 + A2)` | proportion | DERIVED_ADVANCED |
| two_point_conversion_pct | `G2 / A2` | proportion | STANDARD |
| two_point_shooting_value | `2 * (G2 - A2*p2_s)` | PLL scoring points | ORIGINAL_PLL_METRIC |
| team_two_point_attempt_share | `sum_g A2_player_g / sum_g A2_team_g` | proportion | DERIVED_ADVANCED |

- **two_point_attempt_rate**: Shot selection: frequency of choosing the two-point shot. Source: eligible shot events.
- **two_point_conversion_pct**: Observed two-point conversion; not persistent shooting ability. Source: eligible shot events.
- **two_point_shooting_value**: The two-point component of shooting value; never add it again to total shooting value. Source: eligible shot events.
- **team_two_point_attempt_share**: Share of team two-point attempts in the games the player appeared, respecting actual team in each game. Source: eligible events + player-game participation.

## FACEOFF

| Metric | Formula | Units | Classification |
|---|---|---|---|
| faceoff_pct | `W / F` | proportion | STANDARD |
| draw_share | `sum_g F_player_g / sum_g F_team_g` | proportion | DERIVED_ADVANCED |
| faceoff_wins_above_average | `W - F*f_s` | faceoff wins | DERIVED_ADVANCED |

- **faceoff_pct**: Observed faceoff success with attempts and unassigned outcomes visible. Source: player_game_stats.
- **draw_share**: Draw workload in appearances, following actual game team for transfers. Source: player_game_stats + team_game_stats.
- **faceoff_wins_above_average**: Additional wins relative to all recorded league faceoff takers in that season; no point conversion. Source: player_game_stats.

## GOALIE

| Metric | Formula | Units | Classification |
|---|---|---|---|
| save_pct | `SV / (SV + GA)` | proportion | STANDARD |
| one_point_save_pct | `SV1 / (SV1 + GA1)` | proportion | DERIVED_ADVANCED |
| two_point_save_pct | `SV2 / (SV2 + GA2)` | proportion | DERIVED_ADVANCED |
| saves_above_average | `SV - (SV + GA)*s_s` | saves | DERIVED_ADVANCED |

- **save_pct**: Observed saves among resolved saves and goals allowed; shots-faced denominator is explicitly resolved shots. Source: player_game_stats.
- **one_point_save_pct**: Observed one-point stopping among resolved attributable events; show attribution coverage. Source: eligible saved/goal events with goalie_id.
- **two_point_save_pct**: Observed two-point stopping among resolved attributable events; show coverage and small denominator. Source: eligible saved/goal events with goalie_id.
- **saves_above_average**: Saves above season league stopping results at the same resolved workload; not shot-quality adjusted. Source: player_game_stats.

## DEFENSE

| Metric | Formula | Units | Classification |
|---|---|---|---|
| caused_turnovers_per_game | `CT / GP` | events/game | DERIVED_ADVANCED |
| ground_balls_per_game | `GB / GP` | events/game | DERIVED_ADVANCED |
| penalties_per_game | `PEN / GP` | penalties/game | DERIVED_ADVANCED |

- **caused_turnovers_per_game**: Recorded disruption, without individual defensive exposure adjustment. Source: player_game_stats.
- **ground_balls_per_game**: Recorded recoveries, including faceoff-related recoveries; no impact composite. Source: player_game_stats.
- **penalties_per_game**: Penalty frequency per appearance, not per defensive possession or minute. Source: player_game_stats.

## Context and filtering

Context fields (STANDARD): games played, goals, 1PT/2PT goals, assists, traditional player points, attempts, shots on goal, touches, turnovers, faceoff attempts/wins/losses, saves, goals allowed, caused turnovers, ground balls and penalties. Keep PLL scoring points (=G1+2G2) distinct from traditional player points (=G1+2G2+assists). Two-point scoring points (=2G2) are context.

No empirical-Bayes QUALIFIED label in the final product. Always show opportunities and let queries choose a stated minimum (for example 20 attempts). Such thresholds are usability filters, not reliability claims. A zero-opportunity player remains in the roster summary but has NULL rates and no corresponding rate rank. No estimated true two-point talent, rank probability, or predictive interval is published.
