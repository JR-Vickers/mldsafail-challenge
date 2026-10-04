from deploy.recovery_daemon import locked_config_operation
"""Restore-check sealed recovery material in disposable private containers."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import subprocess
import time
import uuid
from deploy.recovery import execute, private_file, validate_set


def normalized_sql_dump(data):
    """Ignore generated comments/nonces, retaining quoted SQL and COPY data."""
    rows = []
    copying = False
    quote = None
    dollar = re.compile(rb'\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$')
    for line in data.splitlines():
        if copying:
            rows.append(line)
            if line == b'\\.': copying = False
            continue
        if quote is None and (not line or line.startswith((b'--', b'\\restrict ', b'\\unrestrict '))):
            continue
        rows.append(line)
        if quote is None and line.startswith(b'COPY ') and line.endswith(b' FROM stdin;'):
            copying = True
            continue
        index = 0
        while index < len(line):
            if quote is not None:
                if line.startswith(quote, index):
                    if quote in (b"'", b'"') and line.startswith(quote * 2, index):
                        index += 2
                        continue
                    index += len(quote)
                    quote = None
                elif quote == b"'" and line[index:index+1] == b'\\':
                    index += 2
                else: index += 1
            elif line.startswith(b'--', index):
                break
            elif line[index:index+1] in (b"'", b'"'):
                quote = line[index:index+1]
                index += 1
            else:
                match = dollar.match(line, index)
                if match:
                    quote = match.group()
                    index = match.end()
                else: index += 1
    if copying or quote is not None:
        raise ValueError('Incomplete COPY or quoted SQL in database verification')
    return b'\n'.join(rows)


@locked_config_operation
def verify(config, destination, operation=None, *, local_set=False):
    if operation is None: raise ValueError('Durable operator ownership required for disposable restoration')
    daemon_manifest_path = config.get('owned_daemon_manifest') or os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
    if not daemon_manifest_path: raise ValueError('Explicit dedicated disposable restoration daemon required')
    from deploy.recovery_daemon import bind
    bind(operation.data, daemon_manifest_path)
    operation.save('dedicated restoration daemon verified')
    if local_set:
        private_file(destination / 'recovery.json')
        roots = [destination / 'recovery.json']
    else:
        execute(config, 'restore', destination=destination, journal=operation)
        roots = list(destination.rglob('recovery.json'))
    if len(roots) != 1:
        raise ValueError('Restore must contain exactly one recovery set')
    root = roots[0].parent
    manifest = validate_set(root)
    if local_set:
        import stat
        for directory in [root, *(path for path in root.rglob('*') if path.is_dir())]:
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('Protected local recovery directories must be owner-private')
        for name in manifest['files']:
            private_file(root / name)
    dumps = list((root / 'database').glob('*.dump'))
    if len(dumps) != 1:
        raise ValueError('Exactly one database snapshot required')
    for key in ['postgres_image', 'coordinator_image']:
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', config[key]):
            raise ValueError('Immutable restore images required')
    name = 'restore-' + uuid.uuid4().hex
    identifier = None
    def command(argv, **kwargs):
        timeout = kwargs.pop('timeout', 60)
        if operation:
            return operation.command(argv, daemon_manifest_path=daemon_manifest_path, stderr=subprocess.DEVNULL, capture_output=True,
                                     check=True, timeout=timeout, **kwargs).stdout
        return subprocess.check_output(argv, stderr=subprocess.DEVNULL, timeout=timeout, **kwargs)
    def run_command(argv, **kwargs):
        return operation.command(argv, daemon_manifest_path=daemon_manifest_path, **kwargs)
    for key in ('postgres_image', 'coordinator_image'):
        info = json.loads(command(['docker', 'image', 'inspect', config[key]]))[0]
        permitted = {'/var/lib/postgresql/data'} if key == 'postgres_image' else set()
        if info['Id'] != config[key] or set(info.get('Config', {}).get('Volumes') or {}) - permitted:
            raise ValueError('Restore image identity or unaccounted image volume mismatch')
    if operation:
        operation.container(name, config['postgres_image'], daemon_manifest_path=daemon_manifest_path)
    original = None
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
        # Compare every schema/data statement against the immutable custom
        # snapshot, including accounts, tokens and tables outside scoring.
        if dumps[0].stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Snapshot exceeds bounded verification transport; preserve and expand tooling')
        expected = command(['docker', 'exec', '-i', identifier, 'pg_restore',
            '--file=-', '--no-owner', '--no-privileges'],
            input=dumps[0].read_bytes(), timeout=600)
        actual = command(['docker', 'exec', identifier, 'pg_dump', '-U', 'postgres',
            '-d', 'restore', '--format=plain', '--no-owner', '--no-privileges'], timeout=600)
        if normalized_sql_dump(expected) != normalized_sql_dump(actual):
            raise ValueError('Restored full database schema/data differs from sealed snapshot')
        source = Path(__file__).with_name('verify_recovery_evidence.py').read_text()
        wrapper = source + '\nprint(__import__("json").dumps(verify("postgresql+psycopg://postgres@127.0.0.1/restore",Path("/recovery/epoch/sealed"),Path("/recovery/evidence"))))\n'
        owned = []
        if operation:
            verifier = 'recovery-verifier-' + uuid.uuid4().hex
            operation.container(verifier, config['coordinator_image'], daemon_manifest_path=daemon_manifest_path)
            owned = ['--name', verifier, '--label', 'org.mldsafail.recovery=' + verifier]
        result = json.loads(command(['docker', 'run', *owned, '--rm', '--network', 'container:' + identifier,
                     '--read-only', '--user', '0:0', '--cap-drop', 'ALL',
                     '--security-opt', 'no-new-privileges', '--memory', '512m', '--pids-limit', '64',
                     '--mount', f'type=bind,src={root.resolve()},dst=/recovery,readonly',
                     '--entrypoint', '/app/.venv/bin/python', '-i', config['coordinator_image'], '-'],
                     input=wrapper.encode(), timeout=600))
        if not result['database_evidence_verified'] or result['epoch_id'] != manifest['epoch_id']:
            raise ValueError('Restored recovery identity mismatch')
    except BaseException as error:
        original = error
    finally:
        try:
            operation.cleanup()
        except BaseException as error:
            if original is None: original = error
            else: original.add_note('Independent isolated restore cleanup: ' + type(error).__name__)
        if original is not None: raise original
    if local_set:
        return {'schema': 'mldsafail-local-protected-restore-v1',
                'restore_verified': True, 'cleanup_complete': True,
                'restored_manifest_sha256': __import__('hashlib').sha256((root / 'recovery.json').read_bytes()).hexdigest(),
                'epoch_id': result['epoch_id'], 'result_count': result['result_count'],
                'offhost_verified': False, 'owner_custody_verified': False}
    state = Path(config['backup_state'])
    from deploy.recovery import STATE_SCHEMA, private_file
    uploaded = json.loads(private_file(config['backup_state']).read_text())
    uploaded_at = uploaded.get('uploaded_at') if (uploaded.get('schema') == STATE_SCHEMA and
        uploaded.get('repository') == config['repository'] and uploaded.get('snapshot') == config['restore_snapshot']) else None
    record = {'schema': STATE_SCHEMA, 'uploaded_at': uploaded_at,
              'restored_manifest_sha256': __import__('hashlib').sha256((root / 'recovery.json').read_bytes()).hexdigest(),
              'repository': config['repository'], 'snapshot': config['restore_snapshot'],
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
