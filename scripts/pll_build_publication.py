"""Build final SQL views and deterministic CSVs without rebuilding archived research."""
import argparse
from pathlib import Path
import duckdb
from pll_current_data import input_paths
ROOT = Path(__file__).resolve().parent.parent
TABLES = ['team_advanced_stats','player_offensive_advanced','player_shooting_advanced','player_two_point_stats','faceoff_advanced','goalie_advanced','defensive_production','player_season_summary','possession_length_analysis','season_baselines','team_game_publication','publication_coverage','possession_sensitivity']
from pll_competitions import SPLIT_YEARS, CHAMPIONSHIP_GAME_IDS
INPUTS = dict(games='games',events='events',possessions='possessions',players='player_game_stats',teams='team_game_stats')

def connect(database=':memory:', segment=None, year=2022):
    if segment not in (None, 'regular', 'post', 'champ_series') or (segment and year not in SPLIT_YEARS) or (segment=='champ_series' and year not in CHAMPIONSHIP_GAME_IDS):
        raise ValueError('Unsupported competition/year')
    con=duckdb.connect(str(database)); con.execute("SET TimeZone='UTC'")
    for name, filename in INPUTS.items():
        parts=[]
        for season in ([year] if segment=='champ_series' else range(2022,2027)):
            paths = ([ROOT/'data/competitions'/str(year)/'champ_series/processed'/(filename+'.csv')] if segment=='champ_series' else input_paths(season, filename))
            if segment=='champ_series' and name=='possessions':
                schema=str(ROOT/'data/processed'/str(year)/'possessions.csv').replace("'","''")
                parts.append(f"SELECT {year} AS season,* FROM read_csv_auto('{schema}',sample_size=-1) WHERE false")
                continue
            path = str(paths[0]).replace("'", "''")
            ids={'players':"{'officialId':'VARCHAR','teamId':'VARCHAR'}",'events':"{'player_id':'VARCHAR','goalie_id':'VARCHAR','event_id':'VARCHAR','team_id':'VARCHAR'}",'teams':"{'officialId':'VARCHAR'}"}.get(name,"{'game_id':'BIGINT'}")
            source = f"read_csv_auto('{path}',types={ids},sample_size=-1)"
            if len(paths) == 2:
                update = str(paths[1]).replace("'", "''")
                delta = f"read_csv_auto('{update}',types={ids},sample_size=-1)"
                parts.append(f"SELECT {season} AS season,* FROM {source} WHERE game_id NOT IN (SELECT game_id FROM {delta})")
                parts.append(f"SELECT {season} AS season,* FROM {delta}")
            else:
                parts.append(f"SELECT {season} AS season,* FROM {source}")
        con.execute(f"CREATE OR REPLACE TABLE raw_{name} AS "+' UNION ALL BY NAME '.join(parts))
    sql = (ROOT/'sql/publication.sql').read_text()
    con.execute(sql)
    if segment in ('regular','post'):
        # Freeze regular-season baselines before selecting a playoff sample.
        con.execute(f"CREATE OR REPLACE VIEW pub_games AS SELECT * FROM raw_games WHERE season={year} AND is_completed AND include_in_league_analytics AND NOT is_all_star AND season_segment='regular'")
        con.execute("CREATE TEMP TABLE regular_baselines AS SELECT * FROM season_baselines")
        con.execute(sql)
        con.execute(f"CREATE OR REPLACE VIEW pub_games AS SELECT * FROM raw_games WHERE season={year} AND is_completed AND include_in_league_analytics AND NOT is_all_star AND season_segment='" + segment + "'")
        con.execute("CREATE OR REPLACE VIEW season_baselines AS SELECT * FROM regular_baselines")
    if segment=='champ_series':
        con.execute("CREATE TEMP TABLE sixes_team_stats AS SELECT * REPLACE (NULL::BIGINT AS score_gap_games) FROM team_advanced_stats")
        con.execute("CREATE OR REPLACE VIEW team_advanced_stats AS SELECT * FROM sixes_team_stats")
        # Missing reconstruction is unknown, never zero possession coverage.
        con.execute("CREATE TEMP TABLE sixes_coverage AS SELECT * REPLACE (NULL::BIGINT AS eligible_possessions,NULL::BIGINT AS ambiguous_possessions,NULL::BIGINT AS measurable_possessions,NULL::DOUBLE AS scoring_gap) FROM publication_coverage")
        con.execute("CREATE OR REPLACE VIEW publication_coverage AS SELECT * FROM sixes_coverage")
    # Reject broken keys and dropped attribution; do not silently lose named players.
    guards = {
        'duplicate game': "SELECT count(*) FROM (SELECT season,game_id FROM raw_games GROUP BY ALL HAVING count(*)<>1)",
        'duplicate canonical event': "SELECT count(*) FROM (SELECT season,game_id,event_id FROM raw_events GROUP BY ALL HAVING count(*)<>1)",
        'duplicate possession': "SELECT count(*) FROM (SELECT season,possession_id FROM raw_possessions GROUP BY ALL HAVING count(*)<>1)",
        'invalid appearance team': "SELECT count(*) FROM raw_players p JOIN pub_games g USING(season,game_id) WHERE p.teamId IS NULL OR p.teamId NOT IN (g.home_team_id,g.away_team_id)",
        'duplicate player appearance': "SELECT count(*) FROM (SELECT season,game_id,officialId FROM pub_player_games GROUP BY ALL HAVING count(*)<>1)",
        'duplicate team game': "SELECT count(*) FROM (SELECT season,game_id,officialId FROM pub_team_games GROUP BY ALL HAVING count(*)<>1)",
        'missing player/team attribution': "SELECT count(*) FROM pub_shots s WHERE player_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pub_player_games p WHERE p.season=s.season AND p.game_id=s.game_id AND p.teamId=s.team_id AND p.officialId=s.player_id)",
        'missing goalie appearance': "SELECT count(*) FROM pub_goalie_games f WHERE NOT EXISTS (SELECT 1 FROM pub_player_games p WHERE p.season=f.season AND p.game_id=f.game_id AND p.teamId=f.team_id AND p.officialId=f.player_id)",
        'unknown shot class': "SELECT count(*) FROM pub_shots WHERE is_two_point_attempt IS NULL",
        'incomplete team spine': "SELECT count(*) FROM team_game_publication WHERE possessions IS NULL OR defensive_possessions IS NULL",
    }
    if segment=='champ_series':guards.pop('incomplete team spine')
    for label, query in guards.items():
        if con.execute(query).fetchone()[0]:
            con.close()
            raise ValueError(label)
    return con

def export(con, out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for table in TABLES:
        frame=con.execute(f'SELECT * FROM {table} ORDER BY ALL').df()
        frame.to_csv(out/(table+'.csv'),index=False,float_format='%.12g')
        for season in range(2022,2027):
            folder=out/str(season);folder.mkdir(exist_ok=True)
            frame[frame.season==season].to_csv(folder/(table+'.csv'),index=False,float_format='%.12g')

def export_splits(out):
    for year in SPLIT_YEARS:
        for segment in (('regular','post','champ_series') if year in CHAMPIONSHIP_GAME_IDS else ('regular','post')):
            con = connect(segment=segment, year=year)
            folder = Path(out)/str(year)/segment
            folder.mkdir(parents=True, exist_ok=True)
            for table in TABLES:
                con.execute(f'SELECT * FROM {table} ORDER BY ALL').df().to_csv(
                    folder/(table+'.csv'), index=False, float_format='%.12g')
            con.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'data/publication')
    parser.add_argument('--database',default=':memory:');args=parser.parse_args()
    from pll_publication_catalog import write_dictionary
    con=connect(args.database);export(con,args.output);write_dictionary(args.output);con.close();export_splits(args.output)
    print('Built 13 final tables, five season slices each; metrics calculated in SQL.')
if __name__=='__main__': main()
