"""Inactive daily recovery with durable interruption cleanup and local retention."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import uuid
from deploy.assemble_recovery import assemble
from deploy.recovery import execute, private_file, validate_set
from deploy.recovery_journal import Journal, atomic_json, safe_path
from deploy.restore_recovery import verify


def remove_owned(root, name):
    if not isinstance(name, str) or not any(name.startswith(prefix) and len(name) == len(prefix) + 32
                                           and all(c in '0123456789abcdef' for c in name[len(prefix):])
                                           for prefix in ('set-', 'restore-')):
        raise ValueError('Invalid run-owned directory')
    path = safe_path(root / name)
    if path.exists():
        if not path.is_dir() or any(p.is_symlink() for p in path.rglob('*')):
            raise ValueError('Unsafe recovery deletion')
        shutil.rmtree(path)


def prune(root, repository, keep):
    if type(keep) is not int or keep < 1:
        raise ValueError('Retain at least one verified set')
    records = []
    for path in (root / 'journals').glob('run-*.json'):
        safe_path(path)
        record = json.loads(private_file(path).read_text())
        run_id = path.stem.removeprefix('run-')
        if record.get('set_directory') != 'set-' + run_id or record.get('restore_directory') != 'restore-' + run_id:
            raise ValueError('Run ownership mismatch')
        if (record.get('repository') == repository and record.get('verified_at') and
                record.get('cleanup_complete') and record.get('restore_verified')):
            records.append((record['verified_at'], path, record))
    for _, path, record in sorted(records, reverse=True):
        if not record.get('pruned'):
            remove_owned(root, record['restore_directory'])
    retained = [row for row in sorted(records, reverse=True) if not row[2].get('pruned')]
    for _, path, record in retained[keep:]:
        target = safe_path(root / record['set_directory'])
        if target.exists() or not record.get('prune_pending'):
            validate_set(target)
        record['prune_pending'] = True
        atomic_json(path, record)
        remove_owned(root, record['set_directory'])
        record['pruned'] = True
        atomic_json(path, record)


def run(config, cleanup_only=False):
    root = safe_path(config['recovery_root'])
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    journals = safe_path(root / 'journals')
    journals.mkdir(mode=0o700, exist_ok=True)
    with safe_path(root / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        operation = Journal(journals / 'operation.json', config)
        if not operation.data['cleanup_complete']:
            operation.cleanup()
        if cleanup_only:
            return {'cleanup_complete': True}
        keep = config.get('local_verified_sets_to_keep', 2)
        if type(keep) is not int or keep < 1:
            raise ValueError('Invalid local retention count')
        if shutil.disk_usage(root).free < 5 * 1024**3:
            raise RuntimeError('disk: recovery floor below 5 GiB; failed evidence preserved')
        run_id = uuid.uuid4().hex
        operation.data.update(services={}, containers=[], run_id=run_id)
        operation.save('preflight complete')
        record_path = journals / ('run-' + run_id + '.json')
        backup = dict(config['backup'])
        record = dict(repository=backup['repository'], set_directory='set-' + run_id,
                      restore_directory='restore-' + run_id, cleanup_complete=False,
                      restore_verified=False)
        atomic_json(record_path, record)
        try:
            operation.save('assembly intent')
            assemble(config['assembly'], root / record['set_directory'], operation=operation)
            operation.save('upload intent')
            execute(backup, 'backup', root / record['set_directory'])
            state = json.loads(Path(backup['backup_state']).read_text())
            if state['repository'] != backup['repository']:
                raise ValueError('Backup repository mismatch')
            backup['restore_snapshot'] = state['snapshot']
            record['snapshot'] = state['snapshot']
            atomic_json(record_path, record)
            operation.save('verification intent')
            verified = verify(backup, root / record['restore_directory'], operation=operation)
            operation.cleanup()
            record.update(restore_verified=True, cleanup_complete=True,
                          verified_at=datetime.now(timezone.utc).isoformat())
            atomic_json(record_path, record)
            atomic_json(safe_path(backup['backup_state']), verified)
            prune(root, backup['repository'], keep)
            return {'daily_recovery_verified': True}
        finally:
            if not operation.data['cleanup_complete']:
                operation.cleanup()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    def interrupted(*_):
        # Ignore subsequent signals while finally cleanup runs; SIGKILL/restart
        # are recovered from the durable journal by ExecStopPost/next invocation.
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        raise InterruptedError('Recovery interrupted')
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    try:
        print(json.dumps(run(json.loads(private_file(args.config).read_text()), args.cleanup)))
    except Exception:
        print(json.dumps({'daily_recovery_failed': True, 'private_evidence_retained': True}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
