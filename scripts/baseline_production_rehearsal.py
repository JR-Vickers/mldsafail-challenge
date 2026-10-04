"""Disposable frozen-0.5.0 baseline rehearsal for the sole native operator.

Fresh generated epoch and synthetic credentials only. No staging mounts/secrets,
public exposure, external OAuth, off-host service, production/default activation.
Failed evidence and owned resources remain fenced until explicit cleanup.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request
import uuid

from deploy.recovery_journal import atomic_json, safe_path

LABEL = 'org.mldsafail.disposable-rehearsal'
ROLE = 'org.mldsafail.disposable-role'


def validate(config):
    root = safe_path(config['run_directory'])
    staging = safe_path(config.get('staging_root', '/srv/mldsafail-evaluator'))
    if root.is_relative_to(staging) or staging.is_relative_to(root):
        raise ValueError('Disposable root must not overlap staging')
    source = safe_path(config['operator_source'])
    if not (source / 'compose.production.yaml').is_file():
        raise ValueError('Retained operator source required')
    metadata = json.loads(safe_path(config['source_manifest']).read_text())
    if not re.fullmatch(r'[a-f0-9]{40}', metadata.get('source_commit', '')):
        raise ValueError('Full retained source identity required')
    files = metadata.get('source_files_sha256', {})
    benchmark = source / 'src/mldsafail/benchmark_v050'
    if not all((benchmark / (name + '.py')).is_file() for name in ('execution', 'generator', 'scoring', 'evidence')):
        raise ValueError('Retained frozen benchmark source required')
    for relative in ['compose.production.yaml', *[str(path.relative_to(source)) for path in
                     (source / 'src/mldsafail/benchmark_v050').rglob('*.py')]]:
        path = safe_path(source / relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != files.get(relative):
            raise ValueError('Frozen source does not match manifest')
    images = config['images']
    if set(images) != {'web', 'coordinator', 'worker', 'postgres', 'caddy', 'rollback_web', 'rollback_coordinator'}:
        raise ValueError('Exact baseline/rollback image inventory required')
    if any(not re.fullmatch(r'sha256:[a-f0-9]{64}', value) for value in images.values()):
        raise ValueError('Immutable local Docker image IDs required')
    release = json.loads(safe_path(config['release_manifest']).read_text())
    rollback = json.loads(safe_path(config['rollback_manifest']).read_text())
    if release['source_commit'] != metadata['source_commit'] or rollback['source_commit'] != 'b4d212da3109b7716eb41553986848e377fb5b3d':
        raise ValueError('Exact retained baseline and b4d212d source identities required')
    for role in ('web', 'coordinator', 'worker'):
        if images[role] != release['images'][role]['id']:
            raise ValueError('Baseline image differs from retained release manifest')
    for role in ('web', 'coordinator'):
        if images['rollback_' + role] != rollback['images'][role]['id']:
            raise ValueError('Rollback image differs from retained release manifest')
    for field in ('mlwe_trusted_fingerprint', 'worker_lock_sha256'):
        if not release.get(field) or release[field] != rollback.get(field):
            raise ValueError('Frozen compatibility identities differ')
    if images['worker'] != rollback['images']['worker']['id']:
        raise ValueError('Frozen worker image must be preserved')
    if not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', config['fixture_repository']):
        raise ValueError('Reviewed public GitHub fixture repository required')
    if not re.fullmatch(r'[a-f0-9]{40}', config['fixture_commit']):
        raise ValueError('Full reviewed fixture commit required')
    solver = Path(config['fixture_solver_path'])
    if solver.is_absolute() or '..' in solver.parts:
        raise ValueError('Repository-relative fixture solver path required')
    if not re.fullmatch(r'/run/user/[1-9][0-9]*/docker.sock', config['docker_socket']):
        raise ValueError('Explicit rootless Docker socket required')
    return root, source


def command(argv, *, cwd=None, env=None, timeout=120, input=None):
    return subprocess.check_output(argv, cwd=cwd, env=env, input=input,
                                   stderr=subprocess.DEVNULL, timeout=timeout)


def cleanup(root, env):
    """Remove only resources with this durable run's exact ownership label."""
    journal = json.loads((root / 'journal.json').read_text())
    run_id = journal['run_id']
    errors = []
    retained_failure_volumes = []
    # Stop dispatch controllers before workers, then rescan once for a worker
    # whose create request raced the first inventory. Every resource is labeled.
    for kind in ('container', 'container', 'volume', 'network'):
        journal.update(cleanup_phase='inventory_' + kind, cleanup_complete=False)
        atomic_json(root / 'journal.json', journal)
        listing = ['docker', 'ps', '-aq'] if kind == 'container' else ['docker', kind, 'ls', '-q']
        try:
            identifiers = command(listing + ['--filter', 'label=' + LABEL + '=' + run_id], env=env).decode().splitlines()
        except Exception as error:
            errors.append({'kind': kind, 'step': 'inventory', 'error_type': type(error).__name__})
            continue
        inspected_resources = []
        for identifier in identifiers:
            try:
                inspected = json.loads(command(['docker', kind, 'inspect', identifier], env=env))[0]
                labels = inspected['Config'].get('Labels', {}) if kind == 'container' else inspected.get('Labels', {})
                if labels.get(LABEL) != run_id:
                    raise RuntimeError('Disposable resource ownership changed')
                inspected_resources.append((labels.get(ROLE) == 'worker', identifier))
            except Exception as error:
                errors.append({'kind': kind, 'error_type': type(error).__name__})
        for _, identifier in sorted(inspected_resources):
            if kind == 'volume' and journal.get('preserve_failed_volumes'):
                retained_failure_volumes.append(identifier)
                continue
            try:
                command(['docker', 'rm', '-f', identifier] if kind == 'container' else
                        ['docker', kind, 'rm', identifier], env=env)
            except Exception as error:
                errors.append({'kind': kind, 'error_type': type(error).__name__})
    final_inventory = {}
    for kind in ('container', 'volume', 'network'):
        listing = ['docker', 'ps', '-aq'] if kind == 'container' else ['docker', kind, 'ls', '-q']
        try:
            remaining = command(listing + ['--filter', 'label=' + LABEL + '=' + run_id], env=env).decode().splitlines()
            final_inventory[kind] = remaining
            expected = set(retained_failure_volumes) if kind == 'volume' else set()
            if set(remaining) != expected:
                errors.append({'kind': kind, 'step': 'final_quiescence_proof'})
        except Exception as error:
            errors.append({'kind': kind, 'step': 'final_inventory', 'error_type': type(error).__name__})
    journal.update(cleanup_complete=not errors, cleanup_errors=errors,
                   retained_failure_volumes=retained_failure_volumes,
                   cleanup_phase='complete' if not errors else 'incomplete', final_inventory=final_inventory)
    atomic_json(root / 'journal.json', journal)
    return not errors


def execute(config, cleanup_only=False):
    root, _ = validate(config)
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = root.with_name('.' + root.name + '-run.lock')
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _execute_locked(config, cleanup_only)
    finally:
        os.close(descriptor)


def _execute_locked(config, cleanup_only=False):
    root, source = validate(config)
    env = {**os.environ, 'DOCKER_HOST': 'unix://' + config['docker_socket'],
           'XDG_RUNTIME_DIR': str(Path(config['docker_socket']).parent)}
    if cleanup_only:
        return {'cleanup_complete': cleanup(root, env)}
    if root.exists():
        raise ValueError('Rehearsal directory must be new; reconcile existing run instead')
    root.mkdir(mode=0o700, parents=True)
    run_id = uuid.uuid4().hex
    project = 'mldsafail-rehearsal-' + run_id
    journal = dict(run_id=run_id, project=project, cleanup_complete=False, state='prepared')
    atomic_json(root / 'journal.json', journal)
    report = dict(scope='disposable frozen-0.5.0 baseline only', benchmark_version='0.5.0',
                  production_activation=False, public_exposure=False, complete=False, stages=[])
    def stage(name, values=None):
        report['stages'].append({'stage': name, **(values or {})})
        atomic_json(root / 'report.json', report)
    stage('protocol', dict(fixture_commit=config['fixture_commit'], images=config['images'],
                          evaluation_ceiling_seconds=1200, epoch_setup_ceiling_seconds=5400,
                          caller_source_commit=json.loads(Path(config['source_manifest']).read_text())['source_commit'],
                          orchestrator_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          operator_source_manifest_sha256=hashlib.sha256(Path(config['source_manifest']).read_bytes()).hexdigest(),
                          release_manifest_sha256=hashlib.sha256(Path(config['release_manifest']).read_bytes()).hexdigest(),
                          rollback_manifest_sha256=hashlib.sha256(Path(config['rollback_manifest']).read_bytes()).hexdigest()))
    try:
        info = json.loads(command(['docker', 'info', '--format', '{{json .}}'], env=env))
        if not any('rootless' in value for value in info.get('SecurityOptions', [])):
            raise RuntimeError('Rootless Docker required')
        images = config['images']
        release = json.loads(Path(config['release_manifest']).read_text())
        rollback = json.loads(Path(config['rollback_manifest']).read_text())
        for image in images.values():
            inspected = json.loads(command(['docker', 'image', 'inspect', image], env=env))[0]
            if inspected['Id'] != image or inspected['Architecture'] != 'amd64':
                raise RuntimeError('Retained Linux amd64 image inventory mismatch')
        for role in ('web', 'coordinator', 'rollback_web', 'rollback_coordinator'):
            inspected = json.loads(command(['docker', 'image', 'inspect', images[role]], env=env))[0]
            expected = rollback['source_commit'] if role.startswith('rollback_') else release['source_commit']
            if inspected['Config'].get('Labels', {}).get('org.mldsafail.source') != expected:
                raise RuntimeError('Application image source label differs from retained manifest')
        evaluator = root / 'evaluator'
        evaluator.mkdir(mode=0o700)
        for name in ('jobs', 'secrets'):
            (evaluator / name).mkdir(mode=0o700)
        (evaluator / 'secrets/signing.key').write_bytes(secrets.token_bytes(32))
        (evaluator / 'secrets/signing.key').chmod(0o600)
        # A trusted external CLI shim adds ownership labels only. Frozen source,
        # solver restrictions, generated data and scoring remain unchanged.
        tools = root / 'owned-docker-cli'
        tools.mkdir(mode=0o700)
        wrapper = tools / 'docker'
        wrapper.write_text('#!/app/.venv/bin/python\nimport os,sys\n'
            'arguments=sys.argv[1:]\n'
            'if arguments and arguments[0]=="run": arguments[1:1]=["--label",' +
            repr(LABEL + '=' + run_id) + ',"--label",' + repr(ROLE + '=worker') + ']\n'
            'os.execv("/usr/local/bin/docker",["docker",*arguments])\n')
        wrapper.chmod(0o700)
        inside_path = '/rehearsal-tools:/app/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin'
        owned_python = ['docker', 'run', '--rm', '--label', LABEL + '=' + run_id, '--label', ROLE + '=controller',
                        '--user', '0:0', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                        '--security-opt', 'no-new-privileges', '--tmpfs', '/tmp:size=128m',
                        '--mount', 'type=bind,src=' + str(evaluator) + ',dst=' + str(evaluator),
                        '--mount', 'type=bind,src=' + str(tools) + ',dst=/rehearsal-tools,readonly',
                        '--mount', 'type=bind,src=' + config['docker_socket'] + ',dst=/var/run/docker.sock',
                        '-e', 'DOCKER_HOST=unix:///var/run/docker.sock', '-e', 'PATH=' + inside_path,
                        '--entrypoint', '/app/.venv/bin/python', images['coordinator'], '-c']
        epoch_code = ('from pathlib import Path; from mldsafail.benchmark_v050 import cli,execution; '
                      'cli.environment=lambda:execution.environment(' + repr(images['worker']) + '); '
                      'cli.create_epoch(Path(' + repr(str(evaluator / 'epoch')) + '))')
        with (root / 'epoch-setup.log').open('xb') as log:
            subprocess.run(owned_python + [epoch_code], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=5400)
        epoch = json.loads((evaluator / 'epoch/manifest.json').read_text())
        if not (evaluator / 'epoch/COMPLETE.json').is_file():
            raise RuntimeError('Fresh epoch not sealed')
        stage('fresh_epoch', {'epoch_id': epoch['id']})
        fingerprint_code = ('from pathlib import Path; from mldsafail.evaluator.mlwe import HostedMLWE; '
                            'print(HostedMLWE(Path(' + repr(str(evaluator / 'epoch')) + '),' +
                            repr(images['worker']) + ',' + repr(epoch['id']) + ').evaluator_fingerprint)')
        hosted_fingerprint = command(owned_python + [fingerprint_code], env=env, timeout=600).decode().strip()
        values = dict(POSTGRES_PASSWORD=secrets.token_hex(32), MLDSAFAIL_SECRET_KEY=secrets.token_hex(32),
                      GITHUB_CLIENT_ID='synthetic-rehearsal', GITHUB_CLIENT_SECRET='synthetic-rehearsal',
                      MLDSAFAIL_DOMAIN='rehearsal.invalid', PRODUCTION_EVALUATOR_ROOT=str(evaluator),
                      ROOTLESS_DOCKER_SOCKET=config['docker_socket'], WEB_IMAGE=images['web'],
                      COORDINATOR_IMAGE=images['coordinator'], WORKER_IMAGE=images['worker'],
                      POSTGRES_IMAGE=images['postgres'], CADDY_IMAGE=images['caddy'],
                      MLDSAFAIL_EVALUATOR_FINGERPRINT=hosted_fingerprint,
                      MLDSAFAIL_HIDDEN_SUITE_VERSION='disposable-' + run_id,
                      MLDSAFAIL_WORKER_CLASS='disposable-baseline-0.5.0', MLDSAFAIL_MLWE_EPOCH_ID=epoch['id'])
        environment_file = root / 'synthetic.env'
        environment_file.write_text(''.join(key + '=' + value + '\n' for key, value in values.items()))
        environment_file.chmod(0o600)
        generated = json.loads(command(['docker', 'compose', '--env-file', str(environment_file),
                         '-f', str(source / 'compose.production.yaml'), 'config', '--format', 'json'], env=env))
        generated['name'] = project
        generated['services'].pop('proxy')  # No TLS/OAuth/public proxy acceptance is claimed.
        generated['volumes'] = {'postgres_data': {'labels': {LABEL: run_id}}}
        generated['networks'] = {'default': {'labels': {LABEL: run_id}}}
        for role, service in generated['services'].items():
            service['labels'] = {**service.get('labels', {}), LABEL: run_id, ROLE: role}
            service['restart'] = 'no'
        generated['services']['coordinator']['environment'].update(PATH=inside_path, DOCKER_HOST='unix:///var/run/docker.sock')
        generated['services']['coordinator']['volumes'].append({'type': 'bind', 'source': str(tools), 'target': '/rehearsal-tools', 'read_only': True})
        generated['services']['web']['ports'] = [{'target': 8000, 'published': '0', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}]
        for role in ('web', 'coordinator'):
            generated['services'][role].pop('depends_on', None)
        compose_file = root / 'compose.json'
        atomic_json(compose_file, generated)
        compose = ['docker', 'compose', '-p', project, '-f', str(compose_file)]
        command(compose + ['up', '-d', '--no-deps', 'db'], env=env)
        deadline = time.monotonic() + 120
        while subprocess.run(compose + ['exec', '-T', 'db', 'pg_isready', '-U', 'mldsafail'], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            if time.monotonic() >= deadline:
                raise RuntimeError('Disposable database readiness timeout')
            time.sleep(1)
        command(compose + ['run', '--rm', '--no-deps', 'migrate'], env=env)
        stage('explicit_fresh_migration')
        command(compose + ['up', '-d', '--no-deps', 'web', 'coordinator'], env=env)
        endpoint = command(compose + ['port', 'web', '8000'], env=env).decode().strip()
        if not endpoint.startswith('127.0.0.1:'):
            raise RuntimeError('Rehearsal is not loopback-only')
        # Reserve the observed ephemeral port for subsequent application recreations.
        generated['services']['web']['ports'][0]['published'] = endpoint.rsplit(':', 1)[1]
        base = 'http://' + endpoint
        token = None
        def request(path, payload=None, key=None):
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            if key:
                headers['Idempotency-Key'] = key
            req = urllib.request.Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, json.load(response)
        deadline = time.monotonic() + 120
        while True:
            try:
                assert request('/health/ready')[0] == 200
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Disposable application readiness timeout')
                time.sleep(1)
        try:
            request('/api/v1/me')
            raise RuntimeError('Unauthenticated API was accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 401
        token_code = '''import json,os
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from mldsafail.web.models import User,utcnow
from mldsafail.web.services import create_api_token
with Session(create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])) as session:
 user=User(display_name='synthetic-disposable-participant');session.add(user);session.commit()
 _,token=create_api_token(session,user,'disposable-rehearsal',expires_at=utcnow()+timedelta(hours=1))
 print(json.dumps({'token':token}))
'''
        token = json.loads(command(compose + ['exec', '-T', 'web', '/app/.venv/bin/python', '-c', token_code], env=env))['token']
        status, _ = request('/api/v1/me')
        assert status == 200
        stage('synthetic_token_authentication')
        payload = dict(repository_url=config['fixture_repository'], commit_sha=config['fixture_commit'],
                       solver_path=config['fixture_solver_path'], benchmark_version='0.5.0', epoch_id=epoch['id'],
                       hypothesis='frozen reference behavior in isolated fresh disposable cohort')
        key = 'rehearsal-' + run_id
        atomic_json(root / 'submission-intent.json', {'idempotency_key': key, 'payload': payload})
        try:
            status, submitted = request('/api/v1/submissions', payload, key)
        except (urllib.error.URLError, TimeoutError):
            # Exactly the same persisted idempotency request, never a fresh key.
            status, submitted = request('/api/v1/submissions', payload, key)
        identifier = submitted['submission']['id']
        atomic_json(root / 'submission-response.json', submitted)
        deadline = time.monotonic() + 1200
        while True:
            _, state = request('/api/v1/submissions/' + identifier)
            if state['submission']['state'] in {'accepted', 'rejected', 'cancelled', 'infrastructure_failed'}:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('20-minute disposable evaluation ceiling exceeded')
            time.sleep(5)
        if state['submission']['state'] != 'accepted':
            raise RuntimeError('Disposable fixture was not accepted')
        _, board = request('/api/v1/leaderboard')
        if not board['leaderboard']:
            raise RuntimeError('Audited disposable leaderboard result absent')
        audit_code = ('import json,os,sys;sys.path.insert(0,"/opt/mldsafail"); from pathlib import Path; '
                      'from deploy.verify_recovery_evidence import verify; '
                      'print(json.dumps(verify(os.environ["MLDSAFAIL_DATABASE_URL"], '
                      'Path(os.environ["MLDSAFAIL_MLWE_EPOCH_PATH"]), '
                      'Path(os.environ["MLDSAFAIL_EVALUATOR_WORK_ROOT"])/"runs")))')
        audited = json.loads(command(compose + ['exec', '-T', 'coordinator', '/app/.venv/bin/python', '-c', audit_code], env=env, timeout=600))
        if not audited['database_evidence_verified'] or audited['result_count'] != 1 or audited['epoch_id'] != epoch['id']:
            raise RuntimeError('Independent disposable result/evidence audit failed')
        stage('submission_to_leaderboard', {'submission_id': identifier, 'independent_audit': True})
        command(compose + ['stop', 'coordinator', 'web'], env=env)
        command([config['python'], '-m', 'deploy.backup_postgres', '--env-file', str(environment_file),
                 '--compose', str(compose_file), '--output', str(root / 'database-backup'), '--verify-restore'], cwd=source, env=env, timeout=360)
        stage('quiescent_disposable_database_restore_equality')
        def database_digest():
            data = command(compose + ['exec', '-T', 'db', 'pg_dump', '-U', 'mldsafail', '--format=plain', '--no-owner', '--no-privileges',
                '--exclude-table-data=rate_limit_states', '--exclude-table-data=api_tokens',
                '--exclude-table-data=audit_events', 'mldsafail'], env=env)
            return hashlib.sha256(b'\n'.join(line for line in data.splitlines() if not line.startswith((b'\\restrict ', b'\\unrestrict ')))).hexdigest()
        before_digest = database_digest()
        epoch_digest = hashlib.sha256((evaluator / 'epoch/COMPLETE.json').read_bytes()).hexdigest()
        for direction, web_image, coordinator_image in [('rollback', images['rollback_web'], images['rollback_coordinator']), ('forward', images['web'], images['coordinator'])]:
            generated['services']['web']['image'] = web_image
            generated['services']['coordinator']['image'] = coordinator_image
            atomic_json(compose_file, generated)
            command(compose + ['up', '-d', '--no-deps', 'web', 'coordinator'], env=env)
            deadline = time.monotonic() + 120
            while True:
                try:
                    assert request('/api/v1/me')[0] == 200
                    assert request('/api/v1/leaderboard')[1] == board
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Disposable application switch readiness failed')
                    time.sleep(1)
            command(compose + ['stop', 'coordinator', 'web'], env=env)
            assert database_digest() == before_digest
            assert hashlib.sha256((evaluator / 'epoch/COMPLETE.json').read_bytes()).hexdigest() == epoch_digest
            assert json.loads(command(['docker', 'image', 'inspect', images['worker']], env=env))[0]['Id'] == images['worker']
            stage(direction + '_application_only_no_migration', {'database_digest': before_digest, 'epoch_digest': epoch_digest,
                    'auth_mutable_rows_excluded': ['rate_limit_states', 'api_tokens', 'audit_events'],
                    'same_token_still_authenticated': True})
        report['behavior_gates_passed'] = True
        stage('baseline_behavior_gates_passed_cleanup_pending')
    except BaseException as error:
        report['error_type'] = type(error).__name__
        stage('failed_partial_evidence_retained')
        raise
    finally:
        journal = json.loads((root / 'journal.json').read_text())
        journal['preserve_failed_volumes'] = not report.get('behavior_gates_passed', False)
        atomic_json(root / 'journal.json', journal)
        report['cleanup_complete'] = cleanup(root, env)
        report['complete'] = report.get('behavior_gates_passed', False) and report['cleanup_complete']
        report['retained_failure_volumes'] = json.loads((root / 'journal.json').read_text()).get('retained_failure_volumes', [])
        atomic_json(root / 'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        result = execute(config, args.cleanup)
        print(json.dumps({'baseline_rehearsal_complete': result.get('complete', False), 'cleanup_complete': result['cleanup_complete']}))
        raise SystemExit(0 if result['cleanup_complete'] else 1)
    except Exception:
        print(json.dumps({'baseline_rehearsal_failed': True, 'private_evidence_retained': True}))
        raise SystemExit(1)
