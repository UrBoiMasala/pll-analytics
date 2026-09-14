"""Presentation-only export. Reads frozen inputs; writes only frontend/dist."""
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FRONT=ROOT/'frontend'
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

def payload(year):
    d=ROOT/'data/processed'/str(year)
    summaries=read(ROOT/'data/publication'/str(year)/'player_season_summary.csv')
    stints=[r for r in read(ROOT/'data/processed/history/player_team_stints_2022_2026.csv') if int(r['season'])==year]
    groups=defaultdict(list)
    for r in stints:groups[r['player_id']].append(r)
    players=[]
    for row in summaries:
        pid=row['player_id'];level=row['aggregation_level'];team=row['team_id']
        matches=groups[pid] if level=='SEASON' else [s for s in groups[pid] if s['team_id']==team]
        if not matches:raise ValueError(f'Missing traditional source {year}/{pid}/{team}')
        advanced={k:number(v) for k,v in row.items() if k not in ['season','player_id','team_id','aggregation_level','player_name','positions']}
        players.append(dict(id=pid,name=row['player_name'],team=team,teams=sorted({s['team_id'] for s in matches}),position=row['positions'] or 'UNK',level=level,season=year,traditional=traditional(matches),advanced=advanced))
    games={r['game_id'] for r in read(d/'games.csv') if r['is_completed']=='True' and r['include_in_league_analytics']=='True' and r['is_all_star']=='False'}
    team_boxes=defaultdict(list)
    for r in read(d/'team_game_stats.csv'):
        if r['game_id'] in games:team_boxes[r['officialId']].append(r)
    names={r['team_id']:r['full_name'] for r in read(d/'teams.csv')}
    teams=[]
    for row in read(ROOT/'data/publication'/str(year)/'team_advanced_stats.csv'):
        tid=row['team_id'];boxes=team_boxes[tid]
        if not boxes:raise ValueError(f'Missing team box source {year}/{tid}')
        converted=[dict(b,games_played=1,points=b['scores']) for b in boxes]
        teams.append(dict(id=tid,name=names.get(tid,tid),team=tid,teams=[tid],position='',season=year,level='SEASON',traditional=traditional(converted),advanced={k:number(v) for k,v in row.items() if k not in ['season','team_id']}))
    coverage=read(ROOT/'data/publication'/str(year)/'publication_coverage.csv')[0]
    return dict(season=year,players=players,teams=teams,partial=coverage['frozen_partial_season']=='True',cutoff=coverage['latest_game_start_utc'])

def main():
    out=FRONT/'dist';out.mkdir(exist_ok=True)
    for file in (FRONT/'src').iterdir():
        if file.is_file():shutil.copyfile(file,out/file.name)
    (out/'data').mkdir(exist_ok=True)
    for year in range(2022,2027):
        (out/'data'/f'{year}.json').write_text(json.dumps(payload(year),allow_nan=False,separators=(',',':'))+'\n')
    dictionary=read(ROOT/'data/publication/metric_dictionary.csv')
    (out/'data/metrics.json').write_text(json.dumps({r['metric_name']:{k:r[k] for k in ['display_name','interpretation','limitation_summary','unit']} for r in dictionary},ensure_ascii=False)+'\n')
    sources=[ROOT/'data/processed/history/player_team_stints_2022_2026.csv']
    for y in range(2022,2027):
        sources.extend(ROOT/'data/processed'/str(y)/f for f in ['games.csv','teams.csv','team_game_stats.csv'])
        sources.extend(ROOT/'data/publication'/str(y)/f for f in ['player_season_summary.csv','team_advanced_stats.csv','publication_coverage.csv'])
    (out/'data/provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2)+'\n')
    print('Built local frontend: five seasons, publication values copied without recalculation.')
if __name__=='__main__':main()
