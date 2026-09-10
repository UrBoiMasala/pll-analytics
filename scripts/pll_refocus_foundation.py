"""Rebuild the retained foundation and canonical v2; never fetch or edit raw data.

The v1 manifest and checkpoint commit are immutable comparison references.
Legacy value/reliability/research products are deliberately not rebuilt here.
"""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import pandas as pd
import duckdb
import pll_build_tables as tables
import pll_build_possessions as possessions
import pll_build_team_metrics as team_metrics
import pll_player_value_models as models

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / 'data/processed'
HIST = PROC / 'history'
SEASONS = range(2022, 2027)
STINT_COUNTS = ['shots', 'shotsOnGoal', 'goals', 'onePointGoals', 'twoPointGoals',
                'twoPointShots', 'points', 'assists', 'touches', 'turnovers',
                'faceoffs', 'faceoffsWon', 'faceoffsLost', 'saves', 'goalsAgainst',
                'twoPointGoalsAgainst', 'groundBalls', 'causedTurnovers', 'numPenalties']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checkpoint():
    checkpoint = json.loads((HIST / 'refocus_source_checkpoint.json').read_text())
    actual = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'data/raw').rglob('*')) if p.is_file()}
    if actual != checkpoint['raw_sha256']:
        raise ValueError('Raw file set or contents changed since checkpoint')
    if sha(HIST / 'CANONICAL_MANIFEST_V1.json') != checkpoint['canonical_v1_sha256']:
        raise ValueError('Canonical v1 manifest changed')
    return checkpoint


def original_csv(relative):
    checkpoint = json.loads((HIST / 'refocus_source_checkpoint.json').read_text())
    data = subprocess.check_output(['git', 'show', checkpoint['checkpoint_commit'] + ':' + relative], cwd=ROOT)
    return pd.read_csv(io.BytesIO(data), low_memory=False)


def player_team_stints(players, games):
    """Exact game-team attribution. Season totals can be summed across stints.

    No modal-team assignment and no allocation by games-played fractions.
    IDs stay strings, including leading zeroes. Zero denominators remain NULL
    in the future metric layer; this table stores counts only.
    """
    if games['game_id'].duplicated().any():
        raise ValueError('Duplicate game key')
    if players.duplicated(['game_id', 'officialId']).any():
        raise ValueError('Duplicate player-game key')
    eligible = games.loc[games.is_completed & games.include_in_league_analytics & ~games.is_all_star]
    p = players.merge(eligible[['game_id', 'home_team_id', 'away_team_id']], on='game_id', validate='many_to_one')
    if not ((p.teamId == p.home_team_id) | (p.teamId == p.away_team_id)).all():
        raise ValueError('Player assigned to nonparticipating team')
    cols = [c for c in STINT_COUNTS if c in p]
    grouped = p.groupby(['officialId', 'teamId'], sort=True)
    out = grouped[cols].sum(min_count=1)
    out.insert(0, 'games_played', grouped.game_id.nunique())
    return out.reset_index().rename(columns={'officialId': 'player_id', 'teamId': 'team_id'})


def main():
    checkpoint = verify_checkpoint()
    impacts, stints, outputs = [], [], []
    for year in SEASONS:
        directory = PROC / str(year)
        tables.set_season(year)
        games = pd.read_csv(directory / 'games.csv')
        usable = [s for s in games.loc[games.is_completed, 'game_slug'] if not tables.missing_raw_endpoints(s)]
        events, _ = tables.build_events_table(usable, games)
        # Compare semantic values before deciding whether to rewrite the CSV.
        path = directory / 'events.csv'
        old = pd.read_csv(path, low_memory=False)
        try:
            pd.testing.assert_frame_equal(old, events, check_dtype=False)
        except AssertionError:
            events.to_csv(path, index=False)
        possessions.set_season(year)
        possessions.main()
        new = pd.read_csv(directory / 'possessions.csv')
        before = original_csv(f'data/processed/{year}/possessions.csv')
        keys = ['possession_id', 'offense_team_id', 'defense_team_id', 'start_event_id',
                'end_event_id', 'duration_seconds', 'points_scored', 'is_ambiguous', 'is_truncated']
        pd.testing.assert_frame_equal(before[keys], new[keys], check_dtype=False)
        for col in ['event_count', 'ground_balls']:
            impacts.append(dict(season=year, quantity=col, before=float(before[col].sum()),
                                after=float(new[col].sum()), changed_rows=int((before[col] != new[col]).sum())))
        for label, frame in [('before', before), ('after', new)]:
            mask = ~frame.is_ambiguous & ~frame.is_truncated
            mask &= (frame.event_count > 1) if label == 'before' else (frame.start_event_id != frame.end_event_id)
            if label == 'before':
                n0, avg0 = int(mask.sum()), float(frame.loc[mask, 'duration_seconds'].mean())
            else:
                impacts.extend([dict(season=year, quantity='measurable_spans', before=n0, after=int(mask.sum()), changed_rows=None),
                                dict(season=year, quantity='mean_measurable_span_seconds', before=avg0,
                                     after=float(frame.loc[mask, 'duration_seconds'].mean()), changed_rows=None)])
        old_events = original_csv(f'data/processed/{year}/events.csv')
        impacts.append(dict(season=year, quantity='chronology_flagged_rows', before=int(old_events.chronology_repair_applied.sum()),
                            after=int(events.chronology_repair_applied.sum()), changed_rows=int(events.chronology_repair_applied.sum()-old_events.chronology_repair_applied.sum())))
        team_metrics.DATA_DIR = directory
        con = duckdb.connect()
        for sql, table, filename in team_metrics.PIPELINE:
            team_metrics.run_sql_file(con, ROOT / 'sql' / sql, directory)
            if filename:
                team_metrics.export(con, table, filename)
        con.close()
        ev = models.load_eligible_events(directory)
        cv, _ = models.fit_shot_models(ev, data_dir=directory)
        cv['selected_model'] = cv.model == 'shot_class'
        cv['status'] = 'EXPERIMENTAL; fixed retrospective diagnostic; not predictive validation'
        cv.to_csv(directory / 'shot_model_validation.csv', index=False)
        p = pd.read_csv(directory / 'player_game_stats.csv', dtype={'officialId': str, 'teamId': str})
        stint = player_team_stints(p, games)
        stint.insert(0, 'season', year)
        stints.append(stint)
        outputs.extend([directory / f for f in ['games.csv', 'teams.csv', 'players.csv', 'events.csv', 'possessions.csv',
                       'player_game_stats.csv', 'team_game_stats.csv', 'team_game_advanced.csv', 'team_season_advanced.csv',
                       'team_rankings.csv', 'possession_length_splits.csv', 'team_metric_sensitivity.csv', 'shot_model_validation.csv']])
    pd.concat(stints, ignore_index=True).to_csv(HIST / 'player_team_stints_2022_2026.csv', index=False)
    pd.DataFrame(impacts).to_csv(HIST / 'refocus_foundation_impact.csv', index=False)
    outputs.extend([HIST / 'player_team_stints_2022_2026.csv', HIST / 'refocus_foundation_impact.csv'])
    manifest = dict(canonical_version='v2.0.0-refocus', parent_version='v1.0.0-phase11',
                    checkpoint_commit=checkpoint['checkpoint_commit'], parent_manifest_sha256=checkpoint['canonical_v1_sha256'],
                    raw_checkpoint='refocus_source_checkpoint.json', seasons=list(SEASONS),
                    definition='Retained foundation only. Legacy Phase 8-13 statistical/value outputs are archived and may describe v1.',
                    changes=['Unique possession boundary-event counts', 'Opening ground balls counted',
                             'Duration eligibility uses distinct boundary IDs', 'All transposed events flagged',
                             'Historical shot diagnostics use matching season metadata', 'Player-team stint counts preserve actual game team'],
                    transformation_sha256={str(p.relative_to(ROOT)): sha(p) for p in [ROOT/'scripts'/n for n in ['pll_build_possessions.py','pll_chronology_repair.py','pll_player_value_models.py','pll_refocus_foundation.py']] + [ROOT/'sql/00_base_views.sql']},
                    artifact_hashes={str(p.relative_to(PROC)): sha(p) for p in outputs})
    verify_checkpoint()
    (HIST / 'CANONICAL_MANIFEST_V2.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Canonical v2 written; raw hashes and v1 manifest unchanged.')


if __name__ == '__main__':
    main()
