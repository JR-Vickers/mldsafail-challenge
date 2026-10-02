"""Restore-check sealed recovery material in disposable private containers."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import uuid
from deploy.recovery import execute, private_file, validate_set


def verify(config, destination):
    execute(config, 'restore', destination=destination)
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
        return subprocess.check_output(argv, stderr=subprocess.DEVNULL, timeout=kwargs.pop('timeout', 60), **kwargs)
    try:
        identifier = command(['docker', 'run', '-d', '--name', name, '--network', 'none',
                    '--label', 'org.mldsafail.recovery=' + name, '--memory', '256m',
                    '--pids-limit', '64', '--tmpfs', '/var/lib/postgresql/data:size=256m',
                    '-e', 'POSTGRES_DB=restore', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
                    config['postgres_image']]).decode().strip()
        deadline = time.monotonic() + 60
        while subprocess.run(['docker', 'exec', identifier, 'pg_isready', '-U', 'postgres', '-d', 'restore'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode:
            if time.monotonic() >= deadline:
                raise RuntimeError('Isolated restore database not ready')
            time.sleep(1)
        with dumps[0].open('rb') as stream:
            subprocess.run(['docker', 'exec', '-i', identifier, 'pg_restore', '-U', 'postgres',
                            '-d', 'restore', '--no-owner', '--no-privileges', '--exit-on-error'], stdin=stream,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=600)
        source = Path(__file__).with_name('verify_recovery_evidence.py').read_text()
        wrapper = source + '\nprint(__import__("json").dumps(verify("postgresql+psycopg://postgres@127.0.0.1/restore",Path("/recovery/epoch/sealed"),Path("/recovery/evidence"))))\n'
        result = json.loads(command(['docker', 'run', '--rm', '--network', 'container:' + identifier,
                     '--read-only', '--user', '0:0', '--cap-drop', 'ALL',
                     '--security-opt', 'no-new-privileges', '--memory', '512m', '--pids-limit', '64',
                     '--mount', f'type=bind,src={root.resolve()},dst=/recovery,readonly',
                     '--entrypoint', '/app/.venv/bin/python', '-i', config['coordinator_image'], '-'],
                     input=wrapper.encode(), timeout=600))
        if not result['database_evidence_verified'] or result['epoch_id'] != manifest['epoch_id']:
            raise ValueError('Restored recovery identity mismatch')
    finally:
        if identifier:
            # Only exact container created here; failed cleanup prevents verification.
            command(['docker', 'rm', '-f', identifier])
    state = Path(config['backup_state'])
    record = {'repository': config['repository'], 'snapshot': config['restore_snapshot'],
              'restore_verified': True, 'verified_at': datetime.now(timezone.utc).isoformat(),
              'epoch_id': result['epoch_id'], 'result_count': result['result_count']}
    temporary = state.with_suffix('.tmp')
    temporary.write_text(json.dumps(record))
    temporary.chmod(0o600)
    temporary.replace(state)
    return {'restore_verified': True, 'result_count': result['result_count']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(json.loads(private_file(args.config).read_text()), args.destination)))
    except Exception:
        print(json.dumps({'restore_verification_failed': True}))
        raise SystemExit(1)
