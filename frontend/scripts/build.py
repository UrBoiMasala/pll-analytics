"""Presentation-only export. Reads frozen inputs; writes only frontend/dist."""
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FRONT=ROOT/'frontend'
sys.path.insert(0, str(ROOT/'scripts'))
from pll_current_data import read_current, input_paths
from pll_competitions import SPLIT_YEARS, CHAMPIONSHIP_GAME_IDS
COUNTS=['games_played','goals','twoPointGoals','assists','points','shots','shotsOnGoal','groundBalls','causedTurnovers','turnovers','saves','goalsAgainst','faceoffsWon','faceoffs','numPenalties']

def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def number(value):return None if value in ('',None) else float(value)
def total(rows,key):
    values=[number(r.get(key)) for r in rows]
    return None if not values or any(v is None for v in values) else sum(values)
def ratio(n,d):return n/d if n is not None and d is not None and d>0 else None
def traditional(rows):
    out={k:total(rows,k) for k in COUNTS}
    out.update(shooting_pct=ratio(out['goals'],out['shots']),faceoff_pct=ratio(out['faceoffsWon'],out['faceoffs']),save_pct=ratio(out['saves'],None if out['saves'] is None or out['goalsAgainst'] is None else out['saves']+out['goalsAgainst']))
    return out

def payload(year, segment=None):
    d=ROOT/'data/processed'/str(year)
    if segment and (year not in SPLIT_YEARS or segment not in ('regular','post','champ_series') or (segment=='champ_series' and year not in CHAMPIONSHIP_GAME_IDS)):
        raise ValueError('Unsupported competition/year')
    if segment=='champ_series':d=ROOT/'data/competitions'/str(year)/'champ_series/processed'
    def inputs(name):return read(d/(name+'.csv')) if segment=='champ_series' else read_current(year,name)
    publication=ROOT/'data/publication'/str(year)
    if segment: publication=publication/segment
    summaries=read(publication/'player_season_summary.csv')
    games={r['game_id'] for r in inputs('games') if r['is_completed']=='True' and r['include_in_league_analytics']=='True' and r['is_all_star']=='False' and (not segment or r['season_segment']==('champseries' if segment=='champ_series' else segment))}
    stints=[dict(r, player_id=r['officialId'], team_id=r['teamId'], games_played=1)
            for r in inputs('player_game_stats') if r['game_id'] in games]
    groups=defaultdict(list)
    for r in stints:groups[r['player_id']].append(r)
    players=[]
    for row in summaries:
        pid=row['player_id'];level=row['aggregation_level'];team=row['team_id']
        matches=groups[pid] if level=='SEASON' else [s for s in groups[pid] if s['team_id']==team]
        if not matches:raise ValueError(f'Missing traditional source {year}/{pid}/{team}')
        advanced={k:number(v) for k,v in row.items() if k not in ['season','player_id','team_id','aggregation_level','player_name','positions']}
        players.append(dict(id=pid,name=row['player_name'],team=team,teams=sorted({s['team_id'] for s in matches}),position=row['positions'] or 'UNK',level=level,season=year,traditional=traditional(matches),advanced=advanced))
    team_boxes=defaultdict(list)
    for r in inputs('team_game_stats'):
        if r['game_id'] in games:team_boxes[r['officialId']].append(r)
    names={r['team_id']:r['full_name'] for r in read(d/'teams.csv')}
    teams=[]
    for row in read(publication/'team_advanced_stats.csv'):
        tid=row['team_id'];boxes=team_boxes[tid]
        if not boxes:raise ValueError(f'Missing team box source {year}/{tid}')
        converted=[dict(b,games_played=1,points=b['scores']) for b in boxes]
        teams.append(dict(id=tid,name=names.get(tid,tid),team=tid,teams=[tid],position='',season=year,level='SEASON',traditional=traditional(converted),advanced={k:number(v) for k,v in row.items() if k not in ['season','team_id']}))
    coverage=read(publication/'publication_coverage.csv')[0]
    result=dict(season=year,players=players,teams=teams,partial=coverage['frozen_partial_season']=='True',cutoff=coverage['latest_game_start_utc'],segment=segment or 'combined',games=len(games))
    if year in SPLIT_YEARS and segment is None:
        result['segments']={key:payload(year,key) for key in ('regular','post')}
        if year in CHAMPIONSHIP_GAME_IDS:result['segments']['champ_series']=payload(year,'champ_series')
        else:result['segments']['champ_series']=dict(season=2022,players=[],teams=[],partial=False,cutoff=None,segment='champ_series',games=0,status='not_held',message='No Championship Series was held in 2022. The first Sixes tournament took place in February 2023.')
    if segment=='champ_series':
        result.update(status='limited',message=f'Sixes: {len(games)} games, separate tournament baseline. Possession and pace metrics are unavailable because the field possession model is not validated for Sixes.')
    return result

def main():
    out=FRONT/'dist';out.mkdir(exist_ok=True)
    for file in (FRONT/'src').iterdir():
        if file.is_file():shutil.copyfile(file,out/file.name)
    (out/'data').mkdir(exist_ok=True)
    for year in range(2022,2027):
        (out/'data'/f'{year}.json').write_text(json.dumps(payload(year),allow_nan=False,separators=(',',':'))+'\n')
    dictionary=read(ROOT/'data/publication/metric_dictionary.csv')
    (out/'data/metrics.json').write_text(json.dumps({r['metric_name']:{k:r[k] for k in ['display_name','interpretation','limitation_summary','unit']} for r in dictionary},ensure_ascii=False)+'\n')
    sources=[]
    for y in range(2022,2027):
        sources.append(ROOT/'data/processed'/str(y)/'teams.csv')
        for name in ['games','player_game_stats','team_game_stats']:
            sources.extend(input_paths(y,name))
        sources.extend(ROOT/'data/publication'/str(y)/f for f in ['player_season_summary.csv','team_advanced_stats.csv','publication_coverage.csv'])
    for y in SPLIT_YEARS:sources.extend((ROOT/'data/publication'/str(y)).glob('*/*.csv'))
    for y in CHAMPIONSHIP_GAME_IDS:sources.extend((ROOT/'data/competitions'/str(y)/'champ_series/processed').glob('*.csv'))
    (out/'data/provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2)+'\n')
    print('Built local frontend: five seasons, publication values copied without recalculation.')
if __name__=='__main__':main()
