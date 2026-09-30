"""Current-snapshot completeness and independent 2022 split reconciliation."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from pll_build_publication import connect
from pll_current_data import current_frame, read_current
from pll_validate_publication import validate

@pytest.fixture(scope='module')
def snapshots():
    connections={key:connect(segment=None if key=='combined' else key) for key in ('combined','regular','post')}
    yield connections
    for con in connections.values():con.close()

def test_update_hashes_and_original_foundation_preserved():
    root=ROOT/'data/updates/2026'
    manifest=json.loads((root/'manifest.json').read_text())
    assert set(manifest['added_game_ids'])=={526,527,529}
    actual={str(p.relative_to(root)) for folder in ['raw','processed'] for p in (root/folder).rglob('*') if p.is_file()}
    assert actual==set(manifest['artifact_sha256'])
    for name,digest in manifest['artifact_sha256'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    from pll_canonical_versions import manifest_failures
    assert manifest_failures()==[]

def test_updated_schedule_is_complete_and_matches_live_snapshot(snapshots):
    c=snapshots['combined']
    schedule=json.loads((ROOT/'data/updates/2026/raw/_schedule/games_2026.json').read_text())['data']['items']
    expected={g['id'] for g in schedule if g['seasonSegment'] in ('regular','post') and g['eventStatus']==3}
    assert len(expected)==53
    assert expected==set(c.execute('SELECT game_id FROM pub_games WHERE season=2026').fetchnumpy()['game_id'])
    assert c.execute('SELECT count(*) FROM pub_games WHERE season=2026 AND is_playoff').fetchone()[0]==5
    assert not c.execute('SELECT frozen_partial_season FROM publication_coverage WHERE season=2026').fetchone()[0]
    assert c.execute('SELECT count(*) FROM team_game_publication WHERE season=2026').fetchone()[0]==106
    assert c.execute('SELECT count(*) FROM team_game_publication WHERE season=2026 AND score_residual<>0').fetchone()[0]==0

@pytest.mark.parametrize('game',[526,527,529])
def test_new_games_score_events_and_participation(snapshots,game):
    c=snapshots['combined']
    assert c.execute('SELECT count(*) FROM pub_events WHERE season=2026 AND game_id=?',[game]).fetchone()[0]>150
    assert c.execute('SELECT count(*) FROM pub_possessions WHERE season=2026 AND game_id=?',[game]).fetchone()[0]>60
    assert c.execute('SELECT count(DISTINCT teamId) FROM pub_player_games WHERE season=2026 AND game_id=?',[game]).fetchone()[0]==2
    # Independently sum valid goal events, including two-point weights.
    scored=c.execute("SELECT sum(CASE WHEN is_valid_goal THEN CASE WHEN is_two_point_attempt THEN 2 ELSE 1 END ELSE 0 END) FROM pub_events WHERE season=2026 AND game_id=?",[game]).fetchone()[0]
    official=c.execute('SELECT home_score+away_score FROM pub_games WHERE season=2026 AND game_id=?',[game]).fetchone()[0]
    assert scored==official

@pytest.mark.parametrize('segment,count',[('regular',40),('post',6)])
def test_split_game_membership_and_stored_values(snapshots,segment,count):
    c=snapshots[segment]
    assert c.execute('SELECT count(*) FROM pub_games').fetchone()[0]==count
    assert c.execute('SELECT count(*) FROM pub_games WHERE season<>2022 OR season_segment<>?',[segment]).fetchone()[0]==0
    report=validate(segment=segment)
    assert (report.status=='PASS').all(),report[report.status!='PASS'].to_string()

def test_split_counts_conserve_combined_and_rates_use_pooled_counts(snapshots):
    cols=['games_played','shots','a1','a2','g1','g2','scoring_points','touches','turnovers','faceoffs','faceoff_wins','resolved_saves','resolved_shots_faced','team_shots_in_appearances','team_a2_in_appearances']
    data={key:c.execute("SELECT * FROM player_season_summary WHERE season=2022 AND aggregation_level='SEASON' ORDER BY player_id").df().set_index('player_id') for key,c in snapshots.items()}
    summed=data['regular'][cols].add(data['post'][cols],fill_value=0).sort_index()
    pd.testing.assert_frame_equal(data['combined'][cols].sort_index(),summed,check_dtype=False,check_names=False)
    for key in ['regular','post']:
        d=data[key];active=d[d.shots>0]
        assert np.allclose(active.shooting_pct,(active.g1+active.g2)/active.shots)
        assert np.allclose(active.shooting_value_above_expected,active.g1+2*active.g2-active.a1*active.p1-2*active.a2*active.p2)
    # Shared baseline makes above-expected comparisons meaningful across stages.
    pd.testing.assert_frame_equal(snapshots['regular'].execute('SELECT * FROM season_baselines').df(),snapshots['post'].execute('SELECT * FROM season_baselines').df())

def test_split_opportunities_use_only_actual_appearances(snapshots):
    for segment in ['regular','post']:
        c=snapshots[segment]
        expected=c.execute('''SELECT p.officialId player_id,sum((SELECT count(*) FROM pub_shots s WHERE s.season=p.season AND s.game_id=p.game_id AND s.team_id=p.teamId)) n FROM pub_player_games p GROUP BY p.officialId ORDER BY p.officialId''').df()
        actual=c.execute("SELECT player_id,team_shots_in_appearances n FROM player_season_summary WHERE aggregation_level='SEASON' ORDER BY player_id").df()
        pd.testing.assert_frame_equal(actual,expected,check_dtype=False)

def test_unsupported_year_splits_are_not_created():
    for year in (2021,2027):
        assert not (ROOT/f'data/publication/{year}/regular').exists()
        assert not (ROOT/f'data/publication/{year}/post').exists()
    with pytest.raises(ValueError):connect(segment='champ_series')

def test_overlay_reader_matches_dataframe():
    for name in ['games','events','possessions','player_game_stats','team_game_stats']:
        rows=read_current(2026,name);df=current_frame(2026,name,low_memory=False)
        assert len(rows)==len(df)
        assert {int(r['game_id']) for r in rows}==set(df.game_id)


def test_new_possession_hard_checks_pass():
    report=pd.read_csv(ROOT/'data/updates/2026/processed/possession_validation_report.csv')
    assert (report.status=='PASS').sum()==17
    assert not (report.status=='FAIL').any()

def test_split_coverage_uses_selected_population(snapshots):
    for key in ['regular','post']:
        c=snapshots[key]
        expected=c.execute('SELECT count(*) FROM pub_player_games WHERE touches IS NULL OR touches<=0 OR turnovers IS NULL').fetchone()[0]
        assert c.execute('SELECT excluded_touch_records FROM publication_coverage').fetchone()[0]==expected
