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
    assert events == ['barrier', 'stop', 'restart', 'publish']
    assert journal['dedicated_daemon']['epoch'] == 'new'


def test_failed_barrier_preserves_independent_stop_and_prohibits_restart(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(module.owned_daemon, 'shutdown_barrier', lambda *a, **kw: {'shutdown_proven': False})
    monkeypatch.setattr(module.owned_client, 'stop', lambda entry: events.append('stop'))
    monkeypatch.setattr(module.owned_daemon, 'restart_and_refresh', lambda *a, **kw: events.append('unsafe_restart'))
    assert module.settle({'dedicated_daemon': {}}, [{}], tmp_path, lambda: None)
    assert events == ['stop']
