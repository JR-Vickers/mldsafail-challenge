import hashlib
import json
from pathlib import Path

import pytest

from deploy.workload_policy import CONTROLS, authorize, policy_bytes, validate_controls, configuration_digest
from deploy.workload_controls import SCENARIOS


def case_fixture(control, name, expected):
    observations = dict(expected)
    if control == 'continuous_monitor': observations.update(abort_latency_ms=1000, control_read_ms=800)
    if control == 'bounded_output': observations.update(enforcement='kernel', log_rlimit_bytes=64*1024**2, max_log_streams=2, generation_filesystem_bytes=1024**3)
    if control == 'native_linux_acceptance': observations.update(platform='linux', retained_before={'db':'birth'}, retained_after={'db':'birth'})
    identities = dict(boot_id='boot', daemon_id='daemon', workload_id='a'*32,
                      scope=dict(path='/sys/fs/cgroup/heavy/workload', device=1, inode=2))
    if control == 'common_cgroup':
        identities['processes'] = [dict(pid=i, start_ticks=i, cgroup='/sys/fs/cgroup/heavy/workload/leaf') for i in (1,2,3)]
    return dict(name=name, outcome='passed', observations=observations, identities=identities,
                trace=[dict(event='injection', monotonic_ns=1), dict(event='observation', monotonic_ns=2)])


def fixture(tmp_path):
    runtime = dict(boot_id='boot', daemon_id='daemon', supervisor_sha256='a'*64,
                   adapter_sha256='b'*64, evaluator_fingerprint='c'*64,
                   cgroup='/sys/fs/cgroup/heavy', socket='/run/private/workload.sock',
                   configuration_sha256='d'*64, release_sha256='e'*64,
                   worker_image='sha256:'+'f'*64, controller_image='sha256:'+'0'*64)
    configurations = {}
    for role in ('supervisor', 'native', 'controller'):
        config_path = tmp_path/(role+'.configuration.json')
        config_path.write_text(json.dumps({'role':role})); config_path.chmod(0o600)
        configurations[role] = dict(path=str(config_path), sha256=hashlib.sha256(config_path.read_bytes()).hexdigest())
    runtime['configuration_sha256'] = configuration_digest(configurations)
    policy = hashlib.sha256(policy_bytes()).hexdigest()
    bindings = {}
    for control in CONTROLS:
        artifact = tmp_path / (control + '.json')
        artifact.write_text(json.dumps(dict(
            schema='mldsafail.control-evidence.v1', control=control, outcome='passed',
            host='host', source='source', resource_policy_sha256=policy,
            runtime={k: runtime[k] for k in ('supervisor_sha256', 'adapter_sha256', 'evaluator_fingerprint', 'configuration_sha256', 'release_sha256', 'worker_image', 'controller_image')},
            cases=[case_fixture(control, name, expected) for name, expected in SCENARIOS[control].items()],
            reviewed_by='reviewer', executed_by='executor')))
        bindings[control] = dict(path=artifact.name, sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
    evidence = dict(schema='mldsafail.operational-controls.v1', host='host', source='source',
                    operation_id='operation', resource_policy_sha256=policy, runtime=runtime,
                    controls={k: True for k in CONTROLS}, evidence=bindings,
                    reviewed_by='reviewer', blockers=[], prepared_at=1000, observed_at=1000, executed_by='executor')
    path = tmp_path / 'receipt.json'
    path.write_text(json.dumps(evidence))
    packet = dict(schema='mldsafail.production-operation.v4', state='execution_ready',
                  capacity_disposition='unmeasured_capacity', resource_policy_sha256=policy,
                  operational_receipt=str(path), operational_receipt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  hostname='host', source='source', operation_id='operation', supervisor_runtime=runtime, configurations=configurations)
    return packet, evidence, path


def test_valid_controls_and_exact_authority(tmp_path):
    packet, _, _ = fixture(tmp_path)
    validate_controls(packet, now=1100)
    raw = json.dumps(packet).encode()
    authority = dict(purpose='production_unmeasured_operation_only', authorized_by='owner',
                     operation_id='operation', time=1100, packet_sha256=hashlib.sha256(raw).hexdigest(), roles=[], lifetime_seconds=9000,
                     native_configuration_sha256=hashlib.sha256(json.dumps(json.loads(Path(packet['configurations']['native']['path']).read_bytes()),sort_keys=True).encode()).hexdigest())
    review = tmp_path/'review.json'
    review.write_text(json.dumps(dict(packet_sha256=authority['packet_sha256'], decision='approved', reviewed_by='independent', implemented_by='implementation_agent')))
    authority.update(review_file=str(review), review_sha256=hashlib.sha256(review.read_bytes()).hexdigest())
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


def rewrite_receipt(packet, evidence, path):
    path.write_text(json.dumps(evidence))
    packet['operational_receipt_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()


def test_generic_passing_checkbox_does_not_certify_a_control(tmp_path):
    packet, evidence, path = fixture(tmp_path)
    artifact_path = tmp_path/'shared_host_gate.json'
    artifact = json.loads(artifact_path.read_bytes())
    artifact['cases'] = [dict(name='synthetic', outcome='passed', observations={'verified':True})]
    artifact_path.write_text(json.dumps(artifact))
    evidence['evidence']['shared_host_gate']['sha256'] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    rewrite_receipt(packet, evidence, path)
    with pytest.raises(ValueError): validate_controls(packet, now=1100)


def test_native_acceptance_endures_but_live_observations_expire(tmp_path):
    packet, evidence, path = fixture(tmp_path)
    artifact = tmp_path/'native_linux_acceptance.json'
    content = json.loads(artifact.read_bytes()); content['accepted_at'] = -1000000
    artifact.write_text(json.dumps(content))
    evidence['evidence']['native_linux_acceptance']['sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    rewrite_receipt(packet, evidence, path)
    validate_controls(packet, execution=True, now=1100)
    with pytest.raises(ValueError): validate_controls(packet, execution=True, now=1300)
    validate_controls(packet, now=1300)
    with pytest.raises(ValueError): validate_controls(packet, now=87400)


@pytest.mark.parametrize('control,case,field,value', [
    ('shared_host_gate','cross_database_and_admin','acquired',2),
    ('continuous_monitor','stale_sample','abort_latency_ms',1500),
    ('bounded_output','log_exhaustion','enforcement','periodic_scan'),
    ('verified_cleanup','surviving_worker','ownership_released',True),
])
def test_rehashed_invalid_control_observations_still_fail(tmp_path, control, case, field, value):
    packet, evidence, path = fixture(tmp_path)
    artifact = tmp_path/(control+'.json'); content=json.loads(artifact.read_bytes())
    next(item for item in content['cases'] if item['name']==case)['observations'][field] = value
    artifact.write_text(json.dumps(content))
    evidence['evidence'][control]['sha256'] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    rewrite_receipt(packet, evidence, path)
    with pytest.raises(ValueError): validate_controls(packet, now=1100)
