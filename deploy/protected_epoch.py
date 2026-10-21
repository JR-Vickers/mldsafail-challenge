"""v4 administrative dispatcher: shared host admission precedes zero-pending SQL."""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import time

from deploy.maintenance_fence import Fence
from deploy.production_maintenance import packet_state
from deploy.workload_policy import authorize, validate_controls
from mldsafail.evaluator.envelope import canonical_payload
from mldsafail.evaluator.native_workload import private_json, publish, require
from mldsafail.evaluator.workload_client import WorkloadClient


def validate(packet, *, execution=False):
    require(packet.get('schema') == 'mldsafail.production-operation.v4' and
            packet.get('purpose') == 'production_epoch_only' and packet.get('benchmark_version') == '0.5.0', 'v4_operation_contract')
    packet_state(packet, private_json(packet['maintenance']), execution=execution)
    require(packet.get('roles') in (['create', 'audit'], ['reference', 'audit'], ['audit']), 'v4_roles_not_predeclared')
    require(packet.get('runtime_files') and type(packet['runtime_files']) is dict, 'v4_runtime_files_missing')
    for name, expected in packet['runtime_files'].items():
        path = Path(name)
        require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)) and
                hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'v4_installed_runtime_changed')
    for key, digest_key in (('release_manifest', 'release_sha256'),):
        require(hashlib.sha256(Path(packet[key]).read_bytes()).hexdigest() == packet['supervisor_runtime'][digest_key], 'v4_installed_release_changed')
    require(packet['supervisor_configuration'] == packet['configurations']['supervisor']['path'], 'v4_supervisor_configuration_path')
    release = private_json(packet['release_manifest'])
    require(release.get('schema') == 'mldsafail.workload-source-release.v1' and
            release.get('benchmark_version') == '0.5.0' and release.get('source_hashes'), 'v4_source_release_missing')
    root = Path(packet['release_root'])
    require(root.is_absolute() and '..' not in root.parts, 'v4_release_root_invalid')
    for relative, expected in release['source_hashes'].items():
        path = Path(relative)
        require(not path.is_absolute() and '..' not in path.parts and
                packet['runtime_files'].get(str(root/path)) == expected, 'v4_source_release_binding')
    service = str(root/'src/mldsafail/evaluator/workload_service.py')
    adapter = str(root/'src/mldsafail/evaluator/native_workload.py')
    require(packet['runtime_files'].get(service) == packet['supervisor_runtime']['supervisor_sha256'] and
            packet['runtime_files'].get(adapter) == packet['supervisor_runtime']['adapter_sha256'], 'v4_runtime_entrypoint_binding')
    from mldsafail.benchmark_v050 import evidence as ev
    source = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted((root/'src/mldsafail/evaluator').glob('*.py'))}
    fingerprint = ev.sha(dict(benchmark_version='0.5.0', environment=release['environment'],
                               settings=ev.SETTINGS, hosted_evaluator=source))
    require(release.get('evaluator_fingerprint') == fingerprint == packet['supervisor_runtime']['evaluator_fingerprint'],
            'v4_hosted_fingerprint_binding')
    require(packet['workload_socket'] == packet['supervisor_runtime']['socket'], 'v4_socket_changed')
    require(packet.get('participant_package_evidence') and packet.get('participant_package_evidence_sha256') ==
            hashlib.sha256(Path(packet['participant_package_evidence']).read_bytes()).hexdigest(), 'v4_participant_package_binding')
    return packet


def prepare(packet_path):
    packet = validate(private_json(packet_path))
    return dict(schema='mldsafail.protected-operation-prepared.v1', execution_authority=False,
                packet_sha256=hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(), roles=packet['roles'])


def make_fence(packet, client):
    import psycopg
    credentials = private_json(packet['database_credentials'])
    require(set(credentials) == {'host', 'port', 'dbname', 'user', 'password'}, 'v4_database_credentials_shape')
    expected = packet['database_container']
    def identity():
        observed = client.environment()['retained']['database']
        require(observed == expected and observed['running'], 'v4_database_container_replaced')
        return observed['id']
    def connect():
        return psycopg.connect(**credentials, autocommit=True, connect_timeout=2,
                               options='-c statement_timeout=500 -c lock_timeout=500')
    return Fence(packet['fence_root'], connect, identity)


def wait_role(client, role, reference, key, fence):
    client.launch(role)
    while True:
        fence.verify()
        client.heartbeat()
        envelope = client.result()
        if envelope is not None:
            payload = envelope['payload']
            expected = dict(workload_id=client.token, role=role, reference=reference)
            signature = hmac.new(key, canonical_payload(payload), hashlib.sha256).hexdigest()
            require(hmac.compare_digest(signature, envelope['signature']) and payload['binding'] == expected,
                    'v4_administrative_result_binding')
            require(payload['status'] == 'administrative_complete', 'v4_administrative_controller_failed')
            return envelope
        time.sleep(.25)


def run(packet_path, authorization_path, *, client=None, fence_factory=make_fence):
    raw = Path(packet_path).read_bytes()
    authorization = private_json(authorization_path)
    authorize(raw, authorization)
    packet = validate(private_json(packet_path), execution=True)
    client = client or WorkloadClient(packet['workload_socket'], packet['client_journal'])
    reference = dict(operation_id=packet['operation_id'], packet_sha256=hashlib.sha256(raw).hexdigest())
    # This marker is exclusive across retries and predates every computational
    # controller. Native/control acceptance never invokes this entrypoint.
    attempt = Path(packet['attempt'])
    require(not attempt.exists(), 'v4_attempt_already_used')
    client.acquire('administration', reference)
    fence = None
    acquired_fence = False
    launched = False
    try:
        fence = fence_factory(packet, client)
        fence.acquire(); acquired_fence = True
        fence.verify()
        descriptor = os.open(attempt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(reference, stream); stream.flush(); os.fsync(stream.fileno())
        def abort():
            client.mutation('abort')
            return True
        results = {}
        key = Path(packet['signing_key']).read_bytes()
        for phase, roles in (('create', [role for role in packet['roles'] if role != 'audit']),
                             ('audit', [role for role in packet['roles'] if role == 'audit'])):
            if not roles: continue
            with fence.phase(phase, abort):
                for role in roles:
                    launched = True
                    results[role] = wait_role(client, role, reference, key, fence)
        client.mutation('postflight')
        fence.resources_stopped(lambda: client.status()['phase'] == 'postflight')
        fence.verify()
        binding = dict(disposition='administrative_complete', workload_id=client.token,
                       operation_id=packet['operation_id'], packet_sha256=reference['packet_sha256'],
                       result_sha256=hashlib.sha256(canonical_payload(results)).hexdigest())
        client.mutation('commit_intent', binding=binding)
        # Durable operator receipt is the administrative commit transaction.
        publish(Path(packet['result_receipt']), dict(binding=binding, results=results))
        fence.release(); acquired_fence = False
        client.acknowledge(binding)
        return binding
    except BaseException:
        if launched:
            state = client.status()
            if state['phase'] not in ('postflight', 'commit_intent', 'committed', 'complete'):
                client.mutation('abort')
        else:
            if fence is not None and getattr(fence, 'backend', None) is not None:
                try:
                    fence.resources_stopped(lambda: not client.status()['resources'])
                    fence.release()
                except BaseException:
                    client.mutation('abort')
                    raise
            # A failed zero-pending fence releases only verified unused ownership.
            client.unused()
        raise
    finally:
        if acquired_fence:
            # Release the DB fence only after the host supervisor confirms empty
            # resources. Failure retains recovery evidence and never restores work.
            state = client.status()
            if state['phase'] in ('cleaned', 'postflight', 'commit_intent', 'committed', 'complete'):
                fence.resources_stopped(lambda: True)
                fence.release()


def audit(packet_path):
    packet = validate(private_json(packet_path))
    receipt = private_json(packet['result_receipt'])
    require(receipt['binding']['packet_sha256'] == hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(), 'v4_receipt_packet_changed')
    require(receipt['binding']['result_sha256'] == hashlib.sha256(canonical_payload(receipt['results'])).hexdigest(), 'v4_receipt_result_changed')
    return receipt['binding']


def finalize(packet_path, destination):
    """Prepare immutable candidate configuration; never install or activate it."""
    packet = validate(private_json(packet_path))
    receipt = private_json(packet['result_receipt'])
    audit(packet_path)
    require(str(destination) == packet['final_destination'], 'v4_final_destination_changed')
    key = Path(packet['signing_key']).read_bytes()
    for role, envelope in receipt['results'].items():
        payload = envelope['payload']
        require(hmac.compare_digest(envelope['signature'], hmac.new(key, canonical_payload(payload), hashlib.sha256).hexdigest()) and
                payload['binding']['role'] == role and payload['binding']['workload_id'] == receipt['binding']['workload_id'] and
                payload['binding']['reference']['packet_sha256'] == receipt['binding']['packet_sha256'], 'v4_final_result_signature')
    audited = receipt['results']['audit']['payload']['result']
    epoch = Path(audited['epoch_path'])
    for name, binding in (('manifest.json','manifest_sha256'), ('reference-costs.json','reference_sha256'), ('COMPLETE.json','seal_sha256')):
        require(hashlib.sha256((epoch/name).read_bytes()).hexdigest() == audited[binding], 'v4_final_epoch_changed')
    destination = Path(destination)
    require(destination.is_absolute() and not any(path.is_symlink() for path in (destination, *destination.parents)), 'v4_final_destination_unsafe')
    destination.mkdir(mode=0o700)
    configurations = packet['configurations']
    controller = private_json(configurations['controller']['path'])
    native = private_json(configurations['native']['path'])
    supervisor = private_json(configurations['supervisor']['path'])
    require(epoch.is_relative_to(Path(native['output'])/receipt['binding']['workload_id']), 'v4_final_epoch_ownership')
    controller['epoch_path'] = str(epoch)
    controller['identity']['epoch_id'] = audited['epoch_id']
    controller['identity']['evaluator_fingerprint'] = packet['supervisor_runtime']['evaluator_fingerprint']
    controller['native_configuration'] = str(destination/'native.json')
    publish(destination/'controller.json', controller)
    native['controller_configuration'] = str(destination/'controller.json')
    native['controller_configuration_sha256'] = hashlib.sha256((destination/'controller.json').read_bytes()).hexdigest()
    publish(destination/'native.json', native)
    require(supervisor['helper'].count(configurations['native']['path']) == 1, 'v4_final_helper_binding')
    supervisor['helper'] = [str(destination/'native.json') if value == configurations['native']['path'] else value for value in supervisor['helper']]
    publish(destination/'supervisor.json', supervisor)
    from deploy.production_preflight import read_private_env
    environment = read_private_env(packet['candidate'])
    environment.update(MLDSAFAIL_MLWE_EPOCH_ID=audited['epoch_id'], MLDSAFAIL_MLWE_EPOCH_PATH=str(epoch),
                       MLDSAFAIL_EVALUATOR_FINGERPRINT=packet['supervisor_runtime']['evaluator_fingerprint'],
                       WORKLOAD_SUPERVISOR_ROOT=supervisor['root'])
    descriptor = os.open(destination/'production.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(''.join(key+'='+value+'\n' for key,value in environment.items())); stream.flush(); os.fsync(stream.fileno())
    files = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.iterdir()}
    publish(destination/'binding.json', dict(schema='mldsafail.protected-final-configuration.v1',
        epoch_id=audited['epoch_id'], epoch_path=str(epoch), packet_sha256=receipt['binding']['packet_sha256'],
        evaluator_fingerprint=packet['supervisor_runtime']['evaluator_fingerprint'], files=files, ready=False,
        acceptance_required='matching_candidate_configuration_native_acceptance_and_owner_installation_authority'))
    return destination/'binding.json'


def reconcile(packet_path, *, client=None):
    """Cleanup and commit reconciliation only; never repeats an administrative role."""
    raw = Path(packet_path).read_bytes(); packet = private_json(packet_path)
    digest = hashlib.sha256(raw).hexdigest()
    require(packet.get('schema') == 'mldsafail.production-operation.v4', 'v4_reconciliation_schema')
    client = client or WorkloadClient(packet['workload_socket'], packet['client_journal'])
    state = client.status()
    require(state and state['kind'] == 'administration' and state['reference'] ==
            dict(operation_id=packet['operation_id'],packet_sha256=digest), 'v4_reconciliation_ownership')
    client.attach(state)
    if state['phase'] not in ('cleaned','postflight','commit_intent','committed','complete'):
        client.mutation('abort'); state = client.status()
    # A known SQL backend is reconciled by birth identity, never by expiry/name.
    if (Path(packet['fence_root'])/'acquisition.json').exists():
        fence = make_fence(packet,client)
        from deploy.maintenance_fence import reconcile as reconcile_fence
        reconcile_fence(packet['fence_root'],fence.connect,fence.identity)
    path = Path(packet['result_receipt'])
    if state['phase'] in ('commit_intent','committed') and path.exists():
        receipt = private_json(path)
        require(receipt['binding'] == state['database_commit'] and
                receipt['binding']['packet_sha256'] == digest and
                receipt['binding']['result_sha256'] == hashlib.sha256(canonical_payload(receipt['results'])).hexdigest(),
                'v4_reconciliation_receipt_conflict')
        key = Path(packet['signing_key']).read_bytes()
        for envelope in receipt['results'].values():
            require(hmac.compare_digest(envelope['signature'],hmac.new(key,canonical_payload(envelope['payload']),hashlib.sha256).hexdigest()),
                    'v4_reconciliation_signature')
        if state['phase']=='commit_intent': client.acknowledge(receipt['binding'])
        elif not state['paused']: client.mutation('release')
        return client.status()
    if state['phase'] in ('committed','complete'):
        require(path.exists(), 'v4_committed_receipt_missing')
        return state
    # Uncommitted orphan output stays retained evidence, never a fresh epoch or
    # an accepted replacement receipt. Scheduling stays paused after this path.
    resolution=dict(disposition='infrastructure_failed',workload_id=state['workload_id'],
                    operation_id=packet['operation_id'],packet_sha256=digest,code='orphaned_administrative_output')
    client.mutation('pause')
    if state['phase']=='commit_intent':
        client.mutation('resolve_commit',binding=state['database_commit'],resolution=resolution)
    else:
        client.mutation('commit_intent',binding=resolution)
    publish(path.with_name(path.name+'.reconciled.json'),resolution)
    client.acknowledge(resolution)
    return client.status()
