"""Independent display-data checks against canonical box scores and publication CSVs."""
import csv
import importlib.util
import json
import unittest
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('frontend_build',ROOT/'frontend/scripts/build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def rows(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def numeric(s):return None if s=='' else float(s)

class SourceChecks(unittest.TestCase):
    def test_every_advanced_value_matches_publication(self):
        for year in range(2022,2027):
            data=build.payload(year)
            source={(r['player_id'],r['aggregation_level'],r['team_id']):r for r in rows(ROOT/f'data/publication/{year}/player_season_summary.csv')}
            self.assertEqual(len(data['players']),len(source))
            for p in data['players']:
                r=source[p['id'],p['level'],p['team']]
                for key,val in p['advanced'].items():self.assertEqual(val,numeric(r[key]),(year,p['id'],key))
            source={r['team_id']:r for r in rows(ROOT/f'data/publication/{year}/team_advanced_stats.csv')}
            for t in data['teams']:
                for key,val in t['advanced'].items():self.assertEqual(val,numeric(source[t['id']][key]),(year,t['id'],key))

    def test_all_traditional_players_against_actual_game_rows(self):
        for year in range(2022,2027):
            d=ROOT/f'data/processed/{year}'
            valid={g['game_id'] for g in rows(d/'games.csv') if g['is_completed']=='True' and g['include_in_league_analytics']=='True' and g['is_all_star']=='False'}
            source=[p for p in rows(d/'player_game_stats.csv') if p['game_id'] in valid]
            for p in build.payload(year)['players']:
                games=[r for r in source if r['officialId']==p['id'] and (p['level']=='SEASON' or r['teamId']==p['team'])]
                self.assertEqual(p['traditional']['games_played'],len(games))
                for key in ['goals','twoPointGoals','assists','points','shots','shotsOnGoal','groundBalls','causedTurnovers','turnovers','saves','goalsAgainst','faceoffsWon','faceoffs']:
                    vals=[numeric(r[key]) for r in games]
                    expected=None if any(v is None for v in vals) else sum(vals)
                    self.assertEqual(p['traditional'][key],expected,(year,p['id'],p['team'],key))

    def test_team_official_points_and_ratios(self):
        for year in range(2022,2027):
            d=ROOT/f'data/processed/{year}';valid={g['game_id'] for g in rows(d/'games.csv') if g['is_completed']=='True' and g['include_in_league_analytics']=='True' and g['is_all_star']=='False'}
            source=rows(d/'team_game_stats.csv')
            for t in build.payload(year)['teams']:
                games=[r for r in source if r['game_id'] in valid and r['officialId']==t['id']];v=t['traditional']
                for key in ['goals','twoPointGoals','assists','shots','shotsOnGoal','groundBalls','turnovers','numPenalties']:
                    self.assertEqual(v[key],sum(float(r[key]) for r in games))
                self.assertEqual(v['points'],sum(float(r['scores']) for r in games))
                self.assertAlmostEqual(v['faceoff_pct'],sum(float(r['faceoffsWon']) for r in games)/sum(float(r['faceoffs']) for r in games))
                self.assertAlmostEqual(v['save_pct'],sum(float(r['saves']) for r in games)/sum(float(r['saves'])+float(r['goalsAgainst']) for r in games))

    def test_exported_bundle_is_current_and_valid_json(self):
        for year in range(2022,2027):
            data=json.loads((ROOT/f'frontend/dist/data/{year}.json').read_text());self.assertEqual(data,build.payload(year));self.assertEqual(data['partial'],year==2026)

    def test_zero_and_missing_are_distinct(self):
        self.assertIsNone(build.ratio(0,0));self.assertEqual(build.ratio(0,10),0);self.assertIsNone(build.total([{'shots':''},{'shots':'1'}],'shots'))

if __name__=='__main__':unittest.main()
