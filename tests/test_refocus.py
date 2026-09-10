"""Independent regression checks for the refocus foundation."""
import sys
from pathlib import Path
import pandas as pd
import pytest
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from test_build_possessions import ev, HOME, AWAY
import pll_build_possessions as bp
import pll_player_value_models as models
from pll_refocus_foundation import player_team_stints, verify_checkpoint


def run(rows):
    return bp.build_possessions_for_game('g', 'g', HOME, AWAY, pd.DataFrame(rows))


def test_opening_goal_counted_once():
    p = run([ev(1, 'goal', HOME, 10, shot_type='2_PT', shot_outcome='goal', is_valid_goal=True)])[0]
    assert p['event_count'] == 1
    assert p['points_scored'] == 2
    assert p['start_event_id'] == p['end_event_id']


def test_turnover_boundary_counted_and_companion_does_not_create_possession():
    p = run([ev(1, 'faceoff', HOME, 1), ev(2, 'turnover', HOME, 8), ev(3, 'shotclockexpired', HOME, 8)])
    assert len(p) == 1
    assert p[0]['event_count'] == 2
    assert p[0]['duration_seconds'] == 7


def test_groundball_starts_and_continuations_count_once():
    p = run([ev(1, 'groundball', HOME, 1), ev(2, 'groundball', HOME, 2),
             ev(3, 'groundball', AWAY, 3), ev(4, 'turnover', AWAY, 4)])
    assert [r['ground_balls'] for r in p] == [2, 1]
    assert sum(r['ground_balls'] for r in p) == 3


def test_transfer_totals_follow_game_team():
    g = pd.DataFrame(dict(game_id=[1,2,3], home_team_id=['A','B','B'], away_team_id=['C']*3,
                          is_completed=[True,True,False], include_in_league_analytics=[True]*3, is_all_star=[False]*3))
    p = pd.DataFrame(dict(game_id=[1,2,3], officialId=['001']*3, teamId=['A','B','B'], shots=[2,5,99]))
    result = player_team_stints(p,g)
    assert result.player_id.tolist() == ['001','001']
    assert result.shots.tolist() == [2,5]
    with pytest.raises(ValueError, match='Duplicate player-game'):
        player_team_stints(pd.concat([p,p.iloc[:1]]),g)


@pytest.mark.parametrize('year', range(2022,2027))
def test_historical_goal_feature_uses_pre_shot_score(year):
    d = ROOT/'data/processed'/str(year)
    evs = models.load_eligible_events(d)
    shots = models._shot_feature_frame(evs, data_dir=d)
    games = pd.read_csv(d/'games.csv').set_index('game_id')
    home_goals = shots[(shots.is_valid_goal == True) & (shots.team_id == shots.game_id.map(games.home_team_id))]
    assert len(home_goals) > 0
    expected = home_goals.home_score_corrected - home_goals.pll_points - home_goals.away_score_corrected
    assert (home_goals.score_margin == expected).all()
    if year != 2026:
        with pytest.raises(ValueError, match='season game metadata'):
            models._shot_feature_frame(evs, data_dir=ROOT/'data/processed/2026')


def test_raw_and_parent_manifest_unchanged():
    verify_checkpoint()
