-- Final publication calculations. Builder registers raw tables with season keys.
CREATE OR REPLACE VIEW pub_games AS SELECT * FROM raw_games WHERE is_completed AND include_in_league_analytics AND NOT is_all_star;
CREATE OR REPLACE VIEW pub_participants AS
 SELECT season,game_id,home_team_id team_id,away_team_id opponent_team_id,home_score official_points FROM pub_games
 UNION ALL SELECT season,game_id,away_team_id,home_team_id,away_score FROM pub_games;
CREATE OR REPLACE VIEW pub_events AS SELECT e.* FROM raw_events e JOIN pub_games g USING(season,game_id) WHERE e.is_analysis_eligible_event;
CREATE OR REPLACE VIEW pub_shots AS SELECT *, shot_outcome IN ('goal','saved','on_goal_no_save') sog,
 CASE WHEN is_valid_goal THEN CASE WHEN is_two_point_attempt THEN 2 ELSE 1 END ELSE 0 END pll_points
 FROM pub_events WHERE event_type IN ('shot','goal') AND shot_outcome IS NOT NULL;
CREATE OR REPLACE VIEW pub_possessions AS SELECT p.*,
 NOT is_ambiguous AND NOT is_truncated AND start_event_id<>end_event_id measurable
 FROM raw_possessions p JOIN pub_games g USING(season,game_id);
CREATE OR REPLACE VIEW pub_player_games AS SELECT p.* FROM raw_players p JOIN pub_games g USING(season,game_id)
 JOIN pub_participants t ON t.season=p.season AND t.game_id=p.game_id AND t.team_id=p.teamId;
CREATE OR REPLACE VIEW pub_team_games AS SELECT t.* FROM raw_teams t JOIN pub_participants g ON t.season=g.season AND t.game_id=g.game_id AND t.officialId=g.team_id;
CREATE OR REPLACE VIEW pub_team_shots AS SELECT season,game_id,team_id,count(*) shots,
 count(*) FILTER(WHERE is_two_point_attempt) a2, sum(pll_points) shooting_points,
 count(*) FILTER(WHERE is_two_point_attempt AND is_valid_goal) g2 FROM pub_shots GROUP BY ALL;
CREATE OR REPLACE VIEW pub_possession_game AS SELECT season,game_id,offense_team_id team_id,count(*) possessions,
 sum(points_scored) points,sum(shot_attempts) possession_shots,
 count(*) FILTER(WHERE shot_attempts>=1) shot_producing_possessions,
 count(*) FILTER(WHERE shot_attempts>=2) multi_shot_possessions,
 count(*) FILTER(WHERE is_ambiguous) ambiguous_possessions,
 count(*) FILTER(WHERE measurable) measurable_possessions,
 sum(duration_seconds) FILTER(WHERE measurable) measurable_seconds
 FROM pub_possessions GROUP BY ALL;
CREATE OR REPLACE VIEW team_game_publication AS SELECT t.season,t.game_id,t.team_id,t.opponent_team_id,
 p.possessions,p.points,o.possessions defensive_possessions,o.points points_allowed,
 p.shot_producing_possessions,p.multi_shot_possessions,p.ambiguous_possessions,
 p.measurable_possessions,p.measurable_seconds,o.measurable_possessions defensive_measurable_possessions,
 o.measurable_seconds defensive_measurable_seconds,t.official_points,
 p.points-t.official_points score_residual,
 coalesce(s.shots,0) shots,coalesce(s.a2,0) a2,coalesce(s.g2,0) g2,coalesce(s.shooting_points,0) shooting_points,
 b.turnovers official_turnovers,b.assists official_assists,b.goals official_goals,
 (SELECT count(*) FROM pub_events e WHERE e.season=t.season AND e.game_id=t.game_id AND e.team_id=t.team_id AND e.event_type='shotclockexpired') shot_clock_events
 FROM pub_participants t LEFT JOIN pub_possession_game p USING(season,game_id,team_id)
 LEFT JOIN pub_possession_game o ON o.season=t.season AND o.game_id=t.game_id AND o.team_id=t.opponent_team_id
 LEFT JOIN pub_team_shots s USING(season,game_id,team_id)
 LEFT JOIN pub_team_games b ON b.season=t.season AND b.game_id=t.game_id AND b.officialId=t.team_id;
CREATE OR REPLACE VIEW team_advanced_stats AS WITH a AS (
 SELECT season,team_id,count(*) games_played,sum(possessions) possessions,sum(defensive_possessions) defensive_possessions,
 sum(points) points,sum(points_allowed) points_allowed,sum(shots) shots,sum(a2) two_point_attempts,sum(g2) two_point_goals,
 sum(shooting_points) shooting_points,sum(shot_producing_possessions) shot_producing_possessions,
 sum(multi_shot_possessions) multi_shot_possessions,sum(ambiguous_possessions) ambiguous_possessions,
 sum(measurable_possessions) measurable_possessions,sum(measurable_seconds) measurable_possession_seconds,
 sum(defensive_measurable_possessions) defensive_measurable_possessions,sum(defensive_measurable_seconds) defensive_measurable_seconds,
 CASE WHEN count(official_turnovers)=count(*) THEN sum(official_turnovers) END official_turnovers,
 CASE WHEN count(official_assists)=count(*) THEN sum(official_assists) END official_assists,
 CASE WHEN count(official_goals)=count(*) THEN sum(official_goals) END official_goals,
 sum(shot_clock_events) shot_clock_events,sum(official_points) official_points,sum(score_residual) score_residual,
 count(*) FILTER(WHERE score_residual<>0) score_gap_games
 FROM team_game_publication GROUP BY ALL)
 SELECT a.*,possessions/games_played possessions_per_game,
 100.0*points/nullif(possessions,0) offensive_efficiency,
 100.0*points_allowed/nullif(defensive_possessions,0) defensive_efficiency,
 offensive_efficiency-defensive_efficiency net_efficiency,
 shots/nullif(possessions,0) shots_per_possession,official_turnovers/nullif(possessions,0) turnovers_per_possession,
 shot_clock_events/nullif(possessions,0) shot_clock_expirations_per_possession,
 measurable_possession_seconds/nullif(measurable_possessions,0) offensive_pace_seconds,
 (SELECT median(duration_seconds) FROM pub_possessions p WHERE p.season=a.season AND p.offense_team_id=a.team_id AND measurable) median_possession_span,
 shot_producing_possessions/nullif(possessions,0) shot_producing_possession_rate,
 multi_shot_possessions/nullif(possessions,0) multi_shot_possession_rate,
 coalesce(measurable_possession_seconds,0)/nullif(coalesce(measurable_possession_seconds,0)+coalesce(defensive_measurable_seconds,0),0) time_of_possession_share,
 defensive_measurable_seconds/nullif(defensive_measurable_possessions,0) defensive_pace_seconds,
 measurable_possessions/nullif(possessions,0) measurable_possession_coverage,
 defensive_measurable_possessions/nullif(defensive_possessions,0) defensive_measurable_coverage,
 official_assists/nullif(official_goals,0) team_assist_to_goal_ratio,
 two_point_attempts/nullif(shots,0) team_two_point_attempt_rate,
 2.0*two_point_goals/nullif(shooting_points,0) team_two_point_scoring_points_share,
 2.0*two_point_goals/nullif(two_point_attempts,0) team_two_point_points_per_attempt
 FROM a;
-- Actual appearance/team joins precede aggregation; ALL is a season-total aggregation_level, never a primary team.
CREATE OR REPLACE VIEW pub_player_shots AS SELECT season,game_id,team_id,player_id,count(*) shots,
 count(*) FILTER(WHERE NOT is_two_point_attempt) a1,count(*) FILTER(WHERE is_two_point_attempt) a2,
 count(*) FILTER(WHERE NOT is_two_point_attempt AND is_valid_goal) g1,count(*) FILTER(WHERE is_two_point_attempt AND is_valid_goal) g2,
 count(*) FILTER(WHERE sog) sog,count(*) FILTER(WHERE shot_outcome='on_goal_no_save') unresolved_sog
 FROM pub_shots GROUP BY ALL;
CREATE OR REPLACE VIEW pub_goalie_games AS SELECT s.season,s.game_id,t.opponent_team_id team_id,s.goalie_id player_id,
 count(*) FILTER(WHERE shot_outcome='saved' AND NOT is_two_point_attempt) sv1,
 count(*) FILTER(WHERE shot_outcome='saved' AND is_two_point_attempt) sv2,
 count(*) FILTER(WHERE shot_outcome='goal' AND NOT is_two_point_attempt) ga1,
 count(*) FILTER(WHERE shot_outcome='goal' AND is_two_point_attempt) ga2,
 count(*) FILTER(WHERE shot_outcome='on_goal_no_save') unresolved_goalie_sog,
 count(*) FILTER(WHERE sog AND is_two_point_attempt) sog2_faced
 FROM pub_shots s JOIN pub_participants t USING(season,game_id,team_id) WHERE s.goalie_id IS NOT NULL GROUP BY ALL;
CREATE OR REPLACE VIEW pub_player_appearance AS SELECT p.season,p.game_id,p.officialId player_id,p.teamId team_id,
 concat_ws(' ',p.firstName,p.lastName) player_name,p.position,
 p.touches,p.turnovers,p.faceoffs,p.faceoffsWon faceoff_wins,p.causedTurnovers caused_turnovers,p.groundBalls ground_balls,p.numPenalties penalties,
 coalesce(s.shots,0) shots,coalesce(s.a1,0) a1,coalesce(s.a2,0) a2,coalesce(s.g1,0) g1,coalesce(s.g2,0) g2,
 coalesce(s.sog,0) sog,coalesce(s.unresolved_sog,0) unresolved_sog,
 coalesce(t.shots,0) team_shots_in_appearances,coalesce(t.a2,0) team_a2_in_appearances,
 b.faceoffs team_faceoffs_in_appearances,
 coalesce(f.sv1,0) sv1,coalesce(f.sv2,0) sv2,coalesce(f.ga1,0) ga1,coalesce(f.ga2,0) ga2,
 coalesce(f.unresolved_goalie_sog,0) unresolved_goalie_sog,coalesce(f.sog2_faced,0) sog2_faced
 FROM pub_player_games p LEFT JOIN pub_player_shots s ON p.season=s.season AND p.game_id=s.game_id AND p.teamId=s.team_id AND p.officialId=s.player_id
 LEFT JOIN pub_team_shots t ON p.season=t.season AND p.game_id=t.game_id AND p.teamId=t.team_id
 LEFT JOIN pub_team_games b ON p.season=b.season AND p.game_id=b.game_id AND p.teamId=b.officialId
 LEFT JOIN pub_goalie_games f ON p.season=f.season AND p.game_id=f.game_id AND p.teamId=f.team_id AND p.officialId=f.player_id;
CREATE OR REPLACE VIEW season_baselines AS WITH shooting AS (
 SELECT season,count(*) FILTER(WHERE NOT is_two_point_attempt) league_a1,count(*) FILTER(WHERE is_two_point_attempt) league_a2,
 count(*) FILTER(WHERE NOT is_two_point_attempt AND is_valid_goal) league_g1,count(*) FILTER(WHERE is_two_point_attempt AND is_valid_goal) league_g2,
 count(*) FILTER(WHERE shot_outcome='saved' AND goalie_id IS NOT NULL) league_saves,
 count(*) FILTER(WHERE shot_outcome IN ('saved','goal') AND goalie_id IS NOT NULL) league_resolved_sog
 FROM pub_shots GROUP BY season), player AS (
 SELECT season,sum(turnovers) FILTER(WHERE touches>0 AND turnovers IS NOT NULL) league_turnovers,
 sum(touches) FILTER(WHERE touches>0 AND turnovers IS NOT NULL) league_touches,
 count(*) FILTER(WHERE touches IS NULL OR touches<=0 OR turnovers IS NULL) excluded_touch_records,
 sum(turnovers) FILTER(WHERE touches IS NULL OR touches<=0) excluded_touch_turnovers,
 sum(faceoffsWon) FILTER(WHERE faceoffs>0 AND faceoffsWon IS NOT NULL) league_wins,
 sum(faceoffs) FILTER(WHERE faceoffs>0 AND faceoffsWon IS NOT NULL) league_faceoffs
 FROM pub_player_games GROUP BY season)
 SELECT *,league_g1/nullif(league_a1,0) p1,league_g2/nullif(league_a2,0) p2,
 league_saves/nullif(league_resolved_sog,0) league_save_rate,
 league_turnovers/nullif(league_touches,0) league_turnover_per_touch,
 league_wins/nullif(league_faceoffs,0) league_faceoff_rate FROM (SELECT DISTINCT season FROM pub_games) seasons LEFT JOIN shooting USING(season) LEFT JOIN player USING(season);

CREATE OR REPLACE VIEW pub_player_totals AS SELECT season,player_id,CASE WHEN grouping(team_id)=1 THEN 'ALL' ELSE team_id END team_id,
 CASE WHEN grouping(team_id)=1 THEN 'SEASON' ELSE 'STINT' END aggregation_level, min(player_name) player_name,string_agg(DISTINCT position,',' ORDER BY position) positions,count(*) games_played,
CASE WHEN count(touches)=count(*) THEN sum(touches) END touches,
CASE WHEN count(turnovers)=count(*) THEN sum(turnovers) END turnovers,
CASE WHEN count(faceoffs)=count(*) THEN sum(faceoffs) END faceoffs,
CASE WHEN count(faceoff_wins)=count(*) THEN sum(faceoff_wins) END faceoff_wins,
CASE WHEN count(caused_turnovers)=count(*) THEN sum(caused_turnovers) END caused_turnovers,
CASE WHEN count(ground_balls)=count(*) THEN sum(ground_balls) END ground_balls,
CASE WHEN count(penalties)=count(*) THEN sum(penalties) END penalties,
CASE WHEN count(shots)=count(*) THEN sum(shots) END shots,
CASE WHEN count(a1)=count(*) THEN sum(a1) END a1,
CASE WHEN count(a2)=count(*) THEN sum(a2) END a2,
CASE WHEN count(g1)=count(*) THEN sum(g1) END g1,
CASE WHEN count(g2)=count(*) THEN sum(g2) END g2,
CASE WHEN count(sog)=count(*) THEN sum(sog) END sog,
CASE WHEN count(unresolved_sog)=count(*) THEN sum(unresolved_sog) END unresolved_sog,
CASE WHEN count(team_shots_in_appearances)=count(*) THEN sum(team_shots_in_appearances) END team_shots_in_appearances,
CASE WHEN count(team_a2_in_appearances)=count(*) THEN sum(team_a2_in_appearances) END team_a2_in_appearances,
CASE WHEN count(team_faceoffs_in_appearances)=count(*) THEN sum(team_faceoffs_in_appearances) END team_faceoffs_in_appearances,
CASE WHEN count(sv1)=count(*) THEN sum(sv1) END sv1,
CASE WHEN count(sv2)=count(*) THEN sum(sv2) END sv2,
CASE WHEN count(ga1)=count(*) THEN sum(ga1) END ga1,
CASE WHEN count(ga2)=count(*) THEN sum(ga2) END ga2,
CASE WHEN count(unresolved_goalie_sog)=count(*) THEN sum(unresolved_goalie_sog) END unresolved_goalie_sog,
CASE WHEN count(sog2_faced)=count(*) THEN sum(sog2_faced) END sog2_faced FROM pub_player_appearance GROUP BY GROUPING SETS ((season,player_id),(season,player_id,team_id));
CREATE OR REPLACE VIEW player_season_summary AS SELECT p.*,
 a1+a2 attempts,g1+g2 goals,g1+2*g2 scoring_points,sv1+sv2 resolved_saves,sv1+sv2+ga1+ga2 resolved_shots_faced,
 b.p1,b.p2,b.league_turnover_per_touch,b.league_faceoff_rate,b.league_save_rate,
 (g1+g2)/nullif(shots,0) shooting_pct,sog/nullif(shots,0) shots_on_goal_pct,
 (g1+2*g2)/nullif(shots,0) scoring_points_per_shot,
 turnovers/nullif(touches,0) turnovers_per_touch,
 CASE WHEN touches>0 THEN touches*league_turnover_per_touch-turnovers END turnovers_below_expected,
 CASE WHEN shots>0 AND (a1=0 OR p1 IS NOT NULL) AND (a2=0 OR p2 IS NOT NULL)
 THEN g1+2*g2-CASE WHEN a1=0 THEN 0 ELSE a1*p1 END-CASE WHEN a2=0 THEN 0 ELSE 2*a2*p2 END END shooting_value_above_expected,
 shots/nullif(team_shots_in_appearances,0) shot_share,
 a2/nullif(team_a2_in_appearances,0) team_two_point_attempt_share,
 a2/nullif(shots,0) two_point_attempt_rate,g2/nullif(a2,0) two_point_conversion_pct,
 CASE WHEN a2>0 THEN 2*(g2-a2*p2) END two_point_shooting_value,
 faceoff_wins/nullif(faceoffs,0) faceoff_pct,faceoffs/nullif(team_faceoffs_in_appearances,0) draw_share,
 CASE WHEN faceoffs>0 THEN faceoff_wins-faceoffs*league_faceoff_rate END faceoff_wins_above_average,
 resolved_saves/nullif(resolved_shots_faced,0) save_pct,sv1/nullif(sv1+ga1,0) one_point_save_pct,
 sv2/nullif(sv2+ga2,0) two_point_save_pct,
 CASE WHEN resolved_shots_faced>0 THEN resolved_saves-resolved_shots_faced*league_save_rate END saves_above_average,
 resolved_shots_faced/nullif(resolved_shots_faced+unresolved_goalie_sog,0) resolved_coverage,
 sog2_faced/nullif(resolved_shots_faced+unresolved_goalie_sog,0) goalie_two_point_shot_mix_faced,
 caused_turnovers/games_played caused_turnovers_per_game,ground_balls/games_played ground_balls_per_game,
 penalties/games_played penalties_per_game FROM pub_player_totals p JOIN season_baselines b USING(season);
CREATE OR REPLACE VIEW player_offensive_advanced AS SELECT season,player_id,team_id,aggregation_level,player_name,positions,games_played,
 touches,turnovers,league_turnover_per_touch,turnovers_per_touch,turnovers_below_expected,shots,team_shots_in_appearances,shot_share FROM player_season_summary;
CREATE OR REPLACE VIEW player_shooting_advanced AS SELECT season,player_id,team_id,aggregation_level,player_name,positions,games_played,
 shots,a1,a2,g1,g2,sog,unresolved_sog,p1,p2,scoring_points,shooting_pct,shots_on_goal_pct,scoring_points_per_shot,shooting_value_above_expected FROM player_season_summary;
CREATE OR REPLACE VIEW player_two_point_stats AS SELECT season,player_id,team_id,aggregation_level,player_name,positions,games_played,
 shots,a2,g2,p2,team_a2_in_appearances,two_point_attempt_rate,two_point_conversion_pct,two_point_shooting_value,team_two_point_attempt_share FROM player_season_summary;
CREATE OR REPLACE VIEW faceoff_advanced AS SELECT season,player_id,team_id,aggregation_level,player_name,positions,games_played,
 faceoffs,faceoff_wins,team_faceoffs_in_appearances,league_faceoff_rate,faceoff_pct,draw_share,faceoff_wins_above_average FROM player_season_summary WHERE faceoffs>0 OR positions LIKE '%FO%';
CREATE OR REPLACE VIEW goalie_advanced AS SELECT season,player_id,team_id,aggregation_level,player_name,positions,games_played,
 sv1,sv2,ga1,ga2,resolved_saves,resolved_shots_faced,unresolved_goalie_sog,resolved_coverage,sog2_faced,league_save_rate,
 save_pct,one_point_save_pct,two_point_save_pct,saves_above_average,goalie_two_point_shot_mix_faced
 FROM player_season_summary WHERE resolved_shots_faced+unresolved_goalie_sog>0 OR positions='G';
CREATE OR REPLACE VIEW defensive_production AS SELECT season,player_id,team_id,aggregation_level,player_name,positions,games_played,
 caused_turnovers,ground_balls,penalties,caused_turnovers_per_game,ground_balls_per_game,penalties_per_game FROM player_season_summary;
CREATE OR REPLACE VIEW possession_length_analysis AS WITH bucketed AS (
 SELECT *,CASE WHEN duration_seconds=0 THEN 0 WHEN duration_seconds<10 THEN 1 WHEN duration_seconds<20 THEN 2
 WHEN duration_seconds<30 THEN 3 WHEN duration_seconds<45 THEN 4 WHEN duration_seconds<60 THEN 5 ELSE 6 END bucket_order
 FROM pub_possessions WHERE measurable), a AS (
 SELECT season,offense_team_id team_id,bucket_order,count(*) possessions,sum(points_scored) points,sum(shot_attempts) shots,
 count(*) FILTER(WHERE end_reason='turnover') turnovers,count(*) FILTER(WHERE shot_attempts>=1) shot_producing_possessions FROM bucketed GROUP BY ALL)
 SELECT a.*, ['0 seconds','1–9 seconds','10–19 seconds','20–29 seconds','30–44 seconds','45–59 seconds','60+ seconds'][bucket_order+1] bucket,
 a.possessions/nullif(sum(a.possessions) OVER(PARTITION BY a.season,a.team_id),0) share_of_possessions,
 a.points/nullif(a.possessions,0) points_per_possession,a.shots/nullif(a.possessions,0) shots_per_possession,
 a.turnovers/nullif(a.possessions,0) turnover_rate,a.shot_producing_possessions/nullif(a.possessions,0) shot_producing_possession_rate,
 t.measurable_possession_coverage,t.possessions eligible_possessions,t.measurable_possessions
 FROM a JOIN team_advanced_stats t USING(season,team_id);

-- Explicit source coverage, including unattributed historical shots retained in league baselines.
CREATE OR REPLACE VIEW publication_coverage AS SELECT g.season,count(*) eligible_games,
 max(start_date_utc) latest_game_start_utc,g.season=2026 frozen_partial_season,
 (SELECT count(*) FROM pub_shots s WHERE s.season=g.season) eligible_shots,
 (SELECT count(*) FROM pub_shots s WHERE s.season=g.season AND s.player_id IS NULL) unattributed_shots,
 (SELECT count(*) FROM pub_shots s WHERE s.season=g.season AND s.sog AND s.goalie_id IS NULL) unattributed_goalie_sog,
 (SELECT count(*) FROM pub_possessions p WHERE p.season=g.season) eligible_possessions,
 (SELECT count(*) FROM pub_possessions p WHERE p.season=g.season AND p.is_ambiguous) ambiguous_possessions,
 (SELECT count(*) FROM pub_possessions p WHERE p.season=g.season AND p.measurable) measurable_possessions,
 (SELECT sum(score_residual) FROM team_game_publication t WHERE t.season=g.season) scoring_gap,
 (SELECT sum(excluded_touch_records) FROM season_baselines b WHERE b.season=g.season) excluded_touch_records,
 (SELECT sum(excluded_touch_turnovers) FROM season_baselines b WHERE b.season=g.season) excluded_touch_turnovers
 FROM pub_games g GROUP BY g.season;
CREATE OR REPLACE VIEW possession_sensitivity AS SELECT season,offense_team_id team_id,
 CASE WHEN grouping(is_ambiguous)=1 THEN 'ALL' WHEN is_ambiguous THEN 'AMBIGUOUS' ELSE 'UNAMBIGUOUS' END population,
 count(*) possessions,count(*) FILTER(WHERE shot_attempts>=1) shot_producing_possessions,
 count(*) FILTER(WHERE shot_attempts>=2) multi_shot_possessions,
 shot_producing_possessions/possessions shot_producing_possession_rate,
 multi_shot_possessions/possessions multi_shot_possession_rate
 FROM pub_possessions GROUP BY GROUPING SETS ((season,offense_team_id),(season,offense_team_id,is_ambiguous));
