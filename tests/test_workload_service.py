"""Control-only entrypoint fixtures; no native resource acceptance claims."""
import json
import sys
import threading

import pytest

from mldsafail.evaluator.workload import HostGate, WorkloadBlocked
from mldsafail.evaluator.workload_service import HelperRuntime, cleanup, main, read_configuration
from test_workload import Runtime


def configuration(tmp_path):
    path = tmp_path / 'configuration.json'
    content = dict(root=str(tmp_path / 'gate'), socket=str(tmp_path / 'gate' / 'supervisor.sock'),
                   helper=[sys.executable, '-m', 'reviewed_missing_runtime_helper'],
                   roles={'participant': {'frozen_role': 'participant'}})
    path.write_text(json.dumps(content))
    path.chmod(0o600)
    return path, content


def test_private_configuration_and_help(tmp_path):
    path, expected = configuration(tmp_path)
    assert read_configuration(path) == expected
    path.chmod(0o644)
    with pytest.raises(WorkloadBlocked, match='private_configuration'): read_configuration(path)
    with pytest.raises(SystemExit) as result: main(['--help'])
    assert result.value.code == 0


@pytest.mark.parametrize('change', [
    lambda config: config.update(helper=['relative-helper']),
    lambda config: config.update(socket='/different/supervisor.sock'),
    lambda config: config.update(roles={}),
    lambda config: config.update(command=['arbitrary']),
])
def test_invalid_configuration_is_rejected(tmp_path, change):
    path, config = configuration(tmp_path)
    change(config)
    path.write_text(json.dumps(config))
    with pytest.raises(WorkloadBlocked, match='invalid_supervisor_configuration'):
        read_configuration(path)


def test_cleanup_only_preserves_pending_result_and_pause(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        gate.launch({})
        gate.postflight()
        gate.commit_intent({'job': 'j', 'attempt': 'a'})
        cleanup(gate)
        assert not runtime.live
        assert gate.state['phase'] == 'commit_intent'
        assert gate.state['database_commit'] == {'job': 'j', 'attempt': 'a'}
        assert gate.state['paused']
        with pytest.raises(WorkloadBlocked): gate.acquire('administration', {})


def test_cleanup_never_infers_stopped_from_database_or_postflight_phase(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('administration', {})
        gate.postflight()
        runtime.live = True
        with pytest.raises(WorkloadBlocked, match='resources_reappeared'): cleanup(gate)
        assert gate.state['paused']
        assert gate.state['phase'] == 'postflight'


def test_helper_monitor_uses_independent_bounded_channel(tmp_path):
    helper = tmp_path / 'helper.py'
    helper.write_text('''import json, sys, time
request = json.load(sys.stdin)
if request['method'] == 'launch': time.sleep(5)
print(json.dumps({'result': 'observed'}))
''')
    runtime = HelperRuntime([sys.executable, str(helper)])
    outcomes = []
    def launch():
        with pytest.raises(WorkloadBlocked, match='deadline'):
            runtime.launch({}, {})
        outcomes.append('timed-out')
    thread = threading.Thread(target=launch)
    thread.start()
    try:
        # Use the same named channel as the supervisor's monitor thread.
        observed = []
        monitor = threading.Thread(target=lambda: observed.append(runtime.sample({})), name='heavy-workload-monitor')
        monitor.start()
        monitor.join(1)
        assert not monitor.is_alive()
        assert observed == ['observed']
    finally:
        thread.join(2)
    assert outcomes == ['timed-out']
    for transport in runtime.transports.values():
        for process in transport.pending:
            process.wait(timeout=1)


def test_explicit_resume_after_restart_of_completed_workload(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        gate.acquire('evaluation', {})
        gate.complete()
    with HostGate(tmp_path, runtime).locked() as gate:
        cleanup(gate)
        assert gate.state['phase'] == 'complete'
        assert gate.state['paused']
        gate.resume()
        gate.acquire('administration', {})
