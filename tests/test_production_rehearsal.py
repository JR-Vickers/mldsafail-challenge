import hashlib
import json
from pathlib import Path

import pytest

from deploy import owned_daemon
from scripts import production_rehearsal as rehearsal
from scripts import production_rehearsal_monitor_load as monitoring


def inputs(tmp_path):
    source = tmp_path / 'operator-source'
    source.mkdir()
    files = {}
    for name in ('Dockerfile', 'Dockerfile.coordinator', '.dockerignore', 'uv.lock', 'pyproject.toml',
                 'compose.production.yaml', 'src/mldsafail/benchmark_v050/worker.py',
                 'src/mldsafail/evaluator/coordinator.py', 'migrations/schema.py',
                 'deploy/worker-linux-amd64.requirements.txt'):
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(name)
        files[name] = hashlib.sha256(file.read_bytes()).hexdigest()
    metadata = dict(source_commit='a' * 40, source_files_sha256=files)
    images = {name: 'sha256:' + hashlib.sha256(name.encode()).hexdigest() for name in
              ('web', 'coordinator', 'worker', 'postgres', 'caddy', 'rollback_web', 'rollback_coordinator')}
    common = dict(source_files_sha256=files, mlwe_trusted_fingerprint='f' * 64,
                  worker_lock_sha256=files['deploy/worker-linux-amd64.requirements.txt'])
    release = dict(common, source_commit='b' * 40,
                   images={role: {'id': images[role]} for role in ('web', 'coordinator', 'worker')})
    rollback = dict(common, source_commit=rehearsal.ROLLBACK_SOURCE,
                    images={role: {'id': images['rollback_' + role] if role != 'worker' else images[role]}
                            for role in ('web', 'coordinator', 'worker')})
    for name, value in [('source', metadata), ('release', release), ('rollback', rollback)]:
        owned_daemon.publish(tmp_path / (name + '.json'), value)
    return dict(run_directory=str(tmp_path / 'state/production'), operator_source=str(source),
                evaluator_root=str(tmp_path / 'state/rehearsal-epoch/evaluator'),
                source_manifest=str(tmp_path / 'source.json'), release_manifest=str(tmp_path / 'release.json'),
                rollback_manifest=str(tmp_path / 'rollback.json'), images=images,
                fixture_repository='https://github.com/owner/fixtures', fixture_commit='c' * 40,
                fixture_solver_path='reference', docker_socket=str(tmp_path / 'daemon.sock'), protected_roots=[])


def test_new_preflight_requires_complete_helpers_and_matching_cohort(tmp_path):
    config = inputs(tmp_path)
    assert rehearsal.validate(config) == (Path(config['run_directory']), Path(config['operator_source']))
    extra = Path(config['operator_source']) / 'unreviewed.py'
    extra.write_text('pass')
    with pytest.raises(ValueError, match='inventory'):
        rehearsal.validate(config)
    extra.unlink()
    rollback = json.loads(Path(config['rollback_manifest']).read_text())
    rollback['source_files_sha256']['src/mldsafail/evaluator/coordinator.py'] = '0' * 64
    owned_daemon.publish(config['rollback_manifest'], rollback)
    with pytest.raises(ValueError, match='cohort'):
        rehearsal.validate(config)


def test_protected_sibling_evaluator_never_passes_preflight(tmp_path):
    config = inputs(tmp_path)
    config['evaluator_root'] = str(tmp_path / 'state/protected-staging')
    config['protected_roots'] = [config['evaluator_root']]
    with pytest.raises(ValueError, match='fresh driver-owned'):
        rehearsal.validate(config)


def test_monitor_cleanup_failure_fences_resource_mutation(tmp_path, monkeypatch):
    root = tmp_path / 'run'
    root.mkdir()
    journal = dict(run_id='owned', monitor_units=[{'path': '/unknown'}])
    owned_daemon.publish(root / 'journal.json', journal)
    def fail(*args, **kwargs): raise RuntimeError('changed monitor identity')
    monkeypatch.setattr(monitoring, 'stop_monitors', fail)
    monkeypatch.setattr(rehearsal.operator_daemon_lifecycle, 'settle', lambda *args, **kwargs: [])
    monkeypatch.setattr(rehearsal, 'command', lambda *args, **kwargs: pytest.fail('Fenced cleanup mutated Docker'))
    assert rehearsal.cleanup(root, {}, journal) is False
    result = json.loads((root / 'journal.json').read_text())
    assert result['cleanup_complete'] is False
    assert any(error['kind'] == 'monitor' for error in result['cleanup_errors'])


def monitor_fixture(tmp_path, *, started=True, present=True):
    root = tmp_path / 'run'
    root.mkdir()
    unit = tmp_path / 'mldsafail-rehearsal-owned-monitor.service'
    payload = b'[Service]\nType=oneshot\n'
    if present: unit.write_bytes(payload)
    owned_daemon.publish(root / 'journal.json', dict(monitor_start_intent=started,
        monitor_units=[dict(path=str(unit), sha256=hashlib.sha256(payload).hexdigest())]))
    owned_daemon.publish(root / 'monitor.json', dict(healthchecks=dict(enabled=True)))
    return root, unit


def test_monitor_stop_and_endpoint_disable_are_independently_recoverable(tmp_path, monkeypatch):
    root, unit = monitor_fixture(tmp_path)
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        if '--property=FragmentPath,LoadState,ActiveState' in argv:
            return f'FragmentPath={unit}\nLoadState=loaded\nActiveState=active\n'.encode()
        return b'inactive\n'
    monkeypatch.setattr(monitoring, 'command', command)
    monitoring.stop_monitors(root, {})
    assert ['systemctl', '--user', 'stop', unit.name] in calls
    assert json.loads((root / 'journal.json').read_text())['monitor_cleanup']['complete'] is True
    assert json.loads((root / 'monitor.json').read_text())['healthchecks']['enabled'] is False


def test_changed_monitor_fragment_cannot_be_stopped_or_claim_cleanup(tmp_path, monkeypatch):
    root, unit = monitor_fixture(tmp_path)
    unit.write_text('changed')
    calls = []
    monkeypatch.setattr(monitoring, 'command', lambda argv, **kwargs: calls.append(argv) or
        f'FragmentPath={unit}\nLoadState=loaded\nActiveState=active\n'.encode())
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        monitoring.stop_monitors(root, {})
    assert not any('stop' in argv for argv in calls)
    assert json.loads((root / 'journal.json').read_text())['monitor_cleanup']['complete'] is False
    assert json.loads((root / 'monitor.json').read_text())['healthchecks']['enabled'] is False


def test_unactivated_partial_install_can_be_settled_without_stopping_unknown_unit(tmp_path, monkeypatch):
    root, unit = monitor_fixture(tmp_path, started=False, present=False)
    monkeypatch.setattr(monitoring, 'command', lambda *args, **kwargs:
                        b'FragmentPath=\nLoadState=not-found\nActiveState=inactive\n')
    monitoring.stop_monitors(root, {})
    assert json.loads((root / 'journal.json').read_text())['monitor_cleanup']['complete'] is True


def test_monitor_invocations_exclude_same_second_dry_run():
    def row(identifier, timestamp):
        return json.dumps(dict(_SYSTEMD_INVOCATION_ID=identifier, __REALTIME_TIMESTAMP=str(timestamp),
                               MESSAGE=json.dumps(dict(scope='service', healthy=True, backup_status='deferred'))))
    raw = '\n'.join([row('dry', 100_800_000), row('before', 100_100_000), row('scheduled', 100_900_000)])
    assert [item['invocation'] for item in monitoring.monitor_rows(raw, since=100.5, excluded={'dry'})] == ['scheduled']


def test_recovery_waits_for_docker_health(tmp_path, monkeypatch):
    calls = []
    states = iter(['starting', 'healthy', 'healthy', 'healthy', 'healthy', 'healthy', 'healthy', 'healthy'])
    def command(argv, **kwargs):
        if 'inspect' not in argv: return b'container\n'
        calls.append(argv)
        return json.dumps([dict(State=dict(Running=True, Health=dict(Status=next(states))))]).encode()
    sleeps = []
    monkeypatch.setattr(monitoring, 'command', command)
    monkeypatch.setattr(monitoring.time, 'sleep', sleeps.append)
    monitoring.wait_service_health(['compose'], {})
    assert len(calls) == 8
    assert sleeps == [2]


@pytest.mark.parametrize('rows,healthy', [([], False), ([], True),
    ([dict(result=dict(healthy=True, backup_status='deferred'))], False),
    ([dict(result=dict(healthy=False, backup_status='deferred', checks=['disk']))], False)])
def test_notification_requires_delivered_phase_specific_health_receipt(rows, healthy):
    with pytest.raises(RuntimeError): monitoring.require_notification(rows, healthy)


def test_monitor_receipt_waits_for_journal_ingestion(monkeypatch):
    from scripts import production_rehearsal_monitor_load as monitoring
    row = dict(MESSAGE=json.dumps(dict(scope='service', healthy=True, backup_status='deferred')),
               _SYSTEMD_INVOCATION_ID='fresh', __REALTIME_TIMESTAMP='101000000')
    outputs = iter([b'', json.dumps(row).encode()])
    sleeps = []
    monkeypatch.setattr(monitoring, 'command', lambda *a, **kw: next(outputs))
    monkeypatch.setattr(monitoring.time, 'sleep', sleeps.append)
    rows = monitoring.wait_monitor_receipt('owned', {}, since=100.5, healthy=True)
    assert rows[0]['invocation'] == 'fresh'
    assert sleeps == [1]


def test_monitor_receipt_never_accepts_missing_or_wrong_health(monkeypatch):
    from scripts import production_rehearsal_monitor_load as monitoring
    monkeypatch.setattr(monitoring, 'command', lambda *a, **kw: b'')
    with pytest.raises(RuntimeError, match='not observed'):
        monitoring.wait_monitor_receipt('owned', {}, since=100, healthy=True, timeout=0)
    row = dict(MESSAGE=json.dumps(dict(scope='service', healthy=True, backup_status='deferred')),
               _SYSTEMD_INVOCATION_ID='fresh', __REALTIME_TIMESTAMP='101000000')
    monkeypatch.setattr(monitoring, 'command', lambda *a, **kw: json.dumps(row).encode())
    with pytest.raises(RuntimeError, match='delivered monitor receipt'):
        monitoring.wait_monitor_receipt('owned', {}, since=100, healthy=False)


@pytest.mark.parametrize('last', ['inactive', 'failed'])
def test_manual_monitor_waits_for_prior_oneshot_to_finish(monkeypatch, last):
    from scripts import production_rehearsal_monitor_load as monitoring
    states = iter([b'activating', b'active', last.encode()])
    sleeps = []
    monkeypatch.setattr(monitoring, 'command', lambda *a, **kw: next(states))
    monkeypatch.setattr(monitoring.time, 'sleep', sleeps.append)
    monitoring.wait_monitor_inactive('owned', {})
    assert sleeps == [1, 1]


@pytest.mark.parametrize('state', [b'active', b'unknown'])
def test_manual_monitor_refuses_unsettled_or_unknown_state(monkeypatch, state):
    from scripts import production_rehearsal_monitor_load as monitoring
    monkeypatch.setattr(monitoring, 'command', lambda *a, **kw: state)
    with pytest.raises(RuntimeError):
        monitoring.wait_monitor_inactive('owned', {}, timeout=0)



@pytest.mark.parametrize('healthy,returncode', [(True, 0), (False, 1)])
def test_monitor_phase_uses_owned_capture_contract_and_expected_receipt(monkeypatch, healthy, returncode):
    from scripts import production_rehearsal_monitor_load as monitoring
    from types import SimpleNamespace
    events = []
    monkeypatch.setattr(monitoring, 'wait_monitor_inactive', lambda *a: events.append('inactive'))
    def owned_run(argv, **kwargs):
        # Custom owned client captures by default; explicit streams must be writable.
        for key in ('stdout', 'stderr'):
            if kwargs.get(key) is not None:
                assert callable(getattr(kwargs[key], 'write', None))
        assert kwargs['check'] is False
        events.append('start')
        return SimpleNamespace(returncode=returncode, stdout=b'', stderr=b'')
    monkeypatch.setattr(monitoring, 'client_run', owned_run)
    def receipt(name, env, *, since, healthy):
        events.append('receipt')
        return [dict(result=dict(healthy=healthy))]
    monkeypatch.setattr(monitoring, 'wait_monitor_receipt', receipt)
    assert monitoring.invoke_monitor('owned', {}, healthy=healthy)[0]['result']['healthy'] is healthy
    assert events == ['inactive', 'start', 'receipt']


@pytest.mark.parametrize('healthy,returncode', [(True, 1), (False, 0)])
def test_monitor_phase_refuses_wrong_exit_before_accepting_receipt(monkeypatch, healthy, returncode):
    from scripts import production_rehearsal_monitor_load as monitoring
    from types import SimpleNamespace
    monkeypatch.setattr(monitoring, 'wait_monitor_inactive', lambda *a: None)
    monkeypatch.setattr(monitoring, 'client_run', lambda *a, **kw: SimpleNamespace(returncode=returncode))
    monkeypatch.setattr(monitoring, 'wait_monitor_receipt', lambda *a, **kw: pytest.fail('Unexpected receipt acceptance'))
    with pytest.raises(RuntimeError, match='exit status'):
        monitoring.invoke_monitor('owned', {}, healthy=healthy)


def test_cleanup_collects_separate_observer_registry_before_settle(tmp_path, monkeypatch):
    observer = dict(id='observer-client')
    owned_daemon.publish(tmp_path / ('observer-clients-' + 'a' * 32 + '.json'), [observer])
    captured = []
    def settle(journal, clients, *args, **kwargs):
        captured.extend(clients)
        return [dict(kind='test_stop')]
    monkeypatch.setattr(rehearsal.operator_daemon_lifecycle, 'settle', settle)
    monkeypatch.setattr(rehearsal, 'command', lambda *a, **k: pytest.fail('Mutation after barrier failure'))
    assert not rehearsal.cleanup(tmp_path, {}, dict(run_id='owned'))
    assert captured == [observer]


def test_observer_client_registry_does_not_write_main_registry(tmp_path, monkeypatch):
    class Completed:
        stdout = b'ok'
    def run(argv, clients, save, root, **kwargs):
        clients.append(dict(id='observer')); save(); return Completed()
    monkeypatch.setattr(rehearsal.owned_client, 'run', run)
    main = tmp_path / 'clients.json'
    owned_daemon.publish(main, [dict(id='main')])
    receipt = 'observer-clients-' + 'b' * 32 + '.json'
    rehearsal.client_run(['docker', 'ps'], env=dict(MLDSAFAIL_OWNED_CLIENT_ROOT=str(tmp_path),
        MLDSAFAIL_OWNED_CLIENT_RECEIPT=receipt), timeout=1)
    assert json.loads(main.read_text()) == [dict(id='main')]
    assert json.loads((tmp_path / receipt).read_text()) == [dict(id='observer')]
