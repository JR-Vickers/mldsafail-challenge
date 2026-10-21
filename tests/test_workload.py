"""Synthetic host ownership tests: no Docker or computational evaluations."""
from dataclasses import asdict

import pytest

from mldsafail.evaluator.workload import HostGate, ProtectionAbort, ResourcePolicy, WorkloadBlocked


class Runtime:
    def __init__(self):
        self.host = {'boot_id': 'boot', 'daemon_id': 'daemon'}
        self.ceiling = 2 * 1024**3
        self.live = False
        self.cleanup = True
        self.lost_ack = False
        self.sample_data = dict(available=1024**3, memory=0, oom_events=0, swap=0,
                                disk_free=6 * 1024**3, logs=0, generation=0, identity_valid=True)

    def identity(self): return dict(self.host)
    def preflight(self, policy): return self.ceiling
    def sample(self, state): return dict(self.sample_data)
    def launch(self, state, specification):
        self.live = True
        if self.lost_ack: raise OSError('lost ack')
        return {'id': 'container', 'birth': 'inspected-birth'}
    def inspect(self, state, birth): return True
    def terminate(self, state):
        if self.cleanup: self.live = False
        return self.cleanup
    def stopped(self, state): return not self.live


def test_host_gate_cross_database_and_admin(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as first:
        first.acquire('evaluation', {'database': 'one'})
        with pytest.raises(WorkloadBlocked, match='host_busy'):
            with HostGate(tmp_path, runtime).locked(): pass
        first.complete()
    with HostGate(tmp_path, runtime).locked() as admin:
        admin.acquire('administration', {'database': 'two'})
        admin.complete()


def test_process_death_requires_cleanup_and_explicit_resume(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {'job': 'one'})
        gate.launch({})
    with HostGate(tmp_path, runtime).locked() as restarted:
        with pytest.raises(WorkloadBlocked): restarted.acquire('evaluation', {})
        restarted.reconcile()
        assert not runtime.live
        with pytest.raises(WorkloadBlocked): restarted.acquire('evaluation', {})
        restarted.resume()
        restarted.acquire('evaluation', {})


@pytest.mark.parametrize('field,value', [
    ('available', 0), ('memory', 2 * 1024**3), ('oom_events', 1), ('swap', 1),
    ('disk_free', 0), ('logs', 129 * 1024**2), ('generation', 1024**3 + 1),
    ('identity_valid', False), ('memory', -1),
])
def test_abort_persists_without_retry(tmp_path, field, value):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        gate.launch({})
        runtime.sample_data[field] = value
        with pytest.raises(ProtectionAbort): gate.complete()
        assert gate.state['paused']
        gate.reconcile()
    with HostGate(tmp_path, runtime).locked() as gate:
        with pytest.raises(WorkloadBlocked): gate.acquire('administration', {})
        runtime.sample_data = Runtime().sample_data
        gate.resume()
        gate.acquire('administration', {})


def test_lost_launch_and_failed_termination(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        runtime.lost_ack = True
        with pytest.raises(OSError): gate.launch({})
        assert gate.state['phase'] == 'launch_intent'
        runtime.cleanup = False
        with pytest.raises(WorkloadBlocked): gate.reconcile()
        with pytest.raises(WorkloadBlocked): gate.resume()


def test_daemon_replacement_never_kills_unknown_resources(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        gate.launch({})
        runtime.host['daemon_id'] = 'replacement'
        with pytest.raises(ProtectionAbort): gate.reconcile()
        assert runtime.live


def test_deferral_and_policy(tmp_path):
    runtime = Runtime()
    runtime.ceiling = 0
    with HostGate(tmp_path, runtime).locked() as gate:
        with pytest.raises(WorkloadBlocked): gate.acquire('evaluation', {})
        assert not gate.path.exists()
    policy = ResourcePolicy()
    assert policy.ceiling(4 * 1024**3, [2 * 1024**3]) == 2 * 1024**3
    assert policy.violation({}, 1024**3) == 'monitor_invalid'
    assert ResourcePolicy(**asdict(policy)).sha256 == policy.sha256


def test_monitor_stops_surviving_worker_without_controller_checkpoint(tmp_path):
    import time
    from mldsafail.evaluator.workload import WorkloadSession
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        gate.launch({})
        session = WorkloadSession(gate).start()
        runtime.sample_data['oom_events'] = 1
        assert session.failed.wait(2)
        session.finish_monitor()
        assert not runtime.live
        with pytest.raises(ProtectionAbort): session.complete()
        assert gate.state['paused']


def test_monitor_exception_is_protection_abort(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        runtime.sample = lambda state: (_ for _ in ()).throw(OSError())
        with pytest.raises(ProtectionAbort, match='monitor_lost'): gate.check()


def test_separate_process_lock_survives_owner_death_as_journal(tmp_path):
    import os
    import signal
    import subprocess
    import sys
    # This child only writes synthetic ownership, never launches resources.
    code = '''
import sys, time
from mldsafail.evaluator.workload import HostGate
class Runtime:
    def identity(self): return {'boot_id': 'boot', 'daemon_id': 'daemon'}
    def preflight(self, policy): return 2147483648
with HostGate(sys.argv[1], Runtime()).locked() as gate:
    gate.acquire('evaluation', {'job': 'synthetic'})
    print('owned', flush=True)
    time.sleep(20)
'''
    child = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'owned'
        with pytest.raises(WorkloadBlocked, match='host_busy'):
            with HostGate(tmp_path, Runtime()).locked(): pass
        os.kill(child.pid, signal.SIGKILL)
        child.wait(timeout=2)
        with HostGate(tmp_path, Runtime()).locked() as gate:
            with pytest.raises(WorkloadBlocked, match='cleanup_or_resume_required'):
                gate.acquire('administration', {})
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=2)
        child.stdout.close()
