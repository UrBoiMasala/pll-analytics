"""Read-only validation of retained analytics; optional --write-report."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import duckdb
from pll_refocus_foundation import verify_checkpoint, SEASONS, player_team_stints, STINT_COUNTS
from pll_canonical_versions import manifest_failures
from pll_build_team_metrics import PIPELINE, run_sql_file
import pll_player_value_models as models
ROOT=Path(__file__).resolve().parent.parent
PROC=ROOT/'data/processed'
HIST=PROC/'history'


def validate():
    failures={k:[] for k in ['raw_payload_hashes','canonical_versions','unique_keys','eligible_completed_scope',
              'possession_boundaries','groundball_accounting','chronology_provenance','event_possession_points',
              'score_reconciliation','transfer_stints','season_shot_metadata','sql_csv_agreement','shooting_formula','catalog_scope']}
    verify_checkpoint()
    failures['canonical_versions']=manifest_failures()
    def check(name,condition,detail):
        if not condition: failures[name].append(detail)
    all_stints=pd.read_csv(HIST/'player_team_stints_2022_2026.csv',dtype={'player_id':str,'team_id':str})
    for year in SEASONS:
        d=PROC/str(year)
        g=pd.read_csv(d/'games.csv')
        e=pd.read_csv(d/'events.csv',low_memory=False,dtype={'player_id':str,'team_id':str,'event_id':str})
        p=pd.read_csv(d/'possessions.csv',dtype={'start_event_id':str,'end_event_id':str})
        pg=pd.read_csv(d/'player_game_stats.csv',dtype={'officialId':str,'teamId':str})
        eligible=g[g.is_completed & g.include_in_league_analytics & ~g.is_all_star]
        ee=e[e.is_analysis_eligible_event & e.game_id.isin(eligible.game_id)]
        check('unique_keys',not g.game_id.duplicated().any() and not e.duplicated(['game_id','event_id']).any()
              and not p.possession_id.duplicated().any() and not pg.duplicated(['game_id','officialId']).any(),str(year))
        check('eligible_completed_scope',p.game_id.isin(eligible.game_id).all() and not ee.is_duplicate_event.any(),str(year))
        # Every boundary resolves to the same game and period, with nonnegative duration.
        bounds=p.merge(e[['game_id','event_id','period']],left_on=['game_id','start_event_id'],right_on=['game_id','event_id'],how='left',suffixes=('','_start'),validate='many_to_one')
        ends=p.merge(e[['game_id','event_id','period']],left_on=['game_id','end_event_id'],right_on=['game_id','event_id'],how='left',suffixes=('','_end'),validate='many_to_one')
        check('possession_boundaries',(bounds.period==bounds.period_start).all() and (ends.period==ends.period_end).all()
              and (p.duration_seconds>=0).all() and ((p.event_count==1)==(p.start_event_id==p.end_event_id)).all(),str(year))
        check('groundball_accounting',p.ground_balls.sum()==(ee.event_type=='groundball').sum(),str(year))
        changed=(e.event_number!=e.event_number_raw)|(e.seconds_passed!=e.seconds_passed_raw)
        check('chronology_provenance',(~changed|e.chronology_repair_applied).all(),str(year))
        goals=ee[ee.is_valid_goal==True].copy()
        goals['q']=np.where(goals.is_two_point_attempt,2,1)
        a=goals.groupby(['game_id','team_id']).q.sum()
        b=p.groupby(['game_id','offense_team_id']).points_scored.sum()
        check('event_possession_points',a.subtract(b,fill_value=0).abs().max()==0,str(year))
        scored=p.groupby('game_id').points_scored.sum()
        official=eligible.set_index('game_id').eval('home_score + away_score')
        delta=scored-official
        bad=delta[delta!=0]
        # This source gap is acknowledged exactly, not a loose tolerance.
        expected=eligible[eligible.game_slug=='archers-cannons-2022-6-18'].game_id.tolist()
        check('score_reconciliation',(not len(bad) and not expected) or (year==2022 and bad.index.tolist()==expected and bad.iloc[0]==-7),str(year)+': '+str(bad.to_dict()))
        rebuilt=player_team_stints(pg,g)
        stored=all_stints[all_stints.season==year].drop(columns='season').reset_index(drop=True)
        try: pd.testing.assert_frame_equal(rebuilt,stored,check_dtype=False)
        except AssertionError: failures['transfer_stints'].append(str(year))
        shots=models._shot_feature_frame(models.load_eligible_events(d),data_dir=d)
        check('season_shot_metadata',shots.game_id.isin(g.game_id).all(),str(year))
        con=duckdb.connect()
        for sql,table,filename in PIPELINE:
            run_sql_file(con,ROOT/'sql'/sql,d)
            if filename:
                actual=con.execute('SELECT * FROM '+table).df()
                stored=pd.read_csv(d/filename)
                if 'start_date_utc' in actual:
                    actual['start_date_utc']=pd.to_datetime(actual['start_date_utc'], utc=True)
                    stored['start_date_utc']=pd.to_datetime(stored['start_date_utc'], utc=True)
                try: pd.testing.assert_frame_equal(actual,stored,check_dtype=False,atol=1e-9,rtol=1e-9)
                except AssertionError: failures['sql_csv_agreement'].append(f'{year}/{filename}')
        con.close()
        # Independent shot-class residual accounting, not a stored PASS column.
        rates=shots.groupby('is_two_point').y.mean()
        residual=shots.pll_points-(1+shots.is_two_point)*shots.is_two_point.map(rates)
        check('shooting_formula',abs(residual.sum())<1e-8,str(year))
    catalog=pd.read_csv(HIST/'final_metric_catalog.csv')
    check('catalog_scope',len(catalog)==29 and not catalog.metric_name.duplicated().any()
          and set(catalog.classification)<= {'STANDARD','DERIVED_ADVANCED','ORIGINAL_PLL_METRIC'}
          and not catalog.metric_name.str.contains('mvp|war|composite|rank_probability').any(),'catalog')
    report=pd.DataFrame([dict(check=k,status='FAIL' if v else 'PASS',n_failures=len(v),detail='; '.join(v) or 'Verified from inputs') for k,v in failures.items()])
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
    result=validate();print(result.to_string(index=False))
    if args.write_report: result.to_csv(HIST/'refocus_validation_report.csv',index=False)
    if (result.status!='PASS').any(): raise SystemExit(1)

if __name__=='__main__': main()
