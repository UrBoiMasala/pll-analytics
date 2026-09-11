"""Behavioral regressions for the publication SQL; fixtures alter inputs, not formulas."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pll_build_publication import connect

@pytest.fixture
def db():
    con=connect()
    try: yield con
    finally: con.close()

def test_undefined_exposure_is_null(db):
    db.execute("UPDATE raw_players SET touches=0,faceoffs=0,faceoffsWon=0 WHERE season=2026")
    db.execute("DELETE FROM raw_events WHERE season=2026 AND event_type IN ('shot','goal')")
    row=db.execute("SELECT shooting_pct,shooting_value_above_expected,two_point_shooting_value,turnovers_per_touch,turnovers_below_expected,faceoff_pct,faceoff_wins_above_average,save_pct,saves_above_average FROM player_season_summary WHERE season=2026 LIMIT 1").fetchone()
    assert all(x is None for x in row)

def test_unresolved_goalie_shots_do_not_become_saves(db):
    season,game,event,goalie=db.execute("SELECT season,game_id,event_id,goalie_id FROM pub_shots WHERE shot_outcome='saved' AND goalie_id IS NOT NULL LIMIT 1").fetchone()
    query="SELECT resolved_saves,resolved_shots_faced,unresolved_goalie_sog FROM player_season_summary WHERE season=? AND player_id=? AND aggregation_level='SEASON'"
    before=db.execute(query,[season,goalie]).fetchone()
    db.execute("UPDATE raw_events SET shot_outcome='on_goal_no_save' WHERE season=? AND game_id=? AND event_id=?",[season,game,event])
    after=db.execute(query,[season,goalie]).fetchone()
    assert after==(before[0]-1,before[1]-1,before[2]+1)

def test_shares_exclude_nonappearance_games(db):
    row=db.execute("SELECT s.season,s.game_id,s.event_id,s.team_id,p.player_id FROM pub_shots s JOIN pub_player_totals p ON p.season=s.season AND p.team_id=s.team_id AND p.team_id<>'ALL' WHERE NOT EXISTS(SELECT 1 FROM pub_player_games a WHERE a.season=s.season AND a.game_id=s.game_id AND a.officialId=p.player_id) LIMIT 1").fetchone()
    season,game,event,team,player=row
    query="SELECT team_shots_in_appearances,shot_share FROM player_season_summary WHERE season=? AND player_id=? AND aggregation_level='SEASON'"
    before=db.execute(query,[season,player]).fetchone()
    db.execute("DELETE FROM raw_events WHERE season=? AND game_id=? AND event_id=?",[season,game,event])
    assert db.execute(query,[season,player]).fetchone()==before

def test_two_point_increment_is_two_points(db):
    season,game,event,player=db.execute("SELECT season,game_id,event_id,player_id FROM pub_shots WHERE is_two_point_attempt AND is_valid_goal IS NOT TRUE AND player_id IS NOT NULL LIMIT 1").fetchone()
    query="SELECT scoring_points,shots FROM player_season_summary WHERE season=? AND player_id=? AND aggregation_level='SEASON'"
    before=db.execute(query,[season,player]).fetchone()
    db.execute("UPDATE raw_events SET is_valid_goal=true,shot_outcome='goal' WHERE season=? AND game_id=? AND event_id=?",[season,game,event])
    after=db.execute(query,[season,player]).fetchone()
    assert after==(before[0]+2,before[1])

def test_missing_box_measure_is_not_zero(db):
    season,player=db.execute('SELECT season,officialId FROM pub_player_games LIMIT 1').fetchone()
    db.execute('UPDATE raw_players SET turnovers=NULL WHERE season=? AND officialId=?',[season,player])
    assert db.execute("SELECT turnovers,turnovers_per_touch,turnovers_below_expected FROM player_season_summary WHERE season=? AND player_id=? AND aggregation_level='SEASON'",[season,player]).fetchone()==(None,None,None)

def test_duration_distinct_event_rule_and_boundaries(db):
    db.execute("UPDATE raw_possessions SET is_ambiguous=false,is_truncated=false,start_event_id='same',end_event_id='same',duration_seconds=999")
    assert db.execute('SELECT count(*) FROM pub_possessions WHERE measurable').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM team_advanced_stats WHERE offensive_pace_seconds IS NOT NULL OR time_of_possession_share IS NOT NULL').fetchone()[0]==0

@pytest.mark.parametrize('season',range(2022,2027))
def test_season_residuals_and_goalie_splits(db,season):
    a=db.execute("SELECT * FROM player_season_summary WHERE season=? AND aggregation_level='SEASON'",[season]).df()
    shot=a[a.shots>0]
    assert np.allclose(shot.shooting_value_above_expected,shot.g1+2*shot.g2-shot.a1*shot.p1-2*shot.a2*shot.p2)
    two=a[a.a2>0];assert np.allclose(two.two_point_shooting_value,2*(two.g2-two.a2*two.p2))
    fo=a[a.faceoffs>0];assert np.allclose(fo.faceoff_wins_above_average,fo.faceoff_wins-fo.faceoffs*fo.league_faceoff_rate)
    goal=a[a.resolved_shots_faced>0];assert np.allclose(goal.saves_above_average,goal.resolved_saves-goal.resolved_shots_faced*goal.league_save_rate)
    for sv,ga,col in [('sv1','ga1','one_point_save_pct'),('sv2','ga2','two_point_save_pct')]:
        r=a[a[sv]+a[ga]>0];assert np.allclose(r[col],r[sv]/(r[sv]+r[ga]))

@pytest.mark.parametrize('season',range(2022,2027))
def test_appearance_denominators_independent(db,season):
    expected=db.execute("""SELECT p.officialId player_id, sum((SELECT count(*) FROM pub_shots s WHERE s.season=p.season AND s.game_id=p.game_id AND s.team_id=p.teamId)) expected_shots, sum((SELECT count(*) FROM pub_shots s WHERE s.season=p.season AND s.game_id=p.game_id AND s.team_id=p.teamId AND s.is_two_point_attempt)) expected_two FROM pub_player_games p WHERE season=? GROUP BY p.officialId ORDER BY p.officialId""",[season]).df()
    actual=db.execute("SELECT player_id,team_shots_in_appearances,team_a2_in_appearances FROM player_season_summary WHERE season=? AND aggregation_level='SEASON' ORDER BY player_id",[season]).df()
    assert expected.player_id.tolist()==actual.player_id.tolist()
    assert np.array_equal(expected.iloc[:,1:].to_numpy(),actual.iloc[:,1:].to_numpy())

def test_official_assists_and_zero_goals(db):
    db.execute('UPDATE raw_teams SET goals=0 WHERE season=2026')
    assert db.execute('SELECT count(*) FROM team_advanced_stats WHERE season=2026 AND team_assist_to_goal_ratio IS NOT NULL').fetchone()[0]==0

def test_duration_bucket_edges(db):
    season,game,team=db.execute('SELECT season,game_id,offense_team_id FROM pub_possessions LIMIT 1').fetchone()
    ids=[r[0] for r in db.execute('SELECT possession_id FROM pub_possessions WHERE season=? AND game_id=? AND offense_team_id=? ORDER BY possession_number LIMIT 12',[season,game,team]).fetchall()]
    assert len(ids)==12
    db.execute('DELETE FROM raw_possessions WHERE possession_id NOT IN (SELECT unnest(?))',[ids])
    for pid,duration in zip(ids,[0,1,9,10,19,20,29,30,44,45,59,60]):
        db.execute("UPDATE raw_possessions SET duration_seconds=?,is_ambiguous=false,is_truncated=false,start_event_id='a',end_event_id='b' WHERE possession_id=?",[duration,pid])
    assert db.execute('SELECT bucket_order,possessions FROM possession_length_analysis ORDER BY bucket_order').fetchall()==[(0,1),(1,2),(2,2),(3,2),(4,2),(5,2),(6,1)]

def test_example_queries_are_runnable(db):
    from pll_build_publication import ROOT
    statements=db.extract_statements((ROOT/'sql/publication_examples.sql').read_text())
    assert len(statements)==16
    for statement in statements:
        assert db.execute(statement).df().shape[1]>0
