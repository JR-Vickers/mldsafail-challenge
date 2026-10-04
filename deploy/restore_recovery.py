"""Restore-check sealed recovery material in disposable private containers."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import uuid
from deploy.recovery import execute, private_file, validate_set


def verify(config, destination, operation=None):
    execute(config, 'restore', destination=destination, journal=operation)
    roots = list(destination.rglob('recovery.json'))
    if len(roots) != 1:
        raise ValueError('Restore must contain exactly one recovery set')
    root = roots[0].parent
    manifest = validate_set(root)
    dumps = list((root / 'database').glob('*.dump'))
    if len(dumps) != 1:
        raise ValueError('Exactly one database snapshot required')
    for key in ['postgres_image', 'coordinator_image']:
        if not config[key].startswith('sha256:') or len(config[key]) != 71:
            raise ValueError('Immutable restore images required')
    name = 'restore-' + uuid.uuid4().hex
    identifier = None
    def command(argv, **kwargs):
        timeout = kwargs.pop('timeout', 60)
        if operation:
            return operation.command(argv, stderr=subprocess.DEVNULL, capture_output=True,
                                     check=True, timeout=timeout, **kwargs).stdout
        return subprocess.check_output(argv, stderr=subprocess.DEVNULL, timeout=timeout, **kwargs)
    run_command = operation.command if operation else subprocess.run
    if operation:
        operation.container(name, config['postgres_image'])
    try:
        identifier = command(['docker', 'run', '-d', '--name', name, '--network', 'none',
                    '--label', 'org.mldsafail.recovery=' + name, '--memory', '256m',
                    '--pids-limit', '64', '--tmpfs', '/var/lib/postgresql/data:size=256m',
                    '-e', 'POSTGRES_DB=restore', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
                    config['postgres_image']]).decode().strip()
        deadline = time.monotonic() + 60
        while run_command(['docker', 'exec', identifier, 'pg_isready', '-U', 'postgres', '-d', 'restore'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False).returncode:
            if time.monotonic() >= deadline:
                raise RuntimeError('Isolated restore database not ready')
            time.sleep(1)
        with dumps[0].open('rb') as stream:
            run_command(['docker', 'exec', '-i', identifier, 'pg_restore', '-U', 'postgres',
                            '-d', 'restore', '--no-owner', '--no-privileges', '--exit-on-error'], stdin=stream,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=600)
        source = Path(__file__).with_name('verify_recovery_evidence.py').read_text()
        wrapper = source + '\nprint(__import__("json").dumps(verify("postgresql+psycopg://postgres@127.0.0.1/restore",Path("/recovery/epoch/sealed"),Path("/recovery/evidence"))))\n'
        owned = []
        if operation:
            verifier = 'recovery-verifier-' + uuid.uuid4().hex
            operation.container(verifier, config['coordinator_image'])
            owned = ['--name', verifier, '--label', 'org.mldsafail.recovery=' + verifier]
        result = json.loads(command(['docker', 'run', *owned, '--rm', '--network', 'container:' + identifier,
                     '--read-only', '--user', '0:0', '--cap-drop', 'ALL',
                     '--security-opt', 'no-new-privileges', '--memory', '512m', '--pids-limit', '64',
                     '--mount', f'type=bind,src={root.resolve()},dst=/recovery,readonly',
                     '--entrypoint', '/app/.venv/bin/python', '-i', config['coordinator_image'], '-'],
                     input=wrapper.encode(), timeout=600))
        if not result['database_evidence_verified'] or result['epoch_id'] != manifest['epoch_id']:
            raise ValueError('Restored recovery identity mismatch')
    finally:
        if operation:
            operation.cleanup()
        elif identifier:
            # Only exact container created here; failed cleanup prevents verification.
            command(['docker', 'rm', '-f', identifier])
    state = Path(config['backup_state'])
    record = {'repository': config['repository'], 'snapshot': config['restore_snapshot'],
              'restore_verified': True, 'cleanup_complete': True, 'verified_at': datetime.now(timezone.utc).isoformat(),
              'epoch_id': result['epoch_id'], 'result_count': result['result_count']}
    if operation:
        return record
    from deploy.recovery_journal import atomic_json, safe_path
    atomic_json(safe_path(state), record)
    return {'restore_verified': True, 'result_count': result['result_count']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    try:
        from deploy.recovery_journal import standalone_operation
        config = json.loads(private_file(args.config).read_text())
        record = standalone_operation(config, args.destination.parent, 'restore',
            lambda operation: verify(config, args.destination, operation=operation), args.cleanup)
        if not args.cleanup:
            from deploy.recovery_journal import atomic_json, safe_path
            atomic_json(safe_path(config['backup_state']), record)
        print(json.dumps(record))
    except Exception:
        print(json.dumps({'restore_verification_failed': True}))
        raise SystemExit(1)
