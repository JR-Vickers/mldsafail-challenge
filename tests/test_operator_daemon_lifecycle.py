import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('operator_daemon_lifecycle', Path(__file__).parents[1]/'scripts/operator_daemon_lifecycle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_barrier_precedes_creator_stop_and_restart(monkeypatch, tmp_path):
    events = []
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', str(tmp_path/'manifest.json'))
    monkeypatch.setattr(module.owned_daemon, 'shutdown_barrier', lambda *a, **kw: events.append('barrier') or {'shutdown_proven': True})
    monkeypatch.setattr(module.owned_client, 'stop', lambda entry: events.append('stop'))
    monkeypatch.setattr(module.owned_daemon, 'restart_and_refresh', lambda *a, **kw: events.append('restart') or {'epoch': 'new'})
    journal = {'dedicated_daemon': {'epoch': 'old'}}
    assert module.settle(journal, [{}], tmp_path, lambda: events.append('publish')) == []
    assert events == ['barrier', 'publish', 'stop', 'restart', 'publish']
    assert journal['dedicated_daemon']['epoch'] == 'new'


def test_failed_barrier_preserves_independent_stop_and_prohibits_restart(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(module.owned_daemon, 'shutdown_barrier', lambda *a, **kw: {'shutdown_proven': False})
    monkeypatch.setattr(module.owned_client, 'stop', lambda entry: events.append('stop'))
    monkeypatch.setattr(module.owned_daemon, 'restart_and_refresh', lambda *a, **kw: events.append('unsafe_restart'))
    assert module.settle({'dedicated_daemon': {}}, [{}], tmp_path, lambda: None)
    assert events == ['stop']


def test_barrier_publication_failure_still_stops_creators_without_restart(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(module.owned_daemon, 'shutdown_barrier', lambda *a, **kw: {'shutdown_proven': True})
    monkeypatch.setattr(module.owned_client, 'stop', lambda entry: events.append('stop'))
    monkeypatch.setattr(module.owned_daemon, 'restart_and_refresh', lambda *a, **kw: events.append('unsafe_restart'))
    errors = module.settle({'dedicated_daemon': {}}, [{}], tmp_path,
                          lambda: (_ for _ in ()).throw(OSError('publication')))
    assert errors and events == ['stop']


def test_durable_pending_barrier_resumes_restart_without_killing_new_daemon(monkeypatch, tmp_path):
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST', str(tmp_path/'manifest.json'))
    monkeypatch.setattr(module.owned_daemon, 'shutdown_barrier', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('must not kill replacement epoch')))
    monkeypatch.setattr(module.owned_client, 'stop', lambda entry: None)
    received = []
    monkeypatch.setattr(module.owned_daemon, 'restart_and_refresh', lambda *a, **kw: received.append(kw['attempt_id']) or {'epoch': 'new'})
    journal = {'dedicated_daemon': {'epoch': 'old'}, 'daemon_reconciliation': {'attempt': 'operator-existing', 'receipt': {'shutdown_proven': True}}}
    assert module.settle(journal, [], tmp_path, lambda: None) == []
    assert received == ['operator-existing']
    assert 'daemon_reconciliation' not in journal


def test_distinct_run_roots_cannot_share_daemon_concurrently(tmp_path):
    import os
    import pytest
    tmp_path.chmod(0o700)
    manifest = {'provisioning': {'base': module.owned_daemon._private_directory(tmp_path)}}
    descriptor = module.lock_daemon(manifest)
    try:
        with pytest.raises(BlockingIOError):
            module.lock_daemon(manifest)
    finally:
        os.close(descriptor)


def test_damaged_creator_authority_prohibits_restart_after_positive_barrier(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(module.owned_daemon, 'shutdown_barrier', lambda *a, **kw: events.append('barrier') or {'shutdown_proven': True})
    monkeypatch.setattr(module.owned_client, 'stop', lambda entry: events.append('stop'))
    monkeypatch.setattr(module.owned_daemon, 'restart_and_refresh', lambda *a, **kw: events.append('unsafe_restart'))
    errors = module.settle({'dedicated_daemon': {}}, [{}], tmp_path, lambda: None, permit_restart=False)
    assert events == ['barrier', 'stop']
    assert errors[-1]['step'] == 'daemon_restart_prohibited'
