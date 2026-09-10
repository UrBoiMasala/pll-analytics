"""Validate both the immutable v1 Git snapshot and the current v2 artifacts."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT/'data/processed'
HIST = PROC/'history'


def manifest_failures():
    from pll_refocus_foundation import verify_checkpoint
    checkpoint = verify_checkpoint()
    old = json.loads((HIST/'CANONICAL_MANIFEST_V1.json').read_text())
    new = json.loads((HIST/'CANONICAL_MANIFEST_V2.json').read_text())
    failures=[]
    for relative, expected in old['artifact_hashes'].items():
        if expected is None:
            continue
        payload=subprocess.check_output(['git','show',checkpoint['checkpoint_commit']+':data/processed/'+relative],cwd=ROOT)
        if hashlib.sha256(payload).hexdigest()!=expected:
            failures.append('v1 checkpoint: '+relative)
    for relative, expected in new['artifact_hashes'].items():
        path=PROC/relative
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            failures.append('v2 current: '+relative)
    for relative, expected in new.get('transformation_sha256', {}).items():
        path=ROOT/relative
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            failures.append('v2 transformation: '+relative)
    return failures
