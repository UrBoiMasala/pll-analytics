"""Build final SQL views and deterministic CSVs without rebuilding archived research."""
import argparse
from pathlib import Path
import duckdb
ROOT = Path(__file__).resolve().parent.parent
TABLES = ['team_advanced_stats','player_offensive_advanced','player_shooting_advanced','player_two_point_stats','faceoff_advanced','goalie_advanced','defensive_production','player_season_summary','possession_length_analysis','season_baselines','team_game_publication','publication_coverage','possession_sensitivity']
INPUTS = dict(games='games',events='events',possessions='possessions',players='player_game_stats',teams='team_game_stats')

def connect(database=':memory:'):
    con=duckdb.connect(str(database)); con.execute("SET TimeZone='UTC'")
    for name, filename in INPUTS.items():
        parts=[]
        for season in range(2022,2027):
            path=str(ROOT/'data/processed'/str(season)/(filename+'.csv')).replace("'","''")
            ids={'players':"{'officialId':'VARCHAR','teamId':'VARCHAR'}",'events':"{'player_id':'VARCHAR','goalie_id':'VARCHAR','event_id':'VARCHAR','team_id':'VARCHAR'}",'teams':"{'officialId':'VARCHAR'}"}.get(name,"{'game_id':'BIGINT'}")
            parts.append(f"SELECT {season} AS season,* FROM read_csv_auto('{path}',types={ids},sample_size=-1)")
        con.execute(f"CREATE OR REPLACE TABLE raw_{name} AS "+' UNION ALL BY NAME '.join(parts))
    con.execute((ROOT/'sql/publication.sql').read_text())
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

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'data/publication')
    parser.add_argument('--database',default=':memory:');args=parser.parse_args()
    from pll_publication_catalog import write_dictionary
    con=connect(args.database);export(con,args.output);write_dictionary(args.output);con.close()
    print('Built 13 final tables, five season slices each; metrics calculated in SQL.')
if __name__=='__main__': main()
