"""Import only the three late-2026 games into a versioned publication update.

Online retrieval is explicit (--fetch). Offline rebuilds validate cached endpoints.
The historical raw files, canonical manifests, and research outputs stay frozen.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
import pll_ingest_season as ingest
import pll_build_tables as tables
import pll_build_possessions as possessions
ROOT = Path(__file__).resolve().parents[1]
UPDATE = ROOT / 'data/updates/2026'
SLUGS = ('2026-semifinal-1', '2026-semifinal-2', '2026-championship-game')

def main(fetch=False):
    raw = UPDATE / 'raw'
    out = UPDATE / 'processed'
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    schedule_path = raw / '_schedule/games_2026.json'
    if fetch:
        if schedule_path.exists():
            raise ValueError('Update already retrieved; rebuild offline or review a new version explicitly')
        schedule = ingest.fetch_json(ingest.BASE_URL + '/games?year=2026', 'schedule')
        ingest.atomic_write_json(schedule_path, schedule)
        for slug in SLUGS:
            metadata = {}
            for endpoint, template in ingest.ENDPOINTS.items():
                url = ingest.BASE_URL + '/' + template.format(slug=slug)
                data = ingest.fetch_json(url, slug)
                status, detail = ingest.validate_payload(endpoint, data)
                if status != 'ok':
                    raise ValueError(f'{slug}/{endpoint}: {status}: {detail}')
                path = raw / slug / (endpoint + '.json')
                ingest.atomic_write_json(path, data)
                metadata[endpoint] = dict(source_url=url, retrieved_at=ingest.utc_now_iso(),
                                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            ingest.atomic_write_json(raw / slug / '_meta.json', metadata)
    schedule = json.loads(schedule_path.read_text())
    selected = [g for g in schedule['data']['items'] if g['slugname'] in SLUGS]
    if len(selected) != 3 or any(not tables.is_completed(g) or g['seasonSegment'] != 'post' for g in selected):
        raise ValueError('Expected exactly three completed postseason games')
    for slug in SLUGS:
        for endpoint in ingest.ENDPOINTS:
            data = json.loads((raw / slug / (endpoint + '.json')).read_text())
            if ingest.validate_payload(endpoint, data)[0] != 'ok':
                raise ValueError(f'Invalid cached {slug}/{endpoint}')
    tables.set_season(2026)
    tables.RAW_DIR = raw
    games = tables.build_games_table()
    games = games[games.game_slug.isin(SLUGS)].reset_index(drop=True)
    events, empty = tables.build_events_table(list(SLUGS), games)
    if empty or events.duplicated(['game_id', 'event_id']).any():
        raise ValueError('Empty or duplicate normalized event feed')
    players = tables.build_player_game_stats(list(SLUGS), games)
    teams, exceptions = tables.build_team_game_stats(list(SLUGS), games)
    if len(exceptions) or tables.validate_team_game_stats(teams, games):
        raise ValueError('Invalid team-game attribution')
    for name, frame in [('games', games), ('events', events), ('player_game_stats', players), ('team_game_stats', teams)]:
        frame.to_csv(out / (name + '.csv'), index=False)
    tables.build_teams_table(list(SLUGS), games).to_csv(out/'teams.csv', index=False)
    possessions.set_season(2026)
    possessions.DATA_DIR = out
    pos = possessions.main()
    import pll_validate_possessions as validation
    validation.set_season(2026)
    validation.DATA_DIR = out
    report = validation.main()
    if (report.status == 'FAIL').any():
        raise ValueError('Possession hard validation failed')
    checks = []
    for g in games.itertuples():
        ep = events[events.game_id == g.game_id]
        pp = pos[pos.game_id == g.game_id]
        for team, score in [(g.home_team_id, g.home_score), (g.away_team_id, g.away_score)]:
            actual = pp.loc[pp.offense_team_id == team, 'points_scored'].sum()
            if actual != score:
                raise ValueError(f'{g.game_slug}: possession score {actual} != official {score}')
        checks.append(dict(game_id=g.game_id, game_slug=g.game_slug, events=len(ep), possessions=len(pp),
                           home_score=g.home_score, away_score=g.away_score, status='PASS'))
    pd.DataFrame(checks).to_csv(UPDATE / 'validation.csv', index=False)
    files = [p for folder in [raw, out] for p in sorted(folder.rglob('*')) if p.is_file()]
    manifest = dict(version='2026-postseason-update-1', foundation='canonical-v2',
                    added_game_ids=games.game_id.tolist(),
                    artifact_sha256={str(p.relative_to(UPDATE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    ingest.atomic_write_json(UPDATE / 'manifest.json', manifest)
    print(pd.DataFrame(checks).to_string(index=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    main(parser.parse_args().fetch)
