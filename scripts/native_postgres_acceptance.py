"""Disposable native PostgreSQL admission gates with durable retryable cleanup."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import uuid

from deploy.recovery_journal import atomic_json, safe_path

LABEL = 'org.mldsafail.native-postgres'


def command(argv, output, receipt, timeout=90, env=None, log=None):
    from deploy.owned_client import run
    from deploy.recovery_daemon import bind, scope
    from contextlib import nullcontext
    selected = receipt.get('owned_daemon_manifest_path')
    context = bind(receipt, selected) if selected else None
    mutation = None
    if Path(argv[0]).name == 'docker' and any(token in {'create', 'run', 'start', 'stop', 'rm'} for token in argv[1:]):
        mutation = {'id': uuid.uuid4().hex, 'acknowledged': False, 'daemon_context': context,
                    'argv_sha256': hashlib.sha256(json.dumps(argv).encode()).hexdigest()}
        receipt.setdefault('daemon_mutations', []).append(mutation)
        receipt['cleanup_complete'] = False
        atomic_json(output / 'ownership.json', receipt)
    start_index = len(receipt.setdefault('clients', []))
    def publish():
        for entry in receipt['clients'][start_index:]: entry['daemon_context'] = context
        atomic_json(output / 'ownership.json', receipt)
    with scope(selected) if selected else nullcontext():
        if selected and env is not None:
            env = dict(env)
            for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', 'MLDSAFAIL_CPU_DAEMON_MANIFEST'):
                value = os.environ.get(key)
                if value is None: env.pop(key, None)
                else: env[key] = value
        result = run(argv, receipt['clients'], publish, output,
                     timeout=timeout, env=env, stdout=log,
                     stderr=subprocess.STDOUT if log else None, text=True)
    if mutation is not None and result.returncode == 0:
        mutation['acknowledged'] = True
        atomic_json(output / 'ownership.json', receipt)
    return result.stdout.strip() if result.stdout is not None else ''


def stop_client(entry):
    from deploy.owned_client import stop
    stop(entry)


def cleanup(output, receipt):
    """Every owned cleanup step is independent; failures retain the fence."""
    if not re.fullmatch(r'[0-9a-f]{32}', receipt.get('run_id', '')) or receipt.get('name') != 'launch-postgres-' + receipt['run_id']:
        raise ValueError('Invalid disposable ownership receipt')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', receipt.get('database_image', '')):
        raise ValueError('Invalid disposable image identity')
    from deploy.recovery_daemon import repair, cleanup_entries
    errors = []
    try:
        errors.extend(repair(receipt, output, lambda: atomic_json(output / 'ownership.json', receipt)))
    except BaseException as error:
        errors.append({'step': 'daemon_repair', 'error_type': type(error).__name__})
    for field in ('clients', 'daemon_mutations'):
        cleanup_entries(receipt, field, errors)
    if receipt.get('corrupt_fields'):
        errors.append({'step': 'retained_corrupt_authority'})
    receipt.update(phase='cleanup', cleanup_complete=False)
    try:
        atomic_json(output / 'ownership.json', receipt)
    except Exception as error:
        errors.append({'step': 'cleanup_intent_publication', 'error_type': type(error).__name__})
    for entry in list(receipt.get('clients', [])):
        try:
            stop_client(entry)
            entry['finished'] = True
        except Exception as error:
            errors.append({'step': 'client_cleanup', 'error_type': type(error).__name__})
    label = LABEL + '=' + receipt['run_id']
    try:
        identifiers = command(['docker', 'ps', '-aq', '--no-trunc', '--filter', 'label=' + label], output, receipt).splitlines()
    except Exception as error:
        identifiers = []
        errors.append({'step': 'inventory', 'error_type': type(error).__name__})
    for identifier in identifiers:
        try:
            if not re.fullmatch(r'[0-9a-f]{64}', identifier):
                raise ValueError('Invalid owned container ID')
            info = json.loads(command(['docker', 'inspect', identifier], output, receipt))[0]
            if (info['Id'] != identifier or info['Name'] != '/' + receipt['name'] or
                    info['Image'] != receipt['database_image'] or
                    info['Config'].get('Labels', {}).get(LABEL) != receipt['run_id']):
                raise RuntimeError('Disposable database ownership mismatch')
            command(['docker', 'rm', '-f', identifier], output, receipt)
        except Exception as error:
            errors.append({'step': 'container_remove', 'error_type': type(error).__name__})
    try:
        # Inventory is resource evidence, never a daemon request completion barrier.
        for _ in range(3):
            if command(['docker', 'ps', '-aq', '--no-trunc', '--filter', 'label=' + label], output, receipt):
                raise RuntimeError('Owned disposable database remains')
            time.sleep(.5)
    except Exception as error:
        errors.append({'step': 'final_inventory', 'error_type': type(error).__name__})
    if any(item.get('acknowledged') is not True and not item.get('resolved_by_barrier') for item in receipt.get('daemon_mutations', [])):
        errors.append({'step': 'daemon_mutation_uncertainty', 'required': 'positive_dedicated_daemon_barrier'})
    receipt.update(cleanup_complete=not errors, cleanup_errors=errors,
                   phase='complete' if not errors else 'cleanup_incomplete')
    attempt = uuid.uuid4().hex + '-cleanup.json'
    atomic_json(output / attempt, {'run_id': receipt['run_id'], 'cleanup_complete': not errors,
                                 'errors': errors})
    receipt.setdefault('cleanup_attempts', []).append(attempt)
    atomic_json(output / 'ownership.json', receipt)
    return not errors


def run(image, output, cleanup_only=False):
    if sys.platform != 'linux':
        raise ValueError('Native Linux required')
    output = safe_path(output)
    if output.parent.stat().st_mode & 0o077:
        raise ValueError('Private evidence parent directory required')
    lock_path = output.parent / ('.' + output.name + '.lock')
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from deploy.recovery_daemon import operation_lock
        selected = os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
        if cleanup_only:
            selected = json.loads((output / 'ownership.json').read_text()).get('owned_daemon_manifest_path')
        with operation_lock(selected):
            return execute(image, output, cleanup_only)
    finally:
        os.close(descriptor)


def execute(image, output, cleanup_only):
    if cleanup_only:
        if output.stat().st_mode & 0o077:
            raise ValueError('Private evidence directory required')
        receipt_path = safe_path(output / 'ownership.json')
        if receipt_path.stat().st_mode & 0o077:
            raise ValueError('Private ownership receipt required')
        receipt = json.loads(receipt_path.read_text())
        if not (output / 'interrupted-ownership.json').exists():
            atomic_json(output / 'interrupted-ownership.json', receipt)
        result = cleanup(output, receipt)
        report_path = output / 'report.json'
        report = json.loads(report_path.read_text()) if report_path.exists() else {'tests_passed': False}
        atomic_json(output / (uuid.uuid4().hex + '-prior-report.json'), report)
        report.update(cleanup_complete=result, passed=report.get('tests_passed', False) and result)
        atomic_json(report_path, report)
        return report
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image or ''):
        raise ValueError('Immutable database image required')
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True):
        raise ValueError('Retained source must be clean')
    output.mkdir(mode=0o700, exist_ok=False)
    identity = uuid.uuid4().hex
    receipt = dict(schema_version=1, run_id=identity, name='launch-postgres-' + identity,
                   database_image=image, source_commit=commit, phase='creation_intent',
                   cleanup_complete=False, clients=[])
    selected = os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST')
    if not selected:
        raise ValueError('Explicit dedicated disposable PostgreSQL daemon manifest required')
    receipt['owned_daemon_manifest_path'] = selected
    from deploy.recovery_daemon import bind
    bind(receipt, selected)
    atomic_json(output / 'ownership.json', receipt)
    database = 'mldsafail_acceptance_' + identity
    password = uuid.uuid4().hex
    report = dict(source_commit=commit, source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  database_image=image, passed=False, tests_passed=False, cleanup_complete=False,
                  python=sys.version, kernel=platform.release(),
                  protocol='three synchronized admission/ownership tests in empty disposable PostgreSQL')
    atomic_json(output / 'report.json', report)
    def call(argv, **kwargs):
        return command(argv, output, receipt, **kwargs)
    try:
        info = json.loads(call(['docker', 'info', '--format', '{{json .}}']))
        if not any('rootless' in value for value in info.get('SecurityOptions', [])):
            raise RuntimeError('Rootless Docker required')
        image_info = json.loads(call(['docker', 'image', 'inspect', image]))[0]
        architecture = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine())
        if not architecture or image_info['Id'] != image or image_info['Architecture'] != architecture or image_info['Os'] != 'linux':
            raise RuntimeError('Native Linux image identity/architecture required')
        if set(image_info.get('Config', {}).get('Volumes') or {}) - {'/var/lib/postgresql/data'}:
            raise RuntimeError('Database image declares unaccounted storage volumes')
        report.update(docker=info.get('ServerVersion'), architecture=architecture)
        atomic_json(output / 'report.json', report)
        call(['docker', 'run', '-d', '--name', receipt['name'], '--label', LABEL + '=' + identity,
              '--tmpfs', '/var/lib/postgresql/data:rw,nosuid,nodev', '-p', '127.0.0.1::5432',
              '-e', 'POSTGRES_DB=' + database, '-e', 'POSTGRES_USER=acceptance',
              '-e', 'POSTGRES_PASSWORD=' + password, image])
        deadline = time.monotonic() + 60
        while True:
            try:
                call(['docker', 'exec', receipt['name'], 'pg_isready', '-U', 'acceptance', '-d', database], timeout=min(5, max(.1, deadline - time.monotonic())))
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Disposable PostgreSQL startup timed out')
                time.sleep(.5)
        container = json.loads(call(['docker', 'inspect', receipt['name']]))[0]
        ports = container['NetworkSettings']['Ports']['5432/tcp']
        if len(ports) != 1 or ports[0]['HostIp'] != '127.0.0.1' or container['Image'] != image:
            raise RuntimeError('Disposable PostgreSQL identity/exposure mismatch')
        report['postgresql_version'] = call(['docker', 'exec', receipt['name'], 'postgres', '--version'])
        environment = dict(os.environ, MLDSAFAIL_NATIVE_TEST_DATABASE_URL='postgresql+psycopg://acceptance:' + password + '@127.0.0.1:' + ports[0]['HostPort'] + '/' + database)
        with (output / 'tests.log').open('w') as log:
            # CWD is frozen repository source; avoid inherited pytest options/plugins.
            environment.pop('PYTEST_ADDOPTS', None)
            environment['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
            previous = Path.cwd()
            try:
                os.chdir(root)
                call([sys.executable, '-m', 'pytest', 'tests/test_native_postgres_admission.py', '-q'],
                     env=environment, log=log, timeout=180)
            finally:
                os.chdir(previous)
        report['tests_passed'] = True
        atomic_json(output / 'report.json', report)
    except BaseException as error:
        report['error_type'] = type(error).__name__
        atomic_json(output / 'report.json', report)
        raise
    finally:
        report['cleanup_complete'] = cleanup(output, receipt)
        report['passed'] = report['tests_passed'] and report['cleanup_complete']
        atomic_json(output / 'report.json', report)
        if not report['cleanup_complete']:
            raise RuntimeError('Owned disposable database cleanup incomplete; retry --cleanup')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    for number in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, lambda *_: (_ for _ in ()).throw(InterruptedError()))
    try:
        print(json.dumps(run(args.image, args.output, args.cleanup)))
    except Exception:
        print(json.dumps({'native_postgres_failed': True, 'private_evidence_retained': True}))
        raise SystemExit(1)
