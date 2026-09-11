-- Run after building the final database. No arbitrary qualification thresholds.
-- Rate tables show exposures; 2026 is partial. All player queries select SEASON only.

-- Team offense
SELECT team_id,offensive_efficiency,possessions FROM team_advanced_stats WHERE season=2026 ORDER BY offensive_efficiency DESC NULLS LAST,team_id;

-- Shot-producing frequency
SELECT team_id,shot_producing_possession_rate,possessionS,ambiguous_possessions FROM team_advanced_stats WHERE season=2026 ORDER BY shot_producing_possession_rate DESC NULLS LAST,team_id;

-- Multiple attempts
SELECT team_id,multi_shot_possessions,multi_shot_possession_rate FROM team_advanced_stats WHERE season=2026 ORDER BY multi_shot_possession_rate DESC NULLS LAST,team_id;

-- Offensive pace
SELECT team_id,offensive_pace_seconds,measurable_possession_coverage FROM team_advanced_stats WHERE season=2026 ORDER BY offensive_pace_seconds NULLS LAST,team_id;

-- Opponent observed spans (not forced duration or defensive skill)
SELECT team_id,defensive_pace_seconds,defensive_measurable_coverage FROM team_advanced_stats WHERE season=2026 ORDER BY defensive_pace_seconds DESC NULLS LAST,team_id;

-- PLL points per shot
SELECT player_id,player_name,scoring_points_per_shot,shots,games_played FROM player_shooting_advanced WHERE season=2026 AND aggregation_level='SEASON' AND shots>0 AND scoring_points_per_shot IS NOT NULL ORDER BY scoring_points_per_shot DESC,player_id;

-- Shooting surplus
SELECT player_id,player_name,shooting_value_above_expected,shots,games_played FROM player_shooting_advanced WHERE season=2026 AND aggregation_level='SEASON' AND shots>0 AND shooting_value_above_expected IS NOT NULL ORDER BY shooting_value_above_expected DESC,player_id;

-- Shot share
SELECT player_id,player_name,shot_share,team_shots_in_appearances,games_played FROM player_offensive_advanced WHERE season=2026 AND aggregation_level='SEASON' AND team_shots_in_appearances>0 AND shot_share IS NOT NULL ORDER BY shot_share DESC,player_id;

-- Team two-point share
SELECT player_id,player_name,team_two_point_attempt_share,team_a2_in_appearances,games_played FROM player_two_point_stats WHERE season=2026 AND aggregation_level='SEASON' AND team_a2_in_appearances>0 AND team_two_point_attempt_share IS NOT NULL ORDER BY team_two_point_attempt_share DESC,player_id;

-- Two-point selection
SELECT player_id,player_name,two_point_attempt_rate,shots,games_played FROM player_two_point_stats WHERE season=2026 AND aggregation_level='SEASON' AND shots>0 AND two_point_attempt_rate IS NOT NULL ORDER BY two_point_attempt_rate DESC,player_id;

-- Faceoff wins above average
SELECT player_id,player_name,faceoff_wins_above_average,faceoffs,games_played FROM faceoff_advanced WHERE season=2026 AND aggregation_level='SEASON' AND faceoffs>0 AND faceoff_wins_above_average IS NOT NULL ORDER BY faceoff_wins_above_average DESC,player_id;

-- Saves above average
SELECT player_id,player_name,saves_above_average,resolved_shots_faced,games_played FROM goalie_advanced WHERE season=2026 AND aggregation_level='SEASON' AND resolved_shots_faced>0 AND saves_above_average IS NOT NULL ORDER BY saves_above_average DESC,player_id;

-- Assist structure
SELECT team_id,team_assist_to_goal_ratio,official_assists,official_goals FROM team_advanced_stats WHERE season=2026 ORDER BY team_assist_to_goal_ratio DESC NULLS LAST,team_id;

-- League two-point environment
SELECT season,sum(two_point_attempts)/nullif(sum(shots),0) two_point_attempt_rate FROM team_advanced_stats GROUP BY season ORDER BY season;

-- League offensive environment
SELECT season,100.0*sum(points)/nullif(sum(possessions),0) offensive_efficiency FROM team_advanced_stats GROUP BY season ORDER BY season;

-- League efficiency by measured span
SELECT season,bucket_order,bucket,sum(possessions) possessions,100.0*sum(points)/nullif(sum(possessions),0) offensive_efficiency FROM possession_length_analysis GROUP BY ALL ORDER BY season,bucket_order;
