"""Independent box-score/event reconciliation for the separate Sixes views."""
import hashlib
import json
import numpy as np
import pandas as pd
from pll_build_publication import ROOT,TABLES,connect
from pll_competitions import CHAMPIONSHIP_GAME_IDS

def validate(output=None,year=2023):
    root=ROOT/'data/competitions'/str(year)/'champ_series';out=output or ROOT/'data/publication'
    con=connect(segment='champ_series',year=year);checks=[]
    def check(name,ok):checks.append(dict(check=f'{year} champ_series: '+name,status='PASS' if bool(ok) else 'FAIL'))
    manifest=json.loads((root/'manifest.json').read_text())
    files={str(p.relative_to(root)) for folder in ['raw','processed'] for p in (root/folder).rglob('*') if p.is_file()}
    check('source file set and hashes',files==set(manifest['artifact_sha256']) and all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in manifest['artifact_sha256'].items()))
    games=pd.read_csv(root/'processed/games.csv');events=pd.read_csv(root/'processed/events.csv',dtype={'player_id':str,'goalie_id':str});players=pd.read_csv(root/'processed/player_game_stats.csv',dtype={'officialId':str});teams=pd.read_csv(root/'processed/team_game_stats.csv')
    schedule=json.loads((root/'raw/_schedule'/f'games_{year}.json').read_text())['data']['items']
    expected={g['id'] for g in schedule if g['year']==year and g.get('league')=='PLL' and g['seasonSegment']=='champseries' and g['eventStatus']==3}
    check('all scheduled PLL games, both box scores',set(games.game_id)==expected==set(CHAMPIONSHIP_GAME_IDS[year]) and len(teams)==2*len(expected) and teams.groupby('game_id').officialId.nunique().eq(2).all())
    shots=events[events.is_analysis_eligible_event & events.event_type.isin(['shot','goal']) & events.shot_outcome.notna()]
    for g in games.itertuples():
        raw=json.loads((root/'raw'/g.game_slug/'play_by_play.json').read_text())['data']['items']
        check(f'{g.game_id} all regulation periods',set(range(1,5)).issubset({e['period'] for e in raw}))
        check(f'{g.game_id} endpoint scores',raw[-1]['eventType']=='gameEnd' and raw[-1]['homeScore']==g.home_score and raw[-1]['visitorScore']==g.away_score)
        for team,score in [(g.home_team_id,g.home_score),(g.away_team_id,g.away_score)]:
            s=shots[(shots.game_id==g.game_id)&(shots.team_id==team)];goals=s[s.is_valid_goal==True]
            check(f'{g.game_id}/{team} event scoring',len(goals)+goals.is_two_point_attempt.sum()==score)
    check('all player shots and goals match official game boxes',con.execute('''SELECT count(*) FROM pub_player_games p LEFT JOIN pub_player_shots s ON p.game_id=s.game_id AND p.officialId=s.player_id AND p.teamId=s.team_id WHERE p.shots<>coalesce(s.shots,0) OR p.onePointGoals<>coalesce(s.g1,0) OR p.twoPointGoals<>coalesce(s.g2,0) OR p.twoPointShots<>coalesce(s.a2,0)''').fetchone()[0]==0)
    check('all goalie saves and goals match official game boxes',con.execute('''SELECT count(*) FROM pub_player_games p LEFT JOIN pub_goalie_games f ON p.game_id=f.game_id AND p.officialId=f.player_id WHERE p.saves<>coalesce(f.sv1+f.sv2,0) OR p.goalsAgainst<>coalesce(f.ga1+f.ga2,0)''').fetchone()[0]==0)
    baseline=con.execute('SELECT * FROM season_baselines').df().iloc[0]
    check('Sixes-only shooting baseline',np.isclose(baseline.p1,players.onePointGoals.sum()/(players.shots-players.twoPointShots).sum()) and np.isclose(baseline.p2,players.twoPointGoals.sum()/players.twoPointShots.sum()))
    check('Sixes-only goalie/faceoff/turnover baselines',np.isclose(baseline.league_save_rate,players.saves.sum()/(players.saves+players.goalsAgainst).sum()) and np.isclose(baseline.league_faceoff_rate,players.faceoffsWon.sum()/players.faceoffs.sum()) and np.isclose(baseline.league_turnover_per_touch,players.turnovers.sum()/players.touches.sum()))
    summary=con.execute("SELECT * FROM player_season_summary WHERE aggregation_level='SEASON' ORDER BY player_id").df().set_index('player_id')
    for key,source in [('shots','shots'),('g1','onePointGoals'),('g2','twoPointGoals'),('turnovers','turnovers'),('touches','touches'),('faceoffs','faceoffs'),('faceoff_wins','faceoffsWon')]:
        expected=players.groupby('officialId')[source].sum().sort_index()
        check('pooled player '+key,np.allclose(summary[key],expected))
    check('appearance denominators',con.execute('''SELECT count(*) FROM pub_player_appearance a WHERE a.team_shots_in_appearances<>(SELECT shots FROM pub_team_games t WHERE t.game_id=a.game_id AND t.officialId=a.team_id)''').fetchone()[0]==0)
    check('possessions withheld as unknown',con.execute('SELECT count(*) FROM pub_possessions').fetchone()[0]==0 and con.execute('SELECT eligible_possessions FROM publication_coverage').fetchone()[0] is None and con.execute('SELECT count(*) FROM team_advanced_stats WHERE offensive_efficiency IS NOT NULL OR offensive_pace_seconds IS NOT NULL').fetchone()[0]==0)
    for table in TABLES:
        actual=con.execute(f'SELECT * FROM {table} ORDER BY ALL').df()
        stored=pd.read_csv(out/str(year)/'champ_series'/(table+'.csv'),dtype={'player_id':str})
        for col in actual:
            if pd.api.types.is_datetime64_any_dtype(actual[col]):stored[col]=pd.to_datetime(stored[col],utc=True)
        try:pd.testing.assert_frame_equal(actual,stored,check_dtype=False,atol=1e-9,rtol=1e-10);ok=True
        except AssertionError:ok=False
        check('stored CSV '+table,ok)
        check('finite '+table,not np.isinf(actual.select_dtypes(include='number')).any().any())
    con.close();return pd.DataFrame(checks)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--year',type=int,choices=sorted(CHAMPIONSHIP_GAME_IDS))
    args=parser.parse_args()
    report=pd.concat([validate(year=y) for y in ([args.year] if args.year else CHAMPIONSHIP_GAME_IDS)],ignore_index=True)
    print(report.to_string(index=False))
    if not report.status.eq('PASS').all():raise SystemExit(1)
