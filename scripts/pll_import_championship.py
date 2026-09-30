"""Import/validate the isolated Sixes tournaments; never infer field possessions."""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
import pll_ingest_season as ingest
import pll_build_tables as tables
ROOT=Path(__file__).resolve().parents[1]
from pll_competitions import CHAMPIONSHIP_GAME_IDS

def main(fetch=False,year=2023):
    if year not in CHAMPIONSHIP_GAME_IDS:raise ValueError('Unsupported Championship Series year')
    COMPETITION=ROOT/'data/competitions'/str(year)/'champ_series'
    SCHEDULE_URL=ingest.BASE_URL+f'/games?year={year}&includeCS=true'
    raw=COMPETITION/'raw';out=COMPETITION/'processed'
    schedule_path=raw/'_schedule'/f'games_{year}.json'
    if fetch:
        if schedule_path.exists():raise ValueError('Reviewed source exists; rebuild offline or review a new version')
        ingest.set_season(year)
        schedule=ingest.fetch_json(SCHEDULE_URL,'schedule')
        ingest.atomic_write_json(schedule_path,schedule)
        for g in schedule['data']['items']:
            if g['seasonSegment']!='champseries' or g.get('league')!='PLL':continue
            slug=g['slugname'];metadata={}
            for endpoint,template in ingest.ENDPOINTS.items():
                url=ingest.BASE_URL+'/'+template.format(slug=slug)
                data=ingest.fetch_json(url,slug)
                status,detail=ingest.validate_payload(endpoint,data)
                if status!='ok':raise ValueError((slug,endpoint,status,detail))
                path=raw/slug/(endpoint+'.json');ingest.atomic_write_json(path,data)
                metadata[endpoint]=dict(source_url=url,retrieved_at=ingest.utc_now_iso(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            ingest.atomic_write_json(raw/slug/'_meta.json',metadata)
    selected=[g for g in json.loads(schedule_path.read_text())['data']['items'] if g['seasonSegment']=='champseries' and g.get('league')=='PLL']
    if {g['id'] for g in selected}!=set(CHAMPIONSHIP_GAME_IDS[year]) or any(g['year']!=year or not tables.is_completed(g) for g in selected):
        raise ValueError(f'Unexpected completed Championship Series membership for {year}')
    for g in selected:
        slug=g['slugname'];meta=json.loads((raw/slug/'_meta.json').read_text())
        for endpoint in ingest.ENDPOINTS:
            path=raw/slug/(endpoint+'.json')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=meta[endpoint]['sha256']:raise ValueError('Changed cached source: '+str(path))
            if ingest.validate_payload(endpoint,json.loads(path.read_text()))[0]!='ok':raise ValueError('Invalid source: '+str(path))
    tables.set_season(year);tables.RAW_DIR=raw
    games=tables.build_games_table();games=games[games.game_id.isin(CHAMPIONSHIP_GAME_IDS[year])].copy()
    slugs=games.game_slug.tolist()
    # Keep field-specific faceoff/chronology repairs disabled during normalization.
    events,empty=tables.build_events_table(slugs,games)
    if empty or events.duplicated(['game_id','event_id']).any():raise ValueError('Incomplete/duplicate event input')
    invalid=((events.event_type=='goal')&(events.is_valid_goal==False)&events.shot_outcome.isna()) | (events.is_valid_penalty==False)
    events['is_analysis_eligible_event']=~events.is_duplicate_event.fillna(False)&~invalid.fillna(False)
    # Eligibility is local to this isolated competition; never part of field totals.
    games['include_in_league_analytics']=True;games['game_type']='championship_series'
    events['include_in_league_analytics']=True;events['game_type']='championship_series'
    players=tables.build_player_game_stats(slugs,games)
    teams,exceptions=tables.build_team_game_stats(slugs,games)
    if len(exceptions) or tables.validate_team_game_stats(teams,games):raise ValueError('Invalid team attribution')
    checks=[]
    for g in games.itertuples():
        e=events[events.game_id==g.game_id];valid=e[e.is_analysis_eligible_event]
        for team,score in [(g.home_team_id,g.home_score),(g.away_team_id,g.away_score)]:
            goals=valid[(valid.team_id==team)&(valid.is_valid_goal==True)]
            if (1+goals.is_two_point_attempt.astype(int)).sum()!=score:raise ValueError('Scoring mismatch')
            box=teams[(teams.game_id==g.game_id)&(teams.officialId==team)].iloc[0]
            shots=valid[(valid.team_id==team)&valid.event_type.isin(['shot','goal'])&valid.shot_outcome.notna()]
            if len(shots)!=box.shots:raise ValueError('Shot count mismatch')
        raw_events=json.loads((raw/g.game_slug/'play_by_play.json').read_text())['data']['items']
        checks.append(dict(game_id=g.game_id,events=len(e),score_reconciles=True,
            invalid_regulation_clocks=sum(x['period']<=4 and 60*x['minutes']+x['seconds']>480 for x in raw_events),
            backwards_time_steps=sum(b['secondsPassed']<a['secondsPassed'] for a,b in zip(raw_events,raw_events[1:])),
            possession_status='withheld_unvalidated_sixes_model'))
    out.mkdir(parents=True,exist_ok=True)
    for name,df in [('games',games),('events',events),('player_game_stats',players),('team_game_stats',teams),('teams',tables.build_teams_table(slugs,games))]:df.to_csv(out/(name+'.csv'),index=False)
    # Schema-only input lets supported SQL metrics run; no invented possessions.
    pd.read_csv(ROOT/'data/processed'/str(year)/'possessions.csv',nrows=0).to_csv(out/'possessions.csv',index=False)
    pd.DataFrame(checks).to_csv(COMPETITION/'validation.csv',index=False)
    files=sorted(p for folder in [raw,out] for p in folder.rglob('*') if p.is_file())
    manifest=dict(version=f'{year}-championship-series-1',schedule_url=SCHEDULE_URL,game_ids=sorted(games.game_id.tolist()),format='sixes',baseline=f'{year} Championship Series only',possession_metrics='withheld',artifact_sha256={str(p.relative_to(COMPETITION)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    ingest.atomic_write_json(COMPETITION/'manifest.json',manifest)
    print(pd.DataFrame(checks).to_string(index=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fetch',action='store_true');parser.add_argument('--year',type=int,choices=sorted(CHAMPIONSHIP_GAME_IDS),default=2023);args=parser.parse_args();main(args.fetch,args.year)
