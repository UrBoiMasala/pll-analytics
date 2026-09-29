"""Source archives retain historical verification without local Git history."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pll_canonical_versions as versions
import pll_refocus_foundation as foundation


@pytest.fixture
def checkpoint(tmp_path, monkeypatch):
    hist = tmp_path / 'data/processed/history'
    hist.mkdir(parents=True)
    (tmp_path / 'archive').mkdir()
    payload = b'game_id\n1\n'
    (hist / 'CANONICAL_MANIFEST_V1.json').write_text(json.dumps({
        'artifact_hashes': {'2022/games.csv': hashlib.sha256(payload).hexdigest()}
    }))
    (hist / 'CANONICAL_MANIFEST_V2.json').write_text(json.dumps({'artifact_hashes': {}}))
    monkeypatch.setattr(versions, 'ROOT', tmp_path)
    monkeypatch.setattr(versions, 'PROC', hist.parent)
    monkeypatch.setattr(versions, 'HIST', hist)
    monkeypatch.setattr(foundation, 'verify_checkpoint', lambda: {'checkpoint_commit': 'original'})
    return tmp_path / 'archive/canonical-v1.zip', payload


def test_portable_archive_verifies_without_git(checkpoint, monkeypatch):
    archive, payload = checkpoint
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('data/processed/2022/games.csv', payload)
    def reject_git(*args, **kwargs):
        raise AssertionError('Portable verification must not require Git')
    monkeypatch.setattr(versions.subprocess, 'check_output', reject_git)
    assert versions.manifest_failures() == []


def test_modified_checkpoint_is_rejected(checkpoint):
    archive, _ = checkpoint
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('data/processed/2022/games.csv', b'game_id\n999\n')
    assert versions.manifest_failures() == ['v1 checkpoint: 2022/games.csv']


def test_missing_checkpoint_member_is_not_silently_skipped(checkpoint):
    archive, _ = checkpoint
    with zipfile.ZipFile(archive, 'w'):
        pass
    with pytest.raises(KeyError):
        versions.manifest_failures()
