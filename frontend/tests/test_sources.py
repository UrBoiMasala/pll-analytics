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
            valid={g['game_id'] for g in build.read_current(year,'games') if g['is_completed']=='True' and g['include_in_league_analytics']=='True' and g['is_all_star']=='False'}
            source=[p for p in build.read_current(year,'player_game_stats') if p['game_id'] in valid]
            for p in build.payload(year)['players']:
                games=[r for r in source if r['officialId']==p['id'] and (p['level']=='SEASON' or r['teamId']==p['team'])]
                self.assertEqual(p['traditional']['games_played'],len(games))
                for key in ['goals','twoPointGoals','assists','points','shots','shotsOnGoal','groundBalls','causedTurnovers','turnovers','saves','goalsAgainst','faceoffsWon','faceoffs']:
                    vals=[numeric(r[key]) for r in games]
                    expected=None if any(v is None for v in vals) else sum(vals)
                    self.assertEqual(p['traditional'][key],expected,(year,p['id'],p['team'],key))

    def test_team_official_points_and_ratios(self):
        for year in range(2022,2027):
            d=ROOT/f'data/processed/{year}';valid={g['game_id'] for g in build.read_current(year,'games') if g['is_completed']=='True' and g['include_in_league_analytics']=='True' and g['is_all_star']=='False'}
            source=build.read_current(year,'team_game_stats')
            for t in build.payload(year)['teams']:
                games=[r for r in source if r['game_id'] in valid and r['officialId']==t['id']];v=t['traditional']
                for key in ['goals','twoPointGoals','assists','shots','shotsOnGoal','groundBalls','turnovers','numPenalties']:
                    self.assertEqual(v[key],sum(float(r[key]) for r in games))
                self.assertEqual(v['points'],sum(float(r['scores']) for r in games))
                self.assertAlmostEqual(v['faceoff_pct'],sum(float(r['faceoffsWon']) for r in games)/sum(float(r['faceoffs']) for r in games))
                self.assertAlmostEqual(v['save_pct'],sum(float(r['saves']) for r in games)/sum(float(r['saves'])+float(r['goalsAgainst']) for r in games))

    def test_exported_bundle_is_current_and_valid_json(self):
        for year in range(2022,2027):
            data=json.loads((ROOT/f'frontend/dist/data/{year}.json').read_text());self.assertEqual(data,build.payload(year));self.assertFalse(data['partial'])

    def test_2022_competition_sources(self):
        for year in range(2022,2027):
            for segment, count in [('regular',48 if year==2026 else 40),('post',6 if year<=2023 else 5)]:
                data=build.payload(year,segment)
                self.assertEqual(data['games'],count)
                source={(r['player_id'],r['aggregation_level'],r['team_id']):r for r in rows(ROOT/f'data/publication/{year}/{segment}/player_season_summary.csv')}
                valid={g['game_id'] for g in build.read_current(year,'games') if g['season_segment']==segment and g['is_completed']=='True'}
                raw=[p for p in build.read_current(year,'player_game_stats') if p['game_id'] in valid]
                for p in data['players']:
                    for key,val in p['advanced'].items():self.assertEqual(val,numeric(source[p['id'],p['level'],p['team']][key]))
                    games=[r for r in raw if r['officialId']==p['id'] and (p['level']=='SEASON' or r['teamId']==p['team'])]
                    self.assertEqual(p['traditional']['games_played'],len(games))
                    for key in ['goals','shots','points','saves','faceoffs']:
                        self.assertEqual(p['traditional'][key],sum(float(r[key]) for r in games))
        empty=build.payload(2022)['segments']['champ_series']
        self.assertEqual(empty['status'],'not_held');self.assertEqual(empty['players'],[]);self.assertEqual(empty['teams'],[])

    def test_sixes_display_values(self):
        for year in range(2023,2027):
            data=build.payload(year,'champ_series')
            self.assertEqual(data['games'],9 if year<=2024 else 8);self.assertEqual(data['status'],'limited')
            root=ROOT/f'data/competitions/{year}/champ_series/processed'
            raw=rows(root/'player_game_stats.csv')
            source={(r['player_id'],r['aggregation_level'],r['team_id']):r for r in rows(ROOT/f'data/publication/{year}/champ_series/player_season_summary.csv')}
            for p in data['players']:
                for key,value in p['advanced'].items():self.assertEqual(value,numeric(source[p['id'],p['level'],p['team']][key]))
                games=[r for r in raw if r['officialId']==p['id'] and (p['level']=='SEASON' or r['teamId']==p['team'])]
                self.assertEqual(p['traditional']['games_played'],len(games))
                for key in ['goals','twoPointGoals','shots','saves','goalsAgainst','faceoffs','faceoffsWon','points']:
                    self.assertEqual(p['traditional'][key],sum(float(r[key]) for r in games))
            for t in data['teams']:self.assertIsNone(t['advanced']['offensive_efficiency'])

    def test_zero_and_missing_are_distinct(self):
        self.assertIsNone(build.ratio(0,0));self.assertEqual(build.ratio(0,10),0);self.assertIsNone(build.total([{'shots':''},{'shots':'1'}],'shots'))

if __name__=='__main__':unittest.main()
