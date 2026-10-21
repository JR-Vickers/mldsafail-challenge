from copy import deepcopy

import pytest

from mldsafail.evaluator.workload import HostGate, WorkloadBlocked
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from test_workload import Runtime


@pytest.fixture(autouse=True)
def request_identifiers():
    global _identifiers, _generation, _sequence
    _identifiers, _generation, _sequence = {}, 0, 0


def request(identifier, method, **argument):
    global _generation, _sequence
    if identifier not in _identifiers:
        if method == 'acquire':
            _generation += 1
            _sequence = 0
        _sequence += 1
        _identifiers[identifier] = f'{_generation}:{_sequence}'
    return dict(id=_identifiers[identifier], method=method, argument=argument)


def finish(protocol, gate, prefix):
    ownership = gate.state['workload_id']
    protocol.dispatch(request(prefix + '-postflight', 'postflight', ownership=ownership))
    binding = {'job': 'synthetic', 'attempt': 1, 'result': 'accepted'}
    protocol.dispatch(request(prefix + '-intent', 'commit_intent', ownership=ownership, binding=binding))
    protocol.dispatch(request(prefix + '-ack', 'acknowledge_commit', ownership=ownership, binding=binding))
    return protocol.dispatch(request(prefix + '-release', 'release', ownership=ownership))


def test_durable_duplicate_launch_and_completion(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'controller': {'frozen': True}})
        acquire = request('a', 'acquire', kind='evaluation', reference={})
        assert protocol.dispatch(acquire) == protocol.dispatch(acquire)
        launch = request('b', 'launch', ownership=gate.state['workload_id'], role='controller')
        birth_token = gate.state['workload_id']
        birth = protocol.dispatch(launch)
        runtime.launch = lambda *args: pytest.fail('duplicate launch')
        assert protocol.dispatch(launch) == birth
        finish(protocol, gate, 'c')
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'controller': {'frozen': True}, 'arbitrary': {}})
        assert protocol.dispatch(launch) == birth
        assert protocol.dispatch(request('c-release', 'release', ownership=birth_token)) is None
        altered = deepcopy(launch)
        altered['argument']['role'] = 'arbitrary'
        with pytest.raises(WorkloadBlocked, match='request_id_reused'): protocol.dispatch(altered)


def test_lost_launch_ack_cannot_repeat_mutation(tmp_path):
    runtime = Runtime()
    runtime.lost_ack = True
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'worker': {}})
        protocol.dispatch(request('a', 'acquire', kind='administration', reference={}))
        launch = request('b', 'launch', ownership=gate.state['workload_id'], role='worker')
        with pytest.raises(OSError): protocol.dispatch(launch)
        with pytest.raises(WorkloadBlocked, match='request_reconciliation_required'): protocol.dispatch(launch)
        protocol.dispatch(request('cleanup', 'reconcile', ownership=gate.state['workload_id']))
        assert not runtime.live
        assert gate.state['paused']


def test_acquire_replay_cannot_replace_new_workload(tmp_path):
    with HostGate(tmp_path, Runtime()).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        old = request('old', 'acquire', kind='evaluation', reference={})
        first = protocol.dispatch(old)
        finish(protocol, gate, 'done')
        second = protocol.dispatch(request('new', 'acquire', kind='administration', reference={}))
        assert first != second
        with pytest.raises(WorkloadBlocked, match='request_generation'):
            protocol.dispatch(old)
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


def test_invalid_requests_never_record_intent(tmp_path):
    with HostGate(tmp_path, Runtime()).locked() as gate:
        protocol = SupervisorProtocol(gate, {'controller': {}})
        token = protocol.dispatch(request('acquire', 'acquire', kind='evaluation', reference={}))
        before = gate.path.read_bytes()
        for malformed in (
            request('bad-role', 'launch', ownership=token, role='unknown'),
            request('bad-token', 'launch', ownership='stale', role='controller'),
            request('bad-binding', 'bind', ownership=token, reference=[]),
            request('bad-release', 'release', ownership=token),
            request('bad-method', 'complete', ownership=token),
            request('bad-extra', 'postflight', ownership=token, extra=True),
        ):
            with pytest.raises(WorkloadBlocked): protocol.dispatch(malformed)
            assert gate.path.read_bytes() == before


def test_postflight_retains_ownership_until_matching_commit_ack(tmp_path):
    runtime = Runtime()
    binding = {'job': 'j', 'attempt': 'a', 'result_sha256': 'f' * 64}
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'controller': {}})
        token = protocol.dispatch(request('a', 'acquire', kind='evaluation', reference={}))
        protocol.dispatch(request('l', 'launch', ownership=token, role='controller'))
        protocol.dispatch(request('p', 'postflight', ownership=token))
        assert not runtime.live
        assert gate.state['phase'] == 'postflight'
        with pytest.raises(WorkloadBlocked): gate.acquire('administration', {})
        with pytest.raises(WorkloadBlocked):
            protocol.dispatch(request('r', 'release', ownership=token))
        protocol.dispatch(request('i', 'commit_intent', ownership=token, binding=binding))
    # A lost DB acknowledgement cannot be erased by cleanup or explicit resume.
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        for method in ('reconcile', 'resume', 'release'):
            with pytest.raises(WorkloadBlocked):
                protocol.dispatch(request(method, method, ownership=token))
        with pytest.raises(WorkloadBlocked):
            protocol.dispatch(request('wrong', 'acknowledge_commit', ownership=token, binding={'job': 'other'}))
        assert request('wrong', 'acknowledge_commit', ownership=token, binding={'job': 'other'})['id'] not in gate.state['requests']
        assert gate.state['database_commit'] == binding
        protocol.dispatch(request('ack', 'acknowledge_commit', ownership=token, binding=binding))
        protocol.dispatch(request('release-ok', 'release', ownership=token))
        assert gate.state['phase'] == 'complete'


def test_bounded_replay_window_rejects_evicted_requests_after_restart(tmp_path):
    runtime = Runtime()
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        token = protocol.dispatch(request('acquire', 'acquire', kind='evaluation', reference={}))
        oldest = request('oldest', 'bind', ownership=token, reference={'job': 'original'})
        protocol.dispatch(oldest)
        for number in range(100):
            protocol.dispatch(request(f'bind-{number}', 'bind', ownership=token, reference={'job': str(number)}))
        assert len(gate.state['requests']) == 64
        assert oldest['id'] not in gate.state['requests']
    with HostGate(tmp_path, runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        with pytest.raises(WorkloadBlocked, match='expired_request_sequence'):
            protocol.dispatch(oldest)
        assert gate.state['reference'] == {'job': '99'}


def test_completed_workload_records_are_bounded_and_generations_never_reopen(tmp_path):
    with HostGate(tmp_path, Runtime()).locked() as gate:
        protocol = SupervisorProtocol(gate, {})
        first = request('first', 'acquire', kind='administration', reference={})
        protocol.dispatch(first)
        finish(protocol, gate, 'first')
        for number in range(20):
            protocol.dispatch(request(f'acquire-{number}', 'acquire', kind='administration', reference={}))
            finish(protocol, gate, str(number))
        assert len(gate.state['completed_workloads']) == 16
        assert len(gate.state['requests']) == 5
        assert gate.state['request_generation'] == 21
        with pytest.raises(WorkloadBlocked, match='request_generation'):
            protocol.dispatch(first)


@pytest.mark.parametrize('wire', [
    b'{"id":"1:1","id":"1:2","method":"acquire","argument":{}}',
    b'{"id":"1:1","method":"acquire","argument":{"reference":{"cost":NaN}}}',
])
def test_ambiguous_wire_requests_rejected_before_dispatch(wire):
    from mldsafail.evaluator.workload_socket import decode_request
    with pytest.raises(ValueError): decode_request(wire)


def test_full_unresolved_ledger_can_only_archive_after_verified_cleanup(tmp_path):
    runtime=Runtime()
    with HostGate(tmp_path,runtime).locked() as gate:
        protocol=SupervisorProtocol(gate,{})
        token=protocol.dispatch(request('acquire','acquire',kind='evaluation',reference={}))
        gate.state['requests']={f'1:{index}':dict(sha256='a'*64,phase='intent') for index in range(1,1025)}
        gate.state['request_sequence']=1024;gate._write()
        compact=dict(id='1:1025',method='compact',argument={'ownership':token})
        with pytest.raises(WorkloadBlocked,match='verified_cleanup_required'):protocol.dispatch(compact)
        gate.reconcile()  # Independent cleanup does not rely on free ledger slots.
        protocol.dispatch(compact)
        assert list(gate.state['requests'])==['1:1025']
        archive=next((tmp_path/'records').glob('*.requests-*.json'))
        import json
        assert len(json.loads(archive.read_bytes())['requests'])==1024
        with pytest.raises(WorkloadBlocked,match='expired_request_sequence'):
            protocol.dispatch(dict(id='1:2',method='resume',argument={'ownership':token}))
