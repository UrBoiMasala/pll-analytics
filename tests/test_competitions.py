"""Field splits conserve totals; Sixes is a disjoint format and baseline."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from pll_build_publication import connect
from pll_competitions import CHAMPIONSHIP_GAME_IDS,FIELD_GAME_COUNTS
from pll_validate_publication import validate
from pll_validate_championship import validate as validate_championship

@pytest.fixture(scope='module',params=range(2023,2027))
def year(request):return request.param

@pytest.fixture(scope='module')
def views(year):
    cs={s:connect(segment=None if s=='combined' else s,year=year) for s in ['combined','regular','post','champ_series']}
    yield cs
    for c in cs.values():c.close()

@pytest.mark.parametrize('segment',['regular','post','champ_series'])
def test_exact_membership(views,segment,year):
    count=len(CHAMPIONSHIP_GAME_IDS[year]) if segment=='champ_series' else FIELD_GAME_COUNTS[year][segment=='post']
    c=views[segment];games=c.execute('SELECT * FROM pub_games').df()
    assert len(games)==count and games.season.eq(year).all()
    assert games.season_segment.eq('champseries' if segment=='champ_series' else segment).all()
    assert c.execute('SELECT count(*) FROM pub_participants').fetchone()[0]==2*count

@pytest.mark.parametrize('segment',['regular','post'])
def test_stored_field_splits(views,segment,year):
    report=validate(segment=segment,year=year)
    assert report.status.eq('PASS').all(),report[report.status!='PASS'].to_string()

def test_sixes_validation(year):
    report=validate_championship(year=year)
    assert report.status.eq('PASS').all(),report[report.status!='PASS'].to_string()

def test_field_counts_conserve_and_sixes_never_enters_combined(views,year):
    cols=['games_played','shots','a1','a2','g1','g2','scoring_points','touches','turnovers','faceoffs','faceoff_wins','resolved_saves','resolved_shots_faced','team_shots_in_appearances']
    dfs={s:c.execute(f"SELECT * FROM player_season_summary WHERE season={year} AND aggregation_level='SEASON' ORDER BY player_id").df().set_index('player_id') for s,c in views.items()}
    pd.testing.assert_frame_equal(dfs['combined'][cols],dfs['regular'][cols].add(dfs['post'][cols],fill_value=0).sort_index(),check_dtype=False)
    field=set(views['combined'].execute(f'SELECT game_id FROM pub_games WHERE season={year}').fetchnumpy()['game_id'])
    sixes=set(views['champ_series'].execute('SELECT game_id FROM pub_games').fetchnumpy()['game_id'])
    assert len(field)==sum(FIELD_GAME_COUNTS[year]) and len(sixes)==len(CHAMPIONSHIP_GAME_IDS[year]) and field.isdisjoint(sixes)

def test_same_field_baseline_and_separate_sixes_baseline(views):
    a=views['regular'].execute('SELECT * FROM season_baselines').df()
    b=views['post'].execute('SELECT * FROM season_baselines').df()
    pd.testing.assert_frame_equal(a,b)
    cs=views['champ_series'].execute('SELECT * FROM season_baselines').df()
    assert not np.isclose(cs.p1.iloc[0],a.p1.iloc[0])
    for segment in ['regular','post','champ_series']:
        v=views[segment].execute('SELECT * FROM player_season_summary WHERE shots>0').df()
        assert np.allclose(v.shooting_pct,(v.g1+v.g2)/v.shots)
        assert np.allclose(v.shooting_value_above_expected,v.g1+2*v.g2-v.a1*v.p1-2*v.a2*v.p2)

def test_actual_appearance_exposure_and_transfer_conservation(views):
    for segment in ['regular','post','champ_series']:
        c=views[segment]
        expected=c.execute('SELECT p.officialId player_id,sum(t.shots) n FROM pub_player_games p JOIN pub_team_shots t ON p.game_id=t.game_id AND p.teamId=t.team_id GROUP BY p.officialId ORDER BY p.officialId').df()
        actual=c.execute("SELECT player_id,team_shots_in_appearances n FROM player_season_summary WHERE aggregation_level='SEASON' ORDER BY player_id").df()
        pd.testing.assert_frame_equal(actual,expected,check_dtype=False)

def test_unsupported_years_rejected():
    for year in [2021,2027]:
        with pytest.raises(ValueError):connect(segment='regular',year=year)
        assert not (ROOT/f'data/publication/{year}/regular').exists()
    with pytest.raises(ValueError):connect(segment='champ_series',year=2022)


def test_clock_defects_are_audited_without_invented_possessions():
    root=ROOT/'data/competitions/2023/champ_series'
    audit=pd.read_csv(root/'validation.csv')
    assert audit.invalid_regulation_clocks.sum()==19
    assert audit.backwards_time_steps.sum()==15
    assert audit.possession_status.eq('withheld_unvalidated_sixes_model').all()
    assert pd.read_csv(root/'processed/possessions.csv').empty
