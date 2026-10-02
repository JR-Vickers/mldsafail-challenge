"""Local tests of the operator runner; no staging or private evidence access."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


driver = load('hosted_vps_failure_driver')
runner = load('hosted_vps_failure_acceptance')


def test_container_targeting_requires_submission_mount_and_image():
    worker = {'Image': 'sha256:worker', 'Name': '/mlwe-random', 'Mounts': [
        {'Source': '/srv/mldsafail-evaluator/jobs/runs/owned/2/solver',
         'Destination': '/solver', 'RW': False}]}
    assert driver.worker_owned(worker, [['owned', 2]], 'sha256:worker')
    for field, value in [('Image', 'other'), ('Name', '/unrelated')]:
        changed = deepcopy(worker)
        changed[field] = value
        assert not driver.worker_owned(changed, [['owned', 2]], 'sha256:worker')
    for field, value in [('Source', '/srv/mldsafail-evaluator/jobs/runs/other/2/solver'),
                         ('Destination', '/epoch'), ('RW', True)]:
        changed = deepcopy(worker)
        changed['Mounts'][0][field] = value
        assert not driver.worker_owned(changed, [['owned', 2]], 'sha256:worker')
    assert not driver.worker_owned(worker, [['owned', 1]], 'sha256:worker')


def config(tmp_path):
    return {'directory': str(tmp_path), 'run_id': 'test-run', 'deployment': '/srv/app',
            'env_file': '/srv/app/private.env', 'fixture_url': 'https://github.com/owner/fixtures',
            'fixture_sha': 'a' * 40, 'release_manifest': {}, 'rollback_manifest': {}}


def test_private_journal_binding_and_resume(tmp_path):
    first = driver.Driver(config(tmp_path))
    first.j['scenarios']['crash'] = {'key': 'persisted', 'submission': 'owned'}
    first.touch()
    assert first.path.stat().st_mode & 0o777 == 0o600
    second = driver.Driver(config(tmp_path))
    assert second.j['scenarios'] == first.j['scenarios']
    changed = config(tmp_path)
    changed['fixture_sha'] = 'b' * 40
    with pytest.raises(RuntimeError, match='different inputs'):
        driver.Driver(changed)


def test_deadline_never_changes_worker_limit(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    subject.guard = lambda _: None
    ticks = iter([0, 0, 2, 4])
    monkeypatch.setattr(driver.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(driver.time, 'sleep', lambda _: None)
    with pytest.raises(RuntimeError, match='deadline'):
        subject.wait(lambda: False, 3)


def evidence(name):
    terminal = {'crash': 'accepted', 'retry': 'accepted', 'lease': 'accepted',
                'exhaustion': 'infrastructure_failed', 'invalid': 'rejected',
                'timeout': 'cancelled', 'cancellation': 'cancelled'}[name]
    count = 3 if name == 'exhaustion' else 2 if name in {'retry', 'lease'} else 1
    attempts = []
    transitions = ['queued']
    for number in range(1, count + 1):
        failure = number < count or name == 'exhaustion'
        attempts.append({'number': number, 'status': 'infrastructure_failed' if failure else terminal,
                         'failure_class': ('lease_expired' if name == 'lease' else 'PermissionError') if failure
                         else ('invalid_answer' if name == 'invalid' else None),
                         'started': f'2026-10-01T00:00:{number * 15:02d}+00:00',
                         'finished': f'2026-10-01T00:00:{number * 15 + 1:02d}+00:00'})
        transitions += ['validating']
        if name == 'lease' and number == 1:
            transitions += ['running']
        if failure:
            transitions += ['infrastructure_failed']
            if number < count:
                transitions += ['queued']
        else:
            transitions += ['running', terminal]
    return {'state': terminal, 'job_status': 'failed' if name == 'exhaustion' else 'complete',
            'attempt_count': count, 'max_attempts': 3, 'attempts': attempts, 'transitions': transitions,
            'results': ['result'] if terminal == 'accepted' else [],
            'rejection_code': 'invalid_answer' if name == 'invalid' else None}


def subject_with_state(tmp_path, monkeypatch, name, state):
    subject = driver.Driver(config(tmp_path))
    subject.j.update(scenarios={name: {}}, owned_attempts=[], worker_image='worker')
    def probe(action, **kw):
        if action == 'state':
            return state
        if action == 'timeout':
            return {'timeout': True}
        return {'evidence_verified': True}
    subject.probe = probe
    subject.api = lambda route, **kw: ({'leaderboard': [{'submission': 'result'}]}
        if route.endswith('leaderboard') else {'submission': {'state': state['state']}})
    subject.guard = lambda *args: None
    monkeypatch.setattr(driver, 'containers', lambda: [])
    monkeypatch.setattr(driver, 'command', lambda *args, **kw: '<safe dashboard>')
    return subject


@pytest.mark.parametrize('name', list(driver.SCENARIOS))
def test_attempt_expectations(tmp_path, monkeypatch, name):
    subject = subject_with_state(tmp_path, monkeypatch, name, evidence(name))
    subject.verify(name, driver.SCENARIOS[name], 'owned')


@pytest.mark.parametrize('mutate', [
    lambda s: s.update(attempt_count=4),
    lambda s: s.update(results=[]),
    lambda s: s['attempts'][0].update(failure_class='crash'),
    lambda s: s['attempts'][1].update(started='2026-10-01T00:00:17+00:00'),
    lambda s: s.update(transitions=['queued', 'validating', 'running', 'accepted']),
])
def test_retry_rejects_false_success(tmp_path, monkeypatch, mutate):
    state = evidence('retry')
    mutate(state)
    subject = subject_with_state(tmp_path, monkeypatch, 'retry', state)
    with pytest.raises(RuntimeError):
        subject.verify('retry', 'reference', 'owned')


def test_lost_submission_response_reconciles_without_post(tmp_path, monkeypatch):
    subject = subject_with_state(tmp_path, monkeypatch, 'crash', evidence('crash'))
    subject.j['user'] = 'participant'
    subject.j['scenarios']['crash'] = {'key': 'stable-key'}
    original = subject.probe
    subject.probe = lambda action, **kw: ({'submission': 'owned'} if action == 'lookup' else original(action, **kw))
    subject.scenario('crash', 'crash')
    assert subject.j['scenarios']['crash']['passed']
    assert subject.j['scenarios']['crash']['submission'] == 'owned'


def test_cleanup_restores_permissions_and_only_owned_containers(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir(mode=0o500)
    journal = tmp_path / 'journal.json'
    driver.save(journal, {'run_id': 'run', 'worker_image': 'worker', 'owned_attempts': [],
                         'work_root': str(work), 'original_mode': 0o700, 'maintenance': True,
                         'compose': ['docker', 'compose']})
    monkeypatch.setattr(driver, 'containers', lambda: [
        {'Id': 'owned', 'Config': {'Labels': {'org.mldsafail.acceptance': 'run'}}},
        {'Id': 'other', 'Config': {'Labels': {}}, 'Image': 'other', 'Name': '/mlwe-other', 'Mounts': []}])
    calls = []
    def command(args, **kw):
        calls.append(args)
        return 'normal' if 'ps' in args else ''
    monkeypatch.setattr(driver, 'command', command)
    driver.cleanup(journal)
    assert work.stat().st_mode & 0o777 == 0o700
    assert ['docker', 'rm', '-f', 'owned'] in calls
    assert not any('other' in call for call in calls)
    assert ['docker', 'compose', 'start', 'coordinator'] in calls
    assert json.loads(journal.read_text())['cleanup_complete']


def test_watchdog_restores_after_heartbeat_expiry(tmp_path, monkeypatch):
    journal = tmp_path / 'journal.json'
    driver.save(journal, {'heartbeat': 0})
    cleaned = []
    monkeypatch.setattr(driver.time, 'sleep', lambda _: None)
    monkeypatch.setattr(driver.time, 'time', lambda: 46)
    monkeypatch.setattr(driver, 'cleanup', lambda p: cleaned.append(p))
    driver.watchdog(journal)
    assert cleaned == [journal]


def test_token_permissions_and_fixture_contents(tmp_path):
    token = tmp_path / 'token'
    token.write_text('synthetic-bearer')
    token.chmod(0o644)
    with pytest.raises(ValueError):
        runner.private_token(token)
    token.chmod(0o600)
    assert runner.private_token(token) == 'synthetic-bearer'
    files = sorted(str(p.relative_to(runner.FIXTURES)) for p in runner.FIXTURES.rglob('*') if p.is_file())
    assert files == ['crash/solver.py', 'hang/solver.py', 'invalid/solver.py', 'reference/solver.py']
    namespace = {}
    exec((runner.FIXTURES / 'invalid/solver.py').read_text(), namespace)
    from mldsafail.benchmark_v050.generator import generate_mlwe
    from mldsafail.benchmark_v050.verify import verify_candidate
    instance = generate_mlwe('small', 0, 1).public
    assert not verify_candidate(instance, namespace['solve'](instance.to_dict()))['verified']


def test_privacy_probe_never_returns_hidden_material(tmp_path, monkeypatch):
    probe = load('hosted_vps_failure_probe')
    epoch = tmp_path / 'epoch'
    epoch.mkdir()
    (epoch / 'manifest.json').write_text(json.dumps({'cases': [{'seed': 987654321012345}]}))
    (epoch / 'secret.json').write_text(json.dumps({'nonce': 'PRIVATE_NONCE_SENTINEL'}))
    monkeypatch.setenv('MLDSAFAIL_DATABASE_URL', 'sqlite://')
    monkeypatch.setenv('MLDSAFAIL_MLWE_EPOCH_PATH', str(epoch))
    assert probe.inspect({'action': 'privacy', 'text': '{"state":"accepted"}'}) == {'private_material_absent': True}
    for text in ('PRIVATE_NONCE_SENTINEL', '987654321012345', '/srv/mldsafail-evaluator/epoch',
                 '{"seed":1}', '{"candidate":{}}', '{"s1":[]}'):
        with pytest.raises(AssertionError):
            probe.inspect({'action': 'privacy', 'text': text})


def test_clone_preserves_service_identity_and_isolation(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    template = {'Image': 'sha256:pinned', 'Config': {'User': '0:0', 'Env': ['PRIVATE=secret'],
        'WorkingDir': '/app', 'Labels': {'com.docker.compose.service': 'coordinator'}},
        'NetworkSettings': {'Networks': {'private': {'IPAddress': 'old'}}},
        'HostConfig': {'Binds': ['/host:/host'], 'NetworkMode': 'private', 'ReadonlyRootfs': True,
                       'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                       'RestartPolicy': {'Name': 'unless-stopped'}}}
    before = deepcopy(template)
    sent = []
    class FakeConnection:
        def __init__(self, *_):
            pass
        def request(self, method, route, body, headers):
            sent.append(json.loads(body))
        def getresponse(self):
            class Response:
                status = 201
                def read(self):
                    return b'{"Id":"owned-coordinator"}'
            return Response()
    monkeypatch.setenv('DOCKER_HOST', 'unix:///rootless.sock')
    monkeypatch.setattr(driver.http.client, 'HTTPConnection', FakeConnection)
    monkeypatch.setattr(driver, 'command', lambda args, **kw: '{"ApiVersion":"1.47"}' if 'version' in args else '')
    assert subject.clone(template, once=True) == 'owned-coordinator'
    actual = sent[0]
    assert actual['NetworkingConfig'] == {'EndpointsConfig': {'private': {}}}
    assert actual['Env'] == template['Config']['Env']
    assert actual['User'] == template['Config']['User']
    assert actual['Image'] == template['Image']
    assert actual['Cmd'][-1] == '--once'
    assert actual['Labels'] == {'org.mldsafail.acceptance': 'test-run'}
    assert actual['HostConfig'] == {**template['HostConfig'], 'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}}
    assert template == before


def test_switch_never_starts_coordinator_or_migrations(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    subject.j.update(identity={'compatible': True}, snapshot={'digest': 'preserved'}, leaderboard={'leaderboard': []})
    subject.c.update(revoked_token='revoked')
    subject.probe_id = 'current-inspector'
    subject.guard = lambda *args: None
    subject.wait = lambda predicate, *args: predicate()
    subject.health = lambda: True
    subject.clone = lambda *args: 'rollback-inspector'
    subject.probe = lambda action: subject.j[action]
    subject.api = lambda route, **kw: subject.j['leaderboard'] if route.endswith('leaderboard') else {}
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        if 'inspect' in args:
            return '[{}]'
        return 'coordinator' if 'ps' in args else ''
    monkeypatch.setattr(driver, 'command', command)
    subject.switch({'images': {'web': {'id': 'sha256:web'}, 'coordinator': {'id': 'sha256:coordinator'}}})
    assert any('create' in c and c[-1] == 'coordinator' and '--no-deps' in c for c in calls)
    assert any('up' in c and c[-1] == 'web' and '--no-deps' in c for c in calls)
    assert not any('up' in c and 'coordinator' in c for c in calls)
    assert not any('migrate' in c or 'db' in c for c in calls)


def test_api_negotiation():
    assert driver.docker_api_version({'ApiVersion': '1.52', 'MinAPIVersion': '1.44'}) == '1.47'
    assert driver.docker_api_version({'ApiVersion': '1.43'}) == '1.43'
    with pytest.raises(RuntimeError):
        driver.docker_api_version({'ApiVersion': '1.40'})
    with pytest.raises(RuntimeError):
        driver.docker_api_version({'ApiVersion': '1.52', 'MinAPIVersion': '1.48'})


def test_cleanup_seals_heartbeat_and_persists_failure(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    subject.j.update(worker_image='worker', cleanup_complete=False)
    subject.touch()
    monkeypatch.setattr(driver, 'containers', lambda: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(RuntimeError, match='incomplete'):
        driver.cleanup(subject.path)
    data = json.loads(subject.path.read_text())
    assert data['closing'] and not data['cleanup_complete'] and data['cleanup_errors']
    with pytest.raises(RuntimeError, match='Cleanup'):
        subject.touch()


def test_cleanup_attempts_service_restore_when_permission_restore_fails(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    subject.j.update(worker_image='worker', cleanup_complete=False,
                     work_root=str(tmp_path / 'missing'), original_mode=0o700,
                     maintenance=True, compose=['docker', 'compose'],
                     service_states={'web': False, 'coordinator': True})
    subject.touch()
    (tmp_path / 'cleanup-token').write_text('private')
    calls = []
    monkeypatch.setattr(driver, 'containers', lambda: [])
    monkeypatch.setattr(driver, 'command', lambda args, **kw: calls.append(args))
    with pytest.raises(RuntimeError, match='incomplete'):
        driver.cleanup(subject.path)
    assert ['docker', 'compose', 'stop', 'web'] in calls
    assert ['docker', 'compose', 'start', 'coordinator'] in calls
    assert not (tmp_path / 'cleanup-token').exists()
    assert not json.loads(subject.path.read_text())['cleanup_complete']
    (tmp_path / 'missing').mkdir()
    driver.cleanup(subject.path)
    assert json.loads(subject.path.read_text())['cleanup_complete']


def test_watchdog_seal_prevents_mutation_and_heartbeat(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    subject.j.update(closing=True, cleanup_complete=False)
    driver.save(subject.path, subject.j)
    before = subject.path.read_bytes()
    subject.heartbeat()
    assert subject.path.read_bytes() == before
    calls = []
    monkeypatch.setattr(driver, 'command', lambda args: calls.append(args))
    with pytest.raises(RuntimeError, match='Cleanup'):
        subject.mutate(['docker', 'start', 'owned'])
    with pytest.raises(RuntimeError, match='Cleanup'):
        subject.clone({})
    assert not calls


def test_heartbeat_thread_cannot_reopen_cleanup(tmp_path, monkeypatch):
    import threading
    subject = driver.Driver(config(tmp_path))
    subject.j.update(worker_image='worker', cleanup_complete=False)
    subject.touch()
    monkeypatch.setattr(driver, 'containers', lambda: [])
    entered = threading.Event()
    release = threading.Event()
    def hold():
        with driver.journal_lock(subject.path):
            entered.set()
            release.wait(2)
    owner = threading.Thread(target=hold)
    owner.start()
    assert entered.wait(2)
    cleanup_thread = threading.Thread(target=driver.cleanup, args=(subject.path,))
    cleanup_thread.start()
    heartbeat = threading.Thread(target=subject.heartbeat)
    heartbeat.start()
    release.set()
    for thread in [owner, cleanup_thread, heartbeat]:
        thread.join(2)
        assert not thread.is_alive()
    data = json.loads(subject.path.read_text())
    assert data['closing'] and data['cleanup_complete']


def test_stale_watchdog_cannot_cleanup_resumed_generation(tmp_path, monkeypatch):
    subject = driver.Driver(config(tmp_path))
    subject.j.update(generation=2, cleanup_complete=False, heartbeat=0)
    driver.save(subject.path, subject.j)
    before = subject.path.read_bytes()
    driver.cleanup(subject.path, generation=1)
    assert subject.path.read_bytes() == before
    monkeypatch.setattr(driver.time, 'sleep', lambda _: None)
    monkeypatch.setattr(driver.time, 'time', lambda: 100)
    driver.watchdog(subject.path, generation=1)
    assert subject.path.read_bytes() == before


@pytest.mark.parametrize('failure', ['permissions', 'inventory', 'container', 'release', 'service', 'credential', 'health'])
def test_cleanup_independently_attempts_each_boundary(tmp_path, monkeypatch, failure):
    work = tmp_path / 'work'
    work.mkdir(mode=0o500)
    subject = driver.Driver(config(tmp_path))
    subject.j.update(worker_image='worker', cleanup_complete=False, original_mode=0o700,
                     work_root=str(work), maintenance=True, compose=['docker', 'compose'],
                     service_states={'web': True, 'coordinator': True}, restore_command=['restore-release'])
    subject.touch()
    credential = tmp_path / 'cleanup-token'
    credential.write_text('private')
    calls = []
    chmod = driver.os.chmod
    unlink = driver.Path.unlink
    def permissions(path, mode):
        calls.append('permissions')
        if failure == 'permissions':
            raise OSError()
        return chmod(path, mode)
    def remove(path, **kwargs):
        if path == credential:
            calls.append('credential')
            if failure == 'credential':
                raise OSError()
        return unlink(path, **kwargs)
    def inventory():
        calls.append('inventory')
        if failure == 'inventory':
            raise RuntimeError()
        return [{'Id': 'owned', 'Config': {'Labels': {'org.mldsafail.acceptance': 'test-run'}}}]
    def command(argv, **kw):
        boundary = ('release' if argv[0] == 'restore-release' else 'health' if argv[0] == 'curl'
                    else 'container' if 'rm' in argv else 'service')
        calls.append(boundary)
        if failure == boundary:
            raise RuntimeError()
        return ''
    monkeypatch.setattr(driver.os, 'chmod', permissions)
    monkeypatch.setattr(driver.Path, 'unlink', remove)
    monkeypatch.setattr(driver, 'containers', inventory)
    monkeypatch.setattr(driver, 'command', command)
    with pytest.raises(RuntimeError, match='incomplete'):
        driver.cleanup(subject.path)
    assert {'permissions', 'inventory', 'release', 'service', 'credential', 'health'} <= set(calls)
    data = json.loads(subject.path.read_text())
    assert data['closing'] and data['cleanup_errors'] and not data['cleanup_complete']
