"""Current publication inputs: immutable foundation plus explicit per-game updates.

An update replaces whole game partitions, never individual events. Research tools
continue reading the frozen foundation; publication and UI read this same overlay.
"""
import csv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def input_paths(year, filename):
    base = ROOT / 'data/processed' / str(year) / (filename + '.csv')
    update = ROOT / 'data/updates' / str(year) / 'processed' / (filename + '.csv')
    return [base, update] if update.exists() else [base]

def read_current(year, filename):
    paths = input_paths(year, filename)
    def read(path):
        with path.open(newline='') as f:
            return list(csv.DictReader(f))
    rows = read(paths[0])
    if len(paths) == 2:
        added = read(paths[1])
        ids = {r['game_id'] for r in added}
        rows = [r for r in rows if r['game_id'] not in ids] + added
    return rows

def current_frame(year, filename, **kwargs):
    import pandas as pd
    paths = input_paths(year, filename)
    frame = pd.read_csv(paths[0], **kwargs)
    if len(paths) == 2:
        added = pd.read_csv(paths[1], **kwargs)
        frame = pd.concat([frame[~frame.game_id.isin(added.game_id)], added], ignore_index=True)
    return frame
