"""Native pinned restic/MinIO HTTPS gate using exclusively synthetic material.

No real storage, production credentials, benchmark epochs or owner custody claim.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from deploy import owned_client
from deploy.recovery_journal import Journal, atomic_json, safe_path


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); return sock.getsockname()[1]


class Server:
    def __init__(self, argv, env, root):
        self.entries = []
        self.error = None
        def target():
            try:
                owned_client.run(argv, self.entries,
                    lambda: atomic_json(root / 'server-clients.json', {'clients': self.entries}),
                    root, env=env, timeout=1200)
            except BaseException as error:
                self.error = type(error).__name__
        self.thread = threading.Thread(target=target)
        self.thread.start()

    def stop(self):
        errors = []
        for entry in self.entries:
            try: owned_client.stop(entry)
            except BaseException as error: errors.append(type(error).__name__)
        self.thread.join(15)
        if self.thread.is_alive(): errors.append('ServerThreadStillAlive')
        if errors: raise RuntimeError('Synthetic server cleanup incomplete: ' + repr(errors))


def _execute_locked(output, artifacts):
    if sys.platform != 'linux': raise RuntimeError('Native Linux required')
    output, artifacts = map(safe_path, (output, artifacts))
    if output.exists() or output.parent.stat().st_mode & 0o077:
        raise ValueError('Fresh private output required')
    source = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']):
        raise ValueError('Clean retained source required')
    pins = json.loads((artifacts / 'artifacts.json').read_text())
    if pins.get('scope') != 'synthetic-only':
        raise ValueError('Explicit synthetic-only artifact scope required')
    for name in ('restic', 'minio'):
        if digest(artifacts / name) != pins[name + '_binary_sha256']:
            raise ValueError('Pinned native binary checksum mismatch')
    output.mkdir(mode=0o700)
    os.umask(0o077)
    protocol = {'schema': 'mldsafail.synthetic-s3.v1', 'synthetic_only': True,
        'actual_offhost_storage_accepted': False, 'actual_owner_custody_accepted': False,
        'benchmark_epoch_data_used': False, 'source_commit': subprocess.check_output(
            ['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
        'script_sha256': digest(__file__), 'helper_sha256': digest(owned_client.__file__),
        'kernel': os.uname().release, 'architecture': os.uname().machine, 'python': sys.version, 'artifacts': pins,
        'protocol': ['trusted local CA required', 'three synthetic snapshots', 'full check and byte-exact restore',
                     'wrong key and wrong S3 credentials rejected', 'real upload interruption after new pack',
                     'retry/check/restore', 'verified synthetic restore before retention',
                     'corrupted S3 encrypted object rejected then repaired', 'all client/server domains removed'],
        'stages': [], 'passed': False, 'cleanup_complete': False}
    atomic_json(output / 'report.json', protocol)
    operation = Journal(output / 'operation.json', {'scope': 'synthetic HTTPS S3 only'})
    def stage(name, **values):
        protocol['stages'].append({'name': name, **values})
        atomic_json(output / 'report.json', protocol)
    def command(argv, env=None, **kwargs):
        return operation.command(argv, env=env, timeout=kwargs.pop('timeout', 120), **kwargs)
    def reject(argv, env):
        result = command(argv, env=env, check=False)
        identifier = uuid.uuid4().hex
        logs = {}
        for name in ('stdout', 'stderr'):
            raw = getattr(result, name) or b''
            path = output / ('expected-rejection-' + identifier + '-' + name + '.log')
            path.write_bytes(raw[:1024 * 1024]); path.chmod(0o600)
            logs[name] = {'file': path.name, 'observed_bytes': len(raw),
                          'retained_bytes': min(len(raw), 1024 * 1024),
                          'truncated': len(raw) > 1024 * 1024}
        protocol.setdefault('expected_rejections', []).append({'returncode': result.returncode, 'logs': logs})
        atomic_json(output / 'report.json', protocol)
        if result.returncode == 0: raise RuntimeError('Expected rejection was accepted')
        return result.returncode
    certs = output / 'certs'; certs.mkdir(mode=0o700)
    command(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
             '-subj', '/CN=synthetic-only', '-addext', 'subjectAltName=IP:127.0.0.1',
             '-keyout', str(certs / 'private.key'), '-out', str(certs / 'public.crt')])
    key = uuid.uuid4().hex
    password = output / 'synthetic-password'; password.write_text(uuid.uuid4().hex); password.chmod(0o600)
    custody = output / 'synthetic-custody-copy'; custody.write_bytes(password.read_bytes()); custody.chmod(0o600)
    credentials = {'AWS_ACCESS_KEY_ID': 'synthetic-only', 'AWS_SECRET_ACCESS_KEY': key,
                   'AWS_DEFAULT_REGION': 'us-east-1'}
    atomic_json(output / 'synthetic-credentials.json', credentials)
    endpoint = 'https://127.0.0.1:' + str(port())
    storage = output / 'storage'; storage.mkdir(mode=0o700)
    server_env = {**os.environ, 'MINIO_ROOT_USER': credentials['AWS_ACCESS_KEY_ID'],
                  'MINIO_ROOT_PASSWORD': key, 'MINIO_BROWSER': 'off'}
    server = Server([str(artifacts / 'minio'), 'server', '--quiet', '--address', endpoint.replace('https://', ''),
                     '--console-address', '127.0.0.1:' + str(port()), '--certs-dir', str(certs), str(storage)], server_env, output)
    restic_env = {**os.environ, **credentials, 'RESTIC_REPOSITORY': 's3:' + endpoint + '/syntheticbucket/staging',
                  'RESTIC_PASSWORD_FILE': str(password), 'RESTIC_CACERT': str(certs / 'public.crt'), 'GOMAXPROCS': '2'}
    base = [str(artifacts / 'restic'), '--no-cache']
    def restic(*args, **kwargs): return command(base + list(args), env=restic_env, **kwargs)
    def curl(method, suffix, *extra):
        return command(['curl', '--fail', '--silent', '--show-error', '--cacert', str(certs / 'public.crt'),
                        '--aws-sigv4', 'aws:amz:us-east-1:s3', '--user', credentials['AWS_ACCESS_KEY_ID'] + ':' + key,
                        '-X', method, endpoint + suffix, *extra])
    original = None
    try:
        protocol['restic_version'] = command([str(artifacts / 'restic'), 'version']).stdout.decode().strip()
        protocol['minio_version'] = command([str(artifacts / 'minio'), '--version']).stdout.decode().strip()
        atomic_json(output / 'report.json', protocol)
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(endpoint + '/minio/health/ready', context=ssl.create_default_context(cafile=str(certs / 'public.crt')), timeout=1).close()
                break
            except (OSError, urllib.error.URLError):
                if not server.thread.is_alive() or time.monotonic() >= deadline: raise RuntimeError('Synthetic S3 server not ready')
                time.sleep(.05)
        curl('PUT', '/syntheticbucket')
        restic('init')
        stage('HTTPS S3 init', passed=True)
        data = output / 'source'; data.mkdir(mode=0o700)
        for i in range(3):
            (data / 'synthetic.txt').write_text('synthetic recovery fixture ' + str(i))
            restic('backup', str(data), '--tag', 'synthetic-staging')
        restic('check', '--read-data')
        snapshots = json.loads(restic('snapshots', '--json').stdout)
        if len(snapshots) != 3: raise RuntimeError('Synthetic snapshot inventory mismatch')
        stage('three snapshots/full check', passed=True)
        wrong = output / 'wrong-password'; wrong.write_text('wrong synthetic key'); wrong.chmod(0o600)
        reject(base + ['snapshots'], {**restic_env, 'RESTIC_PASSWORD_FILE': str(wrong)})
        reject(base + ['snapshots'], {**restic_env, 'AWS_SECRET_ACCESS_KEY': 'incorrect synthetic storage key'})
        reject(base + ['snapshots'], {**restic_env, 'RESTIC_CACERT': ''})
        stage('wrong recovery/storage key and untrusted TLS rejected', passed=True)
        generator = random.Random(0)
        with (data / 'upload-fault.bin').open('wb') as stream:
            for _ in range(1024): stream.write(generator.randbytes(65536))
        synthetic_epoch = 'synthetic-only-' + uuid.uuid4().hex
        atomic_json(data / 'synthetic-manifest.json', {'schema': 'synthetic.restore.v1',
            'epoch_id': synthetic_epoch, 'files': {p.name: digest(p) for p in data.iterdir()}})
        prior = set((storage / 'syntheticbucket' / 'staging' / 'data').rglob('xl.meta'))
        failure = []
        def upload():
            try: restic('backup', str(data), '--tag', 'synthetic-staging', timeout=300)
            except BaseException as error: failure.append(type(error).__name__)
        before_clients = len(operation.data.get('clients', []))
        thread = threading.Thread(target=upload); thread.start()
        deadline = time.monotonic() + 120
        try:
            while True:
                clients = operation.data.get('clients', [])
                if len(clients) > before_clients:
                    entry = clients[before_clients]
                    new = set((storage / 'syntheticbucket' / 'staging' / 'data').rglob('xl.meta')) - prior
                    if entry.get('pid') is not None and new and thread.is_alive():
                        if owned_client.identity(entry['pid'])['cmdline_sha256'] == entry['expected_cmdline_sha256']:
                            owned_client.stop(entry); break
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError('Real upload interruption boundary unavailable')
                time.sleep(.005)
        finally:
            if len(operation.data.get('clients', [])) > before_clients:
                owned_client.stop(operation.data['clients'][before_clients])
            thread.join(15)
            if thread.is_alive(): raise RuntimeError('Upload client did not exit')
        if not failure: raise RuntimeError('Interrupted upload unexpectedly passed')
        restic('unlock')
        restic('check', '--read-data')
        uploaded = restic('backup', str(data), '--tag', 'synthetic-staging', '--json', timeout=300)
        summaries = [json.loads(line) for line in uploaded.stdout.splitlines()]
        snapshot = next(row['snapshot_id'] for row in summaries if row.get('message_type') == 'summary')
        uploaded_at = datetime.now(timezone.utc).isoformat()
        destination = output / 'restored'
        restic('restore', snapshot, '--target', str(destination), timeout=300)
        restored = destination / str(data).lstrip('/')
        for path in data.iterdir():
            if digest(path) != digest(restored / path.name): raise RuntimeError('Synthetic restore bytes differ')
        stage('real upload interrupted/retried and bytes restored', passed=True)
        operation.cleanup()
        from deploy.recovery import STATE_SCHEMA, validate_prune_state
        state = {'schema': STATE_SCHEMA, 'repository': restic_env['RESTIC_REPOSITORY'],
            'snapshot': snapshot, 'epoch_id': synthetic_epoch, 'result_count': 0,
            'restored_manifest_sha256': digest(restored / 'synthetic-manifest.json'),
            'restore_verified': True, 'cleanup_complete': True, 'uploaded_at': uploaded_at,
            'verified_at': datetime.now(timezone.utc).isoformat(), 'synthetic_only': True}
        atomic_json(output / 'verified-state.json', state)
        validate_prune_state({'backup_state': str(output / 'verified-state.json'),
            'repository': restic_env['RESTIC_REPOSITORY'], 'restore_verified_snapshot': snapshot,
            'expected_epoch_id': synthetic_epoch})
        protocol['strict_verified_state_accepted'] = True
        protocol['synthetic_manifest_sha256'] = state['restored_manifest_sha256']
        restic('forget', '--keep-last', '1', '--prune', timeout=300)
        if len(json.loads(restic('snapshots', '--json').stdout)) != 1: raise RuntimeError('Synthetic retention inventory mismatch')
        restic('check', '--read-data')
        stage('retention after byte-verified synthetic restore', passed=True)
        listed = ET.fromstring(curl('GET', '/syntheticbucket?' + urllib.parse.urlencode({'list-type': '2', 'prefix': 'staging/data/', 'max-keys': '1000'})).stdout)
        keys = [element.text for element in listed.iter() if element.tag.rsplit('}', 1)[-1] == 'Key']
        if not keys: raise RuntimeError('No encrypted S3 pack available for corruption')
        suffix = '/syntheticbucket/' + urllib.parse.quote(keys[0], safe='/')
        pack = output / 'original-encrypted-pack'
        curl('GET', suffix, '-o', str(pack))
        raw = bytearray(pack.read_bytes()); raw[len(raw) // 2] ^= 1
        altered = output / 'corrupted-encrypted-pack'; altered.write_bytes(raw)
        try:
            curl('PUT', suffix, '--data-binary', '@' + str(altered))
            reject(base + ['check', '--read-data'], restic_env)
        finally:
            curl('PUT', suffix, '--data-binary', '@' + str(pack))
        restic('check', '--read-data')
        stage('corrupted encrypted S3 pack rejected and original repaired', passed=True)
        protocol['passed'] = True
    except BaseException as error:
        original = error
        protocol['error_type'] = type(error).__name__
    finally:
        errors = []
        try: operation.cleanup()
        except BaseException as error: errors.append({'step': 'clients', 'error_type': type(error).__name__})
        try: server.stop()
        except BaseException as error: errors.append({'step': 'server', 'error_type': type(error).__name__})
        protocol['cleanup_errors'] = errors
        protocol['cleanup_complete'] = not errors
        protocol['passed'] = protocol['passed'] and not errors
        atomic_json(output / 'report.json', protocol)
        if original is not None:
            if errors: original.add_note('Independent synthetic cleanup errors: ' + repr(errors))
            raise original
        if errors: raise RuntimeError('Synthetic S3 cleanup incomplete')
    return protocol


def _cleanup_locked(output):
    from deploy.recovery import private_file
    output = safe_path(output)
    if output.stat().st_uid != os.getuid() or output.stat().st_mode & 0o077:
        raise ValueError('Private owned synthetic output required')
    errors = []
    try:
        Journal(output / 'operation.json', {'scope': 'synthetic HTTPS S3 only'}).cleanup()
    except BaseException as error:
        errors.append({'step': 'client_journal', 'error_type': type(error).__name__})
    try:
        record = json.loads(private_file(output / 'server-clients.json').read_text())
        for entry in record['clients']:
            try: owned_client.stop(entry)
            except BaseException as error: errors.append({'step': 'server_domain', 'error_type': type(error).__name__})
    except BaseException as error:
        errors.append({'step': 'server_journal', 'error_type': type(error).__name__})
    result = {'cleanup_complete': not errors, 'errors': errors}
    atomic_json(output / ('cleanup-' + uuid.uuid4().hex + '.json'), result)
    if errors: raise RuntimeError('Synthetic S3 cleanup incomplete')
    return result


def run_lock(output):
    import contextlib
    import fcntl
    import stat
    @contextlib.contextmanager
    def held():
        path = safe_path(output)
        descriptor = os.open(path.parent / ('.' + path.name + '.lock'),
                             os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('Private owned native fixture lock required')
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(descriptor)
    return held()


def execute(output, artifacts):
    if sys.platform != 'linux': raise RuntimeError('Native Linux required')
    with run_lock(output): return _execute_locked(output, artifacts)


def cleanup(output):
    with run_lock(output): return _cleanup_locked(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if args.cleanup: print(json.dumps(cleanup(args.output)))
    elif args.artifacts: print(json.dumps(execute(args.output, args.artifacts)))
    else: parser.error('--artifacts required for native execution')
