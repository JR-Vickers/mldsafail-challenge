from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import hosted_vps_failure_driver as historical
from scripts.production_rehearsal_exercises import Exercises


@pytest.fixture
def forbid_historical_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Historical unowned I/O must be unreachable')
    monkeypatch.setattr(historical, 'command', forbidden)
    monkeypatch.setattr(historical, 'containers', forbidden)
    monkeypatch.setattr(historical, 'worker_owned', forbidden)


def runner(tmp_path):
    value = object.__new__(Exercises)
    value.path = tmp_path / 'journal.json'
    value.j = dict(closing=False, work_root=str(tmp_path / 'jobs'), original_mode=0o700,
                   worker_image='sha256:' + 'a' * 64, owned_attempts=[], scenarios={}, user='synthetic')
    Path(value.j['work_root']).mkdir(mode=0o700)
    value.path.write_text(json.dumps(value.j))
    value.c = dict(run_id='synthetic-run', fixture_url='https://github.com/owner/fixtures', fixture_sha='a' * 40)
    value.low_memory_since = None
    value.touch = lambda: None
    return value


def test_guard_and_fault_use_only_explicit_disposable_io(tmp_path, monkeypatch, forbid_historical_io):
    value = runner(tmp_path)
    value.probe = lambda *args, **kwargs: {'active': []}
    value.containers = lambda: []
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path: 'MemAvailable: 262144 kB\n'
                        if str(path) == '/proc/meminfo' else original(path))
    monkeypatch.setattr('scripts.production_rehearsal_exercises.shutil.disk_usage', lambda path: SimpleNamespace(free=6 * 1024**3))
    assert value.guard() == []
    value.probe_id = 'owned-probe'
    calls = []
    value.call = lambda args, **kwargs: calls.append(args) or ''
    value.fault(True)
    assert Path(value.j['work_root']).stat().st_mode & 0o222 == 0
    value.fault(False)
    assert Path(value.j['work_root']).stat().st_mode & 0o777 == 0o700
    assert calls[0][:3] == ['docker', 'exec', 'owned-probe']


def test_worker_ownership_uses_fresh_root_and_exact_attempt(tmp_path, forbid_historical_io):
    value = runner(tmp_path)
    info = dict(Image=value.j['worker_image'], Name='/mlwe-owned', Mounts=[dict(
        Destination='/solver', RW=False, Source=str(Path(value.j['work_root']) / 'runs/submission/2/solver'))])
    assert value.worker_owned(info, [['submission', 2]], value.j['worker_image'])
    assert not value.worker_owned(info, [['submission', 1]], value.j['worker_image'])
    info['Mounts'][0]['Source'] = '/srv/mldsafail-evaluator/jobs/runs/submission/2/solver'
    assert not value.worker_owned(info, [['submission', 2]], value.j['worker_image'])


def test_lease_scenario_cannot_fall_back_to_historical_inventory(tmp_path, forbid_historical_io):
    value = runner(tmp_path)
    value.guard = lambda *args: []
    value.containers = lambda: []
    value.api = lambda *args, **kwargs: {'submission': {'id': 'submission'}}
    value.probe = lambda action, **kwargs: {'submission': None} if action == 'lookup' else dict(
        state='running', lease_expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    value.wait = lambda *args: True
    attempts, mutations = [], []
    def one_shot(identifier, attempt):
        attempts.append(attempt)
        value.process = 'owned-coordinator'
    value.one_shot = one_shot
    value.finish_process = lambda *args: None
    value.mutate = lambda argv: mutations.append(argv)
    value.verify = lambda *args: None
    value.scenario('lease', 'reference')
    assert attempts == [1, 2]
    assert mutations == [['docker', 'kill', 'owned-coordinator'], ['docker', 'rm', 'owned-coordinator']]
    assert value.j['scenarios']['lease']['passed'] is True
