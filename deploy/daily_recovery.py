"""Inactive daily assembly/upload/isolated-restore orchestration."""
import argparse
import fcntl
import json
from pathlib import Path
import uuid
from deploy.assemble_recovery import assemble
from deploy.recovery import execute, private_file
from deploy.restore_recovery import verify

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(private_file(args.config).read_text())
    root = Path(config['recovery_root'])
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run = uuid.uuid4().hex
        try:
            assemble(config['assembly'], root / ('set-' + run))
            backup = config['backup']
            execute(backup, 'backup', root / ('set-' + run))
            state = json.loads(Path(backup['backup_state']).read_text())
            backup['restore_snapshot'] = state['snapshot']
            verify(backup, root / ('restore-' + run))
            print(json.dumps({'daily_recovery_verified': True}))
        except Exception:
            print(json.dumps({'daily_recovery_failed': True, 'private_evidence_retained': True}))
            raise SystemExit(1)
