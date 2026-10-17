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


def test_full_run_wait_uses_sparse_polling_and_preserves_exit_audit(monkeypatch):
    from scripts import production_rehearsal_exercises as module
    runner = object.__new__(module.Exercises)
    runner.process = 'owned-coordinator'
    states = iter([True, False, False])
    monkeypatch.setattr(runner, 'inspect', lambda identifier: dict(State=dict(Running=next(states), ExitCode=0)))
    guarded, calls, sleeps = [], [], []
    monkeypatch.setattr(runner, 'guard', guarded.append)
    monkeypatch.setattr(runner, 'probe', lambda *a, **kw: calls.append(a))
    monkeypatch.setattr(runner, 'call', lambda argv: calls.append(argv) or '')
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    runner.finish_process('submission')
    assert sleeps == [10]
    assert guarded == ['submission', 'submission']
    assert ['docker', 'rm', 'owned-coordinator'] in calls
    assert runner.process is None


def test_probe_lifetime_exceeds_explicit_rehearsal_ceiling(tmp_path, monkeypatch):
    from scripts.native_operator_unit import REHEARSAL_OPERATOR_LIMIT
    value = runner(tmp_path)
    calls = []
    value.call = lambda argv: calls.append(argv) or 'probe'
    template = dict(HostConfig=dict(Memory=512, CgroupParent='owned', Tmpfs={}),
        NetworkSettings=dict(Networks={'owned-network': {}}),
        Config=dict(User='0:0', Labels={}, Env=[]), Mounts=[], Image='sha256:' + 'a' * 64)
    value.clone(template)
    code = calls[0][-1]
    import ast
    tree = ast.parse(code)
    duration = tree.body[-1].value.args[0].value
    assert REHEARSAL_OPERATOR_LIMIT < duration <= REHEARSAL_OPERATOR_LIMIT + 1800


def test_short_fault_wait_keeps_two_second_observation_window(tmp_path, monkeypatch):
    from scripts import production_rehearsal_exercises as module
    value = runner(tmp_path)
    value.guard = lambda *a: None
    results = iter([False, True])
    sleeps = []
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    value.wait(lambda: next(results), 90)
    assert sleeps == [2]
