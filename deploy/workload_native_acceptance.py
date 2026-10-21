"""Owner-authorized VPS control-only acceptance; never an evaluation or epoch."""
import argparse
import hashlib
import hmac
import json
import os
import socket
from pathlib import Path
import sys
import time

from deploy.protected_epoch import make_fence
from deploy.workload_deployment import inspected_commands
from mldsafail.evaluator.native_workload import birth, command, private_json, process_birth, publish, require, values
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.evaluator.workload import WorkloadBlocked
from mldsafail.evaluator.envelope import canonical_payload


def execute(packet_path, authorization_path):
    require(sys.platform == 'linux', 'native_acceptance_requires_linux')
    raw = Path(packet_path).read_bytes(); packet = private_json(packet_path)
    authority = private_json(authorization_path)
    require(authority.get('purpose') == 'native_workload_control_only' and authority.get('authorized_by') == 'owner' and
            authority.get('packet_sha256') == hashlib.sha256(raw).hexdigest() and
            0 <= time.time()-authority.get('time', 0) < 180, 'native_acceptance_authority_missing')
    review = private_json(authority['review_file'])
    require(hashlib.sha256(Path(authority['review_file']).read_bytes()).hexdigest() == authority['review_sha256'] and
            review.get('packet_sha256') == authority['packet_sha256'] and review.get('decision') == 'approved' and
            review.get('reviewed_by') and review['reviewed_by'] != review.get('implemented_by'), 'native_acceptance_review_missing')
    require(packet.get('deployment') is not None, 'native_acceptance_inspection_missing')
    inspection = packet['deployment']['identities']
    inspected_commands(inspection)
    require(socket.gethostname()==inspection['hostname'] and os.getuid()==inspection['uid'] and
            Path('/proc/sys/kernel/random/boot_id').read_text().strip()==inspection['boot_id'], 'native_acceptance_wrong_host')
    inputs = inspection['acceptance_inputs']
    native = private_json(inputs['native_configuration'])
    require(hashlib.sha256(json.dumps(native, sort_keys=True).encode()).hexdigest() == authority['native_configuration_sha256'] and
            native['roles']['inert']['operation_id'] == authority['operation_id'] and
            native['roles']['inert']['authorization'] == str(Path(authorization_path).absolute()), 'native_acceptance_configuration_changed')
    for name, expected in inspection['release_files'].items():
        require(hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, 'native_acceptance_release_changed')
    client = WorkloadClient(inspection['socket']['path'], inputs['client_journal'])
    deadline = time.monotonic()+180
    results = []
    fence = None
    before = None
    try:
        for case in ('lifecycle', 'parent_oom', 'supervisor_death'):
            require(time.monotonic() < deadline, 'native_acceptance_deadline')
            state = client.status()
            if state and state['paused']:
                require(state['reference'].get('operation_id') == authority['operation_id'] or state['reference'].get('bootstrap') is True, 'native_unrelated_ownership')
                # This explicit recovery is predeclared fixture authority. It is
                # never used by the participant dispatcher or automatic restart.
                client.attach(state)
                if state['phase'] not in ('cleaned', 'complete'): client.mutation('reconcile')
                client.mutation('resume')
            reference = dict(operation_id=authority['operation_id'], fixture=case, packet_sha256=authority['packet_sha256'])
            client.acquire('administration', reference)
            observed = client.environment()['retained']
            if before is None:
                expected={role:{key:inspection['retained_services'][role][key] for key in ('id','image','started_at','running')} for role in observed}
                expected['coordinator']['running']=False
                require(observed==expected, 'native_inspected_retained_services_changed')
                before = observed
                fence_packet = {**inputs, 'database_container': observed['database']}
                fence = make_fence(fence_packet, client)
                fence.acquire()
            else: require(observed == before, 'native_retained_services_changed')
            fence.verify()
            client.launch('inert')
            if case == 'supervisor_death':
                marker = Path(native['output'])/client.token/'fixture-process.json'
                while not marker.exists():
                    require(time.monotonic() < deadline, 'native_fixture_creation_deadline')
                    client.heartbeat(); time.sleep(.05)
                identity = private_json(marker)
                require(process_birth(identity['pid']) == identity, 'native_fixture_process_replaced')
                supervisor = private_json(Path(native['root'])/'socket.json')['process']
                main_pid = int(command(['/usr/bin/systemctl', '--user', 'show', '--property=MainPID', '--value', 'mldsafail-workload-supervisor.service']).decode())
                require(main_pid == supervisor['pid'] and process_birth(main_pid) == supervisor, 'native_supervisor_replaced')
                command(['/usr/bin/systemctl', '--user', 'kill', '--kill-who=main', '--signal=SIGKILL', 'mldsafail-workload-supervisor.service'])
            while True:
                require(time.monotonic() < deadline, 'native_acceptance_deadline')
                try:
                    state = client.status()
                    require(state['workload_id'] == client.token, 'native_ownership_interference')
                    client.attach(state)
                except OSError:
                    time.sleep(.05); continue
                if state['paused'] and state['phase'] == 'cleaned': break
                if case == 'lifecycle':
                    client.heartbeat()
                    envelope = client.result()
                    if envelope is not None:
                        payload = envelope['payload']
                        expected = dict(workload_id=client.token, role='inert', reference=reference)
                        require(hmac.compare_digest(envelope['signature'], hmac.new(
                            Path(inputs['signing_key']).read_bytes(), canonical_payload(payload), hashlib.sha256).hexdigest()) and
                            payload['binding'] == expected and payload['status'] == 'administrative_complete' and
                            payload['result']['case'] == case and payload['result']['verified'] is True,
                            'native_fixture_result_invalid')
                        client.mutation('postflight')
                        break
                elif not state['paused']:
                    try: client.heartbeat()
                    except WorkloadBlocked:
                        require(client.status()['paused'], 'native_control_unexpected_rejection')
                time.sleep(.05)
            require(state['phase'] == 'cleaned' or client.status()['phase'] == 'postflight', 'native_cleanup_not_verified')
            record = private_json(Path(native['root'])/(client.token+'.native.json'))
            scope = Path(record['scope']['path'])
            require(birth(scope) == record['scope'] and values(scope/'cgroup.events')['populated'] == 0,
                    'native_fixture_scope_populated')
            after = client.environment()['retained']
            require(after == before, 'native_retained_services_changed')
            fixture_record = private_json(Path(record['output'])/'fixture.json')
            fixture_path = Path(fixture_record['scope']['path'])
            require(birth(fixture_path) == fixture_record['scope'], 'native_fixture_birth_changed')
            fixture_events = values(fixture_path/'memory.events')
            if case == 'parent_oom':
                require(fixture_events['oom_kill'] > fixture_record['before']['oom_kill'] and
                        client.status()['reason'] == 'operation_oom', 'native_parent_oom_not_observed')
            fixture_path.rmdir()
            results.append(dict(fixture_events=fixture_events, case=case, workload_id=client.token, state=client.status(), scope=record['scope'],
                                retained_before=before, retained_after=after, monotonic=time.monotonic()))
            if case == 'lifecycle':
                binding = dict(disposition='native_control_fixture', case=case)
                client.mutation('commit_intent', binding=binding); client.acknowledge(binding)
        # Native receipt covers these three actual fixtures only. Other controls
        # still need their separately reviewed local/native records; this never
        # manufactures a complete v4 operational-controls receipt.
        publish(Path(inputs['result_receipt']), dict(schema='mldsafail.native-workload-controls.v1',
                packet_sha256=authority['packet_sha256'], native_configuration_sha256=authority['native_configuration_sha256'],
                cases=results, retained_before=before, retained_after=client.environment()['retained'],
                scheduling_restored=False, elapsed_seconds=180-(deadline-time.monotonic())))
        client.mutation('pause')
        fence.resources_stopped(lambda: client.status()['phase'] in ('cleaned', 'complete'))
        fence.release(); fence = None
    finally:
        state = client.status()
        if state and state['workload_id'] == client.token and state['reference'].get('operation_id') == authority['operation_id'] and state['phase'] not in ('cleaned', 'postflight', 'commit_intent', 'committed', 'complete'):
            client.attach(state); client.mutation('abort')
        if fence is not None:
            state = client.status()
            if state['phase'] in ('cleaned', 'postflight', 'complete'):
                fence.resources_stopped(lambda: True); fence.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    execute(args.packet, args.authorization)


if __name__ == '__main__': main()
