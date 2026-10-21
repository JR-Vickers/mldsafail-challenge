import hashlib
import json

import pytest

from deploy.workload_policy import CONTROLS, authorize, policy_bytes, validate_controls


def fixture(tmp_path):
    runtime = dict(boot_id='boot', daemon_id='daemon', supervisor_sha256='a'*64,
                   adapter_sha256='b'*64, evaluator_fingerprint='c'*64,
                   cgroup='/sys/fs/cgroup/heavy', socket='/run/private/workload.sock')
    policy = hashlib.sha256(policy_bytes()).hexdigest()
    bindings = {}
    for control in CONTROLS:
        artifact = tmp_path / (control + '.json')
        artifact.write_text(json.dumps(dict(
            schema='mldsafail.control-evidence.v1', control=control, outcome='passed',
            host='host', source='source', resource_policy_sha256=policy,
            runtime={k: runtime[k] for k in ('supervisor_sha256', 'adapter_sha256', 'evaluator_fingerprint')},
            cases=[dict(name='synthetic', outcome='passed', observations={'verified': True})],
            reviewed_by='reviewer', executed_by='executor')))
        bindings[control] = dict(path=artifact.name, sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
    evidence = dict(schema='mldsafail.operational-controls.v1', host='host', source='source',
                    operation_id='operation', resource_policy_sha256=policy, runtime=runtime,
                    controls={k: True for k in CONTROLS}, evidence=bindings,
                    reviewed_by='reviewer', blockers=[], prepared_at=1000)
    path = tmp_path / 'receipt.json'
    path.write_text(json.dumps(evidence))
    packet = dict(schema='mldsafail.production-operation.v4', state='execution_ready',
                  capacity_disposition='unmeasured_capacity', resource_policy_sha256=policy,
                  operational_receipt=str(path), operational_receipt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  hostname='host', source='source', operation_id='operation', supervisor_runtime=runtime)
    return packet, evidence, path


def test_valid_controls_and_exact_authority(tmp_path):
    packet, _, _ = fixture(tmp_path)
    validate_controls(packet, now=1100)
    raw = json.dumps(packet).encode()
    authority = dict(purpose='production_unmeasured_operation_only', authorized_by='owner',
                     operation_id='operation', time=1100, packet_sha256=hashlib.sha256(raw).hexdigest())
    authorize(raw, authority, now=1101)
    with pytest.raises(ValueError): authorize(raw + b' ', authority, now=1101)
    authority['purpose'] = 'capacity_investigation_only'
    with pytest.raises(ValueError): authorize(raw, authority, now=1101)


@pytest.mark.parametrize('mutation', ['hash', 'stale', 'proposal', 'native', 'runtime', 'artifact'])
def test_controls_reject(tmp_path, mutation):
    packet, evidence, path = fixture(tmp_path)
    if mutation == 'hash': packet['resource_policy_sha256'] = '0'*64
    if mutation == 'stale': evidence['prepared_at'] = -90000
    if mutation == 'native': evidence['controls']['native_linux_acceptance'] = False
    if mutation == 'runtime': packet['supervisor_runtime'] = {'daemon_id': 'changed'}
    if mutation == 'artifact': (tmp_path / 'native_linux_acceptance.json').write_text('changed')
    if mutation == 'proposal':
        packet['state'] = 'maintenance_proposal'
        with pytest.raises(ValueError): authorize(json.dumps(packet).encode(), {}, now=1100)
        return
    path.write_text(json.dumps(evidence))
    packet['operational_receipt_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError): validate_controls(packet, now=1100)


def test_arbitrary_hashed_json_is_not_control_evidence(tmp_path):
    packet, evidence, path = fixture(tmp_path)
    artifact = tmp_path / 'shared_host_gate.json'
    artifact.write_text('{}')
    evidence['evidence']['shared_host_gate']['sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    path.write_text(json.dumps(evidence))
    packet['operational_receipt_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError): validate_controls(packet, now=1100)
