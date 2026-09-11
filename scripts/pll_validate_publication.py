"""Independent input reconciliation and stored SQL/CSV validation. Read-only by default."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from pll_build_publication import ROOT, TABLES, connect

def validate(output=None):
    output=Path(output or ROOT/'data/publication');c=connect();checks=[]
    def check(name, ok):
        checks.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL'))
    for year in range(2022,2027):
        d=ROOT/'data/processed'/str(year)
        g=pd.read_csv(d/'games.csv');g=g[g.is_completed & g.include_in_league_analytics & ~g.is_all_star]
        p=pd.read_csv(d/'possessions.csv');p=p[p.game_id.isin(g.game_id)]
        e=pd.read_csv(d/'events.csv',dtype={'player_id':str,'goalie_id':str});e=e[e.game_id.isin(g.game_id)&e.is_analysis_eligible_event]
        shots=e[e.event_type.isin(['shot','goal']) & e.shot_outcome.notna()]
        pg=pd.read_csv(d/'player_game_stats.csv',dtype={'officialId':str});pg=pg[pg.game_id.isin(g.game_id)]
        t=c.execute(f'SELECT * FROM team_advanced_stats WHERE season={year}').df()
        v=c.execute(f"SELECT * FROM player_season_summary WHERE season={year} AND aggregation_level='SEASON'").df()
        check(f'{year}: possession and scoring conservation',t.possessions.sum()==len(p) and t.points.sum()==p.points_scored.sum() and t.points_allowed.sum()==p.points_scored.sum())
        check(f'{year}: offensive and defensive formulas',np.allclose(t.offensive_efficiency,100*t.points/t.possessions) and np.allclose(t.defensive_efficiency,100*t.points_allowed/t.defensive_possessions) and np.allclose(t.net_efficiency,t.offensive_efficiency-t.defensive_efficiency))
        check(f'{year}: shot event conservation',t.shots.sum()==len(shots) and v.shots.sum()==shots.player_id.notna().sum() and (v.a1+v.a2==v.shots).all())
        check(f'{year}: possession outcome bounds',t.multi_shot_possession_rate.between(0,1).all() and (t.multi_shot_possession_rate<=t.shot_producing_possession_rate).all())
        m=p[~p.is_ambiguous & ~p.is_truncated & (p.start_event_id!=p.end_event_id)]
        check(f'{year}: duration eligibility',t.measurable_possessions.sum()==len(m) and t.measurable_possession_seconds.sum()==m.duration_seconds.sum() and t.time_of_possession_share.between(0,1).all())
        for row in t.itertuples():
            off=m[m.offense_team_id==row.team_id];de=m[m.defense_team_id==row.team_id]
            assert np.isclose(row.offensive_pace_seconds,off.duration_seconds.mean(),equal_nan=True)
            assert np.isclose(row.defensive_pace_seconds,de.duration_seconds.mean(),equal_nan=True)
        check(f'{year}: opponent pace attribution',True)
        b=c.execute(f'SELECT * FROM possession_length_analysis WHERE season={year}').df()
        check(f'{year}: bucket conservation',b.possessions.sum()==len(m) and b.points.sum()==m.points_scored.sum() and b.shots.sum()==m.shot_attempts.sum() and b.turnovers.sum()==(m.end_reason=='turnover').sum())
        official=pd.read_csv(d/'team_game_stats.csv');official=official[official.game_id.isin(g.game_id)]
        check(f'{year}: official assist source',t.official_assists.sum()==official.assists.sum() and t.official_goals.sum()==official.goals.sum())
        resolved=shots[shots.shot_outcome.isin(['saved','goal']) & shots.goalie_id.notna()]
        check(f'{year}: goalie resolved population',v.resolved_shots_faced.sum()==len(resolved) and v.resolved_saves.sum()==(resolved.shot_outcome=='saved').sum())
        check(f'{year}: player appearances',v.games_played.sum()==len(pg) and v.turnovers.sum()==pg.turnovers.sum())
        st=c.execute(f"SELECT * FROM player_season_summary WHERE season={year} AND aggregation_level='STINT'").df()
        counts=['shots','a1','a2','g1','g2','turnovers','faceoffs','faceoff_wins','resolved_saves','resolved_shots_faced','games_played']
        check(f'{year}: transfer conservation',np.allclose(st.groupby('player_id')[counts].sum().sort_index(),v.set_index('player_id')[counts].sort_index(),equal_nan=True))
    for table in TABLES:
        actual=c.execute(f'SELECT * FROM {table} ORDER BY ALL').df()
        for year in [None,*range(2022,2027)]:
            path=output/(str(year) if year else '')/(table+'.csv')
            stored=pd.read_csv(path,dtype={'player_id':str},keep_default_na=True)
            expected=actual if year is None else actual[actual.season==year].reset_index(drop=True)
            for col in expected:
                if pd.api.types.is_datetime64_any_dtype(expected[col]):
                    stored[col]=pd.to_datetime(stored[col],utc=True)
            try:
                pd.testing.assert_frame_equal(expected,stored,check_dtype=False,atol=1e-9,rtol=1e-10)
                ok=True
            except AssertionError: ok=False
            check(f'CSV agreement: {year or "pooled"}/{table}',ok)
        numeric=actual.select_dtypes(include='number')
        check(f'No infinity: {table}',not np.isinf(numeric).any().any())
    catalog=pd.read_csv(ROOT/'data/publication/metric_dictionary.csv')
    check('35 unique core definitions',len(catalog)==35 and not catalog.metric_name.duplicated().any())
    check('catalog columns exist',all(row.output_column in c.execute('SELECT * FROM '+row.SQL_view+' LIMIT 0').df().columns for row in catalog.itertuples()))
    c.close();return pd.DataFrame(checks)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
    report=validate();print(report.to_string(index=False))
    if args.write_report: report.to_csv(ROOT/'data/publication/validation_report.csv',index=False)
    if (report.status!='PASS').any(): raise SystemExit(1)
if __name__=='__main__':main()
