"""Inactive encrypted recovery tooling; owner configuration required."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import subprocess


def private_file(path):
    path = Path(path)
    info = path.stat()
    if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or
            info.st_uid != os.getuid() or info.st_nlink != 1):
        raise ValueError('Recovery credentials require private regular files')
    return path


def validate_set(root):
    """Manifest is produced from a quiescent DB snapshot, never from live jobs."""
    manifest = json.loads((root / 'recovery.json').read_text())
    required = {'database', 'epoch', 'evidence', 'configuration', 'secrets', 'release', 'images'}
    if set(manifest['categories']) != required or not manifest.get('database_evidence_verified'):
        raise ValueError('Incomplete or unverified database/evidence recovery set')
    listed = manifest['files']
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    if actual != set(listed) | {'recovery.json'}:
        raise ValueError('Unlisted recovery material')
    for name, expected in listed.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe recovery path')
        path = root / relative
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
            raise ValueError('Unsafe recovery file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Recovery checksum mismatch')
        if any(word in name.lower() for word in ('cleanup-token', 'restic-password', 'backup-credentials', '__pycache__')):
            raise ValueError('Excluded recovery material')
    for category in required:
        if not manifest['categories'][category] or not set(manifest['categories'][category]) <= set(listed):
            raise ValueError('Missing recovery category')
    return manifest


STATE_SCHEMA = 'mldsafail.recovery-state.v1'


def validate_verified_state(config, *, now=None, expected_snapshot=None):
    """Accept only a private, versioned, exact restored snapshot receipt."""
    from deploy.recovery_journal import safe_path
    path = safe_path(Path(config['backup_state']))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                info.st_mode & 0o077 or info.st_nlink != 1):
            raise ValueError('Recovery state requires owned private regular file')
        state = json.load(stream)
    return validate_verified_receipt(state, config, now=now, expected_snapshot=expected_snapshot)


def validate_verified_receipt(state, config, *, now=None, expected_snapshot=None):
    if not isinstance(state, dict): raise ValueError('Recovery state must be an object')
    now = now or datetime.now(timezone.utc)
    if (state.get('schema') != STATE_SCHEMA or state.get('repository') != config['repository'] or
            not isinstance(state.get('snapshot'), str) or not re.fullmatch(r'[a-f0-9]{64}', state['snapshot']) or
            state.get('restore_verified') is not True or state.get('cleanup_complete') is not True or
            not isinstance(state.get('epoch_id'), str) or not state['epoch_id'] or
            type(state.get('result_count')) is not int or state['result_count'] < 0 or
            not re.fullmatch(r'[a-f0-9]{64}', str(state.get('restored_manifest_sha256', ''))) or
            (expected_snapshot is not None and state['snapshot'] != expected_snapshot) or
            ('expected_epoch_id' in config and state['epoch_id'] != config['expected_epoch_id'])):
        raise ValueError('Invalid exact repository/snapshot restored identity or incomplete cleanup')
    timestamps = []
    for field in ('uploaded_at', 'verified_at'):
        value = state.get(field)
        if not isinstance(value, str): raise ValueError('Missing recovery timestamp')
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None or timestamp > now:
            raise ValueError('Invalid or future recovery timestamp')
        timestamps.append(timestamp)
    if timestamps[0] > timestamps[1]: raise ValueError('Verification precedes upload')
    return state


def validate_prune_state(config):
    expected = config.get('restore_verified_snapshot')
    if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise ValueError('Pruning requires exact repository/snapshot verified restoration and complete cleanup')
    return validate_verified_state(config, expected_snapshot=expected)


def execute(config, operation, recovery_set=None, destination=None, journal=None):
    binary = Path(config['restic_binary'])
    if hashlib.sha256(binary.read_bytes()).hexdigest() != config['restic_sha256']:
        raise ValueError('Pinned restic binary checksum mismatch')
    password = private_file(config['password_file'])
    credentials = json.loads(private_file(config['credentials_file']).read_text())
    if config['environment'] not in {'staging', 'production'} or not config['repository'].endswith('/' + config['environment']):
        raise ValueError('Separate environment repositories required')
    if not config.get('owner_retained_recovery_key'):
        raise ValueError('Owner must retain the recovery key off host')
    if not set(credentials) <= {'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_DEFAULT_REGION'}:
        raise ValueError('Unexpected storage credential fields')
    if not config['repository'].startswith('s3:https://'):
        raise ValueError('HTTPS S3 repository required')
    env = {**os.environ, **credentials, 'RESTIC_REPOSITORY': config['repository'],
           'RESTIC_PASSWORD_FILE': str(password)}
    argv = [str(binary)]
    if operation == 'backup':
        validate_set(recovery_set)
        if password.is_relative_to(recovery_set) or Path(config['credentials_file']).is_relative_to(recovery_set):
            raise ValueError('Backup credentials inside recovery set')
        argv += ['backup', '--tag', config['environment'], str(recovery_set)]
    elif operation == 'check':
        argv += ['check', '--read-data']
    elif operation == 'prune':
        validate_prune_state(config)
        argv += ['forget', '--tag', config['environment'], '--keep-daily', '7',
                 '--keep-weekly', '4', '--keep-monthly', '6', '--prune']
    elif operation == 'restore':
        if not re.fullmatch(r'[a-f0-9]{64}', str(config.get('restore_snapshot', ''))):
            raise ValueError('Immutable full restore snapshot identity required')
        if destination is None or destination.exists():
            raise ValueError('Restore destination must be new and isolated')
        argv += ['restore', config['restore_snapshot'], '--target', str(destination)]
    else:
        raise ValueError('Unsupported operation')
    runner = journal.command if journal is not None else subprocess.run
    if operation == 'backup':
        argv.insert(1, '--json')
        response = runner(argv, env=env, check=True, capture_output=True,
                                  text=True, timeout=4 * 3600)
        records = [json.loads(line) for line in response.stdout.splitlines()]
        summary = next(row for row in records if row.get('message_type') == 'summary')
        snapshot = summary['snapshot_id']
        if not snapshot or summary.get('errors', 0):
            raise ValueError('Incomplete uploaded snapshot')
        state = Path(config['backup_state'])
        private = {'schema': STATE_SCHEMA, 'repository': config['repository'], 'snapshot': snapshot,
                   'uploaded_at': datetime.now(timezone.utc).isoformat(),
                   'restore_verified': False}
        from deploy.recovery_journal import atomic_json, safe_path
        atomic_json(safe_path(state), private)
    else:
        runner(argv, env=env, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=4 * 3600)
    return {'operation': operation, 'completed': True, 'restore_identity_verification_pending': operation == 'restore'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['backup', 'check', 'restore', 'prune'])
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--set', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    try:
        from deploy.recovery_journal import standalone_operation
        config = json.loads(private_file(args.config).read_text())
        print(json.dumps(standalone_operation(config, Path(config['backup_state']).parent, 'restic',
            lambda operation: execute(config, args.operation,
                args.set.resolve() if args.set else None, args.destination, journal=operation), args.cleanup)))
    except Exception:
        print(json.dumps({'recovery_operation_failed': True}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
