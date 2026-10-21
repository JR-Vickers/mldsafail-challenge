from copy import deepcopy

import pytest

from mldsafail.evaluator.workload import HostGate, WorkloadBlocked
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from test_workload import Runtime


def request(identifier, method, **argument):
    return dict(id=identifier, method=method, argument=argument)


def test_durable_duplicate_launch_and_completion(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'controller': {'frozen': True}})
        acquire = request('a', 'acquire', kind='evaluation', reference={})
        assert protocol.dispatch(acquire) == protocol.dispatch(acquire)
        launch = request('b', 'launch', role='controller')
        birth = protocol.dispatch(launch)
        runtime.launch = lambda *args: pytest.fail('duplicate launch')
        assert protocol.dispatch(launch) == birth
        protocol.dispatch(request('c', 'complete'))
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        assert protocol.dispatch(launch) == birth
        assert protocol.dispatch(request('c', 'complete')) is None
        altered = deepcopy(launch)
        altered['argument']['role'] = 'arbitrary'
        with pytest.raises(WorkloadBlocked, match='request_id_reused'): protocol.dispatch(altered)


def test_lost_launch_ack_cannot_repeat_mutation(tmp_path):
    runtime = Runtime()
    runtime.lost_ack = True
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'worker': {}})
        protocol.dispatch(request('a', 'acquire', kind='administration', reference={}))
        launch = request('b', 'launch', role='worker')
        with pytest.raises(OSError): protocol.dispatch(launch)
        with pytest.raises(WorkloadBlocked, match='request_reconciliation_required'): protocol.dispatch(launch)
        protocol.dispatch(request('cleanup', 'reconcile'))
        assert not runtime.live
        assert gate.state['paused']


def test_acquire_replay_cannot_replace_new_workload(tmp_path):
    with HostGate(tmp_path, Runtime()).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        old = request('old', 'acquire', kind='evaluation', reference={})
        first = protocol.dispatch(old)
        protocol.dispatch(request('done', 'complete'))
        second = protocol.dispatch(request('new', 'acquire', kind='administration', reference={}))
        assert first != second
        assert protocol.dispatch(old) == first
        assert gate.state['workload_id'] == second


def test_private_socket_roundtrip_and_slow_client(tmp_path):
    import json
    import os
    import socket
    import time
    from mldsafail.evaluator.workload_socket import PrivateSocket
    if not hasattr(socket, 'SO_PEERCRED'):
        pytest.skip('Linux peer credentials unavailable')
    tmp_path.chmod(0o700)
    with HostGate(tmp_path / 'gate', Runtime()).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        path = tmp_path / 'supervisor.sock'
        with PrivateSocket(path, protocol) as server:
            assert path.stat().st_mode & 0o777 == 0o600
            with socket.socket(socket.AF_UNIX) as slow, socket.socket(socket.AF_UNIX) as client:
                slow.connect(str(path))
                client.connect(str(path))
                server.poll()
                server.poll()
                slow.sendall(b'{')
                client.sendall(json.dumps(request('status', 'status')).encode() + b'\n')
                for _ in range(4): server.poll(.01)
                client.settimeout(.2)
                assert json.loads(client.recv(4096)) == {'result': None}
                for state in server.clients.values(): state['deadline'] = time.monotonic() - 1
                server.poll(.01)
                assert not server.clients
        assert not path.exists()
